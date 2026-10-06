"""score version

Records which importance criteria scored each story (stage0.SCORE_VERSION), so the worker can
re-score recent stories when the criteria change.

Revision ID: 0010
Revises: 0009
Create Date: 2026-10-06 12:00:00
"""
import sqlalchemy as sa
from alembic import op

revision = '0010'
down_revision = '0009'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('articles', sa.Column('score_version', sa.SmallInteger(), server_default='0', nullable=False))


def downgrade() -> None:
    op.drop_column('articles', 'score_version')
