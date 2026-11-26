"""Classes pilotes : exception à EX.4, accordée par un administrateur (issue #176, décision SEC-D6).

Un domaine actif mais fermé au public (le français pendant le pilote de janvier 2027) n'est accessible qu'aux élèves
des classes inscrites ici. Le contrôle lui-même est fait côté API, route par route, par
`permissions.refus_acces_classe` ; ce module ne fait que tenir la liste.

- Créer une classe pilote : seul chemin qui crée une classe dans un domaine fermé ; l'habilitation du professeur
  reste exigée (`ouvrir_classe`).
- Autoriser une classe existante (par exemple une classe dont le domaine a été fermé depuis).
- Révoquer : l'accès des élèves est coupé immédiatement, séance en cours comprise ; rien n'est supprimé.

Une autorisation suit la classe, pas l'état du domaine : si le domaine devient public, elle est sans effet ; s'il
est refermé ensuite, elle s'applique de nouveau. La révoquer explicitement si ce n'est pas voulu.

Chaque opération est journalisée. Réservé à l'administrateur (second facteur obligatoire en production).
"""
# Issue #176 — Accès au français réservé aux classes pilotes (Claude)

from datetime import datetime

from fastapi import APIRouter, HTTPException, Response, status
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app import journal, permissions
from app.auth import AdminCourant, SessionDB
from app.db import models
from app.referentiel import Niveau, domaine_de
from app.routes.enseignants import ouvrir_classe
from app.routes.familles import ClasseAdminCreation

router = APIRouter(prefix="/admin/classes-pilotes", tags=["administration"])

Motif = Field(min_length=3, max_length=200)


class ClassePiloteCreation(ClasseAdminCreation):
    motif: str = Motif


class AutorisationPilote(BaseModel):
    motif: str = Motif


class ClassePiloteVue(BaseModel):
    classe_id: int
    code: str
    niveau: Niveau
    domaine_code: str
    domaine: str
    enseignant: str
    nb_eleves: int
    motif: str
    accordee_le: datetime
    accordee_par: str | None


def _vue(session: SessionDB, p: models.ClassePilote) -> ClassePiloteVue:
    c = p.classe
    nb = session.scalar(select(func.count()).select_from(models.Eleve).where(models.Eleve.classe_id == c.id))
    return ClassePiloteVue(
        classe_id=c.id, code=c.code, niveau=c.niveau, domaine_code=c.domaine_code,
        domaine=permissions.LIBELLES.get(c.domaine_code, c.domaine_code), enseignant=c.enseignant.nom, nb_eleves=nb,
        motif=p.motif, accordee_le=p.accordee_le, accordee_par=p.accordee_par.nom if p.accordee_par else None,
    )


def _domaine_ferme_et_actif(session: SessionDB, code: str) -> None:
    """Une classe pilote n'a de sens que dans un domaine actif mais fermé au public."""
    d = session.get(models.DomainePedagogique, code)
    if d is None or not d.actif:
        raise HTTPException(status.HTTP_409_CONFLICT,
                            f"{permissions.LIBELLES.get(code, code)} n'est pas actif : activez-le d'abord (sans le rendre public).")
    if d.public:
        raise HTTPException(status.HTTP_409_CONFLICT,
                            f"{d.libelle} est déjà ouvert au public : une classe ordinaire suffit.")


@router.get("", response_model=list[ClassePiloteVue])
def lister(_: AdminCourant, session: SessionDB) -> list[ClassePiloteVue]:
    pilotes = session.scalars(select(models.ClassePilote).order_by(models.ClassePilote.accordee_le))
    return [_vue(session, p) for p in pilotes]


@router.post("", response_model=ClassePiloteVue, status_code=status.HTTP_201_CREATED)
def creer(corps: ClassePiloteCreation, admin: AdminCourant, session: SessionDB) -> ClassePiloteVue:
    """Crée la classe pilote pour un professeur habilité, et l'autorise, en une seule opération."""
    _domaine_ferme_et_actif(session, domaine_de(corps.matiere, corps.niveau))
    enseignant = session.get(models.Enseignant, corps.enseignant_id)
    if enseignant is None or not enseignant.actif:
        raise HTTPException(422, "Choisissez un professeur actif.")
    classe = ouvrir_classe(session, enseignant, corps, pilote=True)
    pilote = models.ClassePilote(classe=classe, accordee_par=admin, motif=corps.motif)
    session.add(pilote)
    session.flush()
    journal.noter(session, admin, "creer", "classe-pilote", classe.id,
                  apres={"code": classe.code, "domaine": classe.domaine_code, "enseignant": enseignant.id, "motif": corps.motif})
    session.commit()
    return _vue(session, pilote)


@router.post("/{classe_id}", response_model=ClassePiloteVue, status_code=status.HTTP_201_CREATED)
def autoriser(classe_id: int, corps: AutorisationPilote, admin: AdminCourant, session: SessionDB) -> ClassePiloteVue:
    """Autorise une classe existante, non archivée, d'un domaine actif mais fermé au public."""
    classe = session.get(models.Classe, classe_id)
    if classe is None or classe.archivee_le is not None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Classe introuvable.")
    _domaine_ferme_et_actif(session, classe.domaine_code)
    if session.get(models.ClassePilote, classe.id):
        raise HTTPException(status.HTTP_409_CONFLICT, "Cette classe est déjà une classe pilote.")
    # Le professeur de la classe doit toujours enseigner cette matière à ce niveau.
    matiere = permissions.MATIERES.get(classe.domaine_code, "")
    refus = permissions.refus_matiere_enseignee(classe.enseignant, matiere, classe.domaine_code, classe.niveau)
    if refus or not classe.enseignant.actif:
        raise HTTPException(status.HTTP_409_CONFLICT,
                            f"Le professeur de {classe.code} n'est plus habilité ou plus actif : {refus or 'compte inactif'}.")
    pilote = models.ClassePilote(classe=classe, accordee_par=admin, motif=corps.motif)
    session.add(pilote)
    try:
        session.flush()
    except IntegrityError:  # deux autorisations simultanées de la même classe
        session.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "Cette classe est déjà une classe pilote.") from None
    journal.noter(session, admin, "autoriser", "classe-pilote", classe.id,
                  apres={"code": classe.code, "domaine": classe.domaine_code, "motif": corps.motif})
    session.commit()
    return _vue(session, pilote)


@router.delete("/{classe_id}", status_code=status.HTTP_204_NO_CONTENT)
def revoquer(classe_id: int, admin: AdminCourant, session: SessionDB) -> Response:
    """Coupe l'accès des élèves de la classe ; la classe, ses élèves et leur travail sont conservés."""
    pilote = session.get(models.ClassePilote, classe_id)
    if pilote is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Classe pilote introuvable.")
    journal.noter(session, admin, "revoquer", "classe-pilote", classe_id,
                  avant={"code": pilote.classe.code, "domaine": pilote.classe.domaine_code, "motif": pilote.motif})
    session.delete(pilote)
    session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
