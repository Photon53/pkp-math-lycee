"""nom du responsable légal : le compte parent porte le nom et le prénom du tuteur légal, facultatifs ; les
comptes existants restent vides (V3, Lot 1)

Revision ID: 0030
Revises: 0029
Create Date: 2026-11-05 20:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = '0030'
down_revision: str | None = '0029'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table('parent') as batch:
        batch.add_column(sa.Column('nom', sa.String(length=50), server_default='', nullable=False))
        batch.add_column(sa.Column('prenom', sa.String(length=50), server_default='', nullable=False))


def downgrade() -> None:
    with op.batch_alter_table('parent') as batch:
        batch.drop_column('prenom')
        batch.drop_column('nom')
