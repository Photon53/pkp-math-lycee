"""Prévalidation IA des exercices, réservée aux administrateurs (ticket #48).

Deux portes, et deux seulement :
- `/admin/prevalidation-ia` (jeton administrateur + permission `prevalidation.ia`) : demander un contrôle sur des
  exercices choisis ou un échantillon, lire les rapports, gérer les jetons du compte de service, mesurer l'essai ;
- `/service-ia` (jeton du compte de service) : lister les demandes en attente, lire l'énoncé PUIS le corrigé
  proposé, déposer le rapport. Ce jeton n'ouvre aucune autre route (format distinct des jetons humains : 401).

Garanties :
- la prévalidation ne touche ni au contenu de l'exercice, ni à `statut_validation` (validation humaine), ni à la
  publication ; aucune route du service ne sait écrire ailleurs que dans `prevalidation_ia` ;
- `version` est l'empreinte du contenu examiné : toute modification ultérieure rend le rapport obsolète, et un
  rapport déposé pour une version dépassée est refusé (409) ;
- chaque appel du service, accepté ou refusé, est inscrit dans `acces_service_ia` ; chaque action d'un
  administrateur, dans le journal d'administration ;
- aucun professeur, validateur non administrateur, parent ou élève n'atteint ces routes (403 ou 401).
"""

import hashlib
import hmac
import json
import secrets
from datetime import UTC, datetime, timedelta
from functools import lru_cache
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import func, or_, select
from sqlalchemy.orm import selectinload

from app import exemplaires, journal, limitation, permissions, programmes
from app.auth import AdminCourant, Identifiants, SessionDB
from app.config import settings
from app.db import models
from app.referentiel import Niveau, StatutValidation

Resultat = Literal["aucune-anomalie", "a-revoir", "erreur-detectee", "incertain"]
Statut = Literal["en-attente", "terminee", "annulee"]
ValeurVerite = Literal["erronee", "correcte"]

PREFIXE_JETON = "pkpia"
TAILLE_MAX_RAPPORT = 60_000  # octets, une fois sérialisé

# Ce qui décide de ce que l'élève voit et de ce qui est compté juste : la moindre différence change la version.
CHAMPS_VERSION = (
    "competence_id", "enonce", "type", "solution", "forme", "difficulte", "correction", "gabarit", "competences_secondaires",
)


def _maintenant() -> datetime:
    return datetime.now(UTC)


def _utc(d: datetime | None) -> datetime | None:
    return d.replace(tzinfo=UTC) if d is not None and d.tzinfo is None else d


def version_de(q: models.Question) -> str:
    """Empreinte SHA-256 du contenu de l'exercice (énoncé, réponse, correction, paramètres…)."""
    contenu = {c: getattr(q, c) for c in CHAMPS_VERSION}
    contenu["type"] = q.type.value
    contenu["forme"] = q.forme.value if q.forme else None
    return hashlib.sha256(json.dumps(contenu, sort_keys=True, ensure_ascii=False, default=str).encode()).hexdigest()


@lru_cache(maxsize=1)
def _attendus() -> dict:
    """Référentiel officiel (attendus du BO) ; vide s'il n'est pas lisible : le contrôle de programme le signalera."""
    try:
        return programmes.charger(verifier_empreintes=False).attendus
    except Exception:  # noqa: BLE001 — dossier absent ou invalide : on sert le reste
        return {}


# ================================================================================================= schémas


class Echantillon(BaseModel):
    model_config = ConfigDict(extra="forbid")
    taille: Annotated[int, Field(ge=1, le=50)] = 10
    domaine: str | None = None
    niveau: Niveau | None = None
    statut_validation: StatutValidation | None = None
    # Exercices dont l'auteur déclaré est une IA (« Brouillon IA (Claude) »…) : le mot « IA » dans le nom de l'auteur.
    auteur_ia: bool = True


class Demande(BaseModel):
    model_config = ConfigDict(extra="forbid")
    question_ids: Annotated[list[int], Field(max_length=50)] = []
    echantillon: Echantillon | None = None

    @model_validator(mode="after")
    def _un_des_deux(self):
        if bool(self.question_ids) == (self.echantillon is not None):
            raise ValueError("Choisissez des exercices ou un échantillon (l'un ou l'autre).")
        return self


class Anomalie(BaseModel):
    model_config = ConfigDict(extra="forbid")
    element: Literal["enonce", "reponse", "etape", "methode", "niveau", "competence", "ambiguite", "autre"]
    etape: Annotated[int, Field(ge=1, le=50)] | None = None
    gravite: Literal["erreur", "a-revoir", "mineure"]
    description: Annotated[str, Field(min_length=3, max_length=2000)]
    justification: Annotated[str, Field(max_length=4000)] = ""
    suggestion: Annotated[str, Field(max_length=4000)] = ""


class AvisEtape(BaseModel):
    model_config = ConfigDict(extra="forbid")
    numero: Annotated[int, Field(ge=1, le=50)]
    avis: Literal["correcte", "a-revoir", "erronee", "non-verifiee"]
    remarque: Annotated[str, Field(max_length=2000)] = ""


class Verification(BaseModel):
    model_config = ConfigDict(extra="forbid")
    nature: Literal["calcul", "symbolique", "programme", "autre"]
    description: Annotated[str, Field(min_length=3, max_length=1000)]
    outil: Annotated[str, Field(max_length=100)] = ""
    issue: Literal["confirme", "ecart", "impossible", "incertain"]


class RapportIA(BaseModel):
    """Rapport déposé par le vérificateur pour une demande, et une seule version de l'exercice."""

    model_config = ConfigDict(extra="forbid")
    version: Annotated[str, Field(min_length=64, max_length=64)]
    modele: Annotated[str, Field(min_length=1, max_length=100)]
    version_modele: Annotated[str, Field(max_length=100)] | None = None
    resultat: Resultat
    synthese: Annotated[str, Field(min_length=3, max_length=3000)]
    # Réponse trouvée en résolvant l'énoncé seul, avant de lire le corrigé proposé.
    reponse_independante: Annotated[str, Field(max_length=2000)] = ""
    remarques_enonce: Annotated[str, Field(max_length=4000)] = ""
    remarques_reponse: Annotated[str, Field(max_length=4000)] = ""
    controle_programme: Annotated[str, Field(max_length=2000)] = ""
    etapes: Annotated[list[AvisEtape], Field(max_length=50)] = []
    anomalies: Annotated[list[Anomalie], Field(max_length=30)] = []
    verifications: Annotated[list[Verification], Field(max_length=20)] = []
    points_incertains: Annotated[list[Annotated[str, Field(min_length=3, max_length=1000)]], Field(max_length=20)] = []

    @model_validator(mode="after")
    def _coherent(self):
        graves = {a.gravite for a in self.anomalies}
        if self.resultat == "aucune-anomalie" and graves & {"erreur", "a-revoir"}:
            raise ValueError("« Aucune anomalie détectée » est incompatible avec une anomalie à revoir ou une erreur.")
        if self.resultat == "erreur-detectee" and "erreur" not in graves:
            raise ValueError("« Erreur détectée » demande au moins une anomalie de gravité « erreur ».")
        if self.resultat == "a-revoir" and not self.anomalies:
            raise ValueError("« À revoir » demande au moins une anomalie décrite.")
        if self.resultat == "incertain" and not self.points_incertains:
            raise ValueError("Un avis incertain précise ce qui n'a pas pu être vérifié (`points_incertains`).")
        return self


class AvisVerite(BaseModel):
    model_config = ConfigDict(extra="forbid")
    verite: ValeurVerite | None
    commentaire: Annotated[str, Field(max_length=1000)] = ""


class NouveauCompte(BaseModel):
    model_config = ConfigDict(extra="forbid")
    nom: Annotated[str, Field(min_length=2, max_length=80)]
    duree_jours: Annotated[int, Field(ge=1)] = 30


class Renouvellement(BaseModel):
    model_config = ConfigDict(extra="forbid")
    duree_jours: Annotated[int, Field(ge=1)] = 30


# ================================================================================================= vues


def _vue_compte(c: models.CompteServiceIA) -> dict:
    maintenant = _maintenant()
    etat = "revoque" if c.revoque_le else "expire" if _utc(c.expire_le) <= maintenant else "actif"
    return {
        "id": c.id, "nom": c.nom, "prefixe": c.prefixe, "etat": etat, "cree_le": _utc(c.cree_le), "expire_le": _utc(c.expire_le),
        "revoque_le": _utc(c.revoque_le), "dernier_usage_le": _utc(c.dernier_usage_le),
    }


def _resume(p: models.PrevalidationIA) -> dict:
    q = p.question
    chapitre = q.competence.chapitre
    rapport = p.rapport or {}
    return {
        "id": p.id, "lot": p.lot, "question_id": q.id, "question_code": q.code, "niveau": chapitre.niveau.value,
        "chapitre": chapitre.titre, "competence": q.competence.libelle, "statut": p.statut, "resultat": p.resultat,
        "version": p.version[:12], "obsolete": p.statut != "annulee" and version_de(q) != p.version,
        "demandee_par": p.demandee_par_nom, "demandee_le": _utc(p.demandee_le), "rendue_le": _utc(p.rendue_le),
        "modele": p.modele, "version_modele": p.version_modele, "nb_anomalies": len(rapport.get("anomalies", [])),
        "verite_humaine": p.verite_humaine,
    }


def _exemplaire(fonction, q: models.Question, tirage: dict | None):
    """Texte de l'exemplaire examiné ; si l'exercice a changé depuis (paramètres retirés), le texte brut."""
    try:
        return fonction(q, tirage)
    except Exception:  # noqa: BLE001 — rapport obsolète : on montre l'exercice tel qu'il est
        return fonction(q, None)


def _detail(p: models.PrevalidationIA) -> dict:
    q = p.question
    return {
        **_resume(p),
        "version_complete": p.version,
        "version_actuelle": version_de(q),
        "tirage": p.tirage,
        "enonce_lu_le": _utc(p.enonce_lu_le),
        "corrige_lu_le": _utc(p.corrige_lu_le),
        "compte_service": p.compte_service.nom if p.compte_service else None,
        "rapport": p.rapport,
        "verite_commentaire": p.verite_commentaire,
        "verite_par": p.verite_par_nom,
        "verite_le": _utc(p.verite_le),
        # L'exercice tel qu'il est aujourd'hui, et son statut de validation humaine (que la prévalidation ne change pas).
        "exercice": {
            "enonce": _exemplaire(exemplaires.enonce, q, p.tirage), "solution": _exemplaire(exemplaires.solution, q, p.tirage),
            "type": q.type.value, "statut_validation": q.statut_validation.value, "valide_par": q.valide_par, "auteur": q.auteur,
        },
    }


# ================================================================================================= administrateurs


def admin_ia(admin: AdminCourant) -> models.Enseignant:
    """Administrateur (rôle revérifié en base par `admin_courant`) ayant la permission `prevalidation.ia`."""
    refus = permissions.exiger(admin, "prevalidation.ia")
    if refus:
        raise HTTPException(status.HTTP_403_FORBIDDEN, refus)
    return admin


AdminIA = Annotated[models.Enseignant, Depends(admin_ia)]
router_admin = APIRouter(prefix="/admin/prevalidation-ia", tags=["prevalidation-ia"])


def _prevalidation(session: SessionDB, prevalidation_id: int) -> models.PrevalidationIA:
    p = session.get(models.PrevalidationIA, prevalidation_id)
    if p is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Prévalidation introuvable.")
    return p


def _echantillon(session: SessionDB, e: Echantillon) -> list[models.Question]:
    filtres = [models.Question.archivee.is_(False)]
    if e.domaine:
        filtres.append(models.Chapitre.domaine_code == e.domaine)
    if e.niveau:
        filtres.append(models.Chapitre.niveau == e.niveau)
    if e.statut_validation:
        filtres.append(models.Question.statut_validation == e.statut_validation)
    if e.auteur_ia:
        motif = func.lower(models.Question.auteur)
        filtres.append(or_(motif.like("% ia %"), motif.like("% ia"), motif.like("ia %"), motif == "ia"))
    candidats = session.scalars(
        select(models.Question).join(models.Competence).join(models.Chapitre).where(*filtres).order_by(models.Question.id)
    ).all()
    # Échantillon varié : tiré au hasard, au plus deux exercices par compétence tant que c'est possible.
    melange = secrets.SystemRandom().sample(candidats, len(candidats))
    retenus, par_competence = [], {}
    for limite in (2, None):
        for q in melange:
            if len(retenus) >= e.taille:
                break
            if q in retenus or (limite and par_competence.get(q.competence_id, 0) >= limite):
                continue
            retenus.append(q)
            par_competence[q.competence_id] = par_competence.get(q.competence_id, 0) + 1
    return retenus


@router_admin.post("/demandes", status_code=status.HTTP_201_CREATED)
def demander(corps: Demande, admin: AdminIA, session: SessionDB) -> dict:
    """Lance la prévalidation d'exercices choisis ou d'un échantillon : une demande par exercice, dans un même lot."""
    if corps.echantillon is not None:
        if corps.echantillon.domaine and corps.echantillon.domaine not in permissions.LIBELLES:
            raise HTTPException(422, f"Domaine inconnu : {corps.echantillon.domaine}.")
        questions = _echantillon(session, corps.echantillon)
    else:
        ids = list(dict.fromkeys(corps.question_ids))
        questions = [session.get(models.Question, i) for i in ids]
        if None in questions:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Exercice introuvable.")
    if not questions:
        raise HTTPException(422, "Aucun exercice ne correspond à ces critères.")
    if len(questions) > settings.prevalidation_ia_max_par_lot:
        raise HTTPException(422, f"Au plus {settings.prevalidation_ia_max_par_lot} exercices par lot.")
    lot = f"L-{_maintenant():%Y%m%d}-{secrets.token_hex(3).upper()}"
    creees, deja = [], []
    for q in questions:
        version = version_de(q)
        en_cours = session.scalar(
            select(models.PrevalidationIA).where(
                models.PrevalidationIA.question_id == q.id,
                models.PrevalidationIA.statut == "en-attente",
                models.PrevalidationIA.version == version,
            )
        )
        if en_cours:
            deja.append(en_cours.id)
            continue
        p = models.PrevalidationIA(
            question=q, lot=lot, version=version, tirage=exemplaires.nouveau_tirage(q), statut="en-attente",
            demandee_par_id=admin.id, demandee_par_nom=admin.nom,
        )
        session.add(p)
        creees.append(p)
    session.flush()
    journal.noter(
        session, admin, "demander", "prevalidation_ia",
        apres={"lot": lot, "questions": [p.question_id for p in creees], "deja_en_attente": deja},
    )
    session.commit()
    return {"lot": lot, "creees": [_resume(p) for p in creees], "deja_en_attente": deja}


@router_admin.get("")
def lister(
    _: AdminIA,
    session: SessionDB,
    statut: Statut | None = None,
    resultat: Resultat | None = None,
    lot: str | None = None,
    question_id: int | None = None,
    obsolete: bool | None = None,
) -> list[dict]:
    requete = (
        select(models.PrevalidationIA)
        .options(selectinload(models.PrevalidationIA.question).selectinload(models.Question.competence).selectinload(models.Competence.chapitre))
        .order_by(models.PrevalidationIA.id.desc())
        .limit(500)
    )
    if statut:
        requete = requete.where(models.PrevalidationIA.statut == statut)
    if resultat:
        requete = requete.where(models.PrevalidationIA.resultat == resultat)
    if lot:
        requete = requete.where(models.PrevalidationIA.lot == lot.strip())
    if question_id is not None:
        requete = requete.where(models.PrevalidationIA.question_id == question_id)
    vues = [_resume(p) for p in session.scalars(requete)]
    return [v for v in vues if obsolete is None or v["obsolete"] == obsolete]


@router_admin.get("/bilan")
def bilan(_: AdminIA, session: SessionDB, lot: str | None = None) -> dict:
    """Mesure de l'essai sur un lot relu par des professeurs : erreurs connues détectées, manquées, fausses alertes."""
    requete = select(models.PrevalidationIA).where(models.PrevalidationIA.statut == "terminee")
    if lot:
        requete = requete.where(models.PrevalidationIA.lot == lot.strip())
    rendues = session.scalars(requete).all()
    par_resultat = {r: 0 for r in ("aucune-anomalie", "a-revoir", "erreur-detectee", "incertain")}
    for p in rendues:
        par_resultat[p.resultat] += 1
    alerte = {"a-revoir", "erreur-detectee"}
    erronees = [p for p in rendues if p.verite_humaine == "erronee"]
    correctes = [p for p in rendues if p.verite_humaine == "correcte"]
    non_detectees = [p.id for p in erronees if p.resultat == "aucune-anomalie"]
    return {
        "rendues": len(rendues),
        "par_resultat": par_resultat,
        "relues_par_un_professeur": len(erronees) + len(correctes),
        "erronees_connues": len(erronees),
        "detectees": sum(p.resultat in alerte for p in erronees),
        "non_detectees": len(non_detectees),
        "non_detectees_ids": non_detectees,
        "incertaines_sur_erronees": sum(p.resultat == "incertain" for p in erronees),
        "correctes_connues": len(correctes),
        "fausses_alertes": sum(p.resultat in alerte for p in correctes),
        "taux_non_detection": round(len(non_detectees) / len(erronees), 3) if erronees else None,
    }


@router_admin.get("/comptes")
def lister_comptes(_: AdminIA, session: SessionDB) -> list[dict]:
    return [_vue_compte(c) for c in session.scalars(select(models.CompteServiceIA).order_by(models.CompteServiceIA.id.desc()))]


def _emettre(session: SessionDB, admin: models.Enseignant, nom: str, duree_jours: int) -> tuple[models.CompteServiceIA, str]:
    if duree_jours > settings.service_ia_duree_max_j:
        raise HTTPException(422, f"Durée maximale d'un jeton : {settings.service_ia_duree_max_j} jours.")
    compte = models.CompteServiceIA(
        nom=nom.strip(), empreinte=secrets.token_hex(32), prefixe="", cree_par_id=admin.id,
        expire_le=_maintenant() + timedelta(days=duree_jours),
    )
    session.add(compte)
    session.flush()
    jeton = f"{PREFIXE_JETON}_{compte.id}_{secrets.token_urlsafe(32)}"
    compte.empreinte, compte.prefixe = _empreinte(jeton), jeton[:18]
    return compte, jeton


@router_admin.post("/comptes", status_code=status.HTTP_201_CREATED)
def creer_compte(corps: NouveauCompte, admin: AdminIA, session: SessionDB) -> dict:
    """Le jeton n'est montré qu'ici, une fois : à ranger dans le gestionnaire de secrets du service IA."""
    compte, jeton = _emettre(session, admin, corps.nom, corps.duree_jours)
    journal.noter(session, admin, "creer", "compte_service_ia", compte.id, apres={"nom": compte.nom, "prefixe": compte.prefixe})
    session.commit()
    return {"compte": _vue_compte(compte), "jeton": jeton}


def _compte(session: SessionDB, compte_id: int) -> models.CompteServiceIA:
    c = session.get(models.CompteServiceIA, compte_id)
    if c is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Compte de service introuvable.")
    return c


def _revoquer(c: models.CompteServiceIA, admin: models.Enseignant) -> None:
    if c.revoque_le is None:
        c.revoque_le, c.revoque_par_id = _maintenant(), admin.id


@router_admin.post("/comptes/{compte_id}/revoquer")
def revoquer(compte_id: int, admin: AdminIA, session: SessionDB) -> dict:
    c = _compte(session, compte_id)
    _revoquer(c, admin)
    journal.noter(session, admin, "revoquer", "compte_service_ia", c.id)
    session.commit()
    return _vue_compte(c)


@router_admin.post("/comptes/{compte_id}/renouveler", status_code=status.HTTP_201_CREATED)
def renouveler(compte_id: int, corps: Renouvellement, admin: AdminIA, session: SessionDB) -> dict:
    """Rotation : un nouveau jeton est émis et l'ancien révoqué dans la même transaction."""
    ancien = _compte(session, compte_id)
    _revoquer(ancien, admin)
    compte, jeton = _emettre(session, admin, ancien.nom, corps.duree_jours)
    journal.noter(session, admin, "renouveler", "compte_service_ia", compte.id, avant={"remplace": ancien.id})
    session.commit()
    return {"compte": _vue_compte(compte), "jeton": jeton}


@router_admin.get("/acces")
def acces(_: AdminIA, session: SessionDB, compte_id: int | None = None) -> list[dict]:
    requete = select(models.AccesServiceIA).order_by(models.AccesServiceIA.id.desc()).limit(300)
    if compte_id is not None:
        requete = requete.where(models.AccesServiceIA.compte_service_id == compte_id)
    return [
        {"id": a.id, "compte_id": a.compte_service_id, "action": a.action, "prevalidation_id": a.prevalidation_id,
         "code_http": a.code_http, "ip": a.ip, "le": _utc(a.le)}
        for a in session.scalars(requete)
    ]


@router_admin.get("/{prevalidation_id}")
def lire(prevalidation_id: int, _: AdminIA, session: SessionDB) -> dict:
    return _detail(_prevalidation(session, prevalidation_id))


@router_admin.post("/{prevalidation_id}/annuler")
def annuler(prevalidation_id: int, admin: AdminIA, session: SessionDB) -> dict:
    p = _prevalidation(session, prevalidation_id)
    if p.statut != "en-attente":
        raise HTTPException(status.HTTP_409_CONFLICT, "Seule une demande en attente peut être annulée.")
    p.statut = "annulee"
    journal.noter(session, admin, "annuler", "prevalidation_ia", p.id)
    session.commit()
    return _detail(p)


@router_admin.post("/{prevalidation_id}/verite")
def noter_verite(prevalidation_id: int, corps: AvisVerite, admin: AdminIA, session: SessionDB) -> dict:
    """Ce que les professeurs savent de l'exercice (lot d'essai à erreurs connues) : sert au bilan, rien d'autre."""
    p = _prevalidation(session, prevalidation_id)
    avant = journal.instantane(p, ("verite_humaine", "verite_commentaire"))
    p.verite_humaine = corps.verite
    p.verite_commentaire = corps.commentaire.strip() or None
    p.verite_par_nom, p.verite_le = (admin.nom, _maintenant()) if corps.verite else (None, None)
    journal.noter(session, admin, "noter_verite", "prevalidation_ia", p.id, avant, journal.instantane(p, ("verite_humaine", "verite_commentaire")))
    session.commit()
    return _detail(p)


# ================================================================================================= compte de service


def _empreinte(jeton: str) -> str:
    """HMAC du jeton par la clé du serveur : une copie de la base seule ne permet pas de le retrouver ni de le forger."""
    return hmac.new(settings.secret_key.encode(), jeton.encode(), hashlib.sha256).hexdigest()


def _tracer(session, compte_id, action, code, ip, prevalidation_id=None) -> None:
    session.add(models.AccesServiceIA(compte_service_id=compte_id, action=action, prevalidation_id=prevalidation_id, code_http=code, ip=ip))


def compte_service(request: Request, identifiants: Identifiants, session: SessionDB) -> models.CompteServiceIA:
    ip = limitation.adresse_ip(request)
    limitation.verifier((limitation.service_ia_refus_par_ip, ip))
    jeton = identifiants.credentials if identifiants else ""
    compte = None
    if jeton.startswith(f"{PREFIXE_JETON}_"):
        compte = session.scalar(select(models.CompteServiceIA).where(models.CompteServiceIA.empreinte == _empreinte(jeton)))
    if compte is None or compte.revoque_le is not None or _utc(compte.expire_le) <= _maintenant():
        limitation.service_ia_refus_par_ip.enregistrer(ip)
        _tracer(session, compte.id if compte else None, "refus:" + request.url.path[-30:], 401, ip)
        session.commit()
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Jeton de service invalide, expiré ou révoqué.", headers={"WWW-Authenticate": "Bearer"})
    cle = str(compte.id)
    limitation.verifier((limitation.service_ia_par_compte, cle))
    limitation.service_ia_par_compte.enregistrer(cle)
    compte.dernier_usage_le = _maintenant()
    return compte


CompteService = Annotated[models.CompteServiceIA, Depends(compte_service)]
router_service = APIRouter(prefix="/service-ia", tags=["service-ia"])


def _demande(session: SessionDB, compte: models.CompteServiceIA, request: Request, prevalidation_id: int, action: str):
    """Demande en attente et à jour, sinon refus (tracé) : hors périmètre, la demande n'existe pas."""
    p = session.get(models.PrevalidationIA, prevalidation_id)
    ip = limitation.adresse_ip(request)
    if p is None or p.statut != "en-attente":
        _tracer(session, compte.id, action, 404, ip, prevalidation_id)
        session.commit()
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Aucune demande en attente sous ce numéro.")
    if version_de(p.question) != p.version:
        _tracer(session, compte.id, action, 409, ip, prevalidation_id)
        session.commit()
        raise HTTPException(status.HTTP_409_CONFLICT, "L'exercice a été modifié depuis la demande : prévalidation obsolète.")
    return p


@router_service.get("/prevalidations")
def a_traiter(compte: CompteService, request: Request, session: SessionDB, limite: Annotated[int, Query(ge=1, le=20)] = 10) -> list[dict]:
    attente = session.scalars(
        select(models.PrevalidationIA).where(models.PrevalidationIA.statut == "en-attente").order_by(models.PrevalidationIA.id)
    ).all()
    a_jour = [p for p in attente if version_de(p.question) == p.version][:limite]
    _tracer(session, compte.id, "lister", 200, limitation.adresse_ip(request))
    session.commit()
    return [{"id": p.id, "lot": p.lot, "question_id": p.question_id, "version": p.version, "demandee_le": _utc(p.demandee_le)} for p in a_jour]


@router_service.get("/prevalidations/{prevalidation_id}/enonce")
def enonce(prevalidation_id: int, compte: CompteService, request: Request, session: SessionDB) -> dict:
    """Étape 1 : l'énoncé et son contexte (niveau, compétences, attendus du programme), sans réponse ni correction."""
    p = _demande(session, compte, request, prevalidation_id, "enonce")
    q = p.question
    competence, chapitre = q.competence, q.competence.chapitre
    referentiel = _attendus()
    attendus = []
    for code in competence.attendus or []:
        trouve = referentiel.get(code)
        attendus.append(
            {"code": code, "programme": trouve[0], "theme": trouve[1].titre, "type": trouve[2].type.value, "texte": trouve[2].texte}
            if trouve else {"code": code, "introuvable": True}
        )
    secondaires = session.scalars(
        select(models.Competence).where(models.Competence.code.in_(q.competences_secondaires or []))
    ).all()
    p.enonce_lu_le = p.enonce_lu_le or _maintenant()
    p.compte_service_id = compte.id
    _tracer(session, compte.id, "enonce", 200, limitation.adresse_ip(request), p.id)
    session.commit()
    return {
        "prevalidation_id": p.id, "lot": p.lot, "version": p.version,
        "exercice": {
            "id": q.id, "code": q.code, "type": q.type.value, "forme": q.forme.value if q.forme else None,
            "difficulte": q.difficulte, "enonce": exemplaires.enonce(q, p.tirage), "valeurs_variables": p.tirage,
        },
        "contexte": {
            "domaine": chapitre.domaine_code, "niveau": chapitre.niveau.value, "parcours": chapitre.parcours.value,
            "chapitre": chapitre.titre,
            "competence": {"code": competence.code, "libelle": competence.libelle, "objectifs": competence.objectifs or [],
                           "prerequis": competence.prerequis or []},
            "competences_secondaires": [{"code": c.code, "libelle": c.libelle} for c in secondaires],
            "attendus_du_programme": attendus,
        },
        "consigne": "Résoudre l'énoncé seul et noter sa réponse avant de demander le corrigé proposé.",
    }


@router_service.get("/prevalidations/{prevalidation_id}/corrige")
def corrige(prevalidation_id: int, compte: CompteService, request: Request, session: SessionDB) -> dict:
    """Étape 2, après l'énoncé : la réponse attendue et la correction proposées, pour les comparer."""
    p = _demande(session, compte, request, prevalidation_id, "corrige")
    if p.enonce_lu_le is None:
        _tracer(session, compte.id, "corrige", 409, limitation.adresse_ip(request), p.id)
        session.commit()
        raise HTTPException(status.HTTP_409_CONFLICT, "Lisez et résolvez d'abord l'énoncé, sans le corrigé.")
    q = p.question
    p.corrige_lu_le = p.corrige_lu_le or _maintenant()
    _tracer(session, compte.id, "corrige", 200, limitation.adresse_ip(request), p.id)
    session.commit()
    return {
        "prevalidation_id": p.id, "version": p.version,
        "reponse_attendue": exemplaires.solution(q, p.tirage),
        "correction": exemplaires.correction(q, p.tirage) if q.correction else None,
        "gabarit": q.gabarit,
        "methodes_du_cours": q.competence.methodes or [],
        "erreurs_frequentes_du_cours": q.competence.erreurs_frequentes or [],
    }


@router_service.post("/prevalidations/{prevalidation_id}/rapport", status_code=status.HTTP_201_CREATED)
def deposer(prevalidation_id: int, corps: RapportIA, compte: CompteService, request: Request, session: SessionDB) -> dict:
    """Dépose le rapport : la demande passe « terminée ». L'exercice et sa validation humaine ne changent pas."""
    p = _demande(session, compte, request, prevalidation_id, "rapport")
    ip = limitation.adresse_ip(request)
    if corps.version != p.version:
        _tracer(session, compte.id, "rapport", 409, ip, p.id)
        session.commit()
        raise HTTPException(status.HTTP_409_CONFLICT, "Ce rapport ne porte pas sur la version demandée de l'exercice.")
    rapport = corps.model_dump(exclude={"version", "modele", "version_modele", "resultat"})
    if len(json.dumps(rapport, ensure_ascii=False).encode()) > TAILLE_MAX_RAPPORT:
        _tracer(session, compte.id, "rapport", 413, ip, p.id)
        session.commit()
        raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, "Rapport trop volumineux.")
    p.statut, p.resultat, p.rapport = "terminee", corps.resultat, rapport
    p.modele, p.version_modele = corps.modele.strip(), (corps.version_modele or "").strip() or None
    p.rendue_le, p.compte_service_id = _maintenant(), compte.id
    _tracer(session, compte.id, "rapport", 201, ip, p.id)
    session.commit()
    return {"id": p.id, "statut": p.statut, "resultat": p.resultat}
