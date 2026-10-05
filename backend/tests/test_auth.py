from datetime import timedelta
from uuid import uuid4

import jwt
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import (
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)
from app.main import app
from app.storage.models import Tenant, User


def test_password_hashing_unit() -> None:
    pw = "SuperSecurePassword123!"
    hashed = hash_password(pw)
    assert hashed != pw
    is_valid, _ = verify_password(pw, hashed)
    assert is_valid is True
    is_invalid, _ = verify_password("WrongPassword123!", hashed)
    assert is_invalid is False


def test_jwt_token_unit() -> None:
    u_id = uuid4()
    t_id = uuid4()
    token = create_access_token(user_id=u_id, tenant_id=t_id, role="owner")
    payload = decode_access_token(token)
    assert payload["sub"] == str(u_id)
    assert payload["tenant_id"] == str(t_id)
    assert payload["role"] == "owner"


def test_jwt_expired_token_unit() -> None:
    u_id = uuid4()
    t_id = uuid4()
    token = create_access_token(
        user_id=u_id,
        tenant_id=t_id,
        role="owner",
        expires_delta=timedelta(seconds=-10),
    )
    with pytest.raises(ValueError, match="Invalid access token"):
        decode_access_token(token)


def test_jwt_tampered_token_unit() -> None:
    u_id = uuid4()
    t_id = uuid4()
    token = create_access_token(user_id=u_id, tenant_id=t_id, role="owner")
    tampered = token[:-4] + "abcd"
    with pytest.raises(ValueError, match="Invalid access token"):
        decode_access_token(tampered)


def test_jwt_wrong_token_type_unit() -> None:
    u_id = uuid4()
    t_id = uuid4()
    payload = {
        "sub": str(u_id),
        "tenant_id": str(t_id),
        "role": "owner",
        "type": "refresh",
    }
    wrong_type_token = jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm="HS256")
    with pytest.raises(ValueError, match="Invalid access token"):
        decode_access_token(wrong_type_token)


@pytest.mark.db
@pytest.mark.asyncio
async def test_auth_full_flow(db_session: AsyncSession) -> None:
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        reg_resp = await ac.post(
            "/auth/register",
            json={
                "tenant_name": "Alpha Corp",
                "tenant_slug": "alpha-corp",
                "email": "owner@alpha.com",
                "full_name": "Alpha Owner",
                "password": "Password123456!",
            },
        )
        assert reg_resp.status_code == 200
        reg_data = reg_resp.json()
        assert "access_token" in reg_data
        assert "refresh_token" in reg_data

        dup_resp = await ac.post(
            "/auth/register",
            json={
                "tenant_name": "Alpha Duplicate",
                "tenant_slug": "alpha-corp",
                "email": "owner2@alpha.com",
                "full_name": "Alpha Owner 2",
                "password": "Password123456!",
            },
        )
        assert dup_resp.status_code == 400

        me_resp = await ac.get(
            "/auth/me",
            headers={"Authorization": f"Bearer {reg_data['access_token']}"},
        )
        assert me_resp.status_code == 200
        me_data = me_resp.json()
        assert me_data["user"]["email"] == "owner@alpha.com"
        assert me_data["user"]["role"] == "owner"
        assert me_data["tenant"]["slug"] == "alpha-corp"

        me_fail = await ac.get(
            "/auth/me",
            headers={"Authorization": "Bearer invalid_token"},
        )
        assert me_fail.status_code == 401

        login_resp = await ac.post(
            "/auth/login",
            json={
                "tenant_slug": "alpha-corp",
                "email": "owner@alpha.com",
                "password": "Password123456!",
            },
        )
        assert login_resp.status_code == 200
        login_data = login_resp.json()

        wrong_pw = await ac.post(
            "/auth/login",
            json={
                "tenant_slug": "alpha-corp",
                "email": "owner@alpha.com",
                "password": "WrongPassword123!",
            },
        )
        assert wrong_pw.status_code == 401
        assert wrong_pw.json()["detail"] == "Invalid credentials"

        wrong_email = await ac.post(
            "/auth/login",
            json={
                "tenant_slug": "alpha-corp",
                "email": "nonexistent@alpha.com",
                "password": "Password123456!",
            },
        )
        assert wrong_email.status_code == 401
        assert wrong_email.json()["detail"] == "Invalid credentials"

        wrong_slug = await ac.post(
            "/auth/login",
            json={
                "tenant_slug": "wrong-slug",
                "email": "owner@alpha.com",
                "password": "Password123456!",
            },
        )
        assert wrong_slug.status_code == 401
        assert wrong_slug.json()["detail"] == "Invalid credentials"

        old_refresh = login_data["refresh_token"]
        ref_resp = await ac.post(
            "/auth/refresh",
            json={"refresh_token": old_refresh},
        )
        assert ref_resp.status_code == 200
        ref_data = ref_resp.json()
        new_refresh = ref_data["refresh_token"]
        assert new_refresh != old_refresh

        reuse_resp = await ac.post(
            "/auth/refresh",
            json={"refresh_token": old_refresh},
        )
        assert reuse_resp.status_code == 401

        logout_resp = await ac.post(
            "/auth/logout",
            json={"refresh_token": new_refresh},
        )
        assert logout_resp.status_code == 200

        ref_after_logout = await ac.post(
            "/auth/refresh",
            json={"refresh_token": new_refresh},
        )
        assert ref_after_logout.status_code == 401


@pytest.mark.db
@pytest.mark.asyncio
async def test_inactive_user_and_tenant_cannot_login(db_session: AsyncSession) -> None:
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        await ac.post(
            "/auth/register",
            json={
                "tenant_name": "Inactive Corp",
                "tenant_slug": "inactive-corp",
                "email": "user@inactive.com",
                "full_name": "Inactive User",
                "password": "Password123456!",
            },
        )

        res_u = await db_session.execute(
            select(User).where(User.email == "user@inactive.com")
        )
        user = res_u.scalar_one()
        user.is_active = False
        db_session.add(user)
        await db_session.commit()

        login_inactive_user = await ac.post(
            "/auth/login",
            json={
                "tenant_slug": "inactive-corp",
                "email": "user@inactive.com",
                "password": "Password123456!",
            },
        )
        assert login_inactive_user.status_code == 401
        assert login_inactive_user.json()["detail"] == "Invalid credentials"

        user.is_active = True
        res_t = await db_session.execute(
            select(Tenant).where(Tenant.slug == "inactive-corp")
        )
        tenant = res_t.scalar_one()
        tenant.is_active = False
        db_session.add_all([user, tenant])
        await db_session.commit()

        login_inactive_tenant = await ac.post(
            "/auth/login",
            json={
                "tenant_slug": "inactive-corp",
                "email": "user@inactive.com",
                "password": "Password123456!",
            },
        )
        assert login_inactive_tenant.status_code == 401
        assert login_inactive_tenant.json()["detail"] == "Invalid credentials"


@pytest.mark.db
@pytest.mark.asyncio
async def test_tenant_isolation_and_user_management(db_session: AsyncSession) -> None:
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        reg_a = (
            await ac.post(
                "/auth/register",
                json={
                    "tenant_name": "Company A",
                    "tenant_slug": "company-a",
                    "email": "shared@domain.com",
                    "full_name": "Owner A",
                    "password": "Password123456!",
                },
            )
        ).json()
        token_a = reg_a["access_token"]

        reg_b = (
            await ac.post(
                "/auth/register",
                json={
                    "tenant_name": "Company B",
                    "tenant_slug": "company-b",
                    "email": "shared@domain.com",
                    "full_name": "Owner B",
                    "password": "Password123456!",
                },
            )
        ).json()
        token_b = reg_b["access_token"]

        login_a = (
            await ac.post(
                "/auth/login",
                json={
                    "tenant_slug": "company-a",
                    "email": "shared@domain.com",
                    "password": "Password123456!",
                },
            )
        ).json()
        me_a = (
            await ac.get(
                "/auth/me",
                headers={"Authorization": f"Bearer {login_a['access_token']}"},
            )
        ).json()
        assert me_a["tenant"]["slug"] == "company-a"

        login_b = (
            await ac.post(
                "/auth/login",
                json={
                    "tenant_slug": "company-b",
                    "email": "shared@domain.com",
                    "password": "Password123456!",
                },
            )
        ).json()
        me_b = (
            await ac.get(
                "/auth/me",
                headers={"Authorization": f"Bearer {login_b['access_token']}"},
            )
        ).json()
        assert me_b["tenant"]["slug"] == "company-b"

        admin_a_resp = await ac.post(
            "/users",
            headers={"Authorization": f"Bearer {token_a}"},
            json={
                "email": "admin@company-a.com",
                "full_name": "Admin A",
                "password": "Password123456!",
                "role": "admin",
            },
        )
        assert admin_a_resp.status_code == 200

        member_a_resp = await ac.post(
            "/users",
            headers={"Authorization": f"Bearer {token_a}"},
            json={
                "email": "member@company-a.com",
                "full_name": "Member A",
                "password": "Password123456!",
                "role": "member",
            },
        )
        assert member_a_resp.status_code == 200

        member_a_login = (
            await ac.post(
                "/auth/login",
                json={
                    "tenant_slug": "company-a",
                    "email": "member@company-a.com",
                    "password": "Password123456!",
                },
            )
        ).json()
        token_member_a = member_a_login["access_token"]

        member_create_fail = await ac.post(
            "/users",
            headers={"Authorization": f"Bearer {token_member_a}"},
            json={
                "email": "newuser@company-a.com",
                "full_name": "New User",
                "password": "Password123456!",
                "role": "member",
            },
        )
        assert member_create_fail.status_code == 403

        admin_a_login = (
            await ac.post(
                "/auth/login",
                json={
                    "tenant_slug": "company-a",
                    "email": "admin@company-a.com",
                    "password": "Password123456!",
                },
            )
        ).json()
        token_admin_a = admin_a_login["access_token"]

        admin_create_owner_fail = await ac.post(
            "/users",
            headers={"Authorization": f"Bearer {token_admin_a}"},
            json={
                "email": "newowner@company-a.com",
                "full_name": "New Owner",
                "password": "Password123456!",
                "role": "owner",
            },
        )
        assert admin_create_owner_fail.status_code == 403

        users_a = (
            await ac.get("/users", headers={"Authorization": f"Bearer {token_a}"})
        ).json()
        assert len(users_a) == 3
        emails_a = {u["email"] for u in users_a}
        assert emails_a == {
            "shared@domain.com",
            "admin@company-a.com",
            "member@company-a.com",
        }

        users_b = (
            await ac.get("/users", headers={"Authorization": f"Bearer {token_b}"})
        ).json()
        assert len(users_b) == 1
        assert users_b[0]["email"] == "shared@domain.com"
        assert users_b[0]["tenant_id"] != users_a[0]["tenant_id"]
