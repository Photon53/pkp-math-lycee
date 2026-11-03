"""Forme d'écriture exigée par une question (développée, factorisée, réduite)

Revision ID: 0021
Revises: 0020
Create Date: 2026-11-03 18:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = '0021'
down_revision: str | None = '0020'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table('question', schema=None) as batch_op:
        batch_op.add_column(sa.Column('forme', sa.Enum('developpee', 'factorisee', 'reduite', name='forme', native_enum=False, create_constraint=True), nullable=True))


def downgrade() -> None:
    # Retirer le CHECK avant la colonne (voir 0006).
    with op.batch_alter_table('question', schema=None) as batch_op:
        batch_op.drop_constraint(op.f('ck_question_forme'), type_='check')
        batch_op.drop_column('forme')
