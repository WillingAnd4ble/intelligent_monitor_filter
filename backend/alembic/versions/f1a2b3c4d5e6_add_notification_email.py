"""add notification_email to user_settings

Revision ID: f1a2b3c4d5e6
Revises: e9c3f5a7b8d1
Create Date: 2026-04-13 14:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 'f1a2b3c4d5e6'
down_revision: Union[str, None] = 'e9c3f5a7b8d1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('user_settings', sa.Column('notification_email', sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column('user_settings', 'notification_email')
