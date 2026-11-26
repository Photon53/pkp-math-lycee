# Issue #184 — Vue élève simulée (Claude)
"""Isolement des élèves fictifs de simulation (issue #184).

Un élève fictif est une vraie ligne `eleve` (les écrans, règles et contrôles de l'espace élève s'appliquent donc
tels quels), mais il doit rester invisible partout ailleurs : listes de classe, statistiques, bilans parents,
demandes d'aide, rédactions et diagnostics à corriger, recherche, purge ordinaire…

Plutôt que d'ajouter un filtre à chacune des requêtes existantes (et d'en oublier une), un filtre ORM global
(`with_loader_criteria`) est ajouté à **toute** lecture : l'élève fictif et tout ce qu'il produit (séances,
réponses, passation et observations du diagnostic, demandes d'aide, rédactions) en sont retirés.

Seule exception : une requête faite avec le jeton d'un élève fictif voit ses propres données (et seulement
les siennes parmi les données fictives) — `autoriser_eleve_fictif`, appelé par `auth.eleve_courant`.
L'option d'exécution `inclure_simulations=True` lève le filtre pour le code qui gère les simulations
(création, réinitialisation, purge).
"""

from sqlalchemy import event, or_, select
from sqlalchemy.orm import ORMExecuteState, Session, with_loader_criteria

from app.db import models

INCLURE = "inclure_simulations"
_CLE_SESSION = "eleve_simulation_id"

_eleve = models.Eleve.__table__
_seance = models.Seance.__table__


def autoriser_eleve_fictif(session: Session, eleve_id: int) -> None:
    """La suite de la requête (même session) voit les données de cet élève fictif, et d'aucun autre."""
    session.info[_CLE_SESSION] = eleve_id


def _ids_fictifs(autorise: int | None):
    # Table Core (et non entité ORM) : le filtre ne s'applique pas à sa propre sous-requête.
    requete = select(_eleve.c.id).where(_eleve.c.simulation_par_id.is_not(None))
    return requete if autorise is None else requete.where(_eleve.c.id != autorise)


def _criteres(autorise: int | None) -> list:
    fictifs = _ids_fictifs(autorise)
    seances_fictives = select(_seance.c.id).where(_seance.c.eleve_id.in_(fictifs))
    if autorise is None:
        criteres = [with_loader_criteria(models.Eleve, lambda cls: cls.simulation_par_id.is_(None), include_aliases=True)]
    else:
        criteres = [with_loader_criteria(
            models.Eleve, lambda cls: or_(cls.simulation_par_id.is_(None), cls.id == autorise), include_aliases=True
        )]
    for modele in (models.Seance, models.PassationDiagnostic, models.ObservationDiagnostic, models.DemandeAide,
                   models.Redaction, models.ProgressionFrancais, models.ReponseQuizFrancais,
                   models.ReponseRedigeeFrancais):
        criteres.append(with_loader_criteria(modele, lambda cls: cls.eleve_id.not_in(fictifs), include_aliases=True))
    criteres.append(with_loader_criteria(
        models.Reponse, lambda cls: cls.seance_id.not_in(seances_fictives), include_aliases=True
    ))
    return criteres


@event.listens_for(Session, "do_orm_execute")
def _masquer_eleves_fictifs(etat: ORMExecuteState) -> None:
    if not etat.is_select or etat.is_column_load or etat.execution_options.get(INCLURE, False):
        return
    etat.statement = etat.statement.options(*_criteres(etat.session.info.get(_CLE_SESSION)))
