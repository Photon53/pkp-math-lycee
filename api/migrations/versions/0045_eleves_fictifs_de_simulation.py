"""eleves fictifs de simulation

Issue #184 — Vue élève simulée (Claude). Ajout seulement : deux colonnes facultatives sur `eleve`
(`simulation_par_id`, `simulation_role`), vides pour tous les élèves existants.

Revision ID: 0045
Revises: 0044
Create Date: 2026-11-19 17:21:23.587243
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = '0045'
down_revision: str | None = '0044'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

INDEX_IDENTIFIANT = 'uq_eleve_identifiant_minuscules'
CONDITION = (
    "(simulation_par_id IS NULL AND simulation_role IS NULL) OR "
    "(simulation_par_id IS NOT NULL AND simulation_role IN ('enseignant', 'admin'))"
)


def upgrade() -> None:
    with op.batch_alter_table('eleve', schema=None) as batch_op:
        batch_op.add_column(sa.Column('simulation_par_id', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('simulation_role', sa.String(length=12), nullable=True))
        batch_op.create_index(batch_op.f('ix_eleve_simulation_par_id'), ['simulation_par_id'], unique=False)
        batch_op.create_unique_constraint('uq_eleve_simulation', ['simulation_par_id', 'simulation_role', 'classe_id'])
        batch_op.create_foreign_key(
            batch_op.f('fk_eleve_simulation_par_id_enseignant'), 'enseignant', ['simulation_par_id'], ['id'],
            ondelete='CASCADE',
        )
        batch_op.create_check_constraint(op.f('ck_eleve_simulation'), CONDITION)
    _retablir_index_identifiant()


def downgrade() -> None:
    with op.batch_alter_table('eleve', schema=None) as batch_op:
        batch_op.drop_constraint(op.f('ck_eleve_simulation'), type_='check')
        batch_op.drop_constraint(batch_op.f('fk_eleve_simulation_par_id_enseignant'), type_='foreignkey')
        batch_op.drop_constraint('uq_eleve_simulation', type_='unique')
        batch_op.drop_index(batch_op.f('ix_eleve_simulation_par_id'))
        batch_op.drop_column('simulation_role')
        batch_op.drop_column('simulation_par_id')
    _retablir_index_identifiant()


def _retablir_index_identifiant() -> None:
    """SQLite : le mode « batch » recrée la table sans l'index d'expression de RGPD-1 (migration 0039), qu'il ne
    sait pas relire ; on le rétablit. PostgreSQL modifie la table en place et le conserve."""
    connexion = op.get_bind()
    if connexion.dialect.name != 'sqlite':
        return
    existe = connexion.execute(
        sa.text("SELECT 1 FROM sqlite_master WHERE type = 'index' AND name = :n"), {'n': INDEX_IDENTIFIANT}
    ).first()
    if existe is None:
        op.create_index(INDEX_IDENTIFIANT, 'eleve', [sa.text('lower(identifiant)')], unique=True)
