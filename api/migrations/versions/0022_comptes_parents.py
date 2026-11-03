"""comptes parents (créés par le professeur) et leurs enfants

Revision ID: 0022
Revises: 0021
Create Date: 2026-11-03 20:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = '0022'
down_revision: str | None = '0021'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        'parent',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('email', sa.String(length=254), nullable=False),
        sa.Column('mot_de_passe_hash', sa.String(length=255), nullable=False),
        sa.Column('mdp_provisoire', sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column('cree_le', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('derniere_connexion', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id', name='pk_parent'),
        sa.UniqueConstraint('email', name='uq_parent_email'),
    )
    op.create_table(
        'parent_eleve',
        sa.Column('parent_id', sa.Integer(), nullable=False),
        sa.Column('eleve_id', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['parent_id'], ['parent.id'], name='fk_parent_eleve_parent_id_parent', ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['eleve_id'], ['eleve.id'], name='fk_parent_eleve_eleve_id_eleve', ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('parent_id', 'eleve_id', name='pk_parent_eleve'),
    )
    op.create_index('ix_parent_eleve_eleve_id', 'parent_eleve', ['eleve_id'])


def downgrade() -> None:
    op.drop_index('ix_parent_eleve_eleve_id', table_name='parent_eleve')
    op.drop_table('parent_eleve')
    op.drop_table('parent')
