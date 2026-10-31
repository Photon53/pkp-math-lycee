"""contenu pédagogique structuré : attendus, méthodes, erreurs fréquentes, corrections détaillées

Revision ID: 0009
Revises: 0008
Create Date: 2026-10-31 12:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = '0009'
down_revision: str | None = '0008'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table('competence', schema=None) as batch_op:
        batch_op.add_column(sa.Column('attendus', sa.JSON(), nullable=True))
        batch_op.add_column(sa.Column('objectifs', sa.JSON(), nullable=True))
        batch_op.add_column(sa.Column('prerequis', sa.JSON(), nullable=True))
        batch_op.add_column(sa.Column('methodes', sa.JSON(), nullable=True))
        batch_op.add_column(sa.Column('erreurs_frequentes', sa.JSON(), nullable=True))

    with op.batch_alter_table('question', schema=None) as batch_op:
        batch_op.add_column(sa.Column('correction', sa.JSON(), nullable=True))
        batch_op.add_column(sa.Column('competences_secondaires', sa.JSON(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('question', schema=None) as batch_op:
        batch_op.drop_column('competences_secondaires')
        batch_op.drop_column('correction')

    with op.batch_alter_table('competence', schema=None) as batch_op:
        batch_op.drop_column('erreurs_frequentes')
        batch_op.drop_column('methodes')
        batch_op.drop_column('prerequis')
        batch_op.drop_column('objectifs')
        batch_op.drop_column('attendus')
