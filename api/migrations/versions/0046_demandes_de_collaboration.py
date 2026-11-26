"""demandes de collaboration

Issue #171 — Candidatures de professeurs et demandes de partenariat (Claude). Ajout seulement : table
`demande_collaboration` (données d'adultes ; le CV est un fichier hors base, supprimé avec la demande).

Revision ID: 0046
Revises: 0045
Create Date: 2026-11-19 17:26:10.911965
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = '0046'
down_revision: str | None = '0045'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table('demande_collaboration',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('reference', sa.String(length=20), nullable=False),
    sa.Column('type', sa.String(length=12), nullable=False),
    sa.Column('prenom', sa.String(length=60), nullable=False),
    sa.Column('nom', sa.String(length=80), nullable=False),
    sa.Column('email', sa.String(length=254), nullable=False),
    sa.Column('telephone', sa.String(length=30), nullable=True),
    sa.Column('matieres', sa.String(length=100), nullable=True),
    sa.Column('niveaux', sa.String(length=100), nullable=True),
    sa.Column('disponibilites', sa.String(length=500), nullable=True),
    sa.Column('structure_nom', sa.String(length=150), nullable=True),
    sa.Column('structure_type', sa.String(length=12), nullable=True),
    sa.Column('fonction', sa.String(length=100), nullable=True),
    sa.Column('message', sa.String(length=3000), nullable=True),
    sa.Column('cv_fichier', sa.String(length=64), nullable=True),
    sa.Column('cv_taille_octets', sa.Integer(), nullable=True),
    sa.Column('statut', sa.String(length=10), nullable=False),
    sa.Column('issue', sa.String(length=16), nullable=True),
    sa.Column('notes_internes', sa.String(length=3000), nullable=True),
    sa.Column('responsable_id', sa.Integer(), nullable=True),
    sa.Column('cree_le', sa.DateTime(timezone=True), nullable=False),
    sa.Column('maj_le', sa.DateTime(timezone=True), nullable=False),
    sa.CheckConstraint("issue IS NULL OR issue IN ('suite-demandee', 'refus', 'cloture')", name=op.f('ck_demande_collaboration_issue')),
    sa.CheckConstraint("statut <> 'traite' OR issue IS NOT NULL", name=op.f('ck_demande_collaboration_issue_si_traite')),
    sa.CheckConstraint("statut IN ('nouveau', 'a-traiter', 'traite')", name=op.f('ck_demande_collaboration_statut')),
    sa.CheckConstraint("structure_type IS NULL OR structure_type IN ('ecole', 'institut', 'association', 'autre')", name=op.f('ck_demande_collaboration_structure_type')),
    sa.CheckConstraint("type = 'candidature' OR cv_fichier IS NULL", name=op.f('ck_demande_collaboration_cv_candidature')),
    sa.CheckConstraint("type IN ('candidature', 'partenariat')", name=op.f('ck_demande_collaboration_type')),
    sa.ForeignKeyConstraint(['responsable_id'], ['enseignant.id'], name=op.f('fk_demande_collaboration_responsable_id_enseignant'), ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_demande_collaboration')),
    sa.UniqueConstraint('reference', name=op.f('uq_demande_collaboration_reference'))
    )
    with op.batch_alter_table('demande_collaboration', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_demande_collaboration_cree_le'), ['cree_le'], unique=False)
        batch_op.create_index(batch_op.f('ix_demande_collaboration_maj_le'), ['maj_le'], unique=False)
        batch_op.create_index(batch_op.f('ix_demande_collaboration_statut'), ['statut'], unique=False)
        batch_op.create_index(batch_op.f('ix_demande_collaboration_type'), ['type'], unique=False)



def downgrade() -> None:
    # Supprime les demandes ; les CV restent dans PKP_DOSSIER_CANDIDATURES et s'effacent à la main.
    with op.batch_alter_table('demande_collaboration', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_demande_collaboration_type'))
        batch_op.drop_index(batch_op.f('ix_demande_collaboration_statut'))
        batch_op.drop_index(batch_op.f('ix_demande_collaboration_maj_le'))
        batch_op.drop_index(batch_op.f('ix_demande_collaboration_cree_le'))

    op.drop_table('demande_collaboration')
