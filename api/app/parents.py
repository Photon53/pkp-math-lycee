"""Comptes parents : rattachement aux enfants, suivi du travail, nettoyage des comptes sans enfant.

Un parent est créé par le professeur d'un de ses enfants (e-mail + mot de passe provisoire, sans envoi
de courriel). Il voit les inscriptions qui lui sont rattachées et leurs inscriptions reliées (même élève
dans plusieurs parcours), tant que le professeur de la classe est actif.
"""

import unicodedata
from collections import defaultdict
from datetime import UTC, datetime, timedelta

from pkp_engine import est_maitrisee
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app import inscriptions
from app.db import models
from app.db.conversions import historique_eleve
from app.progression import competences_du_niveau, progression_eleve
from app.schemas import ChapitreSuivi, EnfantResume, JourActivite, ParentVue, TableauEnfant
from app.security import generer_mot_de_passe_provisoire, hacher_mot_de_passe

# Une réponse restée ouverte (onglet abandonné) ne compte pas des heures de travail.
DUREE_MAX_REPONSE_S = 10 * 60
JOURS_ACTIVITE = 14


def enfants(session: Session, parent: models.Parent) -> list[models.Eleve]:
    """Inscriptions suivies : celles rattachées au parent et leurs inscriptions reliées."""
    vus: dict[int, models.Eleve] = {}
    for eleve in [*parent.enfants, *(i for enfant in parent.famille for i in enfant.inscriptions)]:
        for e in (eleve, *inscriptions.liees(session, eleve)):
            if e.classe.enseignant.actif:
                vus[e.id] = e
    return sorted(vus.values(), key=lambda e: (e.prenom, e.classe.code))


def rattacher(session: Session, eleve: models.Eleve, email: str, par: str) -> tuple[models.Parent, str | None]:
    """Rattache le parent `email` à l'élève, en créant son compte au besoin ; `par` entre dans l'historique.
    Renvoie le mot de passe provisoire en clair, seulement si le compte vient d'être créé."""
    parent = session.scalar(select(models.Parent).where(models.Parent.email == email))
    provisoire = None
    if parent is None:
        provisoire = generer_mot_de_passe_provisoire()
        parent = models.Parent(email=email, mot_de_passe_hash=hacher_mot_de_passe(provisoire), mdp_provisoire=True)
        session.add(parent)
    if eleve not in parent.enfants:
        parent.enfants.append(eleve)
        session.flush()
        session.add(models.RattachementParent(parent_id=parent.id, eleve_id=eleve.id, action="ajout", par=par))
    session.flush()
    return parent, provisoire


def detacher(session: Session, eleve: models.Eleve, parent: models.Parent, par: str) -> bool:
    """Retire le lien ; effet immédiat, le parent est revérifié à chaque requête. Renvoie False si le compte
    parent, sans plus aucun enfant, a été supprimé (avec son historique)."""
    eleve.parents.remove(parent)
    session.add(models.RattachementParent(parent_id=parent.id, eleve_id=eleve.id, action="retrait", par=par))
    parent_id = parent.id
    supprimer_orphelins(session)
    return session.get(models.Parent, parent_id) is not None


def reinitialiser(parent: models.Parent) -> str:
    """Nouveau mot de passe provisoire ; les sessions ouvertes du parent sont fermées."""
    provisoire = generer_mot_de_passe_provisoire()
    parent.mot_de_passe_hash, parent.mdp_provisoire = hacher_mot_de_passe(provisoire), True
    return provisoire


def supprimer_orphelins(session: Session) -> int:
    """RGPD : un compte parent sans enfant rattaché n'a plus de raison d'être conservé."""
    session.flush()
    rattaches = select(models.enfants_de_parent.c.parent_id)
    famille = select(models.enfants_de_famille.c.parent_id)
    resultat = session.execute(
        delete(models.Parent).where(models.Parent.id.not_in(rattaches), models.Parent.id.not_in(famille))
    )
    session.expire_all()
    return resultat.rowcount


def vue(parent: models.Parent, enseignant_id: int | None = None) -> ParentVue:
    """`enseignant_id` : un professeur ne voit, parmi les enfants du parent, que ses propres élèves."""
    visibles = [e for e in parent.enfants if enseignant_id is None or e.classe.enseignant_id == enseignant_id]
    return ParentVue(
        id=parent.id,
        email=parent.email,
        mdp_provisoire=parent.mdp_provisoire,
        derniere_connexion=parent.derniere_connexion,
        enfants=sorted(f"{e.prenom} ({e.classe.code})" for e in visibles),
    )


def mots_interdits(eleve: models.Eleve) -> tuple[str, ...]:
    """Prénom et identifiant, sous la forme d'un code normalisé : un code ne doit pas les contenir."""
    prenom = unicodedata.normalize("NFKD", eleve.prenom).encode("ascii", "ignore").decode().upper()
    mots = ["".join(c for c in prenom if c.isalnum())]
    if eleve.identifiant:
        mots.append(eleve.identifiant.split("-")[0].upper())
    return tuple(m for m in mots if len(m) >= 3)


def _reponses_depuis(session: Session, eleve: models.Eleve, depuis: datetime):
    return session.execute(
        select(models.Reponse.repondu_le, models.Reponse.duree_s, models.Reponse.seance_id)
        .join(models.Seance, models.Seance.id == models.Reponse.seance_id)
        .where(models.Seance.eleve_id == eleve.id, models.Reponse.repondu_le >= depuis)
    ).all()


def _minutes(durees) -> float:
    return round(sum(min(d, DUREE_MAX_REPONSE_S) for d in durees) / 60, 1)


def _utc(instant: datetime) -> datetime:
    # SQLite rend des dates sans fuseau : elles sont enregistrées en UTC.
    return instant if instant.tzinfo else instant.replace(tzinfo=UTC)


def resume(session: Session, eleve: models.Eleve, maintenant: datetime | None = None) -> EnfantResume:
    maintenant = maintenant or datetime.now(UTC)
    historique = historique_eleve(session, eleve.id)
    competences = competences_du_niveau(session, eleve)
    derniere = session.scalar(select(func.max(models.Seance.debut)).where(models.Seance.eleve_id == eleve.id))
    semaine = _reponses_depuis(session, eleve, maintenant - timedelta(days=7))
    return EnfantResume(
        id=eleve.id,
        prenom=eleve.prenom,
        identifiant=eleve.identifiant,
        code_classe=eleve.classe.code,
        niveau=eleve.classe.niveau,
        parcours=eleve.classe.parcours,
        a_un_code=eleve.code_hash is not None,
        nb_reponses=len(historique),
        taux_reussite=sum(r.correcte for r in historique) / len(historique) if historique else None,
        competences_maitrisees=sum(est_maitrisee(historique, c.id) for c in competences),
        competences_total=len(competences),
        derniere_activite=_utc(derniere) if derniere else None,
        minutes_7_jours=_minutes(d for _, d, _ in semaine),
    )


def tableau(session: Session, eleve: models.Eleve, maintenant: datetime | None = None) -> TableauEnfant:
    """Tableau de bord du parent : synthèse, activité des 14 derniers jours, chapitres ouverts, progression."""
    maintenant = maintenant or datetime.now(UTC)
    mois = _reponses_depuis(session, eleve, maintenant - timedelta(days=30))
    par_jour: dict[str, list[float]] = defaultdict(list)
    for repondu_le, duree, _ in mois:
        par_jour[_utc(repondu_le).date().isoformat()].append(duree)
    jours = [(maintenant - timedelta(days=i)).date().isoformat() for i in range(JOURS_ACTIVITE - 1, -1, -1)]

    progression = progression_eleve(session, eleve)
    par_chapitre: dict[str, list[bool]] = defaultdict(list)
    for p in progression:
        par_chapitre[p.chapitre].append(p.maitrisee)
    return TableauEnfant(
        enfant=resume(session, eleve, maintenant),
        activite=[JourActivite(jour=j, nb_reponses=len(par_jour[j]), minutes=_minutes(par_jour[j])) for j in jours],
        minutes_30_jours=_minutes(d for _, d, _ in mois),
        seances_30_jours=len({s for _, _, s in mois}),
        chapitres=[
            ChapitreSuivi(titre=titre, competences_total=len(m), competences_maitrisees=sum(m))
            for titre, m in par_chapitre.items()
        ],
        progression=progression,
    )
