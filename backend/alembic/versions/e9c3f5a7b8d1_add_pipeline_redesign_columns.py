"""add pipeline redesign columns (deep_scan_limit, extracted_markdown, is_top_pick)

Revision ID: e9c3f5a7b8d1
Revises: d8b2f4a5e6c7
Create Date: 2026-04-13 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'e9c3f5a7b8d1'
down_revision: Union[str, None] = 'd8b2f4a5e6c7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('user_settings', sa.Column('deep_scan_limit', sa.Integer(), nullable=True, server_default='10'))
    op.add_column('user_papers', sa.Column('extracted_markdown', sa.Text(), nullable=True))
    op.add_column('user_papers', sa.Column('is_top_pick', sa.Boolean(), nullable=True, server_default='false'))


def downgrade() -> None:
    op.drop_column('user_papers', 'is_top_pick')
    op.drop_column('user_papers', 'extracted_markdown')
    op.drop_column('user_settings', 'deep_scan_limit')
