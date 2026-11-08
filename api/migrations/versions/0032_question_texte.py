"""type de question « texte » (réponse courte) et chapitres rangés par domaine (PKP Français)

Revision ID: 0032
Revises: 0031
Create Date: 2026-11-08 10:00:00.000000
"""

from collections.abc import Sequence

from alembic import op


revision: str = '0032'
down_revision: str | None = '0031'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

AVANT = ('qcm', 'numerique', 'expression')
APRES = AVANT + ('texte',)


def _contrainte(valeurs: tuple[str, ...]) -> None:
    liste = ", ".join(f"'{v}'" for v in valeurs)
    with op.batch_alter_table('question', schema=None) as batch_op:
        batch_op.drop_constraint(op.f('ck_question_type_question'), type_='check')
        batch_op.create_check_constraint(op.f('ck_question_type_question'), f"type IN ({liste})")


def _unicite_chapitres(colonnes: list[str], ancienne: str, nouvelle: str) -> None:
    with op.batch_alter_table('chapitre', schema=None) as batch_op:
        batch_op.drop_constraint(ancienne, type_='unique')
        batch_op.create_unique_constraint(nouvelle, colonnes)


def upgrade() -> None:
    _contrainte(APRES)
    # Un chapitre de français et un chapitre de maths peuvent porter le même rang au même niveau.
    _unicite_chapitres(['domaine_code', 'niveau', 'parcours', 'ordre'], 'uq_chapitre_niveau_parcours_ordre',
                       'uq_chapitre_domaine_niveau_parcours_ordre')


def downgrade() -> None:
    # Ces questions portent des réponses d'élèves : on refuse plutôt que de les supprimer.
    if op.get_bind().exec_driver_sql("SELECT COUNT(*) FROM question WHERE type = 'texte'").scalar():
        raise RuntimeError("Des questions « texte » existent : les retirer du contenu avant de revenir en 0031.")
    if op.get_bind().exec_driver_sql("SELECT COUNT(*) FROM chapitre WHERE domaine_code LIKE 'francais-%'").scalar():
        raise RuntimeError("Des chapitres de français existent : les retirer du contenu avant de revenir en 0031.")
    _unicite_chapitres(['niveau', 'parcours', 'ordre'], 'uq_chapitre_domaine_niveau_parcours_ordre',
                       'uq_chapitre_niveau_parcours_ordre')
    _contrainte(AVANT)
