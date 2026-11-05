"""comptes bloqués : l'administrateur suspend temporairement le compte d'un enfant (sa carte, dans toutes ses
matières) ou celui d'un parent, sans rien effacer ; le débloquer rétablit l'accès

Revision ID: 0028
Revises: 0027
Create Date: 2026-11-05 15:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = '0028'
down_revision: str | None = '0027'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    for table in ('enfant', 'parent'):
        with op.batch_alter_table(table) as batch:
            batch.add_column(sa.Column('bloque_le', sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    for table in ('enfant', 'parent'):
        with op.batch_alter_table(table) as batch:
            batch.drop_column('bloque_le')
