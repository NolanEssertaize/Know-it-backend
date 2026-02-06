"""add subscriptions and usage tables

Revision ID: add_subscriptions_and_usage
Revises: add_flashcards_and_decks
Create Date: 2025-02-06

Creates the user_subscriptions and daily_usage tables for
subscription management and usage quota tracking.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.engine.reflection import Inspector

# revision identifiers, used by Alembic.
revision: str = "add_subscriptions_and_usage"
down_revision: Union[str, None] = "add_flashcards_and_decks"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = Inspector.from_engine(conn)
    existing_tables = inspector.get_table_names()

    if "user_subscriptions" not in existing_tables:
        op.create_table(
            "user_subscriptions",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column(
                "user_id",
                sa.String(36),
                sa.ForeignKey("users.id", ondelete="CASCADE"),
                unique=True,
                nullable=False,
                index=True,
            ),
            sa.Column(
                "plan_type",
                sa.Enum("free", "student", "unlimited", name="plantype"),
                nullable=False,
                server_default="free",
            ),
            sa.Column(
                "status",
                sa.Enum(
                    "active", "expired", "cancelled", "grace_period",
                    name="subscriptionstatus",
                ),
                nullable=False,
                server_default="active",
            ),
            sa.Column(
                "store_platform",
                sa.Enum("apple", "google", name="storeplatform"),
                nullable=True,
            ),
            sa.Column("store_product_id", sa.String(255), nullable=True),
            sa.Column("store_transaction_id", sa.String(255), nullable=True),
            sa.Column("store_original_transaction_id", sa.String(255), nullable=True),
            sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("purchased_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.func.now(),
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.func.now(),
            ),
        )

    if "daily_usage" not in existing_tables:
        op.create_table(
            "daily_usage",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column(
                "user_id",
                sa.String(36),
                sa.ForeignKey("users.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("usage_date", sa.Date, nullable=False),
            sa.Column("sessions_used", sa.Integer, nullable=False, server_default="0"),
            sa.Column("generations_used", sa.Integer, nullable=False, server_default="0"),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.func.now(),
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.func.now(),
            ),
            sa.UniqueConstraint("user_id", "usage_date", name="uq_user_usage_date"),
        )
        op.create_index("ix_user_usage_date", "daily_usage", ["user_id", "usage_date"])


def downgrade() -> None:
    op.drop_table("daily_usage")
    op.drop_table("user_subscriptions")
    op.execute("DROP TYPE IF EXISTS plantype")
    op.execute("DROP TYPE IF EXISTS subscriptionstatus")
    op.execute("DROP TYPE IF EXISTS storeplatform")
