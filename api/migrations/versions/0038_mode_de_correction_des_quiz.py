"""mode de correction des quiz : réglage par groupe et par séance, réponses par question, score du premier essai

Issue #110 — Mode de correction choisi par le professeur (Claude). Les groupes existants reçoivent le mode par
défaut (après chaque question) ; le score du premier essai des progressions existantes reste inconnu (NULL).
Aucune donnée existante supprimée.

Revision ID: 0038
Revises: 0037
Create Date: 2026-11-14 21:27:56.490706
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = '0038'
down_revision: str | None = '0037'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

MODES = "('apres_chaque_question', 'fin_du_quiz')"


def upgrade() -> None:
    op.create_table(
        'mode_correction_seance_anglais',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('groupe_id', sa.Integer(), nullable=False),
        sa.Column('code', sa.String(length=10), nullable=False),
        sa.Column('mode', sa.String(length=25), nullable=False),
        sa.CheckConstraint(f"mode IN {MODES}", name=op.f('ck_mode_correction_seance_anglais_mode')),
        sa.ForeignKeyConstraint(['groupe_id'], ['groupe_anglais.id'],
                                name=op.f('fk_mode_correction_seance_anglais_groupe_id_groupe_anglais'), ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_mode_correction_seance_anglais')),
        sa.UniqueConstraint('groupe_id', 'code', name='uq_mode_correction_seance_anglais_groupe_code'),
    )
    op.create_index(op.f('ix_mode_correction_seance_anglais_groupe_id'), 'mode_correction_seance_anglais', ['groupe_id'], unique=False)

    op.create_table(
        'reponse_anglais',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('eleve_id', sa.Integer(), nullable=False),
        sa.Column('code', sa.String(length=10), nullable=False),
        sa.Column('essai', sa.Integer(), nullable=False),
        sa.Column('question', sa.Integer(), nullable=False),
        sa.Column('choix', sa.Integer(), nullable=False),
        sa.Column('juste', sa.Boolean(), nullable=False),
        sa.Column('repondu_le', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['eleve_id'], ['eleve_anglais.id'],
                                name=op.f('fk_reponse_anglais_eleve_id_eleve_anglais'), ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_reponse_anglais')),
        sa.UniqueConstraint('eleve_id', 'code', 'essai', 'question', name='uq_reponse_anglais_eleve_code_essai_question'),
    )
    op.create_index(op.f('ix_reponse_anglais_eleve_id'), 'reponse_anglais', ['eleve_id'], unique=False)

    with op.batch_alter_table('groupe_anglais', schema=None) as batch_op:
        batch_op.add_column(sa.Column('mode_correction', sa.String(length=25), server_default='apres_chaque_question', nullable=False))
        batch_op.create_check_constraint(op.f('ck_groupe_anglais_mode_correction'), f"mode_correction IN {MODES}")

    with op.batch_alter_table('progression_anglais', schema=None) as batch_op:
        batch_op.add_column(sa.Column('premier_score', sa.Integer(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('progression_anglais', schema=None) as batch_op:
        batch_op.drop_column('premier_score')

    with op.batch_alter_table('groupe_anglais', schema=None) as batch_op:
        batch_op.drop_constraint(op.f('ck_groupe_anglais_mode_correction'), type_='check')
        batch_op.drop_column('mode_correction')

    op.drop_index(op.f('ix_reponse_anglais_eleve_id'), table_name='reponse_anglais')
    op.drop_table('reponse_anglais')
    op.drop_index(op.f('ix_mode_correction_seance_anglais_groupe_id'), table_name='mode_correction_seance_anglais')
    op.drop_table('mode_correction_seance_anglais')
