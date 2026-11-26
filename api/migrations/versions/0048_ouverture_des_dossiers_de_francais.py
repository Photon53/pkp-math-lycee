"""ouverture des dossiers de français

Issue #212 — Circuit du français aligné sur l'anglais (Claude). Table `ouverture_dossier_francais` : dossier de
français ouvert par le professeur à l'une de ses classes ; seule la version validée est servie aux élèves, et
seulement aux classes qui ont accès au domaine (SEC-D6). Aucune donnée personnelle.

Revision ID: 0048
Revises: 0047
Create Date: 2026-11-21 01:41:06.115118
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = '0048'
down_revision: str | None = '0047'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table('ouverture_dossier_francais',
    sa.Column('classe_id', sa.Integer(), nullable=False),
    sa.Column('dossier_id', sa.Integer(), nullable=False),
    sa.Column('ouvert_par_id', sa.Integer(), nullable=True),
    sa.Column('ouvert_le', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
    sa.ForeignKeyConstraint(['classe_id'], ['classe.id'], name=op.f('fk_ouverture_dossier_francais_classe_id_classe'), ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['dossier_id'], ['dossier_francais.id'], name=op.f('fk_ouverture_dossier_francais_dossier_id_dossier_francais'), ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['ouvert_par_id'], ['enseignant.id'], name=op.f('fk_ouverture_dossier_francais_ouvert_par_id_enseignant'), ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('classe_id', 'dossier_id', name=op.f('pk_ouverture_dossier_francais'))
    )
    with op.batch_alter_table('ouverture_dossier_francais', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_ouverture_dossier_francais_dossier_id'), ['dossier_id'], unique=False)



def downgrade() -> None:
    with op.batch_alter_table('ouverture_dossier_francais', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_ouverture_dossier_francais_dossier_id'))

    op.drop_table('ouverture_dossier_francais')
