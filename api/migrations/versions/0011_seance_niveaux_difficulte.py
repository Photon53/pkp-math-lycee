"""séance limitée à des niveaux de difficulté (méthode PKP : je m'entraîne, je me dépasse)

Revision ID: 0011
Revises: 0010
Create Date: 2026-10-31 16:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = '0011'
down_revision: str | None = '0010'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table('seance', schema=None) as batch_op:
        batch_op.add_column(sa.Column('difficulte_min', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('difficulte_max', sa.Integer(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('seance', schema=None) as batch_op:
        batch_op.drop_column('difficulte_max')
        batch_op.drop_column('difficulte_min')
