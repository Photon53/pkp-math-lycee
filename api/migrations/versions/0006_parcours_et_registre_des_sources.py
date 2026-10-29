"""parcours et registre des sources

Revision ID: 0006
Revises: 0005
Create Date: 2026-10-29 02:07:16.322442
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = '0006'
down_revision: str | None = '0005'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table('chapitre', schema=None) as batch_op:
        batch_op.add_column(sa.Column('parcours', sa.Enum('tronc-commun', 'specialite', 'complementaires', 'expertes', name='parcours', native_enum=False, create_constraint=True), server_default='specialite', nullable=False))
        batch_op.drop_constraint(batch_op.f('uq_chapitre_niveau_ordre'), type_='unique')
        batch_op.create_unique_constraint('uq_chapitre_niveau_parcours_ordre', ['niveau', 'parcours', 'ordre'])

    with op.batch_alter_table('classe', schema=None) as batch_op:
        batch_op.add_column(sa.Column('parcours', sa.Enum('tronc-commun', 'specialite', 'complementaires', 'expertes', name='parcours', native_enum=False, create_constraint=True), server_default='specialite', nullable=False))

    # Valeur par défaut « specialite » : juste pour la 1re et la Terminale. La Seconde suit le tronc commun.
    op.execute("UPDATE classe SET parcours = 'tronc-commun' WHERE niveau = '2nde'")
    op.execute("UPDATE chapitre SET parcours = 'tronc-commun' WHERE niveau = '2nde'")

    with op.batch_alter_table('question', schema=None) as batch_op:
        batch_op.add_column(sa.Column('source', sa.String(length=200), server_default='PKP Math', nullable=False))
        batch_op.add_column(sa.Column('source_url', sa.String(length=500), nullable=True))
        batch_op.add_column(sa.Column('licence_source', sa.String(length=100), nullable=True))
        batch_op.add_column(sa.Column('adaptation', sa.Enum('originale', 'inspiree', 'adaptee', 'reproduite', name='adaptation', native_enum=False, create_constraint=True), server_default='originale', nullable=False))
        batch_op.add_column(sa.Column('statut_validation', sa.Enum('a-valider', 'validee', 'a-corriger', name='statut_validation', native_enum=False, create_constraint=True), server_default='a-valider', nullable=False))
        batch_op.add_column(sa.Column('valide_par', sa.String(length=100), nullable=True))
        batch_op.add_column(sa.Column('valide_le', sa.Date(), nullable=True))



def downgrade() -> None:
    # Les colonnes énumérées portent une contrainte CHECK : la retirer avant la colonne,
    # sinon SQLite (mode batch) recrée la table avec un CHECK sur une colonne disparue.
    with op.batch_alter_table('question', schema=None) as batch_op:
        batch_op.drop_constraint(op.f('ck_question_statut_validation'), type_='check')
        batch_op.drop_constraint(op.f('ck_question_adaptation'), type_='check')
        batch_op.drop_column('valide_le')
        batch_op.drop_column('valide_par')
        batch_op.drop_column('statut_validation')
        batch_op.drop_column('adaptation')
        batch_op.drop_column('licence_source')
        batch_op.drop_column('source_url')
        batch_op.drop_column('source')

    with op.batch_alter_table('classe', schema=None) as batch_op:
        batch_op.drop_constraint(op.f('ck_classe_parcours'), type_='check')
        batch_op.drop_column('parcours')

    with op.batch_alter_table('chapitre', schema=None) as batch_op:
        batch_op.drop_constraint('uq_chapitre_niveau_parcours_ordre', type_='unique')
        batch_op.create_unique_constraint(batch_op.f('uq_chapitre_niveau_ordre'), ['niveau', 'ordre'])
        batch_op.drop_constraint(op.f('ck_chapitre_parcours'), type_='check')
        batch_op.drop_column('parcours')

