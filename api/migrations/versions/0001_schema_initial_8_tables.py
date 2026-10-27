"""schema initial 8 tables

Revision ID: 0001
Revises: 
Create Date: 2026-10-27 02:34:25.643623
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = '0001'
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table('chapitre',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('niveau', sa.Enum('2nde', '1re', 'Tle', name='niveau', native_enum=False, create_constraint=True), nullable=False),
    sa.Column('titre', sa.String(length=200), nullable=False),
    sa.Column('ordre', sa.Integer(), nullable=False),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_chapitre')),
    sa.UniqueConstraint('niveau', 'ordre', name='uq_chapitre_niveau_ordre')
    )
    op.create_table('enseignant',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('nom', sa.String(length=100), nullable=False),
    sa.Column('email', sa.String(length=254), nullable=False),
    sa.Column('mot_de_passe_hash', sa.String(length=255), nullable=False),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_enseignant')),
    sa.UniqueConstraint('email', name=op.f('uq_enseignant_email'))
    )
    op.create_table('classe',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('code', sa.String(length=20), nullable=False),
    sa.Column('niveau', sa.Enum('2nde', '1re', 'Tle', name='niveau', native_enum=False, create_constraint=True), nullable=False),
    sa.Column('enseignant_id', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['enseignant_id'], ['enseignant.id'], name=op.f('fk_classe_enseignant_id_enseignant'), ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_classe')),
    sa.UniqueConstraint('code', name=op.f('uq_classe_code'))
    )
    with op.batch_alter_table('classe', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_classe_enseignant_id'), ['enseignant_id'], unique=False)

    op.create_table('competence',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('chapitre_id', sa.Integer(), nullable=False),
    sa.Column('code', sa.String(length=30), nullable=False),
    sa.Column('libelle', sa.String(length=200), nullable=False),
    sa.ForeignKeyConstraint(['chapitre_id'], ['chapitre.id'], name=op.f('fk_competence_chapitre_id_chapitre'), ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_competence')),
    sa.UniqueConstraint('code', name=op.f('uq_competence_code'))
    )
    with op.batch_alter_table('competence', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_competence_chapitre_id'), ['chapitre_id'], unique=False)

    op.create_table('eleve',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('prenom', sa.String(length=50), nullable=False),
    sa.Column('classe_id', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['classe_id'], ['classe.id'], name=op.f('fk_eleve_classe_id_classe'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_eleve')),
    sa.UniqueConstraint('prenom', 'classe_id', name='uq_eleve_prenom_classe')
    )
    with op.batch_alter_table('eleve', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_eleve_classe_id'), ['classe_id'], unique=False)

    op.create_table('question',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('competence_id', sa.Integer(), nullable=False),
    sa.Column('enonce', sa.Text(), nullable=False),
    sa.Column('type', sa.Enum('qcm', 'numerique', 'expression', name='type_question', native_enum=False, create_constraint=True), nullable=False),
    sa.Column('solution', sa.String(length=200), nullable=False),
    sa.Column('difficulte', sa.Integer(), nullable=False),
    sa.Column('archivee', sa.Boolean(), server_default=sa.false(), nullable=False),
    sa.Column('cree_le', sa.DateTime(timezone=True), nullable=False),
    sa.CheckConstraint('difficulte BETWEEN 1 AND 5', name=op.f('ck_question_difficulte_1_a_5')),
    sa.ForeignKeyConstraint(['competence_id'], ['competence.id'], name=op.f('fk_question_competence_id_competence'), ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_question'))
    )
    with op.batch_alter_table('question', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_question_competence_id'), ['competence_id'], unique=False)

    op.create_table('seance',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('eleve_id', sa.Integer(), nullable=False),
    sa.Column('debut', sa.DateTime(timezone=True), nullable=False),
    sa.Column('fin', sa.DateTime(timezone=True), nullable=True),
    sa.ForeignKeyConstraint(['eleve_id'], ['eleve.id'], name=op.f('fk_seance_eleve_id_eleve'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_seance'))
    )
    with op.batch_alter_table('seance', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_seance_eleve_id'), ['eleve_id'], unique=False)

    op.create_table('reponse',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('seance_id', sa.Integer(), nullable=False),
    sa.Column('question_id', sa.Integer(), nullable=False),
    sa.Column('reponse_donnee', sa.String(length=200), nullable=False),
    sa.Column('correcte', sa.Boolean(), nullable=False),
    sa.Column('duree_s', sa.Float(), nullable=False),
    sa.Column('repondu_le', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['question_id'], ['question.id'], name=op.f('fk_reponse_question_id_question'), ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['seance_id'], ['seance.id'], name=op.f('fk_reponse_seance_id_seance'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_reponse'))
    )
    with op.batch_alter_table('reponse', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_reponse_question_id'), ['question_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_reponse_seance_id'), ['seance_id'], unique=False)



def downgrade() -> None:
    with op.batch_alter_table('reponse', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_reponse_seance_id'))
        batch_op.drop_index(batch_op.f('ix_reponse_question_id'))

    op.drop_table('reponse')
    with op.batch_alter_table('seance', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_seance_eleve_id'))

    op.drop_table('seance')
    with op.batch_alter_table('question', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_question_competence_id'))

    op.drop_table('question')
    with op.batch_alter_table('eleve', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_eleve_classe_id'))

    op.drop_table('eleve')
    with op.batch_alter_table('competence', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_competence_chapitre_id'))

    op.drop_table('competence')
    with op.batch_alter_table('classe', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_classe_enseignant_id'))

    op.drop_table('classe')
    op.drop_table('enseignant')
    op.drop_table('chapitre')
