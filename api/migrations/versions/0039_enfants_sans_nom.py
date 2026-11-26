"""enfants sans nom de famille : colonne enfant.nom retirée, compteur des identifiants, identifiants sans casse

Issue #87 — Décision RGPD-1 : retirer le nom des enfants, identifiant prénom + numéro (Claude).

EFFACEMENT IRRÉVERSIBLE : le nom de famille (ou l'initiale) de chaque enfant est supprimé, ainsi que :
- les noms affichés qui en dérivaient dans les classes et groupes (« Lina D. », « Lina Dupont ») : remplacés par
  l'identifiant de l'enfant, unique sur la plateforme (« lina-k7m4 ») ;
- la clé « nom » des entrées du journal d'administration portant sur un enfant.
Faire une sauvegarde avant la mise à jour (`boussole-sauvegarde --sauvegarder --motif avant-deploiement`, T-04).
Les identifiants déjà émis ne changent pas : aucune carte n'est à redistribuer. Le retour arrière recrée une
colonne `nom` VIDE (les noms effacés ne reviennent pas).

Revision ID: 0039
Revises: 0038
Create Date: 2026-11-15 14:00:00.000000
"""

import re
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = '0039'
down_revision: str | None = '0038'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABLES_IDENTIFIANT = ('enfant', 'eleve', 'eleve_anglais')
# Doit rester égal à app.enfants.LONGUEUR_CLE_COMPTEUR (clé du compteur : base en minuscules, 35 caractères).
LONGUEUR_CLE = 35
NOUVEAU_FORMAT = re.compile(r'^([A-Za-z]+)([0-9]+)$')


def upgrade() -> None:
    bind = op.get_bind()

    # 1. Noms affichés dérivés du nom de famille → identifiant de l'enfant (unique : aucun conflit possible).
    for table in ('eleve', 'eleve_anglais'):
        bind.execute(sa.text(
            f"UPDATE {table} SET prenom = (SELECT e.identifiant FROM enfant e WHERE e.id = {table}.enfant_id) "
            f"WHERE enfant_id IS NOT NULL AND lower(prenom) <> "
            f"(SELECT lower(e.prenom) FROM enfant e WHERE e.id = {table}.enfant_id)"
        ))

    # 2. Journal d'administration : la clé « nom » des enfants disparaît des états avant et après.
    journal = sa.table('journal_admin', sa.column('id', sa.Integer), sa.column('objet', sa.String),
                       sa.column('avant', sa.JSON), sa.column('apres', sa.JSON))
    for id_, avant, apres in bind.execute(sa.select(journal.c.id, journal.c.avant, journal.c.apres)
                                          .where(journal.c.objet == 'enfant')).all():
        nettoye = {c: ({k: v for k, v in d.items() if k != 'nom'} if isinstance(d, dict) else d)
                   for c, d in (('avant', avant), ('apres', apres))}
        if nettoye != {'avant': avant, 'apres': apres}:
            bind.execute(journal.update().where(journal.c.id == id_).values(**nettoye))

    # 3. La colonne elle-même.
    with op.batch_alter_table('enfant') as batch:
        batch.drop_column('nom')

    # 4. Compteur des numéros (jamais réattribués). Repris des identifiants au nouveau format déjà présents.
    op.create_table(
        'compteur_identifiant',
        sa.Column('base', sa.String(length=40), nullable=False),
        sa.Column('dernier', sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint('base', name=op.f('pk_compteur_identifiant')),
    )
    derniers: dict[str, int] = {}
    for table in TABLES_IDENTIFIANT:
        for (identifiant,) in bind.execute(sa.text(f"SELECT identifiant FROM {table} WHERE identifiant IS NOT NULL")):
            m = NOUVEAU_FORMAT.match(identifiant)
            if m:
                cle = m.group(1).lower()[:LONGUEUR_CLE]
                derniers[cle] = max(derniers.get(cle, 0), int(m.group(2)))
    if derniers:
        compteur = sa.table('compteur_identifiant', sa.column('base', sa.String), sa.column('dernier', sa.Integer))
        op.bulk_insert(compteur, [{'base': b, 'dernier': n} for b, n in sorted(derniers.items())])

    # 5. Identifiant comparé sans casse : « Lina1 » et « lina1 » ne peuvent pas coexister.
    for table in TABLES_IDENTIFIANT:
        op.create_index(f'uq_{table}_identifiant_minuscules', table, [sa.text('lower(identifiant)')], unique=True)


def downgrade() -> None:
    for table in TABLES_IDENTIFIANT:
        op.drop_index(f'uq_{table}_identifiant_minuscules', table_name=table)
    op.drop_table('compteur_identifiant')
    with op.batch_alter_table('enfant') as batch:  # vide : les noms effacés ne reviennent pas
        batch.add_column(sa.Column('nom', sa.String(length=50), server_default='', nullable=False))
