"""add flashcards and decks tables

Revision ID: add_flashcards_and_decks
Revises: add_topic_favorite
Create Date: 2025-02-04

Creates the decks and flashcards tables for the SRS feature.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.engine.reflection import Inspector

# revision identifiers, used by Alembic.
revision: str = 'add_flashcards_and_decks'
down_revision: Union[str, None] = 'add_topic_favorite'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Get connection and inspector
    conn = op.get_bind()
    inspector = Inspector.from_engine(conn)
    existing_tables = inspector.get_table_names()

    # Create decks table if it doesn't exist
    if 'decks' not in existing_tables:
        op.create_table(
            'decks',
            sa.Column('id', sa.String(36), primary_key=True),
            sa.Column('name', sa.String(200), nullable=False, index=True),
            sa.Column('description', sa.Text(), nullable=True),
            sa.Column('user_id', sa.String(36), nullable=False, index=True),
            sa.Column('topic_id', sa.String(36), nullable=True, index=True),
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
            sa.ForeignKeyConstraint(
                ['user_id'],
                ['users.id'],
                name='fk_decks_user_id',
                ondelete='CASCADE'
            ),
            sa.ForeignKeyConstraint(
                ['topic_id'],
                ['topics.id'],
                name='fk_decks_topic_id',
                ondelete='SET NULL'
            ),
        )

    # Create flashcards table if it doesn't exist
    if 'flashcards' not in existing_tables:
        op.create_table(
            'flashcards',
            sa.Column('id', sa.String(36), primary_key=True),
            sa.Column('front_content', sa.Text(), nullable=False),
            sa.Column('back_content', sa.Text(), nullable=False),
            sa.Column('deck_id', sa.String(36), nullable=False, index=True),
            sa.Column('user_id', sa.String(36), nullable=False, index=True),
            # SRS fields
            sa.Column('step', sa.Integer(), nullable=False, server_default='0'),
            sa.Column(
                'next_review_at',
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.func.now(),
                index=True
            ),
            sa.Column('interval_minutes', sa.Integer(), nullable=False, server_default='60'),
            sa.Column('ease_factor', sa.Float(), nullable=False, server_default='2.5'),
            sa.Column('review_count', sa.Integer(), nullable=False, server_default='0'),
            sa.Column('last_reviewed_at', sa.DateTime(timezone=True), nullable=True),
            # Timestamps
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
            sa.ForeignKeyConstraint(
                ['deck_id'],
                ['decks.id'],
                name='fk_flashcards_deck_id',
                ondelete='CASCADE'
            ),
            sa.ForeignKeyConstraint(
                ['user_id'],
                ['users.id'],
                name='fk_flashcards_user_id',
                ondelete='CASCADE'
            ),
        )

        # Create composite index for efficient "due cards" query
        op.create_index(
            'ix_flashcards_user_next_review',
            'flashcards',
            ['user_id', 'next_review_at']
        )


def downgrade() -> None:
    # Get connection and inspector
    conn = op.get_bind()
    inspector = Inspector.from_engine(conn)
    existing_tables = inspector.get_table_names()

    # Drop flashcards table if it exists
    if 'flashcards' in existing_tables:
        op.drop_index('ix_flashcards_user_next_review', table_name='flashcards')
        op.drop_table('flashcards')

    # Drop decks table if it exists
    if 'decks' in existing_tables:
        op.drop_table('decks')
