"""élèves existants rattachés à un enfant : les élèves créés par un professeur avant les familles deviennent
des enfants (même prénom, niveau de leur classe, même identifiant et même code), que l'administrateur et les
professeurs retrouvent par la recherche et peuvent inscrire dans d'autres classes et groupes

Revision ID: 0027
Revises: 0026
Create Date: 2026-11-05 09:00:00.000000

Une inscription de maths reliée à d'autres (`groupe_id`, même élève dans plusieurs parcours) donne un seul
enfant. Les comptes parents rattachés à l'élève suivent l'enfant. Rien n'est supprimé : les cartes et
connexions existantes continuent de fonctionner.
"""

import re
import secrets
import unicodedata
from collections.abc import Sequence
from datetime import UTC, datetime

import sqlalchemy as sa
from alembic import op

revision: str = '0027'
down_revision: str | None = '0026'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

ALPHABET = "abcdefghjkmnpqrstuvwxyz23456789"

enfant = sa.table(
    'enfant', sa.column('id', sa.Integer), sa.column('prenom', sa.String), sa.column('nom', sa.String),
    sa.column('niveau', sa.String), sa.column('identifiant', sa.String), sa.column('code_hash', sa.String),
    sa.column('cree_le', sa.DateTime(timezone=True)),
)
eleve = sa.table(
    'eleve', sa.column('id', sa.Integer), sa.column('prenom', sa.String), sa.column('classe_id', sa.Integer),
    sa.column('code_hash', sa.String), sa.column('identifiant', sa.String), sa.column('groupe_id', sa.Integer),
    sa.column('enfant_id', sa.Integer), sa.column('cree_le', sa.DateTime(timezone=True)),
)
eleve_anglais = sa.table(
    'eleve_anglais', sa.column('id', sa.Integer), sa.column('prenom', sa.String), sa.column('groupe_id', sa.Integer),
    sa.column('code_hash', sa.String), sa.column('identifiant', sa.String), sa.column('enfant_id', sa.Integer),
    sa.column('cree_le', sa.DateTime(timezone=True)),
)
classe = sa.table('classe', sa.column('id', sa.Integer), sa.column('niveau', sa.String))
groupe_anglais = sa.table('groupe_anglais', sa.column('id', sa.Integer), sa.column('niveau', sa.String))
parent_eleve = sa.table('parent_eleve', sa.column('parent_id', sa.Integer), sa.column('eleve_id', sa.Integer))
parent_enfant = sa.table('parent_enfant', sa.column('parent_id', sa.Integer), sa.column('enfant_id', sa.Integer))


def _identifiant(prenom: str, pris: set[str]) -> str:
    base = unicodedata.normalize("NFKD", prenom).encode("ascii", "ignore").decode().lower()
    base = re.sub(r"[^a-z]+", "", base)[:20] or "eleve"
    while True:
        identifiant = f"{base}-{''.join(secrets.choice(ALPHABET) for _ in range(4))}"
        if identifiant not in pris:
            pris.add(identifiant)
            return identifiant


def upgrade() -> None:
    bind = op.get_bind()
    pris = {i for t in (enfant, eleve, eleve_anglais) for (i,) in bind.execute(sa.select(t.c.identifiant)) if i}
    maintenant = datetime.now(UTC)

    def creer(prenom, niveau, identifiant, code_hash, cree_le) -> int:
        """Nouvel enfant ; l'identifiant de l'élève est repris s'il en avait un (sa carte reste valable)."""
        return bind.execute(
            enfant.insert().values(
                prenom=(prenom or "Élève")[:50], nom="", niveau=niveau,
                identifiant=identifiant or _identifiant(prenom or "", pris), code_hash=code_hash,
                cree_le=cree_le or maintenant,
            ).returning(enfant.c.id)
        ).scalar_one()

    # Maths : une inscription seule, ou un groupe d'inscriptions reliées, donne un enfant.
    lignes = bind.execute(
        sa.select(eleve.c.id, eleve.c.prenom, eleve.c.code_hash, eleve.c.identifiant, eleve.c.groupe_id,
                  eleve.c.cree_le, classe.c.niveau)
        .join(classe, classe.c.id == eleve.c.classe_id)
        .where(eleve.c.enfant_id.is_(None))
        .order_by(eleve.c.id)
    ).all()
    groupes: dict[object, list] = {}
    for ligne in lignes:
        groupes.setdefault(("g", ligne.groupe_id) if ligne.groupe_id is not None else ("e", ligne.id), []).append(ligne)
    for membres in groupes.values():
        tete = membres[0]  # la plus ancienne inscription donne le prénom et le niveau
        identifiant = next((m.identifiant for m in membres if m.identifiant), None)
        code_hash = next((m.code_hash for m in membres if m.code_hash), None)
        enfant_id = creer(tete.prenom, tete.niveau, identifiant, code_hash, tete.cree_le)
        ids = [m.id for m in membres]
        bind.execute(eleve.update().where(eleve.c.id.in_(ids)).values(enfant_id=enfant_id, code_hash=code_hash))
        parents = {p for (p,) in bind.execute(sa.select(parent_eleve.c.parent_id).where(parent_eleve.c.eleve_id.in_(ids)))}
        for parent_id in sorted(parents):
            bind.execute(parent_enfant.insert().values(parent_id=parent_id, enfant_id=enfant_id))

    # Anglais : chaque élève d'un groupe d'anglais devient un enfant du niveau du groupe.
    lignes = bind.execute(
        sa.select(eleve_anglais.c.id, eleve_anglais.c.prenom, eleve_anglais.c.code_hash, eleve_anglais.c.identifiant,
                  eleve_anglais.c.cree_le, groupe_anglais.c.niveau)
        .join(groupe_anglais, groupe_anglais.c.id == eleve_anglais.c.groupe_id)
        .where(eleve_anglais.c.enfant_id.is_(None))
        .order_by(eleve_anglais.c.id)
    ).all()
    for ligne in lignes:
        enfant_id = creer(ligne.prenom, ligne.niveau, ligne.identifiant, ligne.code_hash, ligne.cree_le)
        bind.execute(eleve_anglais.update().where(eleve_anglais.c.id == ligne.id).values(enfant_id=enfant_id))


def downgrade() -> None:
    # Les enfants créés ici ne se distinguent plus des autres : on ne défait pas le rattachement.
    pass
