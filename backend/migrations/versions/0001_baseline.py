"""Baseline: the tables as they were before saved events and the duplicate-event rule

Revision ID: 0001_baseline
Revises:
Create Date: 2026-11-22
"""
from alembic import op
import sqlalchemy as sa


revision = "0001_baseline"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "colleges",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("key", sa.String(length=50), nullable=False, unique=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("seed_account", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=True),
    )

    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("google_sub", sa.String(length=255), nullable=False, unique=True),
        sa.Column("email", sa.String(length=254), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_users_email", "users", ["email"])

    op.create_table(
        "clubs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("college_id", sa.Integer(), sa.ForeignKey("colleges.id"), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("instagram_handle", sa.String(length=255), nullable=False, unique=True),
        sa.Column("instagram_user_id", sa.String(length=64), nullable=True, unique=True),
        sa.Column("profile_pic_url", sa.String(length=500), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=True),
    )

    op.create_table(
        "archived_clubs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("college_id", sa.Integer(), sa.ForeignKey("colleges.id"), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("instagram_handle", sa.String(length=255), nullable=False, unique=True),
        sa.Column("instagram_user_id", sa.String(length=64), nullable=True, unique=True),
        sa.Column("profile_pic_url", sa.String(length=500), nullable=True),
        sa.Column("last_post_at", sa.DateTime(), nullable=True),
        sa.Column("archived_at", sa.DateTime(), nullable=False),
    )

    op.create_table(
        "club_activity",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("club_id", sa.Integer(), sa.ForeignKey("clubs.id"), nullable=False, unique=True),
        sa.Column("college_id", sa.Integer(), sa.ForeignKey("colleges.id"), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("last_post_id", sa.String(length=255), nullable=True),
        sa.Column("last_post_at", sa.DateTime(), nullable=True),
        sa.Column("next_check_at", sa.DateTime(), nullable=True),
        sa.Column("checked_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_club_activity_next_check_at", "club_activity", ["next_check_at"])

    op.create_table(
        "club_post_checkpoints",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("club_id", sa.Integer(), sa.ForeignKey("clubs.id"), nullable=False, unique=True),
        sa.Column("last_post_id", sa.String(length=255), nullable=True),
        sa.Column("last_post_at", sa.DateTime(), nullable=True),
        sa.Column("checked_at", sa.DateTime(), nullable=False),
    )

    op.create_table(
        "events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("club_id", sa.Integer(), sa.ForeignKey("clubs.id"), nullable=False),
        sa.Column("college_id", sa.Integer(), sa.ForeignKey("colleges.id"), nullable=False),
        sa.Column("post_id", sa.String(length=255), nullable=True, unique=True),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("start_time", sa.DateTime(), nullable=True),
        sa.Column("end_time", sa.DateTime(), nullable=True),
        sa.Column("location", sa.String(length=255), nullable=True),
        sa.Column("is_free_food", sa.Boolean(), nullable=True),
        sa.Column("google_form_url", sa.String(length=500), nullable=True),
        sa.Column("source_url", sa.String(length=500), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=True),
    )

    op.create_table(
        "archived_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("club_id", sa.Integer(), sa.ForeignKey("clubs.id"), nullable=False),
        sa.Column("college_id", sa.Integer(), sa.ForeignKey("colleges.id"), nullable=False),
        sa.Column("post_id", sa.String(length=255), nullable=True, unique=True),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("start_time", sa.DateTime(), nullable=True),
        sa.Column("end_time", sa.DateTime(), nullable=True),
        sa.Column("location", sa.String(length=255), nullable=True),
        sa.Column("is_free_food", sa.Boolean(), nullable=True),
        sa.Column("google_form_url", sa.String(length=500), nullable=True),
        sa.Column("source_url", sa.String(length=500), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("archived_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_archived_events_club_id", "archived_events", ["club_id"])


def downgrade():
    op.drop_index("ix_archived_events_club_id", table_name="archived_events")
    op.drop_table("archived_events")
    op.drop_table("events")
    op.drop_table("club_post_checkpoints")
    op.drop_index("ix_club_activity_next_check_at", table_name="club_activity")
    op.drop_table("club_activity")
    op.drop_table("archived_clubs")
    op.drop_table("clubs")
    op.drop_index("ix_users_email", table_name="users")
    op.drop_table("users")
    op.drop_table("colleges")
