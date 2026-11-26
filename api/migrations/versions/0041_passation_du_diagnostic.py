"""passation du diagnostic

Issue #162 — Lot 3 : passation adaptative du diagnostic (Claude). Ajouts seulement : table des passations,
ouverture du diagnostic par classe (fermé par défaut), compétences de retour, statut « je-ne-sais-pas ».

Revision ID: 0041
Revises: 0040
Create Date: 2026-11-17 05:43:43.189382
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

STATUTS_AVANT = ('juste', 'faux', 'en-attente-de-correction')
STATUTS_APRES = ('juste', 'faux', 'je-ne-sais-pas', 'en-attente-de-correction')


def _statuts(valeurs: tuple[str, ...]) -> None:
    liste = ", ".join(f"'{v}'" for v in valeurs)
    with op.batch_alter_table('observation_diagnostic', schema=None) as batch_op:
        batch_op.drop_constraint(op.f('ck_observation_diagnostic_statut_observation'), type_='check')
        batch_op.create_check_constraint(op.f('ck_observation_diagnostic_statut_observation'), f"statut IN ({liste})")


revision: str = '0041'
down_revision: str | None = '0040'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table('passation_diagnostic',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('eleve_id', sa.Integer(), nullable=False),
    sa.Column('debut', sa.DateTime(timezone=True), nullable=False),
    sa.Column('fin', sa.DateTime(timezone=True), nullable=True),
    sa.Column('question_courante_id', sa.Integer(), nullable=True),
    sa.Column('question_servie_le', sa.DateTime(timezone=True), nullable=True),
    sa.ForeignKeyConstraint(['eleve_id'], ['eleve.id'], name=op.f('fk_passation_diagnostic_eleve_id_eleve'), ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['question_courante_id'], ['question.id'], name=op.f('fk_passation_diagnostic_question_courante_id_question'), ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_passation_diagnostic'))
    )
    with op.batch_alter_table('passation_diagnostic', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_passation_diagnostic_eleve_id'), ['eleve_id'], unique=True)

    with op.batch_alter_table('classe', schema=None) as batch_op:
        batch_op.add_column(sa.Column('diagnostic_ouvert', sa.Boolean(), server_default=sa.false(), nullable=False))

    with op.batch_alter_table('competence', schema=None) as batch_op:
        batch_op.add_column(sa.Column('retour', sa.JSON(), nullable=True))

    with op.batch_alter_table('observation_diagnostic', schema=None) as batch_op:
        batch_op.add_column(sa.Column('passation_id', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('duree_s', sa.Float(), nullable=True))
        batch_op.create_index(batch_op.f('ix_observation_diagnostic_passation_id'), ['passation_id'], unique=False)
        batch_op.create_foreign_key(batch_op.f('fk_observation_diagnostic_passation_id_passation_diagnostic'), 'passation_diagnostic', ['passation_id'], ['id'], ondelete='CASCADE')
    _statuts(STATUTS_APRES)


def downgrade() -> None:
    # Ces lignes portent des réponses d'élèves : on refuse plutôt que de les supprimer.
    connexion = op.get_bind()
    if connexion.exec_driver_sql("SELECT COUNT(*) FROM passation_diagnostic").scalar():
        raise RuntimeError("Des passations de diagnostic existent : les exporter avant de revenir en 0040.")
    _statuts(STATUTS_AVANT)
    with op.batch_alter_table('observation_diagnostic', schema=None) as batch_op:
        batch_op.drop_constraint(batch_op.f('fk_observation_diagnostic_passation_id_passation_diagnostic'), type_='foreignkey')
        batch_op.drop_index(batch_op.f('ix_observation_diagnostic_passation_id'))
        batch_op.drop_column('duree_s')
        batch_op.drop_column('passation_id')

    with op.batch_alter_table('competence', schema=None) as batch_op:
        batch_op.drop_column('retour')

    with op.batch_alter_table('classe', schema=None) as batch_op:
        batch_op.drop_column('diagnostic_ouvert')

    with op.batch_alter_table('passation_diagnostic', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_passation_diagnostic_eleve_id'))

    op.drop_table('passation_diagnostic')
