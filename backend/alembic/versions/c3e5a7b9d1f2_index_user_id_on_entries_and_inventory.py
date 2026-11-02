"""index user_id on entries and inventory

Postgres does not index foreign-key columns automatically, so per-user
lookups on these tables were sequential scans. entries gets a composite
index since its queries filter by user and order by created_at.

Revision ID: c3e5a7b9d1f2
Revises: b2d4f6a8c0e1
Create Date: 2026-11-02 14:00:00.000000

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'c3e5a7b9d1f2'
down_revision: Union[str, Sequence[str], None] = 'b2d4f6a8c0e1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_index('ix_entries_user_id_created_at', 'entries', ['user_id', 'created_at'], unique=False)
    op.create_index('ix_inventory_user_id', 'inventory', ['user_id'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('ix_inventory_user_id', table_name='inventory')
    op.drop_index('ix_entries_user_id_created_at', table_name='entries')
