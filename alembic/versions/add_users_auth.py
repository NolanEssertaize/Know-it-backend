"""add users table and link topics

Revision ID: add_users_auth
Revises:
Create Date: 2025-01-09

Note: This migration adds the users table and links topics to users.
If you already have an initial migration, update the 'down_revision' below.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from sqlalchemy.engine.reflection import Inspector

# revision identifiers, used by Alembic.
revision: str = 'add_users_auth'
down_revision: Union[str, None] = None  # Update this if you have existing migrations
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Get connection and inspector
    conn = op.get_bind()
    inspector = Inspector.from_engine(conn)
    existing_tables = inspector.get_table_names()

    # Create auth_provider enum
    auth_provider_enum = postgresql.ENUM(
        'local', 'google',
        name='authprovider',
        create_type=True
    )
    auth_provider_enum.create(op.get_bind(), checkfirst=True)

    # Create users table if it doesn't exist
    if 'users' not in existing_tables:
        op.create_table(
            'users',
            sa.Column('id', sa.String(36), primary_key=True),
            sa.Column('email', sa.String(255), unique=True, nullable=False, index=True),
            sa.Column('hashed_password', sa.String(255), nullable=True),
            sa.Column('full_name', sa.String(255), nullable=True),
            sa.Column('picture_url', sa.String(500), nullable=True),
            sa.Column(
                'auth_provider',
                auth_provider_enum,
                nullable=False,
                server_default='local'
            ),
            sa.Column('google_id', sa.String(255), unique=True, nullable=True, index=True),
            sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
            sa.Column('is_verified', sa.Boolean(), nullable=False, server_default='false'),
            sa.Column(
                'created_at',
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.func.now()
            ),
            sa.Column(
                'updated_at',
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.func.now()
            ),
            sa.Column('last_login', sa.DateTime(timezone=True), nullable=True),
        )

    # Add user_id column to topics table if it exists and doesn't have the column
    if 'topics' in existing_tables:
        columns = [col['name'] for col in inspector.get_columns('topics')]
        if 'user_id' not in columns:
            op.add_column(
                'topics',
                sa.Column('user_id', sa.String(36), nullable=True)
            )

            # Create foreign key constraint
            op.create_foreign_key(
                'fk_topics_user_id',
                'topics',
                'users',
                ['user_id'],
                ['id'],
                ondelete='CASCADE'
            )

            # Create index on user_id
            op.create_index('ix_topics_user_id', 'topics', ['user_id'])


def downgrade() -> None:
    # Get connection and inspector
    conn = op.get_bind()
    inspector = Inspector.from_engine(conn)
    existing_tables = inspector.get_table_names()

    # Drop user_id from topics if it exists
    if 'topics' in existing_tables:
        columns = [col['name'] for col in inspector.get_columns('topics')]
        if 'user_id' in columns:
            op.drop_index('ix_topics_user_id', table_name='topics')
            op.drop_constraint('fk_topics_user_id', 'topics', type_='foreignkey')
            op.drop_column('topics', 'user_id')

    # Drop users table if it exists
    if 'users' in existing_tables:
        op.drop_table('users')

    # Drop enum type
    op.execute('DROP TYPE IF EXISTS authprovider')