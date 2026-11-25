"""学院 v1：课程、课期、讲师、评价、权益五张表

Revision ID: 0001_academy
Revises:
Create Date: 2026-11-25
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0001_academy"
down_revision = None
branch_labels = None
depends_on = None


def _audit_columns() -> list:
    """业务表统一含 id / org_id / site_id / created_at / created_by / updated_at / deleted_at。"""
    return [
        sa.Column("org_id", sa.Uuid(), nullable=False),
        sa.Column("site_id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
    ]


def upgrade() -> None:
    op.create_table(
        "academy_course",
        sa.Column("id", sa.Uuid(), primary_key=True),
        *_audit_columns(),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("subtitle", sa.String(200), nullable=True),
        sa.Column("category", sa.String(64), nullable=True),
        sa.Column("intro", sa.Text(), nullable=True),
        sa.Column("outline", sa.JSON(), nullable=False),
        sa.Column("outcomes", sa.JSON(), nullable=False),
        sa.Column("cover_url", sa.String(500), nullable=True),
        sa.Column("fee_mode", sa.String(32), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
    )
    op.create_index("ix_academy_course_deleted_at", "academy_course", ["deleted_at"])

    op.create_table(
        "academy_instructor",
        sa.Column("id", sa.Uuid(), primary_key=True),
        *_audit_columns(),
        sa.Column("display_name", sa.String(100), nullable=False),
        sa.Column("headline", sa.String(200), nullable=True),
        sa.Column("bio", sa.Text(), nullable=True),
        sa.Column("avatar_url", sa.String(500), nullable=True),
        sa.Column("role", sa.String(32), nullable=False),
        sa.Column("show_company_card", sa.Boolean(), nullable=False),
        sa.Column("crm_company_id", sa.String(64), nullable=True),
        sa.Column("contact_id", sa.Uuid(), nullable=True),
    )

    op.create_table(
        "academy_course_instructor",
        sa.Column("id", sa.Uuid(), primary_key=True),
        *_audit_columns(),
        sa.Column("course_id", sa.Uuid(), nullable=False),
        sa.Column("instructor_id", sa.Uuid(), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.UniqueConstraint("course_id", "instructor_id", name="uq_course_instructor"),
    )

    op.create_table(
        "academy_session",
        sa.Column("id", sa.Uuid(), primary_key=True),
        *_audit_columns(),
        sa.Column("course_id", sa.Uuid(), nullable=False),
        sa.Column("label", sa.String(120), nullable=False),
        sa.Column("start_at", sa.DateTime(), nullable=False),
        sa.Column("end_at", sa.DateTime(), nullable=False),
        sa.Column("signup_open_at", sa.DateTime(), nullable=False),
        sa.Column("signup_deadline", sa.DateTime(), nullable=False),
        sa.Column("room_name", sa.String(120), nullable=True),
        sa.Column("capacity", sa.Integer(), nullable=False),
        sa.Column("seats_taken", sa.Integer(), nullable=False),
        sa.Column("waitlist_count", sa.Integer(), nullable=False),
        sa.Column("waitlist_enabled", sa.Boolean(), nullable=False),
        sa.Column("signup_mode", sa.String(20), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
    )
    op.create_index("ix_academy_session_start_at", "academy_session", ["start_at"])
    op.create_index("ix_academy_session_end_at", "academy_session", ["end_at"])

    op.create_table(
        "academy_enrollment",
        sa.Column("id", sa.Uuid(), primary_key=True),
        *_audit_columns(),
        sa.Column("session_id", sa.Uuid(), nullable=False),
        sa.Column("contact_id", sa.Uuid(), nullable=False),
        sa.Column("state", sa.String(32), nullable=False),
    )

    op.create_table(
        "academy_review",
        sa.Column("id", sa.Uuid(), primary_key=True),
        *_audit_columns(),
        sa.Column("course_id", sa.Uuid(), nullable=False),
        sa.Column("contact_id", sa.Uuid(), nullable=False),
        sa.Column("author_name", sa.String(100), nullable=False),
        sa.Column("anonymous", sa.Boolean(), nullable=False),
        sa.Column("visible", sa.Boolean(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("rating", sa.Integer(), nullable=False),
        sa.Column("rating_content", sa.Integer(), nullable=False),
        sa.Column("rating_instructor", sa.Integer(), nullable=False),
        sa.Column("rating_service", sa.Integer(), nullable=False),
    )

    op.create_table(
        "academy_entitlement",
        sa.Column("id", sa.Uuid(), primary_key=True),
        *_audit_columns(),
        sa.Column("contact_id", sa.Uuid(), nullable=False),
        sa.Column("course_category", sa.String(64), nullable=True),
        sa.Column("remaining_cents", sa.Integer(), nullable=False),
        sa.Column("valid_until", sa.DateTime(), nullable=True),
    )


def downgrade() -> None:
    for table in (
        "academy_entitlement",
        "academy_review",
        "academy_enrollment",
        "academy_session",
        "academy_course_instructor",
        "academy_instructor",
        "academy_course",
    ):
        op.drop_table(table)
