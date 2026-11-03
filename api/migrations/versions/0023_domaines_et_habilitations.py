"""domaines pédagogiques, habilitations par domaine, historique des rattachements parents

Les comptes existants gardent leurs droits : chaque case cochée devient une habilitation, et chaque
administrateur devient validateur de Maths lycée, puisque ce sont eux qui valident les questions
aujourd'hui (CDC V2, EX.8). L'administrateur principal confirme ou retire ensuite, compte par compte.

Revision ID: 0023
Revises: 0022
Create Date: 2026-11-03 22:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = '0023'
down_revision: str | None = '0022'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

COLLEGE = ["6e", "5e", "4e", "3e"]
DOMAINES = [
    ("maths-college", "maths", "college", "Maths collège", COLLEGE, 1, False, False),
    ("maths-lycee", "maths", "lycee", "Maths lycée", ["2nde", "1re", "Tle"], 2, True, True),
    ("anglais-college", "anglais", "college", "Anglais collège", COLLEGE, 3, True, True),
    ("anglais-lycee", "anglais", "lycee", "Anglais lycée", ["2nde", "1re", "Tle"], 4, False, False),
    ("francais-college", "francais", "college", "Français collège", COLLEGE, 5, False, False),
    ("francais-lycee", "francais", "lycee", "Français lycée", ["2nde", "1re"], 6, False, False),
]


def upgrade() -> None:
    domaine = op.create_table(
        'domaine_pedagogique',
        sa.Column('code', sa.String(length=30), nullable=False),
        sa.Column('matiere', sa.String(length=20), nullable=False),
        sa.Column('cycle', sa.String(length=10), nullable=False),
        sa.Column('libelle', sa.String(length=60), nullable=False),
        sa.Column('niveaux', sa.JSON(), nullable=False),
        sa.Column('ordre', sa.Integer(), nullable=False),
        sa.Column('actif', sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column('public', sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.PrimaryKeyConstraint('code', name='pk_domaine_pedagogique'),
    )
    op.bulk_insert(domaine, [
        {"code": c, "matiere": m, "cycle": cy, "libelle": l, "niveaux": n, "ordre": o, "actif": a, "public": p}
        for c, m, cy, l, n, o, a, p in DOMAINES
    ])
    op.create_table(
        'habilitation',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('enseignant_id', sa.Integer(), nullable=False),
        sa.Column('role', sa.String(length=12), nullable=False),
        sa.Column('domaine_code', sa.String(length=30), nullable=False),
        sa.Column('niveau', sa.String(length=4), nullable=True),
        sa.Column('accordee_par_id', sa.Integer(), nullable=True),
        sa.Column('accordee_le', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("role IN ('professeur', 'validateur')", name='ck_habilitation_role'),
        sa.ForeignKeyConstraint(['enseignant_id'], ['enseignant.id'], name='fk_habilitation_enseignant_id_enseignant', ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['domaine_code'], ['domaine_pedagogique.code'], name='fk_habilitation_domaine_code_domaine_pedagogique', ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['accordee_par_id'], ['enseignant.id'], name='fk_habilitation_accordee_par_id_enseignant', ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id', name='pk_habilitation'),
    )
    op.create_index('ix_habilitation_enseignant_id', 'habilitation', ['enseignant_id'])
    op.create_table(
        'rattachement_parent',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('parent_id', sa.Integer(), nullable=False),
        sa.Column('eleve_id', sa.Integer(), nullable=False),
        sa.Column('action', sa.String(length=10), nullable=False),
        sa.Column('par', sa.String(length=120), nullable=False),
        sa.Column('le', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("action IN ('ajout', 'retrait')", name='ck_rattachement_parent_action'),
        sa.ForeignKeyConstraint(['parent_id'], ['parent.id'], name='fk_rattachement_parent_parent_id_parent', ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['eleve_id'], ['eleve.id'], name='fk_rattachement_parent_eleve_id_eleve', ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id', name='pk_rattachement_parent'),
    )
    op.create_index('ix_rattachement_parent_parent_id', 'rattachement_parent', ['parent_id'])
    op.create_index('ix_rattachement_parent_eleve_id', 'rattachement_parent', ['eleve_id'])

    # Droits actuels → habilitations (une par case cochée), sans rien retirer.
    for condition, role, domaine_code in [
        ("enseigne_maths", "professeur", "maths-lycee"),
        ("enseigne_anglais", "professeur", "anglais-college"),
        ("referent_anglais", "validateur", "anglais-college"),
        ("role = 'admin'", "validateur", "maths-lycee"),
    ]:
        op.execute(
            "INSERT INTO habilitation (enseignant_id, role, domaine_code, niveau) "
            f"SELECT id, '{role}', '{domaine_code}', NULL FROM enseignant WHERE {condition}"
        )
    # Les liens existants entrent dans l'historique, datés de la création du compte parent.
    op.execute(
        "INSERT INTO rattachement_parent (parent_id, eleve_id, action, par, le) "
        "SELECT pe.parent_id, pe.eleve_id, 'ajout', 'Rattachement antérieur à l''historique', p.cree_le "
        "FROM parent_eleve pe JOIN parent p ON p.id = pe.parent_id"
    )


def downgrade() -> None:
    op.drop_index('ix_rattachement_parent_eleve_id', table_name='rattachement_parent')
    op.drop_index('ix_rattachement_parent_parent_id', table_name='rattachement_parent')
    op.drop_table('rattachement_parent')
    op.drop_index('ix_habilitation_enseignant_id', table_name='habilitation')
    op.drop_table('habilitation')
    op.drop_table('domaine_pedagogique')
