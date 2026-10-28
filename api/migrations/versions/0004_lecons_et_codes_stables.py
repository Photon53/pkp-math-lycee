"""lecons et codes stables

Revision ID: 0004
Revises: 0003
Create Date: 2026-10-28 17:10:13.451107
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = '0004'
down_revision: str | None = '0003'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table('lecon',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('competence_id', sa.Integer(), nullable=False),
    sa.Column('cours', sa.Text(), nullable=False),
    sa.Column('resume', sa.Text(), nullable=False),
    sa.Column('maj_le', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['competence_id'], ['competence.id'], name=op.f('fk_lecon_competence_id_competence'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_lecon')),
    sa.UniqueConstraint('competence_id', name=op.f('uq_lecon_competence_id'))
    )

    # Les chapitres existants reçoivent un code provisoire « niveau-ordre » (ex. « 2nde-1 »),
    # remplacé par le code du fichier YAML au premier import qui les reconnaît.
    with op.batch_alter_table('chapitre', schema=None) as batch_op:
        batch_op.add_column(sa.Column('code', sa.String(length=40), nullable=True))
    op.execute("UPDATE chapitre SET code = niveau || '-' || CAST(ordre AS VARCHAR(10))")
    with op.batch_alter_table('chapitre', schema=None) as batch_op:
        batch_op.alter_column('code', existing_type=sa.String(length=40), nullable=False)
        batch_op.create_unique_constraint(batch_op.f('uq_chapitre_code'), ['code'])

    with op.batch_alter_table('competence', schema=None) as batch_op:
        batch_op.add_column(sa.Column('ordre', sa.Integer(), server_default='0', nullable=False))
        batch_op.alter_column('code',
               existing_type=sa.VARCHAR(length=30),
               type_=sa.String(length=40),
               existing_nullable=False)

    with op.batch_alter_table('question', schema=None) as batch_op:
        batch_op.add_column(sa.Column('code', sa.String(length=60), nullable=True))
        batch_op.create_unique_constraint(batch_op.f('uq_question_code'), ['code'])


def downgrade() -> None:
    with op.batch_alter_table('question', schema=None) as batch_op:
        batch_op.drop_constraint(batch_op.f('uq_question_code'), type_='unique')
        batch_op.drop_column('code')

    with op.batch_alter_table('competence', schema=None) as batch_op:
        batch_op.alter_column('code',
               existing_type=sa.String(length=40),
               type_=sa.VARCHAR(length=30),
               existing_nullable=False)
        batch_op.drop_column('ordre')

    with op.batch_alter_table('chapitre', schema=None) as batch_op:
        batch_op.drop_constraint(batch_op.f('uq_chapitre_code'), type_='unique')
        batch_op.drop_column('code')

    op.drop_table('lecon')
