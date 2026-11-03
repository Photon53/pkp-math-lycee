"""questions à valeurs variables : gabarit de la question, tirage servi et tirage de chaque réponse

Revision ID: 0017
Revises: 0016
Create Date: 2026-11-02 14:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = '0017'
down_revision: str | None = '0016'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table('question', schema=None) as batch_op:
        batch_op.add_column(sa.Column('gabarit', sa.JSON(), nullable=True))
    with op.batch_alter_table('seance', schema=None) as batch_op:
        batch_op.add_column(sa.Column('tirage_courant', sa.JSON(), nullable=True))
    with op.batch_alter_table('reponse', schema=None) as batch_op:
        batch_op.add_column(sa.Column('tirage', sa.JSON(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('reponse', schema=None) as batch_op:
        batch_op.drop_column('tirage')
    with op.batch_alter_table('seance', schema=None) as batch_op:
        batch_op.drop_column('tirage_courant')
    with op.batch_alter_table('question', schema=None) as batch_op:
        batch_op.drop_column('gabarit')
