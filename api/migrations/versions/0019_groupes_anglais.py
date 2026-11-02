"""groupes PKP Anglais (4e, 3e) et leurs élèves, séparés des classes de maths

Revision ID: 0019
Revises: 0018
Create Date: 2026-11-03 10:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = '0019'
down_revision: str | None = '0018'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        'groupe_anglais',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('nom', sa.String(length=60), nullable=False),
        sa.Column('niveau', sa.String(length=2), nullable=False),
        sa.Column('enseignant_id', sa.Integer(), nullable=False),
        sa.Column('cree_le', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("niveau IN ('4e', '3e')", name='ck_groupe_anglais_niveau'),
        sa.ForeignKeyConstraint(['enseignant_id'], ['enseignant.id'], ondelete='RESTRICT'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_groupe_anglais_enseignant_id', 'groupe_anglais', ['enseignant_id'])
    op.create_table(
        'eleve_anglais',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('prenom', sa.String(length=50), nullable=False),
        sa.Column('groupe_id', sa.Integer(), nullable=False),
        sa.Column('cree_le', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['groupe_id'], ['groupe_anglais.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('prenom', 'groupe_id', name='uq_eleve_anglais_prenom_groupe'),
    )
    op.create_index('ix_eleve_anglais_groupe_id', 'eleve_anglais', ['groupe_id'])


def downgrade() -> None:
    op.drop_index('ix_eleve_anglais_groupe_id', table_name='eleve_anglais')
    op.drop_table('eleve_anglais')
    op.drop_index('ix_groupe_anglais_enseignant_id', table_name='groupe_anglais')
    op.drop_table('groupe_anglais')
