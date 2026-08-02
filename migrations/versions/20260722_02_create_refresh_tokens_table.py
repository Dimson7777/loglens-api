"""create refresh tokens table

Revision ID: 20260722_02
Revises: 20260722_01
Create Date: 2026-07-22
"""

from __future__ import annotations

from alembic import op

# revision identifiers, used by Alembic.
revision = "20260722_02"
down_revision = "20260722_01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS refresh_tokens (
            id SERIAL NOT NULL,
            user_id INTEGER NOT NULL,
            jti_hash VARCHAR(64) NOT NULL,
            family_id VARCHAR(36) NOT NULL,
            replaced_by_jti_hash VARCHAR(64),
            created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
            expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
            revoked_at TIMESTAMP WITH TIME ZONE,
            reuse_detected_at TIMESTAMP WITH TIME ZONE,
            PRIMARY KEY (id),
            FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE
        )
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_refresh_tokens_family_id ON refresh_tokens (family_id)"
    )
    op.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS ix_refresh_tokens_jti_hash ON refresh_tokens (jti_hash)"
    )
    op.execute("CREATE INDEX IF NOT EXISTS ix_refresh_tokens_user_id ON refresh_tokens (user_id)")


def downgrade() -> None:
    op.drop_index(op.f("ix_refresh_tokens_user_id"), table_name="refresh_tokens")
    op.drop_index(op.f("ix_refresh_tokens_jti_hash"), table_name="refresh_tokens")
    op.drop_index(op.f("ix_refresh_tokens_family_id"), table_name="refresh_tokens")
    op.drop_table("refresh_tokens")
