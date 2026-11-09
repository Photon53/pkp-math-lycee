"""demandes d'aide : « J'ai compris » / « Je n'ai pas compris » sur un cours, un exercice ou sa correction, suivies
par le professeur pendant la séance (ticket #28)

Revision ID: 0034
Revises: 0033
Create Date: 2026-11-09 10:00:00.000000

Table nouvelle uniquement : aucune donnée existante n'est modifiée.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = '0034'
down_revision: str | None = '0033'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        'demande_aide',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('eleve_id', sa.Integer(), nullable=False),
        sa.Column('competence_id', sa.Integer(), nullable=False),
        sa.Column('question_id', sa.Integer(), nullable=True),
        sa.Column('seance_id', sa.Integer(), nullable=True),
        sa.Column('objet', sa.String(length=10), nullable=False),
        sa.Column('statut', sa.String(length=20), nullable=False),
        sa.Column('cree_le', sa.DateTime(timezone=True), nullable=False),
        sa.Column('traitee_le', sa.DateTime(timezone=True), nullable=True),
        sa.Column('traitee_par_id', sa.Integer(), nullable=True),
        sa.CheckConstraint("objet IN ('cours', 'exercice', 'corrige')", name=op.f('ck_demande_aide_objet')),
        sa.CheckConstraint(
            "statut IN ('compris', 'ouverte', 'prise-en-charge', 'resolue')", name=op.f('ck_demande_aide_statut')
        ),
        sa.ForeignKeyConstraint(['eleve_id'], ['eleve.id'], name=op.f('fk_demande_aide_eleve_id_eleve'), ondelete='CASCADE'),
        sa.ForeignKeyConstraint(
            ['competence_id'], ['competence.id'], name=op.f('fk_demande_aide_competence_id_competence'), ondelete='CASCADE'
        ),
        sa.ForeignKeyConstraint(
            ['question_id'], ['question.id'], name=op.f('fk_demande_aide_question_id_question'), ondelete='CASCADE'
        ),
        sa.ForeignKeyConstraint(['seance_id'], ['seance.id'], name=op.f('fk_demande_aide_seance_id_seance'), ondelete='SET NULL'),
        sa.ForeignKeyConstraint(
            ['traitee_par_id'], ['enseignant.id'], name=op.f('fk_demande_aide_traitee_par_id_enseignant'), ondelete='SET NULL'
        ),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_demande_aide')),
    )
    op.create_index('ix_demande_aide_eleve_id', 'demande_aide', ['eleve_id'])
    op.create_index('ix_demande_aide_competence_id', 'demande_aide', ['competence_id'])
    op.create_index('ix_demande_aide_cree_le', 'demande_aide', ['cree_le'])


def downgrade() -> None:
    op.drop_table('demande_aide')
