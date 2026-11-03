"""disciplines du professeur : maths (comptes existants) et anglais (coché par un administrateur)

Revision ID: 0018
Revises: 0017
Create Date: 2026-11-02 18:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = '0018'
down_revision: str | None = '0017'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table('enseignant', schema=None) as batch_op:
        batch_op.add_column(sa.Column('enseigne_maths', sa.Boolean(), server_default=sa.true(), nullable=False))
        batch_op.add_column(sa.Column('enseigne_anglais', sa.Boolean(), server_default=sa.false(), nullable=False))


def downgrade() -> None:
    with op.batch_alter_table('enseignant', schema=None) as batch_op:
        batch_op.drop_column('enseigne_anglais')
        batch_op.drop_column('enseigne_maths')
