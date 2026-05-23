"""initial schema: users, jobs (with owner_id), questions

Revision ID: 0001_initial
Revises:
Create Date: 2026-05-21
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    op.create_table(
        "jobs",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("owner_id", sa.Integer(), nullable=False),
        sa.Column("subject", sa.String(), nullable=False),
        sa.Column("language", sa.String(), nullable=False, server_default="English"),
        sa.Column("provider", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False, server_default="pending"),
        sa.Column("pdf_key", sa.String(), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_jobs_owner_id", "jobs", ["owner_id"])

    op.create_table(
        "questions",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("job_id", sa.String(), nullable=False),
        sa.Column("question_text", sa.Text(), nullable=False, server_default=""),
        sa.Column("option_a", sa.Text(), nullable=False, server_default=""),
        sa.Column("option_b", sa.Text(), nullable=False, server_default=""),
        sa.Column("option_c", sa.Text(), nullable=False, server_default=""),
        sa.Column("option_d", sa.Text(), nullable=False, server_default=""),
        sa.Column("correct_answer", sa.String(length=1), nullable=True),
        sa.Column("solution", sa.Text(), nullable=False, server_default=""),
        sa.ForeignKeyConstraint(["job_id"], ["jobs.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_questions_job_id", "questions", ["job_id"])


def downgrade() -> None:
    op.drop_index("ix_questions_job_id", table_name="questions")
    op.drop_table("questions")
    op.drop_index("ix_jobs_owner_id", table_name="jobs")
    op.drop_table("jobs")
    op.drop_index("ix_users_email", table_name="users")
    op.drop_table("users")
