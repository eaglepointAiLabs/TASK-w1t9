"""ops schema"""

from alembic import op
import sqlalchemy as sa


revision = "20260328_0009"
down_revision = "20260328_0008"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "job_queue",
        sa.Column("job_type", sa.String(length=80), nullable=False),
        sa.Column("payload_json", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("max_attempts", sa.Integer(), nullable=False),
        sa.Column("available_at", sa.DateTime(), nullable=False),
        sa.Column("last_error", sa.Text(), nullable=False),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_job_queue_available_at"), "job_queue", ["available_at"], unique=False)
    op.create_index(op.f("ix_job_queue_job_type"), "job_queue", ["job_type"], unique=False)
    op.create_index(op.f("ix_job_queue_status"), "job_queue", ["status"], unique=False)

    op.create_table(
        "job_runs",
        sa.Column("job_id", sa.String(length=36), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("started_at", sa.DateTime(), nullable=False),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
        sa.Column("details_json", sa.Text(), nullable=False),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.ForeignKeyConstraint(["job_id"], ["job_queue.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_job_runs_job_id"), "job_runs", ["job_id"], unique=False)
    op.create_index(op.f("ix_job_runs_status"), "job_runs", ["status"], unique=False)

    op.create_table(
        "backup_jobs",
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("file_path", sa.String(length=255), nullable=False),
        sa.Column("retention_until", sa.DateTime(), nullable=False),
        sa.Column("details_json", sa.Text(), nullable=False),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_backup_jobs_retention_until"), "backup_jobs", ["retention_until"], unique=False)
    op.create_index(op.f("ix_backup_jobs_status"), "backup_jobs", ["status"], unique=False)

    op.create_table(
        "restore_runs",
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("backup_job_id", sa.String(length=36), nullable=True),
        sa.Column("restore_path", sa.String(length=255), nullable=False),
        sa.Column("details_json", sa.Text(), nullable=False),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.ForeignKeyConstraint(["backup_job_id"], ["backup_jobs.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_restore_runs_backup_job_id"), "restore_runs", ["backup_job_id"], unique=False)
    op.create_index(op.f("ix_restore_runs_status"), "restore_runs", ["status"], unique=False)

    op.create_table(
        "rate_limit_buckets",
        sa.Column("bucket_key", sa.String(length=255), nullable=False),
        sa.Column("window_started_at", sa.DateTime(), nullable=False),
        sa.Column("request_count", sa.Integer(), nullable=False),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("bucket_key", name="uq_rate_limit_bucket_key"),
    )
    op.create_index(op.f("ix_rate_limit_buckets_bucket_key"), "rate_limit_buckets", ["bucket_key"], unique=True)
    op.create_index(op.f("ix_rate_limit_buckets_window_started_at"), "rate_limit_buckets", ["window_started_at"], unique=False)

    op.create_table(
        "circuit_breaker_state",
        sa.Column("endpoint_key", sa.String(length=255), nullable=False),
        sa.Column("state", sa.String(length=20), nullable=False),
        sa.Column("failure_count", sa.Integer(), nullable=False),
        sa.Column("opened_at", sa.DateTime(), nullable=True),
        sa.Column("last_failure_at", sa.DateTime(), nullable=True),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("endpoint_key", name="uq_circuit_breaker_endpoint"),
    )
    op.create_index(op.f("ix_circuit_breaker_state_endpoint_key"), "circuit_breaker_state", ["endpoint_key"], unique=True)
    op.create_index(op.f("ix_circuit_breaker_state_state"), "circuit_breaker_state", ["state"], unique=False)


def downgrade():
    op.drop_index(op.f("ix_circuit_breaker_state_state"), table_name="circuit_breaker_state")
    op.drop_index(op.f("ix_circuit_breaker_state_endpoint_key"), table_name="circuit_breaker_state")
    op.drop_table("circuit_breaker_state")
    op.drop_index(op.f("ix_rate_limit_buckets_window_started_at"), table_name="rate_limit_buckets")
    op.drop_index(op.f("ix_rate_limit_buckets_bucket_key"), table_name="rate_limit_buckets")
    op.drop_table("rate_limit_buckets")
    op.drop_index(op.f("ix_restore_runs_status"), table_name="restore_runs")
    op.drop_index(op.f("ix_restore_runs_backup_job_id"), table_name="restore_runs")
    op.drop_table("restore_runs")
    op.drop_index(op.f("ix_backup_jobs_status"), table_name="backup_jobs")
    op.drop_index(op.f("ix_backup_jobs_retention_until"), table_name="backup_jobs")
    op.drop_table("backup_jobs")
    op.drop_index(op.f("ix_job_runs_status"), table_name="job_runs")
    op.drop_index(op.f("ix_job_runs_job_id"), table_name="job_runs")
    op.drop_table("job_runs")
    op.drop_index(op.f("ix_job_queue_status"), table_name="job_queue")
    op.drop_index(op.f("ix_job_queue_job_type"), table_name="job_queue")
    op.drop_index(op.f("ix_job_queue_available_at"), table_name="job_queue")
    op.drop_table("job_queue")
