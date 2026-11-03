"""Espace administrateur : connexion, professeurs, élèves et classes, journal, statistiques.

Toutes les routes, sauf la connexion, exigent un jeton « admin » (30 min, second facteur en
production) ; le rôle est revérifié en base à chaque requête. Chaque écriture est journalisée.
"""

from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException, Request, Response, status
from fastapi.responses import JSONResponse
from sqlalchemy import func, or_, select

from app import journal, limitation, ressources, statistiques
from app.auth import ADMIN, AdminCourant, SessionDB
from app.config import settings
from app.db import models
from app.progression import export_eleve
from app.referentiel import Role
from app.routes import anglais
from app.routes.enseignants import _attribuer_code, verifier_identifiants
from app.schemas import CodeEleve, ConnexionEnseignant
from app.schemas_admin import (
    TAILLE_PAGE,
    Activation,
    ClasseAdmin,
    ConnexionAdmin,
    Deplacement,
    EleveAnglaisAdmin,
    EleveAdmin,
    EnseignantAdmin,
    EnseignantCree,
    EnseignantEdition,
    EntreeJournal,
    GroupeAnglaisAdmin,
    JetonAdmin,
    PageEleves,
    PageJournal,
    Statistiques,
    Transfert,
)
from app.security import (
    creer_jeton,
    generer_mot_de_passe_provisoire,
    hacher_mot_de_passe,
    verifier_totp,
    version_mot_de_passe,
)

router = APIRouter(prefix="/admin", tags=["administration"])

CHAMPS_ENSEIGNANT = ("nom", "email", "role", "enseigne_maths", "enseigne_anglais", "actif")


# --- Connexion ----------------------------------------------------------------------


@router.post("/connexion", response_model=JetonAdmin)
def connexion(corps: ConnexionAdmin, request: Request, session: SessionDB) -> JetonAdmin:
    admin = verifier_identifiants(ConnexionEnseignant(email=corps.email, mot_de_passe=corps.mot_de_passe), request, session)
    if admin.role != Role.ADMIN:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Ce compte n'a pas accès à l'administration.")
    if admin.mdp_provisoire:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Choisissez d'abord un nouveau mot de passe dans l'espace enseignant.")
    if admin.totp_secret is None and settings.totp_requis:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "Second facteur non configuré : python -m app.admin totp --email <votre e-mail>.",
        )
    if admin.totp_secret is not None:
        compte = f"totp:{admin.id}"
        limitation.verifier((limitation.echecs_enseignant, compte))
        if not corps.code_totp:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Code de l'application d'authentification requis.")
        if not verifier_totp(admin.totp_secret, corps.code_totp):
            limitation.echecs_enseignant.enregistrer(compte)
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Code de l'application d'authentification incorrect.")
        limitation.echecs_enseignant.effacer(compte)
    version = version_mot_de_passe(admin.mot_de_passe_hash)
    jeton = creer_jeton(ADMIN, admin.id, settings.duree_jeton_admin_min / 60, version)
    return JetonAdmin(jeton=jeton, nom=admin.nom, expire_dans_min=settings.duree_jeton_admin_min)


@router.get("/moi", response_model=EnseignantAdmin)
def moi(admin: AdminCourant, session: SessionDB) -> EnseignantAdmin:
    return _vue_enseignant(session, admin)


# --- Professeurs -------------------------------------------------------------------------


def _vue_enseignant(session: SessionDB, e: models.Enseignant) -> EnseignantAdmin:
    nb_eleves = session.scalar(
        select(func.count(models.Eleve.id)).join(models.Classe).where(models.Classe.enseignant_id == e.id)
    )
    return EnseignantAdmin(
        id=e.id, nom=e.nom, email=e.email, role=e.role, enseigne_maths=e.enseigne_maths,
        enseigne_anglais=e.enseigne_anglais, actif=e.actif, mdp_provisoire=e.mdp_provisoire,
        totp_configure=e.totp_secret is not None, nb_classes=len(e.classes), nb_eleves=nb_eleves,
        nb_groupes_anglais=len(e.groupes_anglais), nb_eleves_anglais=sum(len(g.eleves) for g in e.groupes_anglais),
        derniere_connexion=e.derniere_connexion,
    )


def _enseignant(session: SessionDB, enseignant_id: int) -> models.Enseignant:
    e = session.get(models.Enseignant, enseignant_id)
    if e is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Professeur introuvable.")
    return e


def _email_libre(session: SessionDB, email: str, sauf_id: int | None = None) -> None:
    existant = session.scalar(select(models.Enseignant).where(models.Enseignant.email == email))
    if existant is not None and existant.id != sauf_id:
        raise HTTPException(status.HTTP_409_CONFLICT, f"Un compte existe déjà pour {email}.")


@router.get("/enseignants", response_model=list[EnseignantAdmin])
def enseignants(admin: AdminCourant, session: SessionDB, q: str | None = None) -> list[EnseignantAdmin]:
    requete = select(models.Enseignant).order_by(models.Enseignant.nom)
    if q:
        motif = f"%{q.strip().lower()}%"
        requete = requete.where(or_(func.lower(models.Enseignant.nom).like(motif), models.Enseignant.email.like(motif)))
    return [_vue_enseignant(session, e) for e in session.scalars(requete)]


@router.post("/enseignants", response_model=EnseignantCree, status_code=status.HTTP_201_CREATED)
def creer_enseignant(corps: EnseignantEdition, admin: AdminCourant, session: SessionDB) -> EnseignantCree:
    _email_libre(session, corps.email)
    provisoire = generer_mot_de_passe_provisoire()
    e = models.Enseignant(
        nom=corps.nom.strip(), email=corps.email, role=corps.role,
        enseigne_maths=corps.enseigne_maths, enseigne_anglais=corps.enseigne_anglais,
        mot_de_passe_hash=hacher_mot_de_passe(provisoire), mdp_provisoire=True,
    )
    session.add(e)
    session.flush()
    journal.noter(session, admin, "creer", "enseignant", e.id, apres=journal.instantane(e, CHAMPS_ENSEIGNANT))
    session.commit()
    return EnseignantCree(enseignant=_vue_enseignant(session, e), mot_de_passe_provisoire=provisoire)


@router.post("/enseignants/{enseignant_id}", response_model=EnseignantAdmin)
def modifier_enseignant(
    enseignant_id: int, corps: EnseignantEdition, admin: AdminCourant, session: SessionDB
) -> EnseignantAdmin:
    e = _enseignant(session, enseignant_id)
    if e.id == admin.id and corps.role != Role.ADMIN:
        raise HTTPException(422, "Vous ne pouvez pas retirer votre propre rôle d'administrateur.")
    _email_libre(session, corps.email, sauf_id=e.id)
    avant = journal.instantane(e, CHAMPS_ENSEIGNANT)
    e.nom, e.email, e.role = corps.nom.strip(), corps.email, corps.role
    e.enseigne_maths, e.enseigne_anglais = corps.enseigne_maths, corps.enseigne_anglais
    journal.noter(session, admin, "modifier", "enseignant", e.id, avant, journal.instantane(e, CHAMPS_ENSEIGNANT))
    session.commit()
    return _vue_enseignant(session, e)


@router.post("/enseignants/{enseignant_id}/reinitialiser", response_model=EnseignantCree)
def reinitialiser_mot_de_passe(enseignant_id: int, admin: AdminCourant, session: SessionDB) -> EnseignantCree:
    """Nouveau mot de passe provisoire ; les sessions ouvertes du professeur sont fermées (EA3.3)."""
    e = _enseignant(session, enseignant_id)
    provisoire = generer_mot_de_passe_provisoire()
    e.mot_de_passe_hash, e.mdp_provisoire = hacher_mot_de_passe(provisoire), True
    journal.noter(session, admin, "reinitialiser-mot-de-passe", "enseignant", e.id)
    session.commit()
    return EnseignantCree(enseignant=_vue_enseignant(session, e), mot_de_passe_provisoire=provisoire)


@router.post("/enseignants/{enseignant_id}/activation", response_model=EnseignantAdmin)
def activer(enseignant_id: int, corps: Activation, admin: AdminCourant, session: SessionDB) -> EnseignantAdmin:
    e = _enseignant(session, enseignant_id)
    if e.id == admin.id and not corps.actif:
        raise HTTPException(422, "Vous ne pouvez pas désactiver votre propre compte.")
    avant = journal.instantane(e, ("actif",))
    e.actif = corps.actif
    journal.noter(session, admin, "activer" if corps.actif else "desactiver", "enseignant", e.id, avant, {"actif": e.actif})
    session.commit()
    return _vue_enseignant(session, e)


@router.post("/enseignants/{enseignant_id}/transfert", response_model=list[EnseignantAdmin])
def transferer_classes(enseignant_id: int, corps: Transfert, admin: AdminCourant, session: SessionDB) -> list[EnseignantAdmin]:
    """Remplacement en cours d'année : toutes les classes passent à un autre professeur (EA3.5)."""
    de, vers = _enseignant(session, enseignant_id), _enseignant(session, corps.vers_enseignant_id)
    if de.id == vers.id:
        raise HTTPException(422, "Choisissez un autre professeur.")
    # Les classes sont celles de l'espace maths : un professeur d'anglais seul ne pourrait pas les ouvrir.
    if not vers.enseigne_maths:
        raise HTTPException(422, "Ce professeur n'enseigne pas les mathématiques.")
    codes = [c.code for c in de.classes]
    for classe in list(de.classes):
        classe.enseignant = vers
    journal.noter(session, admin, "transferer-classes", "enseignant", de.id, {"classes": codes}, {"vers": vers.id})
    session.commit()
    session.refresh(de)
    session.refresh(vers)
    return [_vue_enseignant(session, de), _vue_enseignant(session, vers)]


@router.delete("/enseignants/{enseignant_id}", status_code=status.HTTP_204_NO_CONTENT)
def supprimer_enseignant(enseignant_id: int, confirmation: str, admin: AdminCourant, session: SessionDB) -> Response:
    """Seulement un compte sans classe, après saisie de son e-mail (EA3.6)."""
    e = _enseignant(session, enseignant_id)
    if e.id == admin.id:
        raise HTTPException(422, "Vous ne pouvez pas supprimer votre propre compte.")
    if confirmation.strip().lower() != e.email:
        raise HTTPException(422, "Saisissez l'adresse e-mail du compte pour confirmer.")
    if e.classes:
        raise HTTPException(status.HTTP_409_CONFLICT, "Ce professeur a encore des classes : transférez-les d'abord.")
    if e.groupes_anglais:
        raise HTTPException(status.HTTP_409_CONFLICT, "Ce professeur a encore des groupes d'anglais : transférez-les d'abord.")
    fichiers = [r.fichier for r in session.scalars(select(models.Ressource).where(models.Ressource.auteur_id == e.id))]
    journal.noter(session, admin, "supprimer", "enseignant", e.id, avant=journal.instantane(e, CHAMPS_ENSEIGNANT))
    session.delete(e)
    session.commit()
    for fichier in fichiers:
        ressources.supprimer_fichier(fichier)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# --- Élèves et classes ---------------------------------------------------------------------


def _eleve(session: SessionDB, eleve_id: int) -> models.Eleve:
    eleve = session.get(models.Eleve, eleve_id)
    if eleve is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Élève introuvable.")
    return eleve


@router.get("/eleves", response_model=PageEleves)
def eleves(
    _: AdminCourant,
    session: SessionDB,
    q: str | None = None,
    classe_id: int | None = None,
    enseignant_id: int | None = None,
    page: int = 1,
) -> PageEleves:
    activite = (
        select(
            models.Seance.eleve_id,
            func.count(models.Seance.id).label("nb"),
            func.max(models.Seance.debut).label("derniere"),
        )
        .group_by(models.Seance.eleve_id)
        .subquery()
    )
    filtres = []
    if q:
        filtres.append(func.lower(models.Eleve.prenom).like(f"%{q.strip().lower()}%"))
    if classe_id is not None:
        filtres.append(models.Eleve.classe_id == classe_id)
    if enseignant_id is not None:
        filtres.append(models.Classe.enseignant_id == enseignant_id)
    base = select(models.Eleve).join(models.Classe).where(*filtres)
    total = session.scalar(select(func.count()).select_from(base.subquery()))
    lignes = session.execute(
        select(models.Eleve, activite.c.nb, activite.c.derniere)
        .join(models.Classe)
        .outerjoin(activite, activite.c.eleve_id == models.Eleve.id)
        .where(*filtres)
        .order_by(models.Classe.code, models.Eleve.prenom)
        .offset((max(page, 1) - 1) * TAILLE_PAGE)
        .limit(TAILLE_PAGE)
    ).all()
    return PageEleves(
        total=total,
        elements=[
            EleveAdmin(
                id=e.id, prenom=e.prenom, classe_id=e.classe_id, classe=e.classe.code, niveau=e.classe.niveau,
                enseignant=e.classe.enseignant.nom, nb_seances=nb or 0, derniere_activite=derniere,
                a_un_code=e.code_hash is not None,
            )
            for e, nb, derniere in lignes
        ],
    )


@router.post("/eleves/{eleve_id}/code", response_model=CodeEleve)
def nouveau_code(eleve_id: int, admin: AdminCourant, session: SessionDB) -> CodeEleve:
    eleve = _eleve(session, eleve_id)
    code = _attribuer_code(eleve)
    journal.noter(session, admin, "regenerer-code", "eleve", eleve.id)
    session.commit()
    return code


@router.post("/eleves/{eleve_id}/deplacement", response_model=EleveAdmin)
def deplacer(eleve_id: int, corps: Deplacement, admin: AdminCourant, session: SessionDB) -> EleveAdmin:
    """Vers une autre classe du même professeur (EA3.8)."""
    eleve = _eleve(session, eleve_id)
    cible = session.get(models.Classe, corps.classe_id)
    if cible is None or cible.enseignant_id != eleve.classe.enseignant_id:
        raise HTTPException(422, "Choisissez une autre classe du même professeur.")
    if any(e.prenom == eleve.prenom and e.id != eleve.id for e in cible.eleves):
        raise HTTPException(status.HTTP_409_CONFLICT, f"Un élève prénommé {eleve.prenom} existe déjà dans {cible.code}.")
    avant = {"classe": eleve.classe.code}
    eleve.classe = cible
    journal.noter(session, admin, "deplacer", "eleve", eleve.id, avant, {"classe": cible.code})
    session.commit()
    return eleves(admin, session, classe_id=cible.id, q=eleve.prenom).elements[0]


@router.delete("/eleves/{eleve_id}", status_code=status.HTTP_204_NO_CONTENT)
def supprimer_eleve(eleve_id: int, admin: AdminCourant, session: SessionDB) -> Response:
    eleve = _eleve(session, eleve_id)
    journal.noter(session, admin, "supprimer", "eleve", eleve.id, avant={"prenom": eleve.prenom, "classe": eleve.classe.code})
    session.delete(eleve)
    session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/eleves/{eleve_id}/export")
def exporter(eleve_id: int, admin: AdminCourant, session: SessionDB) -> JSONResponse:
    """L'accès d'un administrateur aux données d'un élève est journalisé (RGPD)."""
    eleve = _eleve(session, eleve_id)
    journal.noter(session, admin, "exporter", "eleve", eleve.id)
    session.commit()
    return export_eleve(session, eleve)


@router.get("/classes", response_model=list[ClasseAdmin])
def classes(_: AdminCourant, session: SessionDB, enseignant_id: int | None = None) -> list[ClasseAdmin]:
    requete = select(models.Classe).order_by(models.Classe.code)
    if enseignant_id is not None:
        requete = requete.where(models.Classe.enseignant_id == enseignant_id)
    return [
        ClasseAdmin(
            id=c.id, code=c.code, niveau=c.niveau, parcours=c.parcours, enseignant_id=c.enseignant_id,
            enseignant=c.enseignant.nom, nb_eleves=len(c.eleves), nb_chapitres_ouverts=len(c.chapitres_proposes),
        )
        for c in session.scalars(requete)
    ]


# --- PKP Anglais : groupes et séances ---------------------------------------------------
# Les groupes d'anglais (4e, 3e) sont séparés des classes de maths : vues et actions dédiées.


def _vue_groupe(g: models.GroupeAnglais) -> GroupeAnglaisAdmin:
    return GroupeAnglaisAdmin(
        id=g.id, nom=g.nom, niveau=g.niveau, enseignant_id=g.enseignant_id, enseignant=g.enseignant.nom,
        eleves=[EleveAnglaisAdmin(id=e.id, prenom=e.prenom) for e in sorted(g.eleves, key=lambda e: e.prenom.lower())],
    )


def _groupe_anglais(session: SessionDB, groupe_id: int) -> models.GroupeAnglais:
    g = session.get(models.GroupeAnglais, groupe_id)
    if g is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Groupe introuvable.")
    return g


@router.get("/anglais/groupes", response_model=list[GroupeAnglaisAdmin])
def groupes_anglais(_: AdminCourant, session: SessionDB) -> list[GroupeAnglaisAdmin]:
    groupes = session.scalars(select(models.GroupeAnglais))
    return [_vue_groupe(g) for g in sorted(
        groupes, key=lambda g: (models.NIVEAUX_ANGLAIS.index(g.niveau), g.enseignant.nom.lower(), g.nom.lower())
    )]


@router.post("/anglais/groupes/{groupe_id}/transfert", response_model=GroupeAnglaisAdmin)
def transferer_groupe_anglais(groupe_id: int, corps: Transfert, admin: AdminCourant, session: SessionDB) -> GroupeAnglaisAdmin:
    """Remplacement en cours d'année : le groupe et ses élèves passent à un autre professeur d'anglais."""
    groupe, vers = _groupe_anglais(session, groupe_id), _enseignant(session, corps.vers_enseignant_id)
    if vers.id == groupe.enseignant_id:
        raise HTTPException(422, "Choisissez un autre professeur.")
    if not vers.enseigne_anglais:
        raise HTTPException(422, "Ce professeur n'enseigne pas l'anglais.")
    if any(g.nom.lower() == groupe.nom.lower() for g in vers.groupes_anglais):
        raise HTTPException(status.HTTP_409_CONFLICT, "Ce professeur a déjà un groupe de ce nom.")
    journal.noter(session, admin, "transferer", "groupe_anglais", groupe.id, {"enseignant": groupe.enseignant_id}, {"enseignant": vers.id})
    groupe.enseignant = vers
    session.commit()
    return _vue_groupe(groupe)


@router.delete("/anglais/groupes/{groupe_id}", status_code=status.HTTP_204_NO_CONTENT)
def supprimer_groupe_anglais(groupe_id: int, admin: AdminCourant, session: SessionDB) -> Response:
    groupe = _groupe_anglais(session, groupe_id)
    journal.noter(session, admin, "supprimer", "groupe_anglais", groupe.id,
                  avant={"nom": groupe.nom, "niveau": groupe.niveau, "eleves": len(groupe.eleves)})
    session.delete(groupe)
    session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.delete("/anglais/eleves/{eleve_id}", status_code=status.HTTP_204_NO_CONTENT)
def supprimer_eleve_anglais(eleve_id: int, admin: AdminCourant, session: SessionDB) -> Response:
    """Droit à l'effacement (RGPD) : le prénom est supprimé, l'action est journalisée."""
    eleve = session.get(models.EleveAnglais, eleve_id)
    if eleve is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Élève introuvable.")
    journal.noter(session, admin, "supprimer", "eleve_anglais", eleve.id, avant={"prenom": eleve.prenom, "groupe": eleve.groupe.nom})
    session.delete(eleve)
    session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/anglais/seances")
def seances_anglais(admin: AdminCourant):
    """Catalogue des séances, pour contrôler ce que reçoivent les professeurs d'anglais."""
    return anglais.lister_seances(admin)


@router.get("/anglais/seances/{code}/pdf/{public}")
def pdf_seance_anglais(code: str, public: str, admin: AdminCourant):
    return anglais.telecharger_pdf(code, public, admin)


# --- Journal et statistiques ---------------------------------------------------------------


@router.get("/journal", response_model=PageJournal)
def lire_journal(
    _: AdminCourant,
    session: SessionDB,
    objet: str | None = None,
    action: str | None = None,
    admin_id: int | None = None,
    page: int = 1,
) -> PageJournal:
    filtres = []
    if objet:
        filtres.append(models.JournalAdmin.objet == objet)
    if action:
        filtres.append(models.JournalAdmin.action == action)
    if admin_id is not None:
        filtres.append(models.JournalAdmin.admin_id == admin_id)
    total = session.scalar(select(func.count(models.JournalAdmin.id)).where(*filtres))
    lignes = session.scalars(
        select(models.JournalAdmin)
        .where(*filtres)
        .order_by(models.JournalAdmin.le.desc(), models.JournalAdmin.id.desc())
        .offset((max(page, 1) - 1) * TAILLE_PAGE)
        .limit(TAILLE_PAGE)
    )
    return PageJournal(
        total=total,
        elements=[
            EntreeJournal(
                id=j.id, le=j.le, admin=j.admin.nom if j.admin else None, action=j.action, objet=j.objet,
                objet_id=j.objet_id, avant=j.avant, apres=j.apres,
            )
            for j in lignes
        ],
    )


@router.get("/statistiques", response_model=Statistiques)
def lire_statistiques(_: AdminCourant, session: SessionDB, periode: int = 30) -> Statistiques:
    if periode not in statistiques.PERIODES:
        raise HTTPException(422, f"Période possible : {', '.join(map(str, statistiques.PERIODES))} jours.")
    return statistiques.calculer(session, periode, maintenant=datetime.now(UTC))
