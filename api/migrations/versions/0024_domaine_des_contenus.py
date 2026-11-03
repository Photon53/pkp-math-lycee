"""domaine enregistré sur les classes, les chapitres, les groupes et les séances d'anglais (CDC V2, EX.2)

Jusqu'ici, le domaine se déduisait de la table : classes et chapitres en Maths lycée, groupes et séances
d'anglais en Anglais collège. Il devient une colonne, remplie d'après l'existant. Les contraintes
`niveau IN ('4e', '3e')` de l'anglais (colonne élargie à 4 caractères) sont remplacées par un contrôle de l'API sur les niveaux du domaine.

Revision ID: 0024
Revises: 0023
Create Date: 2026-11-03 23:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = '0024'
down_revision: str | None = '0023'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABLES = [
    ("classe", "maths-lycee"),
    ("chapitre", "maths-lycee"),
    ("groupe_anglais", "anglais-college"),
    ("seance_anglais", "anglais-college"),
]
CONTRAINTES_ANGLAIS = {"groupe_anglais": "ck_groupe_anglais_niveau", "seance_anglais": "ck_seance_anglais_niveau"}


def upgrade() -> None:
    for table, domaine in TABLES:
        with op.batch_alter_table(table) as batch:
            batch.add_column(
                sa.Column('domaine_code', sa.String(length=30), server_default=domaine, nullable=False)
            )
            batch.create_foreign_key(
                f'fk_{table}_domaine_code_domaine_pedagogique', 'domaine_pedagogique',
                ['domaine_code'], ['code'], ondelete='RESTRICT',
            )
            batch.create_index(f'ix_{table}_domaine_code', ['domaine_code'])
            if table in CONTRAINTES_ANGLAIS:
                batch.drop_constraint(CONTRAINTES_ANGLAIS[table], type_='check')
                # « 2nde » doit tenir quand l'anglais lycée ouvrira.
                batch.alter_column('niveau', type_=sa.String(length=4), existing_type=sa.String(length=2), existing_nullable=False)


def downgrade() -> None:
    for table, _ in reversed(TABLES):
        with op.batch_alter_table(table) as batch:
            batch.drop_index(f'ix_{table}_domaine_code')
            batch.drop_constraint(f'fk_{table}_domaine_code_domaine_pedagogique', type_='foreignkey')
            batch.drop_column('domaine_code')
            if table in CONTRAINTES_ANGLAIS:
                batch.alter_column('niveau', type_=sa.String(length=2), existing_type=sa.String(length=4), existing_nullable=False)
                batch.create_check_constraint(CONTRAINTES_ANGLAIS[table], "niveau IN ('4e', '3e')")
