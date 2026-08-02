"""create background jobs and error analyses tables

Revision ID: 20260723_04
Revises: 20260722_03
Create Date: 2026-07-23
"""

from __future__ import annotations

from alembic import op

# revision identifiers, used by Alembic.
revision = "20260723_04"
down_revision = "20260722_03"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'background_job_status') THEN
                CREATE TYPE background_job_status AS ENUM (
                    'pending',
                    'running',
                    'completed',
                    'failed',
                    'partially_completed'
                );
            END IF;
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'background_job_type') THEN
                CREATE TYPE background_job_type AS ENUM (
                    'bulk_log_ingest',
                    'error_group_analysis',
                    'log_cleanup',
                    'analytics_recalculation'
                );
            END IF;
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'error_analysis_status') THEN
                CREATE TYPE error_analysis_status AS ENUM ('pending', 'completed', 'failed');
            END IF;
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'analysis_priority') THEN
                CREATE TYPE analysis_priority AS ENUM ('low', 'medium', 'high', 'critical');
            END IF;
        END
        $$;
        """
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS background_jobs (
            id VARCHAR(36) NOT NULL,
            job_type background_job_type NOT NULL,
            status background_job_status DEFAULT 'pending' NOT NULL,
            payload JSONB NOT NULL,
            total_items INTEGER DEFAULT 0 NOT NULL,
            processed_items INTEGER DEFAULT 0 NOT NULL,
            success_count INTEGER DEFAULT 0 NOT NULL,
            failure_count INTEGER DEFAULT 0 NOT NULL,
            idempotency_key VARCHAR(128),
            scope_key VARCHAR(255),
            celery_task_id VARCHAR(64),
            error_summary TEXT,
            created_by INTEGER,
            started_at TIMESTAMP WITH TIME ZONE,
            completed_at TIMESTAMP WITH TIME ZONE,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
            updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
            PRIMARY KEY (id),
            FOREIGN KEY(created_by) REFERENCES users (id) ON DELETE SET NULL,
            CONSTRAINT ck_background_jobs_total_items_non_negative CHECK (total_items >= 0),
            CONSTRAINT ck_background_jobs_processed_items_non_negative CHECK (processed_items >= 0),
            CONSTRAINT ck_background_jobs_success_count_non_negative CHECK (success_count >= 0),
            CONSTRAINT ck_background_jobs_failure_count_non_negative CHECK (failure_count >= 0)
        )
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS ix_background_jobs_status ON background_jobs (status)")
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_background_jobs_created_at ON background_jobs (created_at)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_background_jobs_completed_at "
        "ON background_jobs (completed_at)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_background_jobs_scope_key ON background_jobs (scope_key)"
    )
    op.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS ux_background_jobs_active_scope
        ON background_jobs (job_type, scope_key)
        WHERE status IN ('pending', 'running') AND scope_key IS NOT NULL
        """
    )
    op.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS ux_background_jobs_type_idempotency
        ON background_jobs (job_type, idempotency_key)
        WHERE idempotency_key IS NOT NULL
        """
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS error_analyses (
            id SERIAL NOT NULL,
            error_group_id INTEGER NOT NULL,
            status error_analysis_status DEFAULT 'pending' NOT NULL,
            summary TEXT,
            likely_root_cause TEXT,
            suggested_fix TEXT,
            confidence NUMERIC(4, 3),
            affected_component VARCHAR(255),
            recommended_priority analysis_priority,
            reasoning_summary TEXT,
            provider VARCHAR(64),
            model VARCHAR(128),
            latency_ms INTEGER,
            raw_response_metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
            created_by INTEGER,
            completed_at TIMESTAMP WITH TIME ZONE,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
            updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
            PRIMARY KEY (id),
            FOREIGN KEY(error_group_id) REFERENCES error_groups (id) ON DELETE CASCADE,
            FOREIGN KEY(created_by) REFERENCES users (id) ON DELETE SET NULL,
            CONSTRAINT ck_error_analyses_confidence_range CHECK (
                confidence IS NULL OR (confidence >= 0 AND confidence <= 1)
            )
        )
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_error_analyses_error_group_id "
        "ON error_analyses (error_group_id)"
    )
    op.execute("CREATE INDEX IF NOT EXISTS ix_error_analyses_status ON error_analyses (status)")
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_error_analyses_created_at ON error_analyses (created_at)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_error_analyses_completed_at ON error_analyses (completed_at)"
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS error_analyses")
    op.execute("DROP TABLE IF EXISTS background_jobs")
    op.execute("DROP TYPE IF EXISTS analysis_priority")
    op.execute("DROP TYPE IF EXISTS error_analysis_status")
    op.execute("DROP TYPE IF EXISTS background_job_type")
    op.execute("DROP TYPE IF EXISTS background_job_status")
