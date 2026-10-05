from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.storage.base import (
    Base,
    TenantOwnedMixin,
    TimestampMixin,
    UUIDPrimaryKeyMixin,
)


class RefreshToken(Base, UUIDPrimaryKeyMixin, TimestampMixin, TenantOwnedMixin):
    __tablename__ = "refresh_tokens"

    user_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    token_hash: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    revoked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        default=None,
    )

    __table_args__ = (
        UniqueConstraint("token_hash", name="uq_refresh_tokens_token_hash"),
        Index("ix_refresh_tokens_token_hash", "token_hash", unique=True),
    )
