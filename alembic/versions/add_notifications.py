"""Add push notification tables

Revision ID: add_notifications
Revises: add_password_reset_codes
Create Date: 2026-02-12
"""
from typing import Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from sqlalchemy.engine.reflection import Inspector

# revision identifiers
revision: str = "add_notifications"
down_revision: Union[str, None] = "add_password_reset_codes"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = Inspector.from_engine(conn)
    existing_tables = inspector.get_table_names()

    # ── Enums ─────────────────────────────────────────────────────────
    device_platform_enum = postgresql.ENUM(
        "ios", "android",
        name="deviceplatform",
        create_type=True,
    )
    device_platform_enum.create(op.get_bind(), checkfirst=True)

    notification_type_enum = postgresql.ENUM(
        "evening_practice", "morning_flashcards",
        name="notificationtype",
        create_type=True,
    )
    notification_type_enum.create(op.get_bind(), checkfirst=True)

    notification_status_enum = postgresql.ENUM(
        "sent", "failed",
        name="notificationstatus",
        create_type=True,
    )
    notification_status_enum.create(op.get_bind(), checkfirst=True)

    # ── user_push_tokens ──────────────────────────────────────────────
    if "user_push_tokens" not in existing_tables:
        op.create_table(
            "user_push_tokens",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column(
                "user_id",
                sa.String(36),
                sa.ForeignKey("users.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("token", sa.String(255), unique=True, nullable=False),
            sa.Column(
                "platform",
                device_platform_enum,
                nullable=False,
            ),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
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
        op.create_index(
            "ix_user_push_tokens_user_id",
            "user_push_tokens",
            ["user_id"],
        )

    # ── user_notification_settings ────────────────────────────────────
    if "user_notification_settings" not in existing_tables:
        op.create_table(
            "user_notification_settings",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column(
                "user_id",
                sa.String(36),
                sa.ForeignKey("users.id", ondelete="CASCADE"),
                unique=True,
                nullable=False,
            ),
            sa.Column(
                "timezone",
                sa.String(64),
                nullable=False,
                server_default="UTC",
            ),
            sa.Column(
                "evening_reminder_enabled",
                sa.Boolean(),
                nullable=False,
                server_default="true",
            ),
            sa.Column(
                "morning_flashcard_enabled",
                sa.Boolean(),
                nullable=False,
                server_default="true",
            ),
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
        op.create_index(
            "ix_user_notification_settings_user_id",
            "user_notification_settings",
            ["user_id"],
        )

    # ── notification_logs ─────────────────────────────────────────────
    if "notification_logs" not in existing_tables:
        op.create_table(
            "notification_logs",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column(
                "user_id",
                sa.String(36),
                sa.ForeignKey("users.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column(
                "notification_type",
                notification_type_enum,
                nullable=False,
            ),
            sa.Column(
                "status",
                notification_status_enum,
                nullable=False,
            ),
            sa.Column("error_message", sa.Text(), nullable=True),
            sa.Column(
                "sent_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.func.now(),
            ),
        )
        op.create_index(
            "ix_notification_logs_user_type_sent",
            "notification_logs",
            ["user_id", "notification_type", "sent_at"],
        )


def downgrade() -> None:
    op.drop_index("ix_notification_logs_user_type_sent", table_name="notification_logs")
    op.drop_table("notification_logs")

    op.drop_index("ix_user_notification_settings_user_id", table_name="user_notification_settings")
    op.drop_table("user_notification_settings")

    op.drop_index("ix_user_push_tokens_user_id", table_name="user_push_tokens")
    op.drop_table("user_push_tokens")

    op.execute("DROP TYPE IF EXISTS notificationstatus")
    op.execute("DROP TYPE IF EXISTS notificationtype")
    op.execute("DROP TYPE IF EXISTS deviceplatform")
