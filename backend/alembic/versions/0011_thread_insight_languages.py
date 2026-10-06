"""thread insight tone and Spanish summary

Revision ID: 0011
Revises: 0010
Create Date: 2026-10-06 13:00:00
"""
import sqlalchemy as sa
from alembic import op

revision = '0011'
down_revision = '0010'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('thread_insights', sa.Column('tone', sa.String(length=16), nullable=True))
    op.add_column('thread_insights', sa.Column('summary_es', sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column('thread_insights', 'summary_es')
    op.drop_column('thread_insights', 'tone')
