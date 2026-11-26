"""redactions des eleves

Issue #179 — Rédaction en ligne et correction par le professeur (Claude). Ajout seulement : table `redaction`
(une ligne par version, conservée jusqu'au 31 août de l'année scolaire, décision RGPD-2).

Revision ID: 0044
Revises: 0043
Create Date: 2026-11-19 07:28:52.054832
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = '0044'
down_revision: str | None = '0043'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table('redaction',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('eleve_id', sa.Integer(), nullable=False),
    sa.Column('question_id', sa.Integer(), nullable=False),
    sa.Column('version', sa.Integer(), nullable=False),
    sa.Column('texte', sa.Text(), nullable=False),
    sa.Column('statut', sa.String(length=10), nullable=False),
    sa.Column('cree_le', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
    sa.Column('maj_le', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
    sa.Column('remise_le', sa.DateTime(timezone=True), nullable=True),
    sa.Column('commentaire', sa.Text(), nullable=True),
    sa.Column('corrigee_le', sa.DateTime(timezone=True), nullable=True),
    sa.Column('correcteur_id', sa.Integer(), nullable=True),
    sa.Column('conserver_jusqu_au', sa.Date(), nullable=False),
    sa.CheckConstraint("statut IN ('brouillon', 'remise', 'corrigee')", name=op.f('ck_redaction_statut')),
    sa.ForeignKeyConstraint(['correcteur_id'], ['enseignant.id'], name=op.f('fk_redaction_correcteur_id_enseignant'), ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['eleve_id'], ['eleve.id'], name=op.f('fk_redaction_eleve_id_eleve'), ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['question_id'], ['question.id'], name=op.f('fk_redaction_question_id_question'), ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_redaction')),
    sa.UniqueConstraint('eleve_id', 'question_id', 'version', name='uq_redaction_eleve_question_version')
    )
    with op.batch_alter_table('redaction', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_redaction_conserver_jusqu_au'), ['conserver_jusqu_au'], unique=False)
        batch_op.create_index(batch_op.f('ix_redaction_eleve_id'), ['eleve_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_redaction_question_id'), ['question_id'], unique=False)



def downgrade() -> None:
    # Supprime les rédactions des élèves : sauvegarde préalable obligatoire si la table contient des données.
    with op.batch_alter_table('redaction', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_redaction_question_id'))
        batch_op.drop_index(batch_op.f('ix_redaction_eleve_id'))
        batch_op.drop_index(batch_op.f('ix_redaction_conserver_jusqu_au'))

    op.drop_table('redaction')
