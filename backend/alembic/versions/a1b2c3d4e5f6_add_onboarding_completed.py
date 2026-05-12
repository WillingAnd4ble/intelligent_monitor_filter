"""add onboarding_completed to user_settings

Revision ID: a1b2c3d4e5f6
Revises: f1a2b3c4d5e6
Create Date: 2026-05-12 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, None] = 'f1a2b3c4d5e6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'user_settings',
        sa.Column('onboarding_completed', sa.Boolean(), nullable=False, server_default='false'),
    )
    # Backfill: any user with at least one accepted/rejected UserPaper has already onboarded.
    op.execute("""
        UPDATE user_settings
        SET onboarding_completed = TRUE
        WHERE user_id IN (
            SELECT DISTINCT user_id FROM user_papers
            WHERE status IN ('accepted', 'rejected')
        )
    """)


def downgrade() -> None:
    op.drop_column('user_settings', 'onboarding_completed')
