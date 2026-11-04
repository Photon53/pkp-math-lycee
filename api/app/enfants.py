"""Enfants des familles : une personne, un niveau, une carte (identifiant + code personnel).

L'administrateur crée la famille (compte parent + enfants). Le professeur, ou l'administrateur, inscrit
ensuite l'enfant dans des classes de maths (une inscription par parcours : tronc commun, excellence, mise à
niveau…) et dans des groupes d'anglais. Toutes ces inscriptions partagent le code de l'enfant : il se
connecte une seule fois, puis choisit sa matière. Changer son code déconnecte toutes ses inscriptions.
"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import models
from app.referentiel import LIBELLES_PARCOURS
from app.security import generer_code_eleve, generer_identifiant, hacher_code_eleve

MAX_ENFANTS_PAR_FAMILLE = 8


class InscriptionImpossible(ValueError):
    pass


def identifiant_libre(session: Session, prenom: str) -> str:
    """Identifiant unique sur toute la plateforme : enfants, élèves de maths et d'anglais confondus."""
    while True:
        identifiant = generer_identifiant(prenom)
        if not any(
            session.scalar(select(modele.id).where(modele.identifiant == identifiant))
            for modele in (models.Enfant, models.Eleve, models.EleveAnglais)
        ):
            return identifiant


def nom_affiche(enfant: models.Enfant) -> str:
    return f"{enfant.prenom} {enfant.nom}".strip()


def synchroniser(enfant: models.Enfant) -> None:
    """Toutes les inscriptions prennent le code de l'enfant (et perdent leurs anciennes sessions)."""
    for inscription in (*enfant.inscriptions, *enfant.inscriptions_anglais):
        inscription.code_hash = enfant.code_hash


def nouveau_code(enfant: models.Enfant) -> str:
    """Tire un nouveau code, renvoyé en clair une seule fois ; l'ancien cesse de fonctionner partout."""
    code = generer_code_eleve()
    enfant.code_hash = hacher_code_eleve(code)
    synchroniser(enfant)
    return code


def creer(session: Session, prenom: str, nom: str, niveau) -> tuple[models.Enfant, str]:
    enfant = models.Enfant(prenom=prenom, nom=nom, niveau=niveau, identifiant=identifiant_libre(session, prenom))
    code = nouveau_code(enfant)
    session.add(enfant)
    session.flush()  # deux enfants créés ensemble ne tirent pas le même identifiant
    return enfant, code


def _nom_dans(enfant: models.Enfant, pris: set[str]) -> str:
    """Le prénom suffit dans la classe, sinon le prénom et l'initiale, sinon le prénom et le nom."""
    candidats = [enfant.prenom]
    if enfant.nom:
        candidats += [f"{enfant.prenom} {enfant.nom[0].upper()}.", nom_affiche(enfant)]
    for nom in candidats:
        if nom.casefold() not in {p.casefold() for p in pris}:
            return nom[:50]
    raise InscriptionImpossible(
        f"Un élève s'appelle déjà « {enfant.prenom} » dans ce groupe : ajoutez un nom à l'enfant pour les distinguer."
    )


def renommer(enfant: models.Enfant, prenom: str | None = None, nom: str | None = None) -> None:
    """Corrige le prénom ou le nom, et le nom affiché dans chacune de ses classes et chacun de ses groupes
    (avec l'initiale si un homonyme y est déjà). Un homonyme impossible à distinguer bloque la correction."""
    if prenom is not None:
        enfant.prenom = prenom
    if nom is not None:
        enfant.nom = nom
    for inscription in enfant.inscriptions:
        inscription.prenom = _nom_dans(enfant, {e.prenom for e in inscription.classe.eleves if e is not inscription})
    for inscription in enfant.inscriptions_anglais:
        inscription.prenom = _nom_dans(enfant, {e.prenom for e in inscription.groupe.eleves if e is not inscription})


class RenommageRefuse(PermissionError):
    pass


def renommer_inscription(inscription: models.Eleve | models.EleveAnglais, prenom: str, enseignant_id: int) -> None:
    """Le professeur corrige le prénom d'un de ses élèves. Si l'élève suit aussi les cours d'un autre
    professeur, la correction revient à l'administrateur (elle changerait le nom affiché chez ce collègue)."""
    enfant = inscription.enfant
    if enfant is None:
        voisins = inscription.classe.eleves if isinstance(inscription, models.Eleve) else inscription.groupe.eleves
        if any(e is not inscription and e.prenom.casefold() == prenom.casefold() for e in voisins):
            raise InscriptionImpossible(f"Un élève s'appelle déjà « {prenom} » ici.")
        inscription.prenom = prenom
        return
    autres = [e for e in enfant.inscriptions if e.classe.enseignant_id != enseignant_id] + [
        e for e in enfant.inscriptions_anglais if e.groupe.enseignant_id != enseignant_id
    ]
    if autres:
        raise RenommageRefuse(
            f"{enfant.prenom} suit aussi les cours d'un autre professeur : demandez la correction à l'administrateur."
        )
    renommer(enfant, prenom=prenom)


def inscrire_maths(session: Session, enfant: models.Enfant, classe: models.Classe) -> models.Eleve:
    if classe.niveau != enfant.niveau:
        raise InscriptionImpossible(
            f"{enfant.prenom} est en {enfant.niveau.value} : la classe {classe.code} est une classe de {classe.niveau.value}."
        )
    if any(e.enfant_id == enfant.id for e in classe.eleves):
        raise InscriptionImpossible(f"{enfant.prenom} est déjà inscrit dans la classe {classe.code}.")
    eleve = models.Eleve(
        prenom=_nom_dans(enfant, {e.prenom for e in classe.eleves}), classe=classe, enfant=enfant,
        code_hash=enfant.code_hash,
    )
    session.add(eleve)
    session.flush()
    return eleve


def inscrire_anglais(session: Session, enfant: models.Enfant, groupe: models.GroupeAnglais) -> models.EleveAnglais:
    if groupe.niveau != enfant.niveau.value:
        raise InscriptionImpossible(
            f"{enfant.prenom} est en {enfant.niveau.value} : le groupe « {groupe.nom} » est un groupe de {groupe.niveau}."
        )
    if any(e.enfant_id == enfant.id for e in groupe.eleves):
        raise InscriptionImpossible(f"{enfant.prenom} est déjà dans le groupe « {groupe.nom} ».")
    eleve = models.EleveAnglais(
        prenom=_nom_dans(enfant, {e.prenom for e in groupe.eleves}), groupe=groupe, enfant=enfant,
        code_hash=enfant.code_hash,
    )
    session.add(eleve)
    session.flush()
    return eleve


def libelle_parcours(classe: models.Classe) -> str:
    return LIBELLES_PARCOURS.get(classe.parcours, classe.parcours.value)


# --- Descriptions --------------------------------------------------------------------------------------

MATIERES = (("maths", "PKP Math"), ("anglais", "PKP Anglais"), ("francais", "PKP Français"))
# Le français a sa place dans tous les espaces ; son contenu viendra dans un lot dédié.
MATIERES_DISPONIBLES = {"maths", "anglais"}


def matieres():
    from app.schemas import Matiere

    return [Matiere(code=c, libelle=l, disponible=c in MATIERES_DISPONIBLES) for c, l in MATIERES]


def inscriptions_maths(enfant: models.Enfant, actives_seulement: bool = True):
    from app.schemas import InscriptionMaths

    return [
        InscriptionMaths(
            eleve_id=e.id, code_classe=e.classe.code, niveau=e.classe.niveau, parcours=e.classe.parcours,
            libelle_parcours=libelle_parcours(e.classe), enseignant=e.classe.enseignant.nom,
        )
        for e in sorted(enfant.inscriptions, key=lambda e: e.classe.code)
        if not actives_seulement or e.classe.enseignant.actif
    ]


def inscriptions_anglais(enfant: models.Enfant, actives_seulement: bool = True):
    from app.schemas import InscriptionAnglais

    return [
        InscriptionAnglais(eleve_id=e.id, groupe=e.groupe.nom, niveau=e.groupe.niveau, enseignant=e.groupe.enseignant.nom)
        for e in sorted(enfant.inscriptions_anglais, key=lambda e: e.groupe.nom.lower())
        if not actives_seulement or e.groupe.enseignant.actif
    ]


def decrire(enfant: models.Enfant):
    from app.schemas import EnfantFamille

    return EnfantFamille(
        id=enfant.id, prenom=enfant.prenom, nom=enfant.nom, niveau=enfant.niveau, identifiant=enfant.identifiant,
        a_un_code=enfant.code_hash is not None, derniere_connexion=enfant.derniere_connexion,
        maths=inscriptions_maths(enfant, actives_seulement=False), anglais=inscriptions_anglais(enfant, False),
    )


def espace(enfant: models.Enfant):
    from app.schemas import EspaceEnfant

    return EspaceEnfant(
        id=enfant.id, prenom=enfant.prenom, nom=enfant.nom, niveau=enfant.niveau, identifiant=enfant.identifiant,
        matieres=matieres(), maths=inscriptions_maths(enfant), anglais=inscriptions_anglais(enfant),
    )


def carte(enfant: models.Enfant, code: str):
    from app.schemas import CarteEnfant

    return CarteEnfant(
        id=enfant.id, prenom=enfant.prenom, nom=enfant.nom, niveau=enfant.niveau, identifiant=enfant.identifiant,
        code=code,
    )


def choix(enfant: models.Enfant, deja: bool = False):
    from app.schemas import EnfantChoix

    return EnfantChoix(id=enfant.id, nom=nom_affiche(enfant), niveau=enfant.niveau, identifiant=enfant.identifiant,
                       deja_inscrit=deja)


def rechercher(
    session: Session, niveau=None, q: str = "", limite: int = 50, sans_classe: bool = False
) -> list[models.Enfant]:
    """`sans_classe` : seulement les enfants inscrits nulle part (ni classe de maths, ni groupe d'anglais)."""
    filtres = []
    if sans_classe:
        filtres += [~models.Enfant.inscriptions.any(), ~models.Enfant.inscriptions_anglais.any()]
    if niveau is not None:
        filtres.append(models.Enfant.niveau == niveau)
    q = q.strip().lower()
    if q:
        motif = f"%{q}%"
        filtres.append(
            models.Enfant.prenom.ilike(motif) | models.Enfant.nom.ilike(motif) | models.Enfant.identifiant.ilike(motif)
        )
    return list(session.scalars(
        select(models.Enfant).where(*filtres).order_by(models.Enfant.prenom, models.Enfant.nom, models.Enfant.id)
        .limit(limite)
    ))


def ajouter(session: Session, ids: list[int], inscrire) -> tuple[list[str], list[str]]:
    """Inscrit chaque enfant avec `inscrire(enfant)` ; renvoie les noms ajoutés et les refus expliqués."""
    ajoutes, refus = [], []
    for enfant_id in dict.fromkeys(ids):
        enfant = session.get(models.Enfant, enfant_id)
        if enfant is None:
            refus.append(f"Enfant n° {enfant_id} introuvable.")
            continue
        try:
            inscrire(enfant)
            ajoutes.append(nom_affiche(enfant))
        except InscriptionImpossible as e:
            refus.append(str(e))
    return ajoutes, refus
