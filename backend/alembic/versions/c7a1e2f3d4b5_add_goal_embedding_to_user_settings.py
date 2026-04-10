"""add_goal_embedding_to_user_settings

Revision ID: c7a1e2f3d4b5
Revises: b43cd89b88f1
Create Date: 2026-04-05 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector

# revision identifiers, used by Alembic.
revision: str = 'c7a1e2f3d4b5'
down_revision: Union[str, None] = 'b43cd89b88f1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('user_settings', sa.Column('goal_embedding', Vector(768), nullable=True))


def downgrade() -> None:
    op.drop_column('user_settings', 'goal_embedding')
