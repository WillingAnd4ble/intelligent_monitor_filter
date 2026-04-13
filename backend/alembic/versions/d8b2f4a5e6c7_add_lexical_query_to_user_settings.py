"""add_lexical_query_to_user_settings

Revision ID: d8b2f4a5e6c7
Revises: c7a1e2f3d4b5
Create Date: 2026-04-12 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'd8b2f4a5e6c7'
down_revision: Union[str, None] = 'c7a1e2f3d4b5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('user_settings', sa.Column('lexical_query', sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column('user_settings', 'lexical_query')
