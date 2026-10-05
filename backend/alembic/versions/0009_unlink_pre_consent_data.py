"""unlink data collected before consent

Until now every browser got an anonymous user on its first visit. From here on that only happens
after the reader agrees to personalisation, so the existing users are removed: their events are
kept as anonymous counts (user_id set to NULL) and their ratings and interests go with them.

Revision ID: 0009
Revises: 0008
Create Date: 2026-10-05 19:00:00
"""
from alembic import op

revision = '0009'
down_revision = '0008'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("UPDATE events SET user_id = NULL WHERE user_id IS NOT NULL")
    op.execute("DELETE FROM users WHERE email IS NULL")


def downgrade() -> None:
    pass  # deleted data cannot be restored
