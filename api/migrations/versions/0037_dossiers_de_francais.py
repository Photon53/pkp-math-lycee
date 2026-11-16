"""dossiers de français : versions importées du dépôt, parties élève et professeur séparées, circuit de validation

Issue #98 — Intégration du premier dossier Français 3e en DEV (Claude). Tables nouvelles uniquement : aucune donnée
existante modifiée, aucun domaine activé ni ouvert au public.

Revision ID: 0037
Revises: 0036
Create Date: 2026-11-14 18:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = '0037'
down_revision: str | None = '0036'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        'dossier_francais',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('code', sa.String(length=30), nullable=False),
        sa.Column('domaine_code', sa.String(length=30), nullable=False),
        sa.Column('niveau', sa.String(length=4), nullable=False),
        sa.Column('titre', sa.String(length=200), nullable=False),
        sa.ForeignKeyConstraint(['domaine_code'], ['domaine_pedagogique.code'],
                                name=op.f('fk_dossier_francais_domaine_code_domaine_pedagogique'), ondelete='RESTRICT'),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_dossier_francais')),
        sa.UniqueConstraint('code', name=op.f('uq_dossier_francais_code')),
    )
    op.create_index(op.f('ix_dossier_francais_domaine_code'), 'dossier_francais', ['domaine_code'], unique=False)
    op.create_table(
        'dossier_francais_version',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('dossier_id', sa.Integer(), nullable=False),
        sa.Column('numero', sa.Integer(), nullable=False),
        sa.Column('eleve', sa.JSON(), nullable=False),
        sa.Column('professeur', sa.JSON(), nullable=False),
        sa.Column('meta', sa.JSON(), nullable=False),
        sa.Column('empreinte', sa.String(length=64), nullable=False),
        sa.Column('statut', sa.String(length=10), nullable=False),
        sa.Column('auteur_id', sa.Integer(), nullable=True),
        sa.Column('cree_le', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('validateur_id', sa.Integer(), nullable=True),
        sa.Column('decide_le', sa.DateTime(timezone=True), nullable=True),
        sa.Column('motif_refus', sa.Text(), nullable=True),
        sa.CheckConstraint("statut IN ('brouillon', 'soumis', 'valide', 'refuse', 'archive')",
                           name=op.f('ck_dossier_francais_version_ck_dossier_francais_version_statut')),
        sa.ForeignKeyConstraint(['dossier_id'], ['dossier_francais.id'],
                                name=op.f('fk_dossier_francais_version_dossier_id_dossier_francais'), ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['auteur_id'], ['enseignant.id'],
                                name=op.f('fk_dossier_francais_version_auteur_id_enseignant'), ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['validateur_id'], ['enseignant.id'],
                                name=op.f('fk_dossier_francais_version_validateur_id_enseignant'), ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_dossier_francais_version')),
        sa.UniqueConstraint('dossier_id', 'numero', name=op.f('uq_dossier_francais_version_numero')),
        sa.UniqueConstraint('dossier_id', 'empreinte', name=op.f('uq_dossier_francais_version_empreinte')),
    )
    op.create_index(op.f('ix_dossier_francais_version_dossier_id'), 'dossier_francais_version', ['dossier_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_dossier_francais_version_dossier_id'), table_name='dossier_francais_version')
    op.drop_table('dossier_francais_version')
    op.drop_index(op.f('ix_dossier_francais_domaine_code'), table_name='dossier_francais')
    op.drop_table('dossier_francais')
