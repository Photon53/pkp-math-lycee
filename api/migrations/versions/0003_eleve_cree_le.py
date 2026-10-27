"""eleve cree le

Revision ID: 0003
Revises: 0002
Create Date: 2026-10-27 03:42:18.624336
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = '0003'
down_revision: str | None = '0002'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Les élèves existants reçoivent la date de la migration : leur durée de
    # conservation démarre à ce moment-là.
    with op.batch_alter_table('eleve', schema=None) as batch_op:
        batch_op.add_column(sa.Column('cree_le', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False))



def downgrade() -> None:
    with op.batch_alter_table('eleve', schema=None) as batch_op:
        batch_op.drop_column('cree_le')

