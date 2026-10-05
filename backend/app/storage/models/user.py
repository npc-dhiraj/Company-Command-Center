from enum import Enum
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, String, UniqueConstraint
from sqlalchemy import Enum as SQLEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.storage.base import (
    Base,
    TenantOwnedMixin,
    TimestampMixin,
    UUIDPrimaryKeyMixin,
)

if TYPE_CHECKING:
    from app.storage.models.tenant import Tenant


class UserRole(str, Enum):
    OWNER = "owner"
    ADMIN = "admin"
    MEMBER = "member"


class User(Base, UUIDPrimaryKeyMixin, TimestampMixin, TenantOwnedMixin):
    __tablename__ = "users"

    email: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[UserRole] = mapped_column(
        SQLEnum(UserRole, native_enum=False, length=50),
        nullable=False,
        default=UserRole.MEMBER,
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    tenant: Mapped["Tenant"] = relationship("Tenant", back_populates="users")

    __table_args__ = (
        UniqueConstraint("tenant_id", "email", name="uq_users_tenant_id_email"),
    )
