"""Tests for the connector framework (Phase 3).

Covers crypto, registry, connection CRUD, tenant isolation,
credential security, role enforcement, and timeout handling.
"""

import json
import logging

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.connectors.registry import (
    _clear_registry,
    get_connector,
    list_connectors,
    register_connector,
)
from app.core.crypto import decrypt_json, encrypt_json
from app.main import app
from app.storage.models import Connection
from tests.fakes.fake_connector import FakeConnector

# ──────────────────────────────────────────────────────────────────────
# Fixtures
# ──────────────────────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def _register_fake_connector():
    """Register the fake connector for every test and clean up after."""
    register_connector(FakeConnector)
    yield
    _clear_registry()


async def _register_tenant(ac: AsyncClient, slug: str, email: str) -> dict:
    resp = await ac.post(
        "/auth/register",
        json={
            "tenant_name": f"Tenant {slug}",
            "tenant_slug": slug,
            "email": email,
            "full_name": f"Owner of {slug}",
            "password": "Password123456!",
        },
    )
    assert resp.status_code == 200
    return resp.json()


async def _login(ac: AsyncClient, slug: str, email: str) -> str:
    resp = await ac.post(
        "/auth/login",
        json={
            "tenant_slug": slug,
            "email": email,
            "password": "Password123456!",
        },
    )
    assert resp.status_code == 200
    return resp.json()["access_token"]


async def _create_member(ac: AsyncClient, owner_token: str, email: str) -> str:
    """Create a member user and return their access token."""
    resp = await ac.post(
        "/users",
        headers={"Authorization": f"Bearer {owner_token}"},
        json={
            "email": email,
            "full_name": "Member User",
            "password": "Password123456!",
            "role": "member",
        },
    )
    assert resp.status_code == 200
    return resp.json()


# ──────────────────────────────────────────────────────────────────────
# Unit tests: crypto
# ──────────────────────────────────────────────────────────────────────


def test_crypto_round_trip() -> None:
    """encrypt_json → decrypt_json must return the original dict."""
    data = {"api_key": "sk-secret-123", "nested": {"a": 1}}
    token = encrypt_json(data)
    assert decrypt_json(token) == data


def test_crypto_tampered_data_fails() -> None:
    """Tampered ciphertext must raise a generic ValueError."""
    token = encrypt_json({"key": "value"})
    tampered = token[:10] + "AAAA" + token[14:]
    with pytest.raises(ValueError, match="invalid or corrupted"):
        decrypt_json(tampered)


def test_crypto_wrong_key_fails() -> None:
    """Ciphertext encrypted with a different key must fail to decrypt."""
    from cryptography.fernet import Fernet, MultiFernet

    other_key = Fernet.generate_key()
    other_fernet = MultiFernet([Fernet(other_key)])
    token = other_fernet.encrypt(json.dumps({"k": "v"}).encode()).decode()
    with pytest.raises(ValueError, match="invalid or corrupted"):
        decrypt_json(token)


def test_crypto_error_message_has_no_secret_material() -> None:
    """Error messages from decrypt must not contain plaintext or ciphertext."""
    token = encrypt_json({"secret_key": "super-secret-value"})
    tampered = token[:10] + "XXXX" + token[14:]
    try:
        decrypt_json(tampered)
    except ValueError as exc:
        msg = str(exc)
        assert "super-secret-value" not in msg
        assert "secret_key" not in msg
        assert tampered not in msg


# ──────────────────────────────────────────────────────────────────────
# Unit tests: registry
# ──────────────────────────────────────────────────────────────────────


def test_registry_register_and_lookup() -> None:
    """Registered connector should be retrievable by provider key."""
    # FakeConnector is auto-registered by fixture
    assert get_connector("fake") is FakeConnector


def test_registry_list() -> None:
    """list_connectors should include all registered connectors."""
    connectors = list_connectors()
    assert "fake" in connectors
    assert connectors["fake"] is FakeConnector


def test_registry_duplicate_rejected() -> None:
    """Registering the same provider key twice must raise ValueError."""
    with pytest.raises(ValueError, match="Duplicate"):
        register_connector(FakeConnector)


def test_registry_unknown_provider() -> None:
    """Looking up an unregistered provider must raise KeyError."""
    with pytest.raises(KeyError, match="Unknown"):
        get_connector("nonexistent")


# ──────────────────────────────────────────────────────────────────────
# DB tests: connection CRUD
# ──────────────────────────────────────────────────────────────────────


@pytest.mark.db
@pytest.mark.asyncio
async def test_create_connection_success(db_session: AsyncSession) -> None:
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        tokens = await _register_tenant(ac, "conn-corp", "owner@conn.com")
        token = tokens["access_token"]

        resp = await ac.post(
            "/connections",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "provider": "fake",
                "name": "My Fake",
                "credentials": {"api_key": "good-key"},
                "config": {"setting": "value"},
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["provider"] == "fake"
        assert data["name"] == "My Fake"
        assert data["status"] == "active"
        assert data["config"] == {"setting": "value"}
        assert "credentials" not in data
        assert "encrypted_credentials" not in data


@pytest.mark.db
@pytest.mark.asyncio
async def test_create_connection_invalid_credentials_rejected(
    db_session: AsyncSession,
) -> None:
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        tokens = await _register_tenant(ac, "inv-cred-corp", "owner@invcred.com")
        token = tokens["access_token"]

        resp = await ac.post(
            "/connections",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "provider": "fake",
                "name": "Bad Creds",
                "credentials": {},  # missing api_key
            },
        )
        assert resp.status_code == 422

        # Verify nothing was stored
        result = await db_session.execute(
            select(Connection).where(Connection.name == "Bad Creds")
        )
        assert result.scalar_one_or_none() is None


@pytest.mark.db
@pytest.mark.asyncio
async def test_create_connection_failing_test_rejected(
    db_session: AsyncSession,
) -> None:
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        tokens = await _register_tenant(ac, "fail-test-corp", "owner@failtest.com")
        token = tokens["access_token"]

        resp = await ac.post(
            "/connections",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "provider": "fake",
                "name": "Failing Test",
                "credentials": {"api_key": "bad"},
            },
        )
        assert resp.status_code == 422

        # Verify nothing was stored
        result = await db_session.execute(
            select(Connection).where(Connection.name == "Failing Test")
        )
        assert result.scalar_one_or_none() is None


@pytest.mark.db
@pytest.mark.asyncio
async def test_create_connection_unknown_provider(db_session: AsyncSession) -> None:
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        tokens = await _register_tenant(ac, "unk-prov-corp", "owner@unkprov.com")
        token = tokens["access_token"]

        resp = await ac.post(
            "/connections",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "provider": "nonexistent",
                "name": "Unknown",
                "credentials": {"api_key": "test"},
            },
        )
        assert resp.status_code == 400
        assert "Unknown connector provider" in resp.json()["detail"]


@pytest.mark.db
@pytest.mark.asyncio
async def test_duplicate_connection_rejected(db_session: AsyncSession) -> None:
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        tokens = await _register_tenant(ac, "dup-corp", "owner@dup.com")
        token = tokens["access_token"]

        for _ in range(2):
            resp = await ac.post(
                "/connections",
                headers={"Authorization": f"Bearer {token}"},
                json={
                    "provider": "fake",
                    "name": "Duplicate Name",
                    "credentials": {"api_key": "good-key"},
                },
            )

        assert resp.status_code == 409


@pytest.mark.db
@pytest.mark.asyncio
async def test_same_name_allowed_different_tenant(db_session: AsyncSession) -> None:
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        tokens_a = await _register_tenant(ac, "samename-a", "owner@sna.com")
        tokens_b = await _register_tenant(ac, "samename-b", "owner@snb.com")

        for token_data in [tokens_a, tokens_b]:
            resp = await ac.post(
                "/connections",
                headers={"Authorization": f"Bearer {token_data['access_token']}"},
                json={
                    "provider": "fake",
                    "name": "Shared Name",
                    "credentials": {"api_key": "good-key"},
                },
            )
            assert resp.status_code == 200


@pytest.mark.db
@pytest.mark.asyncio
async def test_encrypted_credentials_not_plaintext(db_session: AsyncSession) -> None:
    """Stored encrypted_credentials must be ciphertext that decrypts back."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        tokens = await _register_tenant(ac, "enc-corp", "owner@enc.com")
        token = tokens["access_token"]

        resp = await ac.post(
            "/connections",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "provider": "fake",
                "name": "Encrypted Test",
                "credentials": {"api_key": "my-secret-key"},
            },
        )
        assert resp.status_code == 200
        conn_id = resp.json()["id"]

        # Query DB directly
        result = await db_session.execute(
            select(Connection).where(Connection.id == conn_id)
        )
        connection = result.scalar_one()

        # Must NOT be readable JSON
        assert "my-secret-key" not in connection.encrypted_credentials
        try:
            parsed = json.loads(connection.encrypted_credentials)
            # If it parses as JSON, it should NOT have the key in plain text
            assert parsed.get("api_key") != "my-secret-key"
        except json.JSONDecodeError:
            pass  # Expected — it's Fernet ciphertext, not JSON

        # Must decrypt back to original
        decrypted = decrypt_json(connection.encrypted_credentials)
        assert decrypted == {"api_key": "my-secret-key"}


# ──────────────────────────────────────────────────────────────────────
# Credential security: responses never contain credential values
# ──────────────────────────────────────────────────────────────────────


@pytest.mark.db
@pytest.mark.asyncio
async def test_responses_never_contain_credentials(db_session: AsyncSession) -> None:
    """Assert that no endpoint leaks credentials in the response body."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        tokens = await _register_tenant(ac, "noleak-corp", "owner@noleak.com")
        token = tokens["access_token"]

        # Create
        create_resp = await ac.post(
            "/connections",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "provider": "fake",
                "name": "No Leak",
                "credentials": {"api_key": "super-secret-api-key-12345"},
            },
        )
        assert create_resp.status_code == 200
        conn_id = create_resp.json()["id"]
        body_text = create_resp.text
        assert "super-secret-api-key-12345" not in body_text
        assert "encrypted_credentials" not in body_text

        # List
        list_resp = await ac.get(
            "/connections", headers={"Authorization": f"Bearer {token}"}
        )
        assert "super-secret-api-key-12345" not in list_resp.text
        assert "encrypted_credentials" not in list_resp.text

        # Get
        get_resp = await ac.get(
            f"/connections/{conn_id}", headers={"Authorization": f"Bearer {token}"}
        )
        assert "super-secret-api-key-12345" not in get_resp.text
        assert "encrypted_credentials" not in get_resp.text

        # Test
        test_resp = await ac.post(
            f"/connections/{conn_id}/test",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert "super-secret-api-key-12345" not in test_resp.text
        assert "encrypted_credentials" not in test_resp.text


# ──────────────────────────────────────────────────────────────────────
# Credential security: credentials do not appear in logs
# ──────────────────────────────────────────────────────────────────────


@pytest.mark.db
@pytest.mark.asyncio
async def test_credentials_not_in_logs(
    db_session: AsyncSession, caplog: pytest.LogCaptureFixture
) -> None:
    """Credentials must never appear in captured log output."""
    with caplog.at_level(logging.DEBUG):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            tokens = await _register_tenant(ac, "logtest-corp", "owner@logtest.com")
            token = tokens["access_token"]

            await ac.post(
                "/connections",
                headers={"Authorization": f"Bearer {token}"},
                json={
                    "provider": "fake",
                    "name": "Log Test",
                    "credentials": {"api_key": "ultra-secret-log-test-key"},
                },
            )

    for record in caplog.records:
        assert "ultra-secret-log-test-key" not in record.getMessage()


# ──────────────────────────────────────────────────────────────────────
# Role enforcement
# ──────────────────────────────────────────────────────────────────────


@pytest.mark.db
@pytest.mark.asyncio
async def test_member_gets_403_on_create_test_delete(
    db_session: AsyncSession,
) -> None:
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        tokens = await _register_tenant(ac, "role-corp", "owner@role.com")
        owner_token = tokens["access_token"]

        # Create a member user
        await _create_member(ac, owner_token, "member@role.com")
        member_token = await _login(ac, "role-corp", "member@role.com")

        # Member cannot create
        create_resp = await ac.post(
            "/connections",
            headers={"Authorization": f"Bearer {member_token}"},
            json={
                "provider": "fake",
                "name": "Member Create",
                "credentials": {"api_key": "test"},
            },
        )
        assert create_resp.status_code == 403

        # Owner creates a connection for further testing
        owner_create = await ac.post(
            "/connections",
            headers={"Authorization": f"Bearer {owner_token}"},
            json={
                "provider": "fake",
                "name": "Owner Created",
                "credentials": {"api_key": "good-key"},
            },
        )
        assert owner_create.status_code == 200
        conn_id = owner_create.json()["id"]

        # Member CAN list and get
        list_resp = await ac.get(
            "/connections", headers={"Authorization": f"Bearer {member_token}"}
        )
        assert list_resp.status_code == 200

        get_resp = await ac.get(
            f"/connections/{conn_id}",
            headers={"Authorization": f"Bearer {member_token}"},
        )
        assert get_resp.status_code == 200

        # Member cannot test
        test_resp = await ac.post(
            f"/connections/{conn_id}/test",
            headers={"Authorization": f"Bearer {member_token}"},
        )
        assert test_resp.status_code == 403

        # Member cannot delete
        del_resp = await ac.delete(
            f"/connections/{conn_id}",
            headers={"Authorization": f"Bearer {member_token}"},
        )
        assert del_resp.status_code == 403


# ──────────────────────────────────────────────────────────────────────
# Connection test endpoint
# ──────────────────────────────────────────────────────────────────────


@pytest.mark.db
@pytest.mark.asyncio
async def test_post_test_updates_status(db_session: AsyncSession) -> None:
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        tokens = await _register_tenant(ac, "test-corp", "owner@test-corp.com")
        token = tokens["access_token"]

        resp = await ac.post(
            "/connections",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "provider": "fake",
                "name": "Test Status",
                "credentials": {"api_key": "good-key"},
            },
        )
        assert resp.status_code == 200
        conn_id = resp.json()["id"]

        # Test should succeed
        test_resp = await ac.post(
            f"/connections/{conn_id}/test",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert test_resp.status_code == 200
        data = test_resp.json()
        assert data["status"] == "active"
        assert data["last_tested_at"] is not None
        assert data["last_error"] is None


@pytest.mark.db
@pytest.mark.asyncio
async def test_post_test_timeout_handled_safely(db_session: AsyncSession) -> None:
    """A connector that hangs should result in a safe timeout error."""
    from unittest.mock import patch

    from app.services import connection_service

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        tokens = await _register_tenant(ac, "timeout-corp", "owner@timeout.com")
        token = tokens["access_token"]

        # Use a very short timeout for testing
        with patch.object(connection_service, "_TEST_TIMEOUT_SECONDS", 0.1):
            resp = await ac.post(
                "/connections",
                headers={"Authorization": f"Bearer {token}"},
                json={
                    "provider": "fake",
                    "name": "Timeout Test",
                    "credentials": {"api_key": "timeout"},
                },
            )
            assert resp.status_code == 422
            assert "timed out" in resp.json()["detail"]


# ──────────────────────────────────────────────────────────────────────
# Delete
# ──────────────────────────────────────────────────────────────────────


@pytest.mark.db
@pytest.mark.asyncio
async def test_delete_removes_row(db_session: AsyncSession) -> None:
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        tokens = await _register_tenant(ac, "del-corp", "owner@del.com")
        token = tokens["access_token"]

        resp = await ac.post(
            "/connections",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "provider": "fake",
                "name": "To Delete",
                "credentials": {"api_key": "good-key"},
            },
        )
        conn_id = resp.json()["id"]

        del_resp = await ac.delete(
            f"/connections/{conn_id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert del_resp.status_code == 204

        # Verify it's gone
        get_resp = await ac.get(
            f"/connections/{conn_id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert get_resp.status_code == 404


# ──────────────────────────────────────────────────────────────────────
# TENANT ISOLATION (critical)
# ──────────────────────────────────────────────────────────────────────


@pytest.mark.db
@pytest.mark.asyncio
async def test_tenant_isolation(db_session: AsyncSession) -> None:
    """Tenant A must NOT be able to list/get/test/delete Tenant B's connections."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        tokens_a = await _register_tenant(ac, "iso-a", "owner@iso-a.com")
        tokens_b = await _register_tenant(ac, "iso-b", "owner@iso-b.com")
        token_a = tokens_a["access_token"]
        token_b = tokens_b["access_token"]

        # Tenant A creates a connection
        resp_a = await ac.post(
            "/connections",
            headers={"Authorization": f"Bearer {token_a}"},
            json={
                "provider": "fake",
                "name": "A Private",
                "credentials": {"api_key": "secret-a"},
            },
        )
        assert resp_a.status_code == 200
        conn_a_id = resp_a.json()["id"]

        # Tenant B creates a connection
        resp_b = await ac.post(
            "/connections",
            headers={"Authorization": f"Bearer {token_b}"},
            json={
                "provider": "fake",
                "name": "B Private",
                "credentials": {"api_key": "secret-b"},
            },
        )
        assert resp_b.status_code == 200
        conn_b_id = resp_b.json()["id"]

        # Tenant B cannot see Tenant A's connections in list
        list_b = await ac.get(
            "/connections", headers={"Authorization": f"Bearer {token_b}"}
        )
        assert list_b.status_code == 200
        b_names = {c["name"] for c in list_b.json()}
        assert "A Private" not in b_names
        assert "B Private" in b_names

        # Tenant B gets 404 (not 403) for Tenant A's connection
        get_resp = await ac.get(
            f"/connections/{conn_a_id}",
            headers={"Authorization": f"Bearer {token_b}"},
        )
        assert get_resp.status_code == 404

        # Tenant B cannot test Tenant A's connection (404)
        test_resp = await ac.post(
            f"/connections/{conn_a_id}/test",
            headers={"Authorization": f"Bearer {token_b}"},
        )
        assert test_resp.status_code == 404

        # Tenant B cannot delete Tenant A's connection (404)
        del_resp = await ac.delete(
            f"/connections/{conn_a_id}",
            headers={"Authorization": f"Bearer {token_b}"},
        )
        assert del_resp.status_code == 404

        # Tenant A cannot see Tenant B's connections
        get_resp_a = await ac.get(
            f"/connections/{conn_b_id}",
            headers={"Authorization": f"Bearer {token_a}"},
        )
        assert get_resp_a.status_code == 404


# ──────────────────────────────────────────────────────────────────────
# GET /connectors returns empty in production (but populated in tests)
# ──────────────────────────────────────────────────────────────────────


@pytest.mark.db
@pytest.mark.asyncio
async def test_list_connectors_endpoint(db_session: AsyncSession) -> None:
    """GET /connectors should return the fake connector in test context."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        tokens = await _register_tenant(ac, "meta-corp", "owner@meta.com")
        token = tokens["access_token"]

        resp = await ac.get(
            "/connectors", headers={"Authorization": f"Bearer {token}"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["provider_key"] == "fake"
        assert data[0]["display_name"] == "Fake Connector"
        assert len(data[0]["credential_fields"]) >= 1
        field_names = [f["name"] for f in data[0]["credential_fields"]]
        assert "api_key" in field_names
