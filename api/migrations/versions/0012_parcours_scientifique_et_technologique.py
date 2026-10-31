"""parcours « enseignement scientifique » (1re sans la spécialité) et « voie technologique » (1re, Tle)

Revision ID: 0012
Revises: 0011
Create Date: 2026-10-31 18:00:00.000000
"""

from collections.abc import Sequence

from alembic import op


revision: str = '0012'
down_revision: str | None = '0011'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

AVANT = ('tronc-commun', 'specialite', 'complementaires', 'expertes')
APRES = AVANT + ('scientifique', 'technologique')


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
    nouveaux = "('scientifique', 'technologique')"
    if op.get_bind().exec_driver_sql(f"SELECT COUNT(*) FROM chapitre WHERE parcours IN {nouveaux}").scalar():
        raise RuntimeError("Des chapitres de ces parcours existent : les retirer du contenu avant de revenir en 0011.")
    op.execute(f"UPDATE classe SET parcours = 'specialite' WHERE parcours IN {nouveaux}")
    _contrainte(AVANT)
