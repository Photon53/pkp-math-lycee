"""chapitres de diagnostic, types choix_multiples et redaction, observations du diagnostic

Issue #162 — Lot 2 : diagnostic des acquis antérieurs (Claude). Ajouts seulement : les chapitres existants
deviennent des chapitres d'apprentissage, aucune donnée existante n'est modifiée ni supprimée. Les observations
du diagnostic ont leur propre table, distincte de `reponse` (le taux de maîtrise n'en tient pas compte).

Revision ID: 0040
Revises: 0039
Create Date: 2026-11-17 04:42:44.314037
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = '0040'
down_revision: str | None = '0039'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TYPES_AVANT = ('qcm', 'numerique', 'expression', 'texte')
TYPES_APRES = TYPES_AVANT + ('choix_multiples', 'redaction')


def _liste(valeurs: tuple[str, ...]) -> str:
    return ", ".join(f"'{v}'" for v in valeurs)


def _types_de_question(valeurs: tuple[str, ...], longueur: int) -> None:
    with op.batch_alter_table('question', schema=None) as batch_op:
        batch_op.drop_constraint(op.f('ck_question_type_question'), type_='check')
        batch_op.alter_column('type', existing_type=sa.String(), type_=sa.String(length=longueur), existing_nullable=False)
        batch_op.create_check_constraint(op.f('ck_question_type_question'), f"type IN ({_liste(valeurs)})")


def upgrade() -> None:
    _types_de_question(TYPES_APRES, 15)

    with op.batch_alter_table('chapitre', schema=None) as batch_op:
        batch_op.add_column(sa.Column('nature', sa.String(length=13), server_default='apprentissage', nullable=False))
        batch_op.add_column(sa.Column('publics', sa.JSON(), nullable=True))
        batch_op.add_column(sa.Column('programme_prerequis', sa.String(length=40), nullable=True))
        batch_op.create_check_constraint(
            op.f('ck_chapitre_nature_chapitre'), "nature IN ('apprentissage', 'diagnostic')"
        )

    op.create_table(
        'observation_diagnostic',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('eleve_id', sa.Integer(), nullable=False),
        sa.Column('question_id', sa.Integer(), nullable=False),
        sa.Column('reponse_donnee', sa.Text(), nullable=False),
        sa.Column(
            'statut',
            sa.Enum('juste', 'faux', 'en-attente-de-correction', name='statut_observation', native_enum=False,
                    create_constraint=True),
            nullable=False,
        ),
        sa.Column('observe_le', sa.DateTime(timezone=True), nullable=False),
        sa.Column('corrige_par_id', sa.Integer(), nullable=True),
        sa.Column('corrige_le', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['corrige_par_id'], ['enseignant.id'],
                                name=op.f('fk_observation_diagnostic_corrige_par_id_enseignant'), ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['eleve_id'], ['eleve.id'], name=op.f('fk_observation_diagnostic_eleve_id_eleve'),
                                ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['question_id'], ['question.id'],
                                name=op.f('fk_observation_diagnostic_question_id_question'), ondelete='RESTRICT'),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_observation_diagnostic')),
    )
    with op.batch_alter_table('observation_diagnostic', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_observation_diagnostic_eleve_id'), ['eleve_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_observation_diagnostic_question_id'), ['question_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_observation_diagnostic_statut'), ['statut'], unique=False)


def downgrade() -> None:
    # Ces lignes portent des réponses d'élèves : on refuse plutôt que de les supprimer.
    connexion = op.get_bind()
    if connexion.exec_driver_sql("SELECT COUNT(*) FROM observation_diagnostic").scalar():
        raise RuntimeError("Des observations de diagnostic existent : les exporter avant de revenir en 0039.")
    if connexion.exec_driver_sql(
        "SELECT COUNT(*) FROM question WHERE type IN ('choix_multiples', 'redaction')"
    ).scalar() or connexion.exec_driver_sql("SELECT COUNT(*) FROM chapitre WHERE nature = 'diagnostic'").scalar():
        raise RuntimeError("Des chapitres ou questions de diagnostic existent : les retirer avant de revenir en 0039.")

    with op.batch_alter_table('observation_diagnostic', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_observation_diagnostic_statut'))
        batch_op.drop_index(batch_op.f('ix_observation_diagnostic_question_id'))
        batch_op.drop_index(batch_op.f('ix_observation_diagnostic_eleve_id'))
    op.drop_table('observation_diagnostic')

    with op.batch_alter_table('chapitre', schema=None) as batch_op:
        batch_op.drop_constraint(op.f('ck_chapitre_nature_chapitre'), type_='check')
        batch_op.drop_column('programme_prerequis')
        batch_op.drop_column('publics')
        batch_op.drop_column('nature')

    _types_de_question(TYPES_AVANT, 10)
