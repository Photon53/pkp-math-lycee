"""seance question courante

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-27 02:42:22.024874
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = '0002'
down_revision: str | None = '0001'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table('seance', schema=None) as batch_op:
        batch_op.add_column(sa.Column('question_courante_id', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('question_servie_le', sa.DateTime(timezone=True), nullable=True))
        batch_op.create_foreign_key(batch_op.f('fk_seance_question_courante_id_question'), 'question', ['question_courante_id'], ['id'], ondelete='RESTRICT')



def downgrade() -> None:
    with op.batch_alter_table('seance', schema=None) as batch_op:
        batch_op.drop_constraint(batch_op.f('fk_seance_question_courante_id_question'), type_='foreignkey')
        batch_op.drop_column('question_servie_le')
        batch_op.drop_column('question_courante_id')

