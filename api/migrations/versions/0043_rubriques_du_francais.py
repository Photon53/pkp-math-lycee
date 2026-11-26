"""rubriques du francais

Issue #177 — Rubriques des chapitres de français (Claude). Ajout seulement : colonne `chapitre.rubrique`, vide
pour tous les chapitres existants (maths), valeurs contrôlées : conjugaison, grammaire, redaction, mon_cours.

Revision ID: 0043
Revises: 0042
Create Date: 2026-11-19 00:39:39.205747
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = '0043'
down_revision: str | None = '0042'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table('chapitre', schema=None) as batch_op:
        batch_op.add_column(sa.Column('rubrique', sa.String(length=11), nullable=True))
        batch_op.create_check_constraint(
            op.f('ck_chapitre_rubrique_francais'), "rubrique IN ('conjugaison', 'grammaire', 'redaction', 'mon_cours')"
        )


def downgrade() -> None:
    # Retire seulement le classement des chapitres de français ; aucun chapitre ni aucune réponse n'est supprimé.
    with op.batch_alter_table('chapitre', schema=None) as batch_op:
        batch_op.drop_constraint(op.f('ck_chapitre_rubrique_francais'), type_='check')
        batch_op.drop_column('rubrique')
