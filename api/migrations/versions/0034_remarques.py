"""remarques et suggestions des élèves, parents et professeurs, avec ou sans leur nom (ticket #30)

Revision ID: 0034
Revises: 0033
Create Date: 2026-11-09 11:00:00.000000

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
        'remarque',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('reference', sa.String(length=20), nullable=False),
        sa.Column('code_suivi_empreinte', sa.String(length=64), nullable=False),
        sa.Column('categorie', sa.String(length=30), nullable=False),
        sa.Column('description', sa.String(length=3000), nullable=False),
        sa.Column('page', sa.String(length=300), nullable=True),
        sa.Column('anonyme', sa.Boolean(), nullable=False),
        sa.Column('auteur_role', sa.String(length=12), nullable=True),
        sa.Column('auteur_id', sa.Integer(), nullable=True),
        sa.Column('auteur_nom', sa.String(length=120), nullable=True),
        sa.Column('statut', sa.String(length=10), nullable=False),
        sa.Column('priorite', sa.String(length=10), nullable=False),
        sa.Column('assignee_id', sa.Integer(), nullable=True),
        sa.Column('reponse', sa.String(length=3000), nullable=True),
        sa.Column('cree_le', sa.DateTime(timezone=True), nullable=False),
        sa.Column('maj_le', sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "categorie IN ('bug', 'dysfonctionnement', 'amelioration-fonctionnelle', 'amelioration-pedagogique', "
            "'erreur-pedagogique', 'lien-inaccessible', 'question', 'autre')",
            name=op.f('ck_remarque_categorie'),
        ),
        sa.CheckConstraint("statut IN ('recue', 'en-cours', 'resolue', 'fermee')", name=op.f('ck_remarque_statut')),
        sa.CheckConstraint("priorite IN ('basse', 'normale', 'haute')", name=op.f('ck_remarque_priorite')),
        sa.CheckConstraint(
            "NOT anonyme OR (auteur_role IS NULL AND auteur_id IS NULL AND auteur_nom IS NULL)",
            name=op.f('ck_remarque_anonymat'),
        ),
        sa.ForeignKeyConstraint(
            ['assignee_id'], ['enseignant.id'], name=op.f('fk_remarque_assignee_id_enseignant'), ondelete='SET NULL'
        ),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_remarque')),
        sa.UniqueConstraint('reference', name=op.f('uq_remarque_reference')),
    )
    op.create_index('ix_remarque_categorie', 'remarque', ['categorie'])
    op.create_index('ix_remarque_statut', 'remarque', ['statut'])
    op.create_index('ix_remarque_cree_le', 'remarque', ['cree_le'])


def downgrade() -> None:
    op.drop_table('remarque')
