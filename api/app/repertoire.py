"""Répertoire des élèves (V3, Lot 1) : un élève = un enfant de famille, avec ses responsables, ses inscriptions
(parcours principal et options) et les points à vérifier ; la fiche réunit sa progression, ses archives et
l'historique des opérations d'administration qui le concernent.
"""

from sqlalchemy import case, func, or_, select
from sqlalchemy.orm import Session, selectinload

from app import archives, enfants
from app.db import models
from app.referentiel import PARCOURS_PRINCIPAUX
from app.schemas import ArchiveResume
from app.schemas_admin import (
    TAILLE_PAGE,
    EnfantRepertoire,
    EntreeHistoriqueEleve,
    FicheEleve,
    PageRepertoire,
    ResponsableResume,
    SuiviAnglais,
    SuiviMaths,
)

TRIS = {"nom", "niveau", "connexion", "recent"}

# Points à vérifier, affichés sur la ligne de l'élève.
SANS_RESPONSABLE = "Aucun responsable"
SANS_PRINCIPAL = "Pas de parcours principal en maths"
DEUX_PRINCIPAUX = "Plusieurs parcours principaux en maths"
AUTRE_NIVEAU = "Inscrit dans une classe d'un autre niveau"


def _inscriptions_maths_du_niveau(principales: bool):
    """Nombre d'inscriptions de maths de l'enfant à son niveau (seulement les parcours principaux si demandé)."""
    requete = (
        select(func.count(models.Eleve.id))
        .join(models.Classe, models.Classe.id == models.Eleve.classe_id)
        .where(models.Eleve.enfant_id == models.Enfant.id, models.Classe.niveau == models.Enfant.niveau,
               models.Classe.archivee_le.is_(None))
    )
    if principales:
        requete = requete.where(models.Classe.parcours.in_([p.value for p in PARCOURS_PRINCIPAUX]))
    return requete.correlate(models.Enfant).scalar_subquery()


def alertes(enfant: models.Enfant) -> list[str]:
    points = []
    if not enfant.parents:
        points.append(SANS_RESPONSABLE)
    # Les classes archivées (années passées) ne comptent plus (V3, Lot 3).
    en_cours = [e for e in enfant.inscriptions if e.classe.archivee_le is None]
    du_niveau = [e for e in en_cours if e.classe.niveau == enfant.niveau]
    principales = sum(e.classe.parcours in PARCOURS_PRINCIPAUX for e in du_niveau)
    if du_niveau and principales == 0:
        points.append(SANS_PRINCIPAL)
    elif principales > 1:
        points.append(DEUX_PRINCIPAUX)
    if any(e.classe.niveau != enfant.niveau for e in en_cours):
        points.append(AUTRE_NIVEAU)
    return points


def responsables(enfant: models.Enfant) -> list[ResponsableResume]:
    return [
        ResponsableResume(id=p.id, email=p.email, nom=p.nom, prenom=p.prenom, mdp_provisoire=p.mdp_provisoire,
                          bloque=p.bloque_le is not None, derniere_connexion=p.derniere_connexion)
        for p in sorted(enfant.parents, key=lambda p: p.id)
    ]


def decrire(enfant: models.Enfant) -> EnfantRepertoire:
    return EnfantRepertoire(
        **enfants.decrire(enfant).model_dump(), cree_le=enfant.cree_le, responsables=responsables(enfant),
        alertes=alertes(enfant),
    )


def chercher(
    session: Session,
    *,
    q: str = "",
    niveau: str | None = None,
    domaine: str | None = None,
    classe_id: int | None = None,
    groupe_id: int | None = None,
    statut: str | None = None,
    sans_responsable: bool = False,
    sans_classe: bool = False,
    a_verifier: bool = False,
    tri: str = "nom",
    page: int = 1,
) -> PageRepertoire:
    E = models.Enfant
    filtres = []
    q = q.strip()
    if q:
        motif = f"%{q}%"
        filtres.append(or_(
            E.prenom.ilike(motif), E.nom.ilike(motif), E.identifiant.ilike(motif),
            (func.lower(E.prenom) + " " + func.lower(E.nom)).like(f"%{q.lower()}%"),
            E.inscriptions.any(models.Eleve.classe.has(models.Classe.code.ilike(motif))),
            E.inscriptions_anglais.any(models.EleveAnglais.groupe.has(models.GroupeAnglais.nom.ilike(motif))),
            E.parents.any(models.Parent.email.ilike(motif) | models.Parent.nom.ilike(motif)),
        ))
    if niveau:
        filtres.append(E.niveau == niveau)
    if domaine:
        filtres.append(
            E.inscriptions.any(models.Eleve.classe.has(models.Classe.domaine_code == domaine))
            | E.inscriptions_anglais.any(models.EleveAnglais.groupe.has(models.GroupeAnglais.domaine_code == domaine))
        )
    if classe_id is not None:
        filtres.append(E.inscriptions.any(models.Eleve.classe_id == classe_id))
    if groupe_id is not None:
        filtres.append(E.inscriptions_anglais.any(models.EleveAnglais.groupe_id == groupe_id))
    if statut == "bloque":
        filtres.append(E.bloque_le.is_not(None))
    elif statut == "actif":
        filtres.append(E.bloque_le.is_(None))
    if sans_responsable:
        filtres.append(~E.parents.any())
    if sans_classe:  # inscrit nulle part cette année : seules des classes archivées, ou aucune
        filtres += [
            ~E.inscriptions.any(models.Eleve.classe.has(models.Classe.archivee_le.is_(None))),
            ~E.inscriptions_anglais.any(models.EleveAnglais.groupe.has(models.GroupeAnglais.archivee_le.is_(None))),
        ]
    if a_verifier:
        du_niveau, principales = _inscriptions_maths_du_niveau(False), _inscriptions_maths_du_niveau(True)
        autre_niveau = E.inscriptions.any(
            models.Eleve.classe.has((models.Classe.niveau != E.niveau) & models.Classe.archivee_le.is_(None))
        )
        filtres.append(or_(~E.parents.any(), (du_niveau > 0) & (principales != 1), autre_niveau))

    ordre = {
        "nom": [E.prenom, E.nom, E.id],
        "niveau": [E.niveau, E.prenom, E.nom, E.id],
        "connexion": [E.derniere_connexion.is_(None), E.derniere_connexion.desc(), E.id],
        "recent": [E.cree_le.desc(), E.id.desc()],
    }[tri if tri in TRIS else "nom"]
    total = session.scalar(select(func.count(E.id)).where(*filtres)) or 0
    trouves = session.scalars(
        select(E).where(*filtres).order_by(*ordre)
        .options(
            selectinload(E.parents),
            selectinload(E.inscriptions).selectinload(models.Eleve.classe).selectinload(models.Classe.enseignant),
            selectinload(E.inscriptions_anglais).selectinload(models.EleveAnglais.groupe)
            .selectinload(models.GroupeAnglais.enseignant),
        )
        .offset((max(page, 1) - 1) * TAILLE_PAGE).limit(TAILLE_PAGE)
    )
    return PageRepertoire(total=total, elements=[decrire(e) for e in trouves])


def _suivi_maths(session: Session, eleve: models.Eleve) -> SuiviMaths:
    nb_seances, derniere = session.execute(
        select(func.count(models.Seance.id), func.max(models.Seance.debut)).where(models.Seance.eleve_id == eleve.id)
    ).one()
    nb_reponses, correctes = session.execute(
        select(func.count(models.Reponse.id), func.sum(case((models.Reponse.correcte, 1), else_=0)))
        .join(models.Seance).where(models.Seance.eleve_id == eleve.id)
    ).one()
    c = eleve.classe
    return SuiviMaths(
        eleve_id=eleve.id, code_classe=c.code, niveau=c.niveau, parcours=c.parcours,
        libelle_parcours=enfants.libelle_parcours(c), principal=c.parcours in PARCOURS_PRINCIPAUX,
        enseignant=c.enseignant.nom, inscrit_le=eleve.cree_le, seances=nb_seances, reponses=nb_reponses,
        taux_reussite=((correctes or 0) / nb_reponses) if nb_reponses else None, derniere_activite=derniere,
        archivee=c.archivee_le is not None,
    )


def _suivi_anglais(eleve: models.EleveAnglais) -> SuiviAnglais:
    g = eleve.groupe
    return SuiviAnglais(
        eleve_id=eleve.id, groupe=g.nom, niveau=g.niveau, enseignant=g.enseignant.nom, inscrit_le=eleve.cree_le,
        seances=len(eleve.progression), derniere_activite=max((p.maj_le for p in eleve.progression), default=None),
        archivee=g.archivee_le is not None,
    )


def historique(session: Session, enfant: models.Enfant) -> list[EntreeHistoriqueEleve]:
    """Opérations d'administration sur l'enfant : celles qui le visent, et les opérations en masse qui
    l'incluaient (blocage, suppression), lues dans le journal."""
    lignes = session.scalars(
        select(models.JournalAdmin)
        .where(or_(
            (models.JournalAdmin.objet == "enfant") & (models.JournalAdmin.objet_id == enfant.id),
            models.JournalAdmin.action.in_(("rattacher-enfant", "detacher-enfant", "ajouter-enfant")),
            models.JournalAdmin.objet_id.is_(None) & (models.JournalAdmin.objet == "enfant"),
        ))
        .order_by(models.JournalAdmin.le.desc(), models.JournalAdmin.id.desc())
        .limit(500)
    )
    entrees = []
    for j in lignes:
        if j.objet_id is None or j.objet != "enfant":
            avant, apres = j.avant or {}, j.apres or {}
            ids = [*avant.get("ids", []), *apres.get("ids", []), apres.get("enfant"), avant.get("enfant")]
            if enfant.id not in ids:
                continue
        entrees.append(EntreeHistoriqueEleve(le=j.le, admin=j.admin.nom if j.admin else None, action=j.action,
                                             objet=j.objet, avant=j.avant, apres=j.apres))
    return entrees[:100]


def fiche(session: Session, enfant: models.Enfant) -> FicheEleve:
    return FicheEleve(
        eleve=decrire(enfant),
        maths=[_suivi_maths(session, e) for e in sorted(enfant.inscriptions, key=lambda e: e.classe.code)],
        anglais=[_suivi_anglais(e) for e in sorted(enfant.inscriptions_anglais, key=lambda e: e.groupe.nom.lower())],
        archives=[ArchiveResume.model_validate(a) for a in archives.de_l_enfant(session, enfant.id)],
        historique=historique(session, enfant),
    )
