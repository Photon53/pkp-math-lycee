# Issue #184 — Vue élève simulée (Claude)
"""Vue élève simulée : entrée depuis l'espace professeur ou administrateur, puis espace élève ordinaire.

- `/enseignants/simulation/…` (jeton professeur) et `/admin/simulation/…` (jeton administrateur) listent les
  classes autorisées et ouvrent un élève fictif ; la réponse est un jeton **élève** ordinaire, qui ne donne accès
  à aucune route professeur ou administrateur ;
- `/eleves/moi/simulation/…` (jeton de l'élève fictif) décrit le contexte, réinitialise le travail fictif ou ferme
  la simulation. Un vrai élève y reçoit 404.
"""

from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, HTTPException, Response, status

from app import permissions, simulation
from app.auth import ELEVE, AdminCourant, EleveCourant, EnseignantCourant, SessionDB
from app.db import models
from app.routes.eleves import _info
from app.schemas import ContexteSimulation, DemandeSimulation, InfoSimulation, JetonSimulation
from app.security import creer_jeton, version_mot_de_passe

router = APIRouter(tags=["simulation"])


def _contexte(session: SessionDB, acteur: models.Enseignant, role: str, classe: models.Classe) -> ContexteSimulation:
    motif = permissions.refus_acces_classe(session, classe)
    return ContexteSimulation(
        classe_id=classe.id, code_classe=classe.code, niveau=classe.niveau, parcours=classe.parcours,
        matiere=permissions.MATIERES.get(classe.domaine_code, "maths"),
        domaine=permissions.LIBELLES.get(classe.domaine_code, classe.domaine_code),
        professeur=classe.enseignant.nom, ouverte_aux_eleves=motif is None, motif_fermeture=motif,
        en_cours=simulation.eleve_fictif(session, acteur, role, classe) is not None,
    )


def _info_simulation(eleve: models.Eleve, expire_le: datetime | None = None) -> InfoSimulation:
    classe = eleve.classe
    return InfoSimulation(
        role=eleve.simulation_role, classe_id=classe.id, code_classe=classe.code, niveau=classe.niveau,
        matiere=permissions.MATIERES.get(classe.domaine_code, "maths"),
        domaine=permissions.LIBELLES.get(classe.domaine_code, classe.domaine_code), expire_le=expire_le,
    )


def _jeton(eleve: models.Eleve) -> JetonSimulation:
    expire_le = datetime.now(UTC) + timedelta(hours=simulation.DUREE_JETON_H)
    jeton = creer_jeton(ELEVE, eleve.id, simulation.DUREE_JETON_H, version_mot_de_passe(eleve.code_hash))
    return JetonSimulation(jeton=jeton, eleve=_info(eleve), simulation=_info_simulation(eleve, expire_le))


def _ouvrir(session: SessionDB, acteur: models.Enseignant, role: str, classe_id: int) -> JetonSimulation:
    classe = session.get(models.Classe, classe_id)
    # 404 identique pour une classe inexistante ou hors du périmètre : rien n'est révélé.
    if classe is None or simulation.refus_classe(acteur, role, classe):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Classe introuvable.")
    eleve = simulation.ouvrir(session, acteur, role, classe)
    session.commit()
    return _jeton(eleve)


@router.get("/enseignants/simulation/classes", response_model=list[ContexteSimulation])
def classes_professeur(enseignant: EnseignantCourant, session: SessionDB) -> list[ContexteSimulation]:
    """Les classes actives du professeur, dans lesquelles il peut voir l'espace comme un élève."""
    role = simulation.ENSEIGNANT
    return [_contexte(session, enseignant, role, c) for c in simulation.classes_simulables(session, enseignant, role)]


@router.post("/enseignants/simulation", response_model=JetonSimulation)
def ouvrir_professeur(corps: DemandeSimulation, enseignant: EnseignantCourant, session: SessionDB) -> JetonSimulation:
    return _ouvrir(session, enseignant, simulation.ENSEIGNANT, corps.classe_id)


@router.get("/admin/simulation/classes", response_model=list[ContexteSimulation])
def classes_admin(admin: AdminCourant, session: SessionDB) -> list[ContexteSimulation]:
    """Toutes les classes actives (périmètre de l'administration)."""
    role = simulation.ADMIN
    return [_contexte(session, admin, role, c) for c in simulation.classes_simulables(session, admin, role)]


@router.post("/admin/simulation", response_model=JetonSimulation)
def ouvrir_admin(corps: DemandeSimulation, admin: AdminCourant, session: SessionDB) -> JetonSimulation:
    return _ouvrir(session, admin, simulation.ADMIN, corps.classe_id)


def _fictif(eleve: models.Eleve) -> models.Eleve:
    if not simulation.est_fictif(eleve):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Aucune simulation en cours.")
    return eleve


@router.get("/eleves/moi/simulation", response_model=InfoSimulation)
def ma_simulation(eleve: EleveCourant) -> InfoSimulation:
    return _info_simulation(_fictif(eleve))


@router.post("/eleves/moi/simulation/reinitialiser", response_model=JetonSimulation)
def reinitialiser(eleve: EleveCourant, session: SessionDB) -> JetonSimulation:
    """Efface les réponses, la progression et le travail fictifs : la simulation repart d'un élève nouveau."""
    nouveau = simulation.reinitialiser(session, _fictif(eleve))
    session.commit()
    return _jeton(nouveau)


@router.post("/eleves/moi/simulation/fermer", status_code=status.HTTP_204_NO_CONTENT)
def fermer(eleve: EleveCourant, session: SessionDB) -> Response:
    """Retour à l'espace d'origine : le jeton de simulation ne sert plus, dans aucun onglet."""
    simulation.fermer(session, _fictif(eleve))
    session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
