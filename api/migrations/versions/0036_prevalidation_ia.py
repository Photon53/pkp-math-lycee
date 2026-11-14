"""prévalidation IA des exercices, réservée aux administrateurs : compte de service, demandes et rapports (ticket #48)

Revision ID: 0036
Revises: 0035
Create Date: 2026-11-10 10:00:00.000000

Tables nouvelles uniquement : aucune donnée existante n'est modifiée (la validation humaine n'est pas touchée).
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = '0036'
down_revision: str | None = '0035'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        'compte_service_ia',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('nom', sa.String(length=80), nullable=False),
        sa.Column('empreinte', sa.String(length=64), nullable=False),
        sa.Column('prefixe', sa.String(length=24), nullable=False),
        sa.Column('cree_le', sa.DateTime(timezone=True), nullable=False),
        sa.Column('cree_par_id', sa.Integer(), nullable=True),
        sa.Column('expire_le', sa.DateTime(timezone=True), nullable=False),
        sa.Column('revoque_le', sa.DateTime(timezone=True), nullable=True),
        sa.Column('revoque_par_id', sa.Integer(), nullable=True),
        sa.Column('dernier_usage_le', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ['cree_par_id'], ['enseignant.id'], name=op.f('fk_compte_service_ia_cree_par_id_enseignant'), ondelete='SET NULL'
        ),
        sa.ForeignKeyConstraint(
            ['revoque_par_id'], ['enseignant.id'], name=op.f('fk_compte_service_ia_revoque_par_id_enseignant'), ondelete='SET NULL'
        ),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_compte_service_ia')),
        sa.UniqueConstraint('empreinte', name=op.f('uq_compte_service_ia_empreinte')),
    )
    op.create_table(
        'prevalidation_ia',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('question_id', sa.Integer(), nullable=False),
        sa.Column('lot', sa.String(length=24), nullable=False),
        sa.Column('version', sa.String(length=64), nullable=False),
        sa.Column('tirage', sa.JSON(), nullable=True),
        sa.Column('statut', sa.String(length=12), nullable=False),
        sa.Column('resultat', sa.String(length=20), nullable=True),
        sa.Column('demandee_par_id', sa.Integer(), nullable=True),
        sa.Column('demandee_par_nom', sa.String(length=100), nullable=False),
        sa.Column('demandee_le', sa.DateTime(timezone=True), nullable=False),
        sa.Column('compte_service_id', sa.Integer(), nullable=True),
        sa.Column('enonce_lu_le', sa.DateTime(timezone=True), nullable=True),
        sa.Column('corrige_lu_le', sa.DateTime(timezone=True), nullable=True),
        sa.Column('rendue_le', sa.DateTime(timezone=True), nullable=True),
        sa.Column('modele', sa.String(length=100), nullable=True),
        sa.Column('version_modele', sa.String(length=100), nullable=True),
        sa.Column('rapport', sa.JSON(), nullable=True),
        sa.Column('verite_humaine', sa.String(length=10), nullable=True),
        sa.Column('verite_commentaire', sa.String(length=1000), nullable=True),
        sa.Column('verite_par_nom', sa.String(length=100), nullable=True),
        sa.Column('verite_le', sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("statut IN ('en-attente', 'terminee', 'annulee')", name=op.f('ck_prevalidation_ia_statut')),
        sa.CheckConstraint(
            "resultat IS NULL OR resultat IN ('aucune-anomalie', 'a-revoir', 'erreur-detectee', 'incertain')",
            name=op.f('ck_prevalidation_ia_resultat'),
        ),
        sa.CheckConstraint(
            "verite_humaine IS NULL OR verite_humaine IN ('erronee', 'correcte')", name=op.f('ck_prevalidation_ia_verite_humaine')
        ),
        sa.ForeignKeyConstraint(
            ['question_id'], ['question.id'], name=op.f('fk_prevalidation_ia_question_id_question'), ondelete='CASCADE'
        ),
        sa.ForeignKeyConstraint(
            ['demandee_par_id'], ['enseignant.id'], name=op.f('fk_prevalidation_ia_demandee_par_id_enseignant'), ondelete='SET NULL'
        ),
        sa.ForeignKeyConstraint(
            ['compte_service_id'], ['compte_service_ia.id'],
            name=op.f('fk_prevalidation_ia_compte_service_id_compte_service_ia'), ondelete='SET NULL',
        ),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_prevalidation_ia')),
    )
    op.create_index('ix_prevalidation_ia_question_id', 'prevalidation_ia', ['question_id'])
    op.create_index('ix_prevalidation_ia_lot', 'prevalidation_ia', ['lot'])
    op.create_index('ix_prevalidation_ia_statut', 'prevalidation_ia', ['statut'])
    op.create_index('ix_prevalidation_ia_demandee_le', 'prevalidation_ia', ['demandee_le'])
    op.create_table(
        'acces_service_ia',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('compte_service_id', sa.Integer(), nullable=True),
        sa.Column('action', sa.String(length=40), nullable=False),
        sa.Column('prevalidation_id', sa.Integer(), nullable=True),
        sa.Column('code_http', sa.Integer(), nullable=False),
        sa.Column('ip', sa.String(length=45), nullable=True),
        sa.Column('le', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ['compte_service_id'], ['compte_service_ia.id'],
            name=op.f('fk_acces_service_ia_compte_service_id_compte_service_ia'), ondelete='SET NULL',
        ),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_acces_service_ia')),
    )
    op.create_index('ix_acces_service_ia_compte_service_id', 'acces_service_ia', ['compte_service_id'])
    op.create_index('ix_acces_service_ia_le', 'acces_service_ia', ['le'])


def downgrade() -> None:
    op.drop_table('acces_service_ia')
    op.drop_table('prevalidation_ia')
    op.drop_table('compte_service_ia')
