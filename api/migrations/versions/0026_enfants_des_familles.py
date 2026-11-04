"""enfants des familles : une personne, un niveau, une carte ; ses inscriptions en maths et en anglais

Revision ID: 0026
Revises: 0025
Create Date: 2026-11-04 18:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = '0026'
down_revision: str | None = '0025'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

NIVEAUX = "niveau IN ('6e', '5e', '4e', '3e', '2nde', '1re', 'Tle')"


def upgrade() -> None:
    op.create_table(
        'enfant',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('prenom', sa.String(length=50), nullable=False),
        sa.Column('nom', sa.String(length=50), server_default='', nullable=False),
        sa.Column('niveau', sa.String(length=4), nullable=False),
        sa.Column('identifiant', sa.String(length=40), nullable=False),
        sa.Column('code_hash', sa.String(length=255), nullable=True),
        sa.Column('cree_le', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.Column('derniere_connexion', sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(NIVEAUX, name=op.f('ck_enfant_niveau')),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_enfant')),
        sa.UniqueConstraint('identifiant', name=op.f('uq_enfant_identifiant')),
    )
    op.create_table(
        'parent_enfant',
        sa.Column('parent_id', sa.Integer(), nullable=False),
        sa.Column('enfant_id', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['enfant_id'], ['enfant.id'], name=op.f('fk_parent_enfant_enfant_id_enfant'), ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['parent_id'], ['parent.id'], name=op.f('fk_parent_enfant_parent_id_parent'), ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('parent_id', 'enfant_id', name=op.f('pk_parent_enfant')),
    )
    op.create_index(op.f('ix_parent_enfant_enfant_id'), 'parent_enfant', ['enfant_id'], unique=False)
    for table in ('eleve', 'eleve_anglais'):
        with op.batch_alter_table(table) as batch:
            batch.add_column(sa.Column('enfant_id', sa.Integer(), nullable=True))
            batch.create_index(batch.f(f'ix_{table}_enfant_id'), ['enfant_id'], unique=False)
            batch.create_foreign_key(
                batch.f(f'fk_{table}_enfant_id_enfant'), 'enfant', ['enfant_id'], ['id'], ondelete='CASCADE'
            )


def downgrade() -> None:
    for table in ('eleve_anglais', 'eleve'):
        op.execute(f"DELETE FROM {table} WHERE enfant_id IS NOT NULL")
        with op.batch_alter_table(table) as batch:
            batch.drop_constraint(batch.f(f'fk_{table}_enfant_id_enfant'), type_='foreignkey')
            batch.drop_index(batch.f(f'ix_{table}_enfant_id'))
            batch.drop_column('enfant_id')
    op.drop_index(op.f('ix_parent_enfant_enfant_id'), table_name='parent_enfant')
    op.drop_table('parent_enfant')
    op.drop_table('enfant')
