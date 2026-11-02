"""identifiant de connexion de l'élève : identifiant + code personnel, sans prénom ni code classe

Revision ID: 0016
Revises: 0015
Create Date: 2026-11-02 10:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from app.security import generer_identifiant

revision: str = '0016'
down_revision: str | None = '0015'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table('eleve', schema=None) as batch_op:
        batch_op.add_column(sa.Column('identifiant', sa.String(length=40), nullable=True))
        batch_op.create_unique_constraint('uq_eleve_identifiant', ['identifiant'])

    # Les élèves déjà inscrits reçoivent leur identifiant ; leur code personnel ne change pas.
    connexion = op.get_bind()
    pris: set[str] = set()
    for eleve_id, prenom in connexion.execute(sa.text('SELECT id, prenom FROM eleve ORDER BY id')).all():
        identifiant = generer_identifiant(prenom)
        while identifiant in pris:
            identifiant = generer_identifiant(prenom)
        pris.add(identifiant)
        connexion.execute(
            sa.text('UPDATE eleve SET identifiant = :i WHERE id = :e'), {'i': identifiant, 'e': eleve_id}
        )


def downgrade() -> None:
    with op.batch_alter_table('eleve', schema=None) as batch_op:
        batch_op.drop_constraint('uq_eleve_identifiant', type_='unique')
        batch_op.drop_column('identifiant')
