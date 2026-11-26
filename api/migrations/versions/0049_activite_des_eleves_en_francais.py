"""activite des eleves en francais

Issue #217 — Parcours du français au niveau de l'anglais (Claude). Quiz corrigé des dossiers (colonne `quiz` de la
version, vide pour les versions existantes), mode de correction de la classe et d'un dossier (#110), progression
(scores, premier essai, auto-évaluation), réponses au quiz par essai, réponses rédigées avec retour du professeur
(données d'élèves, règles RGPD-2 : conservation jusqu'au 31 août, suppression avec l'élève). Aucune donnée existante
n'est transformée.

Revision ID: 0049
Revises: 0048
Create Date: 2026-11-23 12:49:51.588323
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = '0049'
down_revision: str | None = '0048'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table('mode_correction_dossier_francais',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('classe_id', sa.Integer(), nullable=False),
    sa.Column('code', sa.String(length=30), nullable=False),
    sa.Column('mode', sa.String(length=25), nullable=False),
    sa.CheckConstraint("mode IN ('apres_chaque_question', 'fin_du_quiz')", name=op.f('ck_mode_correction_dossier_francais_mode')),
    sa.ForeignKeyConstraint(['classe_id'], ['classe.id'], name=op.f('fk_mode_correction_dossier_francais_classe_id_classe'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_mode_correction_dossier_francais')),
    sa.UniqueConstraint('classe_id', 'code', name='uq_mode_correction_dossier_francais_classe_code')
    )
    with op.batch_alter_table('mode_correction_dossier_francais', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_mode_correction_dossier_francais_classe_id'), ['classe_id'], unique=False)

    op.create_table('progression_francais',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('eleve_id', sa.Integer(), nullable=False),
    sa.Column('code', sa.String(length=30), nullable=False),
    sa.Column('meilleur_score', sa.Integer(), nullable=False),
    sa.Column('total', sa.Integer(), nullable=False),
    sa.Column('tentatives', sa.Integer(), nullable=False),
    sa.Column('premier_score', sa.Integer(), nullable=True),
    sa.Column('auto_evaluation', sa.JSON(), nullable=False),
    sa.Column('maj_le', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['eleve_id'], ['eleve.id'], name=op.f('fk_progression_francais_eleve_id_eleve'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_progression_francais')),
    sa.UniqueConstraint('eleve_id', 'code', name='uq_progression_francais_eleve_code')
    )
    with op.batch_alter_table('progression_francais', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_progression_francais_eleve_id'), ['eleve_id'], unique=False)

    op.create_table('reponse_quiz_francais',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('eleve_id', sa.Integer(), nullable=False),
    sa.Column('code', sa.String(length=30), nullable=False),
    sa.Column('essai', sa.Integer(), nullable=False),
    sa.Column('question', sa.Integer(), nullable=False),
    sa.Column('choix', sa.Integer(), nullable=False),
    sa.Column('juste', sa.Boolean(), nullable=False),
    sa.Column('repondu_le', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['eleve_id'], ['eleve.id'], name=op.f('fk_reponse_quiz_francais_eleve_id_eleve'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_reponse_quiz_francais')),
    sa.UniqueConstraint('eleve_id', 'code', 'essai', 'question', name='uq_reponse_quiz_francais_eleve_code_essai_question')
    )
    with op.batch_alter_table('reponse_quiz_francais', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_reponse_quiz_francais_eleve_id'), ['eleve_id'], unique=False)

    op.create_table('reponse_redigee_francais',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('eleve_id', sa.Integer(), nullable=False),
    sa.Column('code', sa.String(length=30), nullable=False),
    sa.Column('question', sa.String(length=10), nullable=False),
    sa.Column('texte', sa.Text(), nullable=False),
    sa.Column('statut', sa.String(length=10), nullable=False),
    sa.Column('maj_le', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
    sa.Column('remise_le', sa.DateTime(timezone=True), nullable=True),
    sa.Column('commentaire', sa.Text(), nullable=True),
    sa.Column('corrigee_le', sa.DateTime(timezone=True), nullable=True),
    sa.Column('correcteur_id', sa.Integer(), nullable=True),
    sa.Column('conserver_jusqu_au', sa.Date(), nullable=False),
    sa.CheckConstraint("statut IN ('brouillon', 'remise', 'corrigee')", name=op.f('ck_reponse_redigee_francais_statut')),
    sa.ForeignKeyConstraint(['correcteur_id'], ['enseignant.id'], name=op.f('fk_reponse_redigee_francais_correcteur_id_enseignant'), ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['eleve_id'], ['eleve.id'], name=op.f('fk_reponse_redigee_francais_eleve_id_eleve'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_reponse_redigee_francais')),
    sa.UniqueConstraint('eleve_id', 'code', 'question', name='uq_reponse_redigee_francais_eleve_code_question')
    )
    with op.batch_alter_table('reponse_redigee_francais', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_reponse_redigee_francais_conserver_jusqu_au'), ['conserver_jusqu_au'], unique=False)
        batch_op.create_index(batch_op.f('ix_reponse_redigee_francais_eleve_id'), ['eleve_id'], unique=False)

    with op.batch_alter_table('classe', schema=None) as batch_op:
        batch_op.add_column(sa.Column('mode_correction', sa.String(length=25), server_default='apres_chaque_question', nullable=False))
        batch_op.create_check_constraint(
            op.f('ck_classe_mode_correction'), "mode_correction IN ('apres_chaque_question', 'fin_du_quiz')"
        )

    with op.batch_alter_table('dossier_francais_version', schema=None) as batch_op:
        batch_op.add_column(sa.Column('quiz', sa.JSON(), server_default='[]', nullable=False))



def downgrade() -> None:
    with op.batch_alter_table('dossier_francais_version', schema=None) as batch_op:
        batch_op.drop_column('quiz')

    with op.batch_alter_table('classe', schema=None) as batch_op:
        batch_op.drop_constraint(op.f('ck_classe_mode_correction'), type_='check')
        batch_op.drop_column('mode_correction')

    with op.batch_alter_table('reponse_redigee_francais', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_reponse_redigee_francais_eleve_id'))
        batch_op.drop_index(batch_op.f('ix_reponse_redigee_francais_conserver_jusqu_au'))

    op.drop_table('reponse_redigee_francais')
    with op.batch_alter_table('reponse_quiz_francais', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_reponse_quiz_francais_eleve_id'))

    op.drop_table('reponse_quiz_francais')
    with op.batch_alter_table('progression_francais', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_progression_francais_eleve_id'))

    op.drop_table('progression_francais')
    with op.batch_alter_table('mode_correction_dossier_francais', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_mode_correction_dossier_francais_classe_id'))

    op.drop_table('mode_correction_dossier_francais')
