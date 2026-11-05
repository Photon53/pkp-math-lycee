"""archivage des classes et des groupes : une classe ou un groupe archivé sort des listes actives et n'ouvre
plus de séance, mais garde ses inscriptions, séances et réponses ; rien n'est archivé à la migration (V3, Lot 3)

Revision ID: 0031
Revises: 0030
Create Date: 2026-11-06 09:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = '0031'
down_revision: str | None = '0030'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABLES = ('classe', 'groupe_anglais')


def upgrade() -> None:
    for table in TABLES:
        with op.batch_alter_table(table) as batch:
            batch.add_column(sa.Column('archivee_le', sa.DateTime(timezone=True), nullable=True))
            batch.add_column(sa.Column('archivee_par', sa.String(length=80), nullable=True))
            batch.add_column(sa.Column('motif_archivage', sa.String(length=200), nullable=True))
            batch.create_index(f'ix_{table}_archivee_le', ['archivee_le'])


def downgrade() -> None:
    for table in TABLES:
        with op.batch_alter_table(table) as batch:
            batch.drop_index(f'ix_{table}_archivee_le')
            batch.drop_column('motif_archivage')
            batch.drop_column('archivee_par')
            batch.drop_column('archivee_le')
