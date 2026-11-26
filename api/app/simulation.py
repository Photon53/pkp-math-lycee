# Issue #184 — Vue élève simulée (Claude)
"""Vue élève simulée : un professeur ou un administrateur parcourt l'espace élève avec un élève fictif.

Choix du premier lot (voir docs/SIMULATION-ELEVE.md) :
- l'élève fictif est une vraie inscription (`eleve`) dans la classe choisie, propre à l'acteur, à son rôle
  d'origine (professeur ou administrateur) et à la classe : l'espace élève existant, ses règles et ses contrôles
  serveur s'appliquent sans copie ;
- il n'a ni identifiant ni code personnel : on n'y entre que par l'espace de l'acteur, avec un jeton élève
  ordinaire (aucun pouvoir professeur ou administrateur) ;
- `app.db.simulation` le retire de toutes les autres requêtes (listes, statistiques, bilans parents, purge…) ;
- chaque requête revérifie que l'acteur a toujours le droit de simuler cette classe (`refus_acteur`).
"""

import secrets
from datetime import UTC, datetime, timedelta

from sqlalchemy import DateTime, func, select
from sqlalchemy.orm import Session

from app import journal, permissions
from app.db import models
from app.db.simulation import INCLURE
from app.referentiel import Role
from app.security import version_mot_de_passe

ENSEIGNANT, ADMIN = "enseignant", "admin"
ROLES = (ENSEIGNANT, ADMIN)
# Une simulation dure au plus deux heures : au-delà, l'acteur la relance depuis son espace.
DUREE_JETON_H = 2
# Élève fictif sans activité depuis ce délai (ou dont la classe est archivée) : supprimé par la purge.
JOURS_CONSERVATION = 30
_PREFIXE = "simulation"


def _empreinte(acteur: models.Enseignant) -> str:
    """Tient lieu de `code_hash` : jamais un code saisissable (connexion impossible), et liée au mot de passe de
    l'acteur, qui révoque la simulation en changeant."""
    return f"{_PREFIXE}${secrets.token_urlsafe(16)}${version_mot_de_passe(acteur.mot_de_passe_hash)}"


def est_fictif(eleve: models.Eleve) -> bool:
    return eleve.simulation_par_id is not None


def refus_classe(acteur: models.Enseignant, role: str, classe: models.Classe) -> str | None:
    """Motif du refus, ou None si l'acteur peut simuler un élève de cette classe dans ce rôle."""
    if classe.archivee_le is not None:
        return "Cette classe est archivée."
    if role == ENSEIGNANT:
        if classe.enseignant_id != acteur.id:
            return "Cette classe n'est pas l'une des vôtres."
        if not (acteur.enseigne_maths or permissions.enseigne_francais(acteur)):
            return "Réservé aux professeurs de mathématiques ou de français."
        return None
    if role == ADMIN:
        return None if acteur.role == Role.ADMIN else "Réservé aux administrateurs."
    return "Rôle de simulation inconnu."


def refus_acteur(session: Session, eleve: models.Eleve) -> str | None:
    """Contrôle d'un élève fictif à chaque requête : acteur actif, mot de passe inchangé, droit sur la classe."""
    acteur = session.get(models.Enseignant, eleve.simulation_par_id)
    if acteur is None or not acteur.actif or acteur.mdp_provisoire:
        return "Simulation fermée."
    if not eleve.code_hash or eleve.code_hash.rsplit("$", 1)[-1] != version_mot_de_passe(acteur.mot_de_passe_hash):
        return "Simulation fermée."
    return refus_classe(acteur, eleve.simulation_role, eleve.classe)


def classes_simulables(session: Session, acteur: models.Enseignant, role: str) -> list[models.Classe]:
    requete = select(models.Classe).where(models.Classe.archivee_le.is_(None))
    if role == ENSEIGNANT:
        requete = requete.where(models.Classe.enseignant_id == acteur.id)
    classes = session.scalars(requete.order_by(models.Classe.code)).all()
    return [c for c in classes if refus_classe(acteur, role, c) is None]


def eleve_fictif(session: Session, acteur: models.Enseignant, role: str, classe: models.Classe) -> models.Eleve | None:
    return session.scalar(
        select(models.Eleve)
        .where(models.Eleve.simulation_par_id == acteur.id, models.Eleve.simulation_role == role,
               models.Eleve.classe_id == classe.id)
        .execution_options(**{INCLURE: True})
    )


def _prenom(acteur: models.Enseignant, role: str) -> str:
    # Unique dans la classe (contrainte prénom + classe) et sans lien avec un vrai élève.
    return f"Élève fictif {'A' if role == ADMIN else 'P'}{acteur.id}"


def _creer(session: Session, acteur: models.Enseignant, role: str, classe: models.Classe) -> models.Eleve:
    eleve = models.Eleve(
        prenom=_prenom(acteur, role), classe=classe, code_hash=_empreinte(acteur),
        simulation_par_id=acteur.id, simulation_role=role,
    )
    session.add(eleve)
    session.flush()
    return eleve


def ouvrir(session: Session, acteur: models.Enseignant, role: str, classe: models.Classe) -> models.Eleve:
    """Reprend l'élève fictif de l'acteur dans cette classe (ou le crée), avec un nouveau jeton : les jetons
    émis avant, dans un autre onglet par exemple, sont révoqués."""
    eleve = eleve_fictif(session, acteur, role, classe)
    if eleve is None:
        eleve = _creer(session, acteur, role, classe)
    else:
        eleve.code_hash = _empreinte(acteur)
    _noter(session, acteur, "simulation.ouverture", eleve)
    return eleve


def reinitialiser(session: Session, eleve: models.Eleve) -> models.Eleve:
    """Efface tout le travail fictif (séances, réponses, diagnostic, demandes d'aide, rédactions) en recréant
    l'élève fictif ; aucune autre donnée n'est touchée."""
    acteur = session.get(models.Enseignant, eleve.simulation_par_id)
    role, classe = eleve.simulation_role, eleve.classe
    session.delete(eleve)
    session.flush()
    nouveau = _creer(session, acteur, role, classe)
    _noter(session, acteur, "simulation.reinitialisation", nouveau)
    return nouveau


def fermer(session: Session, eleve: models.Eleve) -> None:
    """Retour à l'espace d'origine : le jeton de simulation est révoqué, le travail fictif est conservé."""
    eleve.code_hash = None
    _noter(session, session.get(models.Enseignant, eleve.simulation_par_id), "simulation.fermeture", eleve)


def _noter(session: Session, acteur: models.Enseignant, action: str, eleve: models.Eleve) -> None:
    # Acteur, contexte et événement seulement : ni réponse, ni texte, ni secret.
    journal.noter(session, acteur, action, "classe", eleve.classe_id,
                  apres={"role": eleve.simulation_role, "classe": eleve.classe.code})


def purger(session: Session, maintenant: datetime | None = None) -> int:
    """Supprime les élèves fictifs inactifs depuis `JOURS_CONSERVATION` jours, ou dont la classe est archivée."""
    limite = (maintenant or datetime.now(UTC)) - timedelta(days=JOURS_CONSERVATION)
    derniere = (
        select(models.Seance.eleve_id, func.max(models.Seance.debut).label("debut"))
        .group_by(models.Seance.eleve_id).subquery()
    )
    activite = func.coalesce(derniere.c.debut, models.Eleve.cree_le, type_=DateTime(timezone=True))
    fictifs = session.scalars(
        select(models.Eleve).join(models.Classe)
        .outerjoin(derniere, derniere.c.eleve_id == models.Eleve.id)
        .where(models.Eleve.simulation_par_id.is_not(None), (activite < limite) | models.Classe.archivee_le.is_not(None))
        .execution_options(**{INCLURE: True})
    ).all()
    for eleve in fictifs:
        session.delete(eleve)
    return len(fictifs)
