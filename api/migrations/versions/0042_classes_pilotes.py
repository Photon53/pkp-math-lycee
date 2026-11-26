"""classes pilotes

Issue #176 — Classes pilotes autorisées dans un domaine actif mais fermé au public (Claude). Ajout seulement :
table `classe_pilote` (exception à EX.4, décision SEC-D6), aucune donnée existante modifiée.

Revision ID: 0042
Revises: 0041
Create Date: 2026-11-19 00:07:50.043008
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = '0042'
down_revision: str | None = '0041'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table('classe_pilote',
    sa.Column('classe_id', sa.Integer(), nullable=False),
    sa.Column('accordee_par_id', sa.Integer(), nullable=True),
    sa.Column('accordee_le', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
    sa.Column('motif', sa.String(length=200), nullable=False),
    sa.ForeignKeyConstraint(['accordee_par_id'], ['enseignant.id'], name=op.f('fk_classe_pilote_accordee_par_id_enseignant'), ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['classe_id'], ['classe.id'], name=op.f('fk_classe_pilote_classe_id_classe'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('classe_id', name=op.f('pk_classe_pilote'))
    )


def downgrade() -> None:
    # Retire seulement les autorisations : les classes, leurs élèves et leur travail restent.
    op.drop_table('classe_pilote')
