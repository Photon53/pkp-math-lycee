"""séance ciblée sur des compétences (entrainement depuis une leçon)

Revision ID: 0010
Revises: 0009
Create Date: 2026-10-31 14:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = '0010'
down_revision: str | None = '0009'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table('seance_competence',
    sa.Column('seance_id', sa.Integer(), nullable=False),
    sa.Column('competence_id', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['competence_id'], ['competence.id'], name=op.f('fk_seance_competence_competence_id_competence'), ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['seance_id'], ['seance.id'], name=op.f('fk_seance_competence_seance_id_seance'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('seance_id', 'competence_id', name=op.f('pk_seance_competence'))
    )


def downgrade() -> None:
    op.drop_table('seance_competence')
