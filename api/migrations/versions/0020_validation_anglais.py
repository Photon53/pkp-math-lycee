"""PKP Anglais : séances versionnées et validées, codes de connexion et progression des élèves

Revision ID: 0020
Revises: 0019
Create Date: 2026-11-03 16:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = '0020'
down_revision: str | None = '0019'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table('enseignant', schema=None) as batch_op:
        batch_op.add_column(sa.Column('referent_anglais', sa.Boolean(), server_default=sa.false(), nullable=False))
    with op.batch_alter_table('eleve_anglais', schema=None) as batch_op:
        batch_op.add_column(sa.Column('identifiant', sa.String(length=40), nullable=True))
        batch_op.add_column(sa.Column('code_hash', sa.String(length=255), nullable=True))
        batch_op.create_unique_constraint('uq_eleve_anglais_identifiant', ['identifiant'])
    op.create_table(
        'seance_anglais',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('code', sa.String(length=10), nullable=False),
        sa.Column('niveau', sa.String(length=2), nullable=False),
        sa.CheckConstraint("niveau IN ('4e', '3e')", name='ck_seance_anglais_niveau'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('code', name='uq_seance_anglais_code'),
    )
    op.create_table(
        'seance_anglais_version',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('seance_id', sa.Integer(), nullable=False),
        sa.Column('numero', sa.Integer(), nullable=False),
        sa.Column('contenu', sa.JSON(), nullable=False),
        sa.Column('cahier', sa.JSON(), nullable=False),
        sa.Column('quiz', sa.JSON(), nullable=False),
        sa.Column('statut', sa.String(length=10), nullable=False),
        sa.Column('auteur_id', sa.Integer(), nullable=True),
        sa.Column('cree_le', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('validateur_id', sa.Integer(), nullable=True),
        sa.Column('decide_le', sa.DateTime(timezone=True), nullable=True),
        sa.Column('motif_refus', sa.Text(), nullable=True),
        sa.CheckConstraint(
            "statut IN ('brouillon', 'soumis', 'valide', 'refuse', 'archive')", name='ck_seance_anglais_version_statut'
        ),
        sa.ForeignKeyConstraint(['seance_id'], ['seance_anglais.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['auteur_id'], ['enseignant.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['validateur_id'], ['enseignant.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('seance_id', 'numero', name='uq_seance_anglais_version_numero'),
    )
    op.create_index('ix_seance_anglais_version_seance_id', 'seance_anglais_version', ['seance_id'])
    op.create_table(
        'progression_anglais',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('eleve_id', sa.Integer(), nullable=False),
        sa.Column('code', sa.String(length=10), nullable=False),
        sa.Column('meilleur_score', sa.Integer(), nullable=False),
        sa.Column('total', sa.Integer(), nullable=False),
        sa.Column('tentatives', sa.Integer(), nullable=False),
        sa.Column('i_can', sa.JSON(), nullable=False),
        sa.Column('maj_le', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['eleve_id'], ['eleve_anglais.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('eleve_id', 'code', name='uq_progression_anglais_eleve_code'),
    )
    op.create_index('ix_progression_anglais_eleve_id', 'progression_anglais', ['eleve_id'])


def downgrade() -> None:
    op.drop_index('ix_progression_anglais_eleve_id', table_name='progression_anglais')
    op.drop_table('progression_anglais')
    op.drop_index('ix_seance_anglais_version_seance_id', table_name='seance_anglais_version')
    op.drop_table('seance_anglais_version')
    op.drop_table('seance_anglais')
    with op.batch_alter_table('eleve_anglais', schema=None) as batch_op:
        batch_op.drop_constraint('uq_eleve_anglais_identifiant', type_='unique')
        batch_op.drop_column('code_hash')
        batch_op.drop_column('identifiant')
    with op.batch_alter_table('enseignant', schema=None) as batch_op:
        batch_op.drop_column('referent_anglais')
