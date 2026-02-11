"""Increase picture_url column length to 2048

Revision ID: fix_picture_url_len
Revises: add_subscriptions_and_usage
Create Date: 2026-02-11
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers
revision = "fix_picture_url_len"
down_revision = "add_subscriptions_and_usage"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "users",
        "picture_url",
        existing_type=sa.String(500),
        type_=sa.String(2048),
        existing_nullable=True,
    )


def downgrade() -> None:
    op.alter_column(
        "users",
        "picture_url",
        existing_type=sa.String(2048),
        type_=sa.String(500),
        existing_nullable=True,
    )
