"""niveaux du collège (6e à 3e) pour les classes et les chapitres de maths (domaine Maths collège)

Revision ID: 0025
Revises: 0024
Create Date: 2026-11-04 10:00:00.000000
"""

from collections.abc import Sequence

from alembic import op

revision: str = '0025'
down_revision: str | None = '0024'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

LYCEE = "niveau IN ('2nde', '1re', 'Tle')"
TOUS = "niveau IN ('6e', '5e', '4e', '3e', '2nde', '1re', 'Tle')"


def _remplacer(condition: str) -> None:
    for table in ("classe", "chapitre"):
        with op.batch_alter_table(table) as batch:
            batch.drop_constraint(op.f(f'ck_{table}_niveau'), type_='check')
            batch.create_check_constraint('niveau', condition)


def upgrade() -> None:
    _remplacer(TOUS)


def downgrade() -> None:
    op.execute("DELETE FROM classe_chapitre WHERE chapitre_id IN (SELECT id FROM chapitre WHERE niveau NOT IN ('2nde', '1re', 'Tle'))")
    _remplacer(LYCEE)
