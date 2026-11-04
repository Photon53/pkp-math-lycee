"""Familles : l'administrateur crée les comptes parents et leurs enfants (une carte par enfant) ; le
professeur, ou l'administrateur, inscrit ensuite chaque enfant dans ses classes de maths et ses groupes
d'anglais ; le parent suit ses enfants et peut renouveler leur accès.
"""

from typing import Annotated

from fastapi import APIRouter, HTTPException, Response, status
from pkp_engine import Niveau
from pydantic import BaseModel, Field
from sqlalchemy import select

from app import enfants, journal, parents
from app.auth import AdminCourant, EnseignantAnglais, EnseignantCourant, ParentCourant, SessionDB
from app.db import models
from app.routes.anglais import ELEVES_PAR_GROUPE, _mon_groupe
from app.routes.enseignants import _ma_classe, _resume_classe, ouvrir_classe
from app.schemas import (
    AjoutEnfants,
    CarteEnfant,
    ClasseCreation,
    ClasseResume,
    CodeEnfantFamille,
    EnfantChoix,
    EnfantFamille,
    EnfantModification,
    EnfantSaisi,
    NouvelleCarte,
    ParentCreation,
    ProgressionAnglaisEnfant,
    ResultatAjoutEnfants,
    SuiviEnfant,
)
from app.security import hacher_code_eleve, normaliser_code, probleme_code_choisi

router = APIRouter(tags=["familles"])

# Un professeur ne parcourt pas la liste des enfants : il cherche par prénom, nom ou identifiant.
RECHERCHE_MIN = 2


# --- Administrateur : familles et enfants ----------------------------------------------------------


class FamilleNouvelle(ParentCreation):
    enfants: Annotated[list[EnfantSaisi], Field(min_length=1, max_length=enfants.MAX_ENFANTS_PAR_FAMILLE)]


class FamilleOuverte(BaseModel):
    """Le mot de passe provisoire et les cartes ne sont donnés qu'une fois, à la création."""

    parent_id: int
    email: str
    mot_de_passe_provisoire: str | None
    cartes: list[CarteEnfant]


class ClasseAdminCreation(ClasseCreation):
    enseignant_id: int


def _par(admin: models.Enseignant) -> str:
    return f"Administrateur : {admin.nom}"


def _enfant(session: SessionDB, enfant_id: int) -> models.Enfant:
    enfant = session.get(models.Enfant, enfant_id)
    if enfant is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Enfant introuvable.")
    return enfant


def _parent(session: SessionDB, parent_id: int) -> models.Parent:
    parent = session.get(models.Parent, parent_id)
    if parent is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Parent introuvable.")
    return parent


@router.post("/admin/familles", response_model=FamilleOuverte, status_code=status.HTTP_201_CREATED)
def creer_famille(corps: FamilleNouvelle, admin: AdminCourant, session: SessionDB) -> FamilleOuverte:
    """Compte parent (mot de passe provisoire, à changer à la première connexion) et ses enfants, chacun avec
    son niveau et sa carte. Si l'adresse a déjà un compte, les enfants s'ajoutent à cette famille."""
    parent = session.scalar(select(models.Parent).where(models.Parent.email == corps.email))
    provisoire = None
    if parent is None:
        parent = models.Parent(email=corps.email, mot_de_passe_hash="", mdp_provisoire=True)
        provisoire = parents.reinitialiser(parent)
        session.add(parent)
    if len(parent.famille) + len(corps.enfants) > enfants.MAX_ENFANTS_PAR_FAMILLE:
        raise HTTPException(422, f"Une famille compte au plus {enfants.MAX_ENFANTS_PAR_FAMILLE} enfants.")
    cartes = []
    for saisi in corps.enfants:
        enfant, code = enfants.creer(session, saisi.prenom, saisi.nom, saisi.niveau)
        parent.famille.append(enfant)
        cartes.append(enfants.carte(enfant, code))
    session.flush()
    journal.noter(session, admin, "creer-famille", "parent", parent.id,
                  apres={"enfants": [c.id for c in cartes], "compte_cree": provisoire is not None})
    session.commit()
    return FamilleOuverte(parent_id=parent.id, email=parent.email, mot_de_passe_provisoire=provisoire, cartes=cartes)


@router.get("/admin/parents/{parent_id}/famille", response_model=list[EnfantFamille])
def famille(parent_id: int, _: AdminCourant, session: SessionDB) -> list[EnfantFamille]:
    parent = _parent(session, parent_id)
    return [enfants.decrire(e) for e in sorted(parent.famille, key=lambda e: e.prenom)]


@router.post("/admin/parents/{parent_id}/famille", response_model=CarteEnfant, status_code=status.HTTP_201_CREATED)
def ajouter_enfant(parent_id: int, corps: EnfantSaisi, admin: AdminCourant, session: SessionDB) -> CarteEnfant:
    parent = _parent(session, parent_id)
    if len(parent.famille) >= enfants.MAX_ENFANTS_PAR_FAMILLE:
        raise HTTPException(422, f"Une famille compte au plus {enfants.MAX_ENFANTS_PAR_FAMILLE} enfants.")
    enfant, code = enfants.creer(session, corps.prenom, corps.nom, corps.niveau)
    parent.famille.append(enfant)
    session.flush()
    journal.noter(session, admin, "ajouter-enfant", "parent", parent.id, apres={"enfant": enfant.id})
    session.commit()
    return enfants.carte(enfant, code)


@router.post("/admin/parents/{parent_id}/famille/{enfant_id}", response_model=list[EnfantFamille])
def rattacher_enfant(parent_id: int, enfant_id: int, admin: AdminCourant, session: SessionDB) -> list[EnfantFamille]:
    """Second responsable légal : il suit le même enfant (aucune nouvelle carte)."""
    parent, enfant = _parent(session, parent_id), _enfant(session, enfant_id)
    if enfant not in parent.famille:
        parent.famille.append(enfant)
        journal.noter(session, admin, "rattacher-enfant", "parent", parent.id, apres={"enfant": enfant.id})
        session.commit()
    return [enfants.decrire(e) for e in sorted(parent.famille, key=lambda e: e.prenom)]


@router.get("/admin/enfants", response_model=list[EnfantFamille])
def rechercher_enfants(
    _: AdminCourant, session: SessionDB, q: str = "", niveau: Niveau | None = None
) -> list[EnfantFamille]:
    return [enfants.decrire(e) for e in enfants.rechercher(session, niveau, q)]


@router.get("/admin/enfants/{enfant_id}", response_model=EnfantFamille)
def enfant_admin(enfant_id: int, _: AdminCourant, session: SessionDB) -> EnfantFamille:
    return enfants.decrire(_enfant(session, enfant_id))


@router.patch("/admin/enfants/{enfant_id}", response_model=EnfantFamille)
def modifier_enfant(enfant_id: int, corps: EnfantModification, admin: AdminCourant, session: SessionDB) -> EnfantFamille:
    """Correction du prénom ou du nom, ou passage au niveau supérieur. Les inscriptions déjà faites restent :
    le professeur les retire quand il le souhaite."""
    enfant = _enfant(session, enfant_id)
    avant = {"prenom": enfant.prenom, "nom": enfant.nom, "niveau": enfant.niveau.value}
    for champ in ("prenom", "nom", "niveau"):
        valeur = getattr(corps, champ)
        if valeur is not None:
            setattr(enfant, champ, valeur)
    journal.noter(session, admin, "modifier", "enfant", enfant.id, avant=avant,
                  apres={"prenom": enfant.prenom, "nom": enfant.nom, "niveau": enfant.niveau.value})
    session.commit()
    return enfants.decrire(enfant)


@router.post("/admin/enfants/{enfant_id}/carte", response_model=CarteEnfant)
def nouvelle_carte_admin(enfant_id: int, admin: AdminCourant, session: SessionDB) -> CarteEnfant:
    """Carte perdue : nouveau code (l'identifiant ne change pas) ; l'ancien cesse de fonctionner partout."""
    enfant = _enfant(session, enfant_id)
    code = enfants.nouveau_code(enfant)
    journal.noter(session, admin, "nouvelle-carte", "enfant", enfant.id)
    session.commit()
    return enfants.carte(enfant, code)


@router.delete("/admin/enfants/{enfant_id}", status_code=status.HTTP_204_NO_CONTENT)
def supprimer_enfant(enfant_id: int, confirmation: str, admin: AdminCourant, session: SessionDB) -> Response:
    """Efface l'enfant et toutes ses inscriptions (séances et réponses comprises), après saisie de son
    identifiant. Un compte parent qui n'a plus aucun enfant est supprimé (RGPD)."""
    enfant = _enfant(session, enfant_id)
    if confirmation.strip().lower() != enfant.identifiant:
        raise HTTPException(422, "Saisissez l'identifiant de l'enfant pour confirmer.")
    journal.noter(session, admin, "supprimer", "enfant", enfant.id,
                  avant={"parents": [p.id for p in enfant.parents], "inscriptions": len(enfant.inscriptions)})
    session.delete(enfant)
    parents.supprimer_orphelins(session)
    session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# --- Administrateur : classes et groupes ---------------------------------------------------------------


@router.post("/admin/classes", response_model=ClasseResume, status_code=status.HTTP_201_CREATED)
def creer_classe_admin(corps: ClasseAdminCreation, admin: AdminCourant, session: SessionDB) -> ClasseResume:
    """L'administrateur crée une classe pour un professeur de mathématiques."""
    enseignant = session.get(models.Enseignant, corps.enseignant_id)
    if enseignant is None or not enseignant.actif or not enseignant.enseigne_maths:
        raise HTTPException(422, "Choisissez un professeur de mathématiques actif.")
    classe = ouvrir_classe(session, enseignant, corps)
    journal.noter(session, admin, "creer", "classe", classe.id, apres={"code": classe.code, "enseignant": enseignant.id})
    session.commit()
    return _resume_classe(session, classe)


def _ajout(session: SessionDB, ids: list[int], inscrire) -> ResultatAjoutEnfants:
    ajoutes, refus = enfants.ajouter(session, ids, inscrire)
    session.commit()
    return ResultatAjoutEnfants(ajoutes=ajoutes, refus=refus)


@router.post("/admin/classes/{classe_id}/enfants", response_model=ResultatAjoutEnfants)
def inscrire_en_classe_admin(classe_id: int, corps: AjoutEnfants, admin: AdminCourant, session: SessionDB) -> ResultatAjoutEnfants:
    classe = session.get(models.Classe, classe_id)
    if classe is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Classe introuvable.")
    journal.noter(session, admin, "inscrire", "classe", classe.id, apres={"enfants": corps.enfant_ids})
    return _ajout(session, corps.enfant_ids, lambda e: enfants.inscrire_maths(session, e, classe))


@router.post("/admin/anglais/groupes/{groupe_id}/enfants", response_model=ResultatAjoutEnfants)
def inscrire_en_groupe_admin(groupe_id: int, corps: AjoutEnfants, admin: AdminCourant, session: SessionDB) -> ResultatAjoutEnfants:
    groupe = session.get(models.GroupeAnglais, groupe_id)
    if groupe is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Groupe introuvable.")
    _place(groupe, corps)
    journal.noter(session, admin, "inscrire", "groupe_anglais", groupe.id, apres={"enfants": corps.enfant_ids})
    return _ajout(session, corps.enfant_ids, lambda e: enfants.inscrire_anglais(session, e, groupe))


def _place(groupe: models.GroupeAnglais, corps: AjoutEnfants) -> None:
    if len(groupe.eleves) + len(set(corps.enfant_ids)) > ELEVES_PAR_GROUPE:
        raise HTTPException(422, f"Un groupe compte au plus {ELEVES_PAR_GROUPE} élèves.")


# --- Professeurs : ajouter des enfants à leurs classes et groupes ------------------------------------------


def _choix(session: SessionDB, niveau, q: str, deja: set[int]) -> list[EnfantChoix]:
    if len(q.strip()) < RECHERCHE_MIN:
        raise HTTPException(422, f"Saisissez au moins {RECHERCHE_MIN} lettres du prénom, du nom ou de l'identifiant.")
    return [enfants.choix(e, e.id in deja) for e in enfants.rechercher(session, niveau, q, limite=20)]


@router.get("/enseignants/classes/{classe_id}/enfants", response_model=list[EnfantChoix])
def chercher_pour_classe(classe_id: int, enseignant: EnseignantCourant, session: SessionDB, q: str = "") -> list[EnfantChoix]:
    """Enfants du niveau de la classe dont le prénom, le nom ou l'identifiant contient `q`."""
    classe = _ma_classe(session, classe_id, enseignant)
    return _choix(session, classe.niveau, q, {e.enfant_id for e in classe.eleves if e.enfant_id})


@router.post("/enseignants/classes/{classe_id}/enfants", response_model=ResultatAjoutEnfants)
def inscrire_en_classe(classe_id: int, corps: AjoutEnfants, enseignant: EnseignantCourant, session: SessionDB) -> ResultatAjoutEnfants:
    classe = _ma_classe(session, classe_id, enseignant)
    return _ajout(session, corps.enfant_ids, lambda e: enfants.inscrire_maths(session, e, classe))


@router.get("/anglais/groupes/{groupe_id}/enfants", response_model=list[EnfantChoix])
def chercher_pour_groupe(groupe_id: int, enseignant: EnseignantAnglais, session: SessionDB, q: str = "") -> list[EnfantChoix]:
    groupe = _mon_groupe(session, groupe_id, enseignant)
    return _choix(session, Niveau(groupe.niveau), q, {e.enfant_id for e in groupe.eleves if e.enfant_id})


@router.post("/anglais/groupes/{groupe_id}/enfants", response_model=ResultatAjoutEnfants)
def inscrire_en_groupe(groupe_id: int, corps: AjoutEnfants, enseignant: EnseignantAnglais, session: SessionDB) -> ResultatAjoutEnfants:
    groupe = _mon_groupe(session, groupe_id, enseignant)
    _place(groupe, corps)
    return _ajout(session, corps.enfant_ids, lambda e: enfants.inscrire_anglais(session, e, groupe))


# --- Parents : leurs enfants, toutes matières ----------------------------------------------------------


def _mon_enfant(parent: models.Parent, enfant_id: int) -> models.Enfant:
    enfant = next((e for e in parent.famille if e.id == enfant_id), None)
    if enfant is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Enfant introuvable.")
    return enfant


def _anglais(eleve: models.EleveAnglais) -> ProgressionAnglaisEnfant:
    faites = [p for p in eleve.progression if p.tentatives]
    scores = [p.meilleur_score / p.total for p in faites if p.total]
    return ProgressionAnglaisEnfant(
        groupe=eleve.groupe.nom, niveau=eleve.groupe.niveau, seances_faites=len(faites),
        score_moyen=sum(scores) / len(scores) if scores else None,
        i_can=sum(len(p.i_can or []) for p in eleve.progression),
    )


@router.get("/parents/famille", response_model=list[SuiviEnfant])
def ma_famille(parent: ParentCourant, session: SessionDB) -> list[SuiviEnfant]:
    """Chaque enfant de la famille : maths (par inscription), anglais, et le français à venir."""
    return [_suivi(session, e) for e in sorted(parent.famille, key=lambda e: e.prenom)]


def _suivi(session: SessionDB, enfant: models.Enfant) -> SuiviEnfant:
    maths = [parents.resume(session, e) for e in sorted(enfant.inscriptions, key=lambda e: e.classe.code)
             if e.classe.enseignant.actif]
    anglais = [_anglais(e) for e in enfant.inscriptions_anglais if e.groupe.enseignant.actif]
    return SuiviEnfant(enfant=enfants.decrire(enfant), matieres=enfants.matieres(), maths=maths, anglais=anglais)


@router.get("/parents/famille/{enfant_id}", response_model=SuiviEnfant)
def suivi_enfant(enfant_id: int, parent: ParentCourant, session: SessionDB) -> SuiviEnfant:
    return _suivi(session, _mon_enfant(parent, enfant_id))


@router.post("/parents/famille/{enfant_id}/acces", response_model=NouvelleCarte)
def renouveler_acces(enfant_id: int, corps: CodeEnfantFamille, parent: ParentCourant, session: SessionDB) -> NouvelleCarte:
    """Le parent réinitialise l'accès de son enfant : code choisi (8 à 16 caractères) ou tiré au hasard.
    L'ancien code et toutes les sessions ouvertes de l'enfant, dans toutes les matières, cessent de fonctionner."""
    enfant = _mon_enfant(parent, enfant_id)
    if not corps.code.strip():
        code = enfants.nouveau_code(enfant)
        session.commit()
        return NouvelleCarte(identifiant=enfant.identifiant, code=code)
    code = normaliser_code(corps.code)
    probleme = probleme_code_choisi(code, parents.mots_interdits(enfant))
    if probleme:
        raise HTTPException(422, probleme)
    enfant.code_hash = hacher_code_eleve(code)
    enfants.synchroniser(enfant)
    session.commit()
    return NouvelleCarte(identifiant=enfant.identifiant)
