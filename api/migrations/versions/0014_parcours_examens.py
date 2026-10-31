"""parcours « examens » en 1re et Tle : épreuve anticipée, bac blanc, sujets type annales

Revision ID: 0014
Revises: 0013
Create Date: 2026-10-31 22:00:00.000000
"""

from collections.abc import Sequence

from alembic import op


revision: str = '0014'
down_revision: str | None = '0013'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

AVANT = (
    'tronc-commun', 'specialite', 'complementaires', 'expertes', 'scientifique', 'technologique',
    'excellence', 'mise-a-niveau',
)
APRES = AVANT + ('examens',)


def _contrainte(valeurs: tuple[str, ...]) -> None:
    liste = ", ".join(f"'{v}'" for v in valeurs)
    for table in ('chapitre', 'classe'):
        with op.batch_alter_table(table, schema=None) as batch_op:
            batch_op.drop_constraint(op.f(f'ck_{table}_parcours'), type_='check')
            batch_op.create_check_constraint(op.f(f'ck_{table}_parcours'), f"parcours IN ({liste})")


def upgrade() -> None:
    _contrainte(APRES)


def downgrade() -> None:
    # Les chapitres de ce parcours portent des réponses d'élèves : on refuse plutôt que de les supprimer.
    if op.get_bind().exec_driver_sql("SELECT COUNT(*) FROM chapitre WHERE parcours = 'examens'").scalar():
        raise RuntimeError("Des chapitres « examens » existent : les retirer du contenu avant de revenir en 0013.")
    op.execute("UPDATE classe SET parcours = 'specialite' WHERE parcours = 'examens'")
    _contrainte(AVANT)
