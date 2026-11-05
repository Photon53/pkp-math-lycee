"""archives des inscriptions : avant qu'une classe, un groupe d'anglais ou une inscription d'un enfant de famille
soit supprimé, une copie figée de son travail (séances, réponses, progression) est conservée et reste consultable
sur la fiche de l'enfant (V3, Lot 0)

Revision ID: 0029
Revises: 0028
Create Date: 2026-11-05 18:00:00.000000

Table nouvelle uniquement : aucune donnée existante n'est modifiée.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = '0029'
down_revision: str | None = '0028'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        'archive_inscription',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('enfant_id', sa.Integer(), nullable=False),
        sa.Column('matiere', sa.String(length=20), nullable=False),
        sa.Column('domaine_code', sa.String(length=30), nullable=False),
        sa.Column('niveau', sa.String(length=4), nullable=False),
        sa.Column('parcours', sa.String(length=30), nullable=True),
        sa.Column('cours', sa.String(length=60), nullable=False),
        sa.Column('enseignant', sa.String(length=100), nullable=False),
        sa.Column('inscrit_le', sa.DateTime(timezone=True), nullable=True),
        sa.Column('archivee_le', sa.DateTime(timezone=True), nullable=False),
        sa.Column('par', sa.String(length=120), nullable=False),
        sa.Column('motif', sa.String(length=60), nullable=False),
        sa.Column('resume', sa.JSON(), nullable=False),
        sa.Column('contenu', sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(
            ['enfant_id'], ['enfant.id'], name=op.f('fk_archive_inscription_enfant_id_enfant'), ondelete='CASCADE'
        ),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_archive_inscription')),
    )
    op.create_index('ix_archive_inscription_enfant_id', 'archive_inscription', ['enfant_id'])
    op.create_index('ix_archive_inscription_archivee_le', 'archive_inscription', ['archivee_le'])


def downgrade() -> None:
    op.drop_table('archive_inscription')
