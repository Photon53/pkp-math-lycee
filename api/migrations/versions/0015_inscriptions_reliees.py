"""inscriptions reliées : un même élève suivi dans plusieurs parcours, avec un seul code

Revision ID: 0015
Revises: 0014
Create Date: 2026-10-31 23:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = '0015'
down_revision: str | None = '0014'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table('eleve', schema=None) as batch_op:
        batch_op.add_column(sa.Column('groupe_id', sa.Integer(), nullable=True))
        batch_op.create_index(batch_op.f('ix_eleve_groupe_id'), ['groupe_id'], unique=False)


def downgrade() -> None:
    with op.batch_alter_table('eleve', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_eleve_groupe_id'))
        batch_op.drop_column('groupe_id')
