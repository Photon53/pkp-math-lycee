"""parcours « professionnel » en 2nde : seconde préparant au baccalauréat professionnel (ticket #25)

Revision ID: 0033
Revises: 0032
Create Date: 2026-11-08 14:00:00.000000

Seule la liste des valeurs permises change : aucune classe, aucun chapitre ni aucune progression existants
ne sont modifiés.
"""

from collections.abc import Sequence

from alembic import op


revision: str = '0033'
down_revision: str | None = '0032'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

AVANT = (
    'tronc-commun', 'specialite', 'complementaires', 'expertes', 'scientifique', 'technologique',
    'excellence', 'mise-a-niveau', 'examens',
)
APRES = AVANT + ('professionnel',)


def _contrainte(valeurs: tuple[str, ...]) -> None:
    liste = ", ".join(f"'{v}'" for v in valeurs)
    for table in ('chapitre', 'classe'):
        with op.batch_alter_table(table, schema=None) as batch_op:
            batch_op.drop_constraint(op.f(f'ck_{table}_parcours'), type_='check')
            batch_op.create_check_constraint(op.f(f'ck_{table}_parcours'), f"parcours IN ({liste})")


def upgrade() -> None:
    _contrainte(APRES)


def downgrade() -> None:
    # Classes et chapitres de ce parcours portent des élèves et des réponses : on refuse plutôt que de les modifier.
    bind = op.get_bind()
    for table in ('chapitre', 'classe'):
        if bind.exec_driver_sql(f"SELECT COUNT(*) FROM {table} WHERE parcours = 'professionnel'").scalar():
            raise RuntimeError(
                f"Des lignes « {table} » du parcours professionnel existent : les retirer avant de revenir en 0032."
            )
    _contrainte(AVANT)
