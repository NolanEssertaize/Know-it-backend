"""Add password_reset_codes table

Revision ID: add_password_reset_codes
Revises: fix_picture_url_len
Create Date: 2026-02-12
"""
from typing import Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.engine.reflection import Inspector

# revision identifiers
revision: str = "add_password_reset_codes"
down_revision: Union[str, None] = "fix_picture_url_len"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = Inspector.from_engine(conn)
    existing_tables = inspector.get_table_names()

    if "password_reset_codes" not in existing_tables:
        op.create_table(
            "password_reset_codes",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column(
                "user_id",
                sa.String(36),
                sa.ForeignKey("users.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("email", sa.String(255), nullable=False),
            sa.Column("code", sa.String(6), nullable=False),
            sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("max_attempts", sa.Integer(), nullable=False, server_default="5"),
            sa.Column("is_used", sa.Boolean(), nullable=False, server_default="false"),
            sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.func.now(),
            ),
            sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        )

        op.create_index(
            "ix_password_reset_codes_user_id",
            "password_reset_codes",
            ["user_id"],
        )
        op.create_index(
            "ix_password_reset_codes_email",
            "password_reset_codes",
            ["email"],
        )


def downgrade() -> None:
    op.drop_index("ix_password_reset_codes_email", table_name="password_reset_codes")
    op.drop_index("ix_password_reset_codes_user_id", table_name="password_reset_codes")
    op.drop_table("password_reset_codes")
