"""phase 2 extraction review"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "media_assets",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("version_id", sa.Uuid(), sa.ForeignKey("film_versions.id"), nullable=False),
        sa.Column("kind", sa.String(16), nullable=False),
        sa.Column("original_name", sa.String(180), nullable=False),
        sa.Column("content_type", sa.String(80), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("checksum_sha256", sa.String(64), nullable=False),
        sa.Column("storage_uri", sa.String(1000), nullable=False),
        sa.Column("duration_seconds", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("version_id", "kind", name="uq_version_media_kind"),
    )
    op.create_index("ix_media_assets_version_id", "media_assets", ["version_id"])
    op.create_table(
        "extraction_jobs",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("version_id", sa.Uuid(), sa.ForeignKey("film_versions.id"), nullable=False),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("provider", sa.String(24), nullable=False),
        sa.Column("model_name", sa.String(120), nullable=True),
        sa.Column("prompt_version", sa.String(40), nullable=False),
        sa.Column("error_code", sa.String(80), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_extraction_jobs_version_id", "extraction_jobs", ["version_id"])
    op.create_table(
        "extraction_documents",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("job_id", sa.Uuid(), sa.ForeignKey("extraction_jobs.id"), nullable=False),
        sa.Column("version_id", sa.Uuid(), sa.ForeignKey("film_versions.id"), nullable=False),
        sa.Column("content", sa.JSON(), nullable=False),
        sa.Column("review_status", sa.String(24), nullable=False),
        sa.Column("reviewed_by", sa.Uuid(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("job_id", name="uq_extraction_document_job"),
    )
    op.create_index("ix_extraction_documents_version_id", "extraction_documents", ["version_id"])


def downgrade() -> None:
    op.drop_table("extraction_documents")
    op.drop_table("extraction_jobs")
    op.drop_table("media_assets")
