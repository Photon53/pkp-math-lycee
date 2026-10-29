"""chapitres proposes et choisis

Revision ID: 0007
Revises: 0006
Create Date: 2026-10-29 03:10:47.835433
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = '0007'
down_revision: str | None = '0006'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table('classe_chapitre',
    sa.Column('classe_id', sa.Integer(), nullable=False),
    sa.Column('chapitre_id', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['chapitre_id'], ['chapitre.id'], name=op.f('fk_classe_chapitre_chapitre_id_chapitre'), ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['classe_id'], ['classe.id'], name=op.f('fk_classe_chapitre_classe_id_classe'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('classe_id', 'chapitre_id', name=op.f('pk_classe_chapitre'))
    )
    op.create_table('seance_chapitre',
    sa.Column('seance_id', sa.Integer(), nullable=False),
    sa.Column('chapitre_id', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['chapitre_id'], ['chapitre.id'], name=op.f('fk_seance_chapitre_chapitre_id_chapitre'), ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['seance_id'], ['seance.id'], name=op.f('fk_seance_chapitre_seance_id_seance'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('seance_id', 'chapitre_id', name=op.f('pk_seance_chapitre'))
    )

    # Classes existantes : tous les chapitres de leur programme (niveau + parcours) restent ouverts,
    # pour que rien ne change pour elles. L'enseignant pourra ensuite en fermer.
    op.execute(
        "INSERT INTO classe_chapitre (classe_id, chapitre_id) "
        "SELECT classe.id, chapitre.id FROM classe JOIN chapitre "
        "ON chapitre.niveau = classe.niveau AND chapitre.parcours = classe.parcours"
    )


def downgrade() -> None:
    op.drop_table('seance_chapitre')
    op.drop_table('classe_chapitre')
