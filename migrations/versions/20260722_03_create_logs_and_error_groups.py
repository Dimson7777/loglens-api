"""create logs and error groups tables

Revision ID: 20260722_03
Revises: 20260722_02
Create Date: 2026-07-22
"""

from __future__ import annotations

from alembic import op

# revision identifiers, used by Alembic.
revision = "20260722_03"
down_revision = "20260722_02"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'log_environment') THEN
                CREATE TYPE log_environment AS ENUM ('development', 'staging', 'production');
            END IF;
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'log_level') THEN
                CREATE TYPE log_level AS ENUM ('debug', 'info', 'warning', 'error', 'critical');
            END IF;
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'error_group_status') THEN
                CREATE TYPE error_group_status AS ENUM (
                    'unresolved',
                    'investigating',
                    'resolved',
                    'ignored'
                );
            END IF;
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'error_group_severity') THEN
                CREATE TYPE error_group_severity AS ENUM ('low', 'medium', 'high', 'critical');
            END IF;
        END
        $$;
        """
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS error_groups (
            id SERIAL NOT NULL,
            fingerprint VARCHAR(64) NOT NULL,
            title VARCHAR(512) NOT NULL,
            service_name VARCHAR(128) NOT NULL,
            environment log_environment NOT NULL,
            exception_type VARCHAR(255),
            first_seen TIMESTAMP WITH TIME ZONE NOT NULL,
            last_seen TIMESTAMP WITH TIME ZONE NOT NULL,
            occurrence_count BIGINT DEFAULT '1' NOT NULL,
            status error_group_status DEFAULT 'unresolved' NOT NULL,
            severity error_group_severity DEFAULT 'medium' NOT NULL,
            assigned_to INTEGER,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
            updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
            PRIMARY KEY (id),
            FOREIGN KEY(assigned_to) REFERENCES users (id) ON DELETE SET NULL,
            CONSTRAINT ck_error_groups_occurrence_count_non_negative CHECK (occurrence_count >= 0),
            CONSTRAINT uq_error_groups_service_environment_fingerprint UNIQUE (
                service_name,
                environment,
                fingerprint
            )
        )
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_error_groups_service_name ON error_groups (service_name)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_error_groups_environment ON error_groups (environment)"
    )
    op.execute("CREATE INDEX IF NOT EXISTS ix_error_groups_status ON error_groups (status)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_error_groups_severity ON error_groups (severity)")
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_error_groups_assigned_to ON error_groups (assigned_to)"
    )
    op.execute("CREATE INDEX IF NOT EXISTS ix_error_groups_last_seen ON error_groups (last_seen)")

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS logs (
            id SERIAL NOT NULL,
            service_name VARCHAR(128) NOT NULL,
            environment log_environment NOT NULL,
            log_level log_level NOT NULL,
            message TEXT NOT NULL,
            normalized_message TEXT NOT NULL,
            exception_type VARCHAR(255),
            stack_trace TEXT,
            metadata JSONB NOT NULL,
            fingerprint VARCHAR(64),
            error_group_id INTEGER,
            timestamp TIMESTAMP WITH TIME ZONE NOT NULL,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
            PRIMARY KEY (id),
            FOREIGN KEY(error_group_id) REFERENCES error_groups (id) ON DELETE SET NULL
        )
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS ix_logs_service_name ON logs (service_name)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_logs_environment ON logs (environment)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_logs_log_level ON logs (log_level)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_logs_fingerprint ON logs (fingerprint)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_logs_timestamp ON logs (timestamp)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_logs_error_group_id ON logs (error_group_id)")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS logs")
    op.execute("DROP TABLE IF EXISTS error_groups")
    op.execute("DROP TYPE IF EXISTS error_group_severity")
    op.execute("DROP TYPE IF EXISTS error_group_status")
    op.execute("DROP TYPE IF EXISTS log_level")
    op.execute("DROP TYPE IF EXISTS log_environment")
