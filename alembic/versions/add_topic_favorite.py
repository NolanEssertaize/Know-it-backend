"""add is_favorite column to topics

Revision ID: add_topic_favorite
Revises: add_users_auth
Create Date: 2025-02-03

Adds the is_favorite boolean column to topics table.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.engine.reflection import Inspector

# revision identifiers, used by Alembic.
revision: str = 'add_topic_favorite'
down_revision: Union[str, None] = 'add_users_auth'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Get connection and inspector
    conn = op.get_bind()
    inspector = Inspector.from_engine(conn)
    existing_tables = inspector.get_table_names()

    if 'topics' in existing_tables:
        columns = [col['name'] for col in inspector.get_columns('topics')]
        if 'is_favorite' not in columns:
            op.add_column(
                'topics',
                sa.Column('is_favorite', sa.Boolean(), nullable=False, server_default='false')
            )
            # Create index for efficient filtering by favorite status
            op.create_index('ix_topics_is_favorite', 'topics', ['is_favorite'])


def downgrade() -> None:
    # Get connection and inspector
    conn = op.get_bind()
    inspector = Inspector.from_engine(conn)
    existing_tables = inspector.get_table_names()

    if 'topics' in existing_tables:
        columns = [col['name'] for col in inspector.get_columns('topics')]
        if 'is_favorite' in columns:
            op.drop_index('ix_topics_is_favorite', table_name='topics')
            op.drop_column('topics', 'is_favorite')
