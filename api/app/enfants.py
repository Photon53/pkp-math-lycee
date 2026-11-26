"""Enfants des familles : une personne, un niveau, une carte (identifiant + code personnel).

L'administrateur crée la famille (compte parent + enfants). Le professeur, ou l'administrateur, inscrit
ensuite l'enfant dans des classes de maths (une inscription par parcours : tronc commun, excellence, mise à
niveau…) et dans des groupes d'anglais. Toutes ces inscriptions partagent le code de l'enfant : il se
connecte une seule fois, puis choisit sa matière. Changer son code déconnecte toutes ses inscriptions.
"""

from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, object_session

from app.db import models
from app.referentiel import LIBELLES_PARCOURS, est_principal
from app.security import LONGUEUR_IDENTIFIANT, base_identifiant, cle_identifiant, generer_code_eleve, hacher_code_eleve

MAX_ENFANTS_PAR_FAMILLE = 8


class InscriptionImpossible(ValueError):
    pass


# Numéro à 5 chiffres au plus : la base gardée est d'au moins 35 caractères, longueur de la clé du compteur.
# Deux identifiants de bases différentes ne peuvent donc jamais coïncider (voir identifiant_libre).
NUMERO_MAX = 99_999
LONGUEUR_CLE_COMPTEUR = LONGUEUR_IDENTIFIANT - len(str(NUMERO_MAX))
ESSAIS_IDENTIFIANT = 20


class IdentifiantsEpuises(RuntimeError):
    pass


def _numero_suivant(session: Session, cle: str) -> int:
    """Incrément atomique du compteur de cette base : deux créations simultanées n'obtiennent jamais le même
    numéro (la ligne reste verrouillée jusqu'à la fin de la transaction). Le compteur ne recule jamais."""
    for _ in range(ESSAIS_IDENTIFIANT):
        n = session.execute(
            update(models.CompteurIdentifiant).where(models.CompteurIdentifiant.base == cle)
            .values(dernier=models.CompteurIdentifiant.dernier + 1).returning(models.CompteurIdentifiant.dernier)
        ).scalar()
        if n is not None:
            return n
        try:
            with session.begin_nested():   # première fois pour cette base ; créée en même temps ailleurs : on recompte
                session.add(models.CompteurIdentifiant(base=cle, dernier=1))
            return 1
        except IntegrityError:
            continue
    raise IdentifiantsEpuises(f"Compteur d'identifiant « {cle} » indisponible.")


def identifiant_pris(session: Session, identifiant: str) -> bool:
    cle = cle_identifiant(identifiant)
    return any(
        session.scalar(select(modele.id).where(func.lower(modele.identifiant) == cle))
        for modele in (models.Enfant, models.Eleve, models.EleveAnglais)
    )


def identifiant_libre(session: Session, prenom: str) -> str:
    """Identifiant d'un nouveau compte (décision RGPD-1, #87) : prénom sans accent suivi d'un numéro, sans
    séparateur (« Lina1 », « Lea2 »), de 40 caractères au plus, unique sur toute la plateforme (enfants, élèves de
    maths et d'anglais, anciens identifiants « lina-k7m4 » compris), comparé sans casse ni accents.

    Le numéro vient d'un compteur par base normalisée (« Léa » et « Lea » partagent « lea ») qui n'est jamais
    remis à zéro : un numéro n'est pas réattribué, même après purge. La base est tronquée à 40 − (chiffres du
    numéro) ; la clé du compteur est la base en minuscules tronquée à 35 caractères, si bien que deux prénoms longs
    de même début partagent un compteur, et que l'identifiant reste unique. Un identifiant déjà pris (saisi à la
    main, ancienne base) est sauté : numéro suivant, nombre d'essais borné.
    """
    base = base_identifiant(prenom) or "Eleve"
    cle = base.lower()[:LONGUEUR_CLE_COMPTEUR]
    for _ in range(ESSAIS_IDENTIFIANT):
        n = _numero_suivant(session, cle)
        if n > NUMERO_MAX:
            break
        identifiant = base[: LONGUEUR_IDENTIFIANT - len(str(n))] + str(n)
        if not identifiant_pris(session, identifiant):
            return identifiant
    raise IdentifiantsEpuises(f"Aucun identifiant libre pour « {base} ».")


def nom_affiche(enfant: models.Enfant) -> str:
    """Un enfant n'a pas de nom de famille (RGPD-1) : son prénom, et son identifiant pour lever une ambiguïté."""
    return enfant.prenom


def synchroniser(enfant: models.Enfant) -> None:
    """Toutes les inscriptions prennent le code de l'enfant (et perdent leurs anciennes sessions)."""
    for inscription in (*enfant.inscriptions, *enfant.inscriptions_anglais):
        inscription.code_hash = enfant.code_hash


# La carte d'un enfant de famille vaut pour toutes ses inscriptions, chez tous ses professeurs : un professeur
# qui la régénérerait obtiendrait le code d'un enfant qu'il peut inscrire lui-même dans sa classe (#115).
CARTE_DE_FAMILLE = (
    "La carte de cet élève est celle de sa famille : un nouveau code se demande à l'administrateur "
    "ou à ses parents."
)


def nouveau_code(enfant: models.Enfant) -> str:
    """Tire un nouveau code, renvoyé en clair une seule fois ; l'ancien cesse de fonctionner partout."""
    code = generer_code_eleve()
    enfant.code_hash = hacher_code_eleve(code)
    synchroniser(enfant)
    return code


def creer(session: Session, prenom: str, niveau) -> tuple[models.Enfant, str]:
    enfant = models.Enfant(prenom=prenom, niveau=niveau, identifiant=identifiant_libre(session, prenom))
    code = nouveau_code(enfant)
    session.add(enfant)
    session.flush()  # deux enfants créés ensemble ne tirent pas le même identifiant
    return enfant, code


def _nom_dans(enfant: models.Enfant, pris: set[str]) -> str:
    """Le prénom suffit dans la classe ; sinon l'identifiant de l'enfant (« Lina2 »), unique sur la plateforme.
    Avec lui, la connexion prénom + code classe + code personnel (SEC-D1) reste possible pour chacun."""
    for nom in (enfant.prenom, enfant.identifiant):
        if nom.casefold() not in {p.casefold() for p in pris}:
            return nom[:50]
    raise InscriptionImpossible(f"Un élève s'appelle déjà « {enfant.prenom} » dans ce groupe.")


def renommer(enfant: models.Enfant, prenom: str) -> None:
    """Corrige le prénom, et le nom affiché dans chacune de ses classes et chacun de ses groupes (l'identifiant
    si un homonyme y est déjà). L'identifiant de connexion ne change pas : la carte reste valable."""
    enfant.prenom = prenom
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
    if classe.archivee_le is not None:
        raise InscriptionImpossible(f"La classe {classe.code} est archivée : rétablissez-la avant d'y inscrire un élève.")
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
    if groupe.archivee_le is not None:
        raise InscriptionImpossible(f"Le groupe « {groupe.nom} » est archivé : rétablissez-le avant d'y inscrire un élève.")
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
    if classe.domaine_code.startswith("francais-"):
        return "Français"
    return LIBELLES_PARCOURS.get(classe.parcours, classe.parcours.value)


# --- Descriptions --------------------------------------------------------------------------------------

MATIERES = (("maths", "Boussole Maths"), ("anglais", "Boussole Anglais"), ("francais", "Boussole Français"))
MATIERES_DISPONIBLES = {"maths", "anglais"}
# Boussole Français : disponible dès qu'un de ses domaines est public, ou que l'enfant y a une classe (F1).
DOMAINES_FRANCAIS = ("francais-college", "francais-lycee")


def francais_disponible(session: Session | None, enfant: models.Enfant | None = None) -> bool:
    if enfant is not None and inscriptions_francais(enfant):
        return True
    if session is None:
        return False
    return bool(session.scalar(select(func.count()).select_from(models.DomainePedagogique).where(
        models.DomainePedagogique.code.in_(DOMAINES_FRANCAIS), models.DomainePedagogique.public.is_(True))))


def matieres(session: Session | None = None, enfant: models.Enfant | None = None):
    from app.schemas import Matiere

    disponibles = MATIERES_DISPONIBLES | ({"francais"} if francais_disponible(session, enfant) else set())
    return [Matiere(code=c, libelle=l, disponible=c in disponibles) for c, l in MATIERES]


def _inscriptions_classes(enfant: models.Enfant, matiere: str, actives_seulement: bool):
    """Inscriptions de l'enfant dans les classes d'une matière (maths ou français : même espace élève)."""
    from app.schemas import InscriptionMaths

    return [
        InscriptionMaths(
            eleve_id=e.id, code_classe=e.classe.code, niveau=e.classe.niveau, parcours=e.classe.parcours,
            libelle_parcours=libelle_parcours(e.classe), enseignant=e.classe.enseignant.nom,
            principal=est_principal(e.classe.parcours), archivee=e.classe.archivee_le is not None,
        )
        for e in sorted(enfant.inscriptions, key=lambda e: e.classe.code)
        if e.classe.domaine_code.startswith(f"{matiere}-")
        and (not actives_seulement or (e.classe.enseignant.actif and e.classe.archivee_le is None))
    ]


def inscriptions_maths(enfant: models.Enfant, actives_seulement: bool = True):
    return _inscriptions_classes(enfant, "maths", actives_seulement)


def inscriptions_francais(enfant: models.Enfant, actives_seulement: bool = True):
    return _inscriptions_classes(enfant, "francais", actives_seulement)


def inscriptions_anglais(enfant: models.Enfant, actives_seulement: bool = True):
    from app.schemas import InscriptionAnglais

    return [
        InscriptionAnglais(eleve_id=e.id, groupe=e.groupe.nom, niveau=e.groupe.niveau, enseignant=e.groupe.enseignant.nom,
                           archivee=e.groupe.archivee_le is not None)
        for e in sorted(enfant.inscriptions_anglais, key=lambda e: e.groupe.nom.lower())
        if not actives_seulement or (e.groupe.enseignant.actif and e.groupe.archivee_le is None)
    ]


def decrire(enfant: models.Enfant):
    from app.schemas import EnfantFamille

    return EnfantFamille(
        id=enfant.id, prenom=enfant.prenom, niveau=enfant.niveau, identifiant=enfant.identifiant,
        a_un_code=enfant.code_hash is not None, derniere_connexion=enfant.derniere_connexion,
        maths=inscriptions_maths(enfant, actives_seulement=False), anglais=inscriptions_anglais(enfant, False),
        francais=inscriptions_francais(enfant, actives_seulement=False), bloque=enfant.bloque_le is not None,
    )


def espace(enfant: models.Enfant):
    from app.schemas import EspaceEnfant

    return EspaceEnfant(
        id=enfant.id, prenom=enfant.prenom, niveau=enfant.niveau, identifiant=enfant.identifiant,
        matieres=matieres(object_session(enfant), enfant), maths=inscriptions_maths(enfant),
        anglais=inscriptions_anglais(enfant), francais=inscriptions_francais(enfant),
    )


def carte(enfant: models.Enfant, code: str):
    from app.schemas import CarteEnfant

    return CarteEnfant(
        id=enfant.id, prenom=enfant.prenom, niveau=enfant.niveau, identifiant=enfant.identifiant,
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
            models.Enfant.prenom.ilike(motif) | models.Enfant.identifiant.ilike(motif)
        )
    return list(session.scalars(
        select(models.Enfant).where(*filtres).order_by(models.Enfant.prenom, models.Enfant.id)
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
