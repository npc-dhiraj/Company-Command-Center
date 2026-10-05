"""add auth fields and refresh tokens

Revision ID: 0002_auth
Revises: 0001_initial
Create Date: 2026-10-05 00:01:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0002_auth"
down_revision: str | None = "0001_initial"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Add password_hash and role columns to users
    op.add_column(
        "users",
        sa.Column(
            "password_hash",
            sa.String(length=255),
            nullable=False,
            server_default="",
        ),
    )
    op.add_column(
        "users",
        sa.Column(
            "role",
            sa.String(length=50),
            nullable=False,
            server_default="member",
        ),
    )
    # Remove temporary server default for password_hash so future inserts require value
    op.alter_column("users", "password_hash", server_default=None)

    # Create refresh_tokens table
    op.create_table(
        "refresh_tokens",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("token_hash", sa.String(length=255), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.id"],
            name=op.f("fk_refresh_tokens_tenant_id_tenants"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_refresh_tokens_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_refresh_tokens")),
        sa.UniqueConstraint("token_hash", name=op.f("uq_refresh_tokens_token_hash")),
    )
    op.create_index(
        op.f("ix_refresh_tokens_tenant_id"),
        "refresh_tokens",
        ["tenant_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_refresh_tokens_user_id"),
        "refresh_tokens",
        ["user_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_refresh_tokens_token_hash"),
        "refresh_tokens",
        ["token_hash"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_refresh_tokens_token_hash"), table_name="refresh_tokens")
    op.drop_index(op.f("ix_refresh_tokens_user_id"), table_name="refresh_tokens")
    op.drop_index(op.f("ix_refresh_tokens_tenant_id"), table_name="refresh_tokens")
    op.drop_table("refresh_tokens")
    op.drop_column("users", "role")
    op.drop_column("users", "password_hash")
