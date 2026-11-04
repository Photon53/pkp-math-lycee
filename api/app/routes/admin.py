"""Espace administrateur : connexion, professeurs, élèves et classes, journal, statistiques.

Toutes les routes, sauf la connexion, exigent un jeton « admin » (30 min, second facteur en
production) ; le rôle est revérifié en base à chaque requête. Chaque écriture est journalisée.
"""

from datetime import UTC, datetime
from urllib.parse import urlencode

from fastapi import APIRouter, HTTPException, Request, Response, status
from fastapi.responses import JSONResponse
from sqlalchemy import func, or_, select

from app import anglais_contenu, inscriptions, journal, limitation, parents, permissions, ressources, statistiques
from app.auth import ADMIN, AdminCourant, FiltreDomaine, SessionDB
from app.config import settings
from app.db import models
from app.progression import export_eleve
from app.referentiel import Role
from app.routes import anglais
from app.routes.enseignants import _attribuer_code, verifier_identifiants
from app.schemas import CodeEleve, ConnexionEnseignant, ParentCree, ParentVue
from app.schemas_admin import (
    ResultatRecherche,
    SeanceAnglaisEdition,
    TAILLE_PAGE,
    Activation,
    ClasseAdmin,
    ConnexionAdmin,
    Deplacement,
    DomaineAdmin,
    DomaineEdition,
    EleveAnglaisAdmin,
    EleveAdmin,
    EnseignantAdmin,
    EnseignantCree,
    EnseignantEdition,
    EnfantRattache,
    EntreeJournal,
    EntreeRattachement,
    FamilleAdmin,
    FamilleCreation,
    FamilleCreee,
    FamilleDetail,
    GroupeAnglaisAdmin,
    HabilitationVue,
    JetonAdmin,
    PageEleves,
    PageFamilles,
    PageJournal,
    RattachementEnfant,
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

CHAMPS_ENSEIGNANT = ("nom", "email", "role", "enseigne_maths", "enseigne_anglais", "referent_anglais", "actif")


def _instantane(e: models.Enseignant) -> dict:
    """Pour le journal : les champs du compte et ses habilitations (« validateur maths-lycee 1re »)."""
    return journal.instantane(e, CHAMPS_ENSEIGNANT) | {
        "habilitations": [" ".join(filter(None, p)) for p in permissions.portees(e)]
    }


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
    vue = _vue_enseignant(session, admin)
    vue.permissions = sorted(permissions.permissions_de(admin))
    return vue


# --- Professeurs -------------------------------------------------------------------------


def _vue_enseignant(session: SessionDB, e: models.Enseignant) -> EnseignantAdmin:
    nb_eleves = session.scalar(
        select(func.count(models.Eleve.id)).join(models.Classe).where(models.Classe.enseignant_id == e.id)
    )
    return EnseignantAdmin(
        id=e.id, nom=e.nom, email=e.email, role=e.role, enseigne_maths=e.enseigne_maths,
        enseigne_anglais=e.enseigne_anglais, referent_anglais=e.referent_anglais, actif=e.actif,
        mdp_provisoire=e.mdp_provisoire,
        totp_configure=e.totp_secret is not None, nb_classes=len(e.classes), nb_eleves=nb_eleves,
        nb_groupes_anglais=len(e.groupes_anglais), nb_eleves_anglais=sum(len(g.eleves) for g in e.groupes_anglais),
        derniere_connexion=e.derniere_connexion,
        habilitations=[
            HabilitationVue(role=h.role, domaine=h.domaine_code, niveau=h.niveau,
                            libelle=permissions.LIBELLES.get(h.domaine_code, h.domaine_code), accordee_le=h.accordee_le)
            for h in e.habilitations
        ],
    )


def _habiliter(session: SessionDB, e: models.Enseignant, corps: EnseignantEdition, admin: models.Enseignant) -> None:
    """Habilitations envoyées, sinon déduites des anciennes cases à cocher ; 422 si une portée est refusée."""
    if corps.habilitations is not None:
        voulues = [permissions.Portee(h.role, h.domaine, h.niveau) for h in corps.habilitations]
    else:
        voulues = permissions.depuis_cases(
            permissions.portees(e), enseigne_maths=corps.enseigne_maths, enseigne_anglais=corps.enseigne_anglais,
            referent_anglais=corps.referent_anglais,
        )
    try:
        permissions.appliquer(session, e, voulues, admin)
    except permissions.HabilitationRefusee as erreur:
        raise HTTPException(422, str(erreur)) from None


def _garder_un_admin(session: SessionDB, e: models.Enseignant) -> None:
    """EA.7 : le dernier administrateur actif ne perd ni son rôle ni l'accès."""
    autres = session.scalar(
        select(func.count(models.Enseignant.id))
        .where(models.Enseignant.role == Role.ADMIN, models.Enseignant.actif, models.Enseignant.id != e.id)
    )
    if not autres:
        raise HTTPException(422, "C'est le dernier administrateur actif : nommez-en un autre d'abord.")


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
def enseignants(
    admin: AdminCourant, session: SessionDB, domaine: FiltreDomaine, q: str | None = None
) -> list[EnseignantAdmin]:
    requete = select(models.Enseignant).order_by(models.Enseignant.nom)
    if domaine:
        requete = requete.where(models.Enseignant.habilitations.any(models.Habilitation.domaine_code == domaine))
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
        enseigne_maths=False, enseigne_anglais=False, referent_anglais=False,
        mot_de_passe_hash=hacher_mot_de_passe(provisoire), mdp_provisoire=True,
    )
    session.add(e)
    _habiliter(session, e, corps, admin)
    session.flush()
    journal.noter(session, admin, "creer", "enseignant", e.id, apres=_instantane(e))
    session.commit()
    return EnseignantCree(enseignant=_vue_enseignant(session, e), mot_de_passe_provisoire=provisoire)


@router.post("/enseignants/{enseignant_id}", response_model=EnseignantAdmin)
def modifier_enseignant(
    enseignant_id: int, corps: EnseignantEdition, admin: AdminCourant, session: SessionDB
) -> EnseignantAdmin:
    e = _enseignant(session, enseignant_id)
    if e.id == admin.id and corps.role != Role.ADMIN:
        raise HTTPException(422, "Vous ne pouvez pas retirer votre propre rôle d'administrateur.")
    if e.role == Role.ADMIN and corps.role != Role.ADMIN and e.actif:
        _garder_un_admin(session, e)
    _email_libre(session, corps.email, sauf_id=e.id)
    avant = _instantane(e)
    e.nom, e.email, e.role = corps.nom.strip(), corps.email, corps.role
    _habiliter(session, e, corps, admin)
    journal.noter(session, admin, "modifier", "enseignant", e.id, avant, _instantane(e))
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
    if e.role == Role.ADMIN and e.actif and not corps.actif:
        _garder_un_admin(session, e)
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
    domaine: FiltreDomaine,
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
    if domaine:
        filtres.append(models.Classe.domaine_code == domaine)
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
    return eleves(admin, session, None, classe_id=cible.id, q=eleve.prenom).elements[0]


@router.delete("/eleves/{eleve_id}", status_code=status.HTTP_204_NO_CONTENT)
def supprimer_eleve(eleve_id: int, admin: AdminCourant, session: SessionDB) -> Response:
    eleve = _eleve(session, eleve_id)
    journal.noter(session, admin, "supprimer", "eleve", eleve.id, avant={"prenom": eleve.prenom, "classe": eleve.classe.code})
    inscriptions.delier(session, eleve)  # ses autres parcours restent ; un enfant de famille garde sa carte
    session.delete(eleve)
    parents.supprimer_orphelins(session)
    session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/eleves/{eleve_id}/export")
def exporter(eleve_id: int, admin: AdminCourant, session: SessionDB) -> JSONResponse:
    """L'accès d'un administrateur aux données d'un élève est journalisé (RGPD)."""
    eleve = _eleve(session, eleve_id)
    journal.noter(session, admin, "exporter", "eleve", eleve.id)
    session.commit()
    return export_eleve(session, eleve)


# --- Familles (comptes parents) ------------------------------------------------------
# Pas de liste complète des familles : on cherche par e-mail (3 caractères au moins) ou par classe.


def _par(admin: models.Enseignant) -> str:
    return f"Administrateur : {admin.nom}"


def _famille(p: models.Parent) -> FamilleAdmin:
    return FamilleAdmin(
        id=p.id, email=p.email, mdp_provisoire=p.mdp_provisoire, cree_le=p.cree_le, derniere_connexion=p.derniere_connexion,
        enfants=[
            EnfantRattache(id=e.id, prenom=e.prenom, classe=e.classe.code, niveau=e.classe.niveau, enseignant=e.classe.enseignant.nom)
            for e in sorted(p.enfants, key=lambda e: (e.prenom, e.classe.code))
        ],
        famille=[f"{f.prenom} {f.nom}".strip() + f" ({f.niveau.value})" for f in sorted(p.famille, key=lambda f: f.prenom)],
    )


def _detail_famille(session: SessionDB, p: models.Parent) -> FamilleDetail:
    historique = session.scalars(
        select(models.RattachementParent)
        .where(models.RattachementParent.parent_id == p.id)
        .order_by(models.RattachementParent.le.desc(), models.RattachementParent.id.desc())
    )
    return FamilleDetail(
        **_famille(p).model_dump(),
        historique=[
            EntreeRattachement(le=r.le, action=r.action, par=r.par, enfant=f"{r.eleve.prenom} ({r.eleve.classe.code})")
            for r in historique
        ],
    )


def _parent(session: SessionDB, parent_id: int) -> models.Parent:
    parent = session.get(models.Parent, parent_id)
    if parent is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Parent introuvable.")
    return parent


@router.get("/parents", response_model=PageFamilles)
def familles(
    _: AdminCourant, session: SessionDB, domaine: FiltreDomaine, q: str | None = None, classe_id: int | None = None,
    page: int = 1,
) -> PageFamilles:
    """Comptes parents, les plus récents d'abord ; filtres facultatifs : e-mail, classe d'un enfant, domaine.

    Une famille dont aucun enfant n'est encore inscrit reste visible quel que soit le domaine choisi :
    l'administrateur qui l'a créée doit la retrouver pour la compléter."""
    q = (q or "").strip().lower()
    filtres = []
    if q:
        filtres.append(models.Parent.email.like(f"%{q}%"))
    if classe_id is not None:
        filtres.append(
            models.Parent.enfants.any(models.Eleve.classe_id == classe_id)
            | models.Parent.famille.any(models.Enfant.inscriptions.any(models.Eleve.classe_id == classe_id))
        )
    if domaine:
        dans_le_domaine = models.Eleve.classe.has(models.Classe.domaine_code == domaine)
        filtres.append(
            models.Parent.enfants.any(dans_le_domaine)
            | models.Parent.famille.any(
                models.Enfant.inscriptions.any(dans_le_domaine)
                | models.Enfant.inscriptions_anglais.any(
                    models.EleveAnglais.groupe.has(models.GroupeAnglais.domaine_code == domaine)
                )
                | (~models.Enfant.inscriptions.any() & ~models.Enfant.inscriptions_anglais.any())
            )
        )
    total = session.scalar(select(func.count(models.Parent.id)).where(*filtres))
    trouves = session.scalars(
        select(models.Parent).where(*filtres).order_by(models.Parent.cree_le.desc(), models.Parent.id.desc())
        .offset((max(page, 1) - 1) * TAILLE_PAGE).limit(TAILLE_PAGE)
    )
    return PageFamilles(total=total, elements=[_famille(p) for p in trouves])


@router.get("/parents/{parent_id}", response_model=FamilleDetail)
def famille(parent_id: int, _: AdminCourant, session: SessionDB) -> FamilleDetail:
    return _detail_famille(session, _parent(session, parent_id))


@router.post("/parents", response_model=FamilleCreee, status_code=status.HTTP_201_CREATED)
def creer_famille(corps: FamilleCreation, admin: AdminCourant, session: SessionDB) -> FamilleCreee:
    """Crée le compte parent rattaché à un premier enfant, ou rattache cet enfant à un compte existant."""
    eleve = _eleve(session, corps.eleve_id)
    parent, provisoire = parents.rattacher(session, eleve, corps.email, _par(admin))
    journal.noter(session, admin, "rattacher", "parent", parent.id, apres={"eleve": eleve.id, "cree": provisoire is not None})
    session.commit()
    return FamilleCreee(famille=_detail_famille(session, parent), mot_de_passe_provisoire=provisoire)


@router.post("/parents/{parent_id}/enfants", response_model=FamilleDetail)
def rattacher_enfant(parent_id: int, corps: RattachementEnfant, admin: AdminCourant, session: SessionDB) -> FamilleDetail:
    parent, eleve = _parent(session, parent_id), _eleve(session, corps.eleve_id)
    if eleve in parent.enfants:
        raise HTTPException(status.HTTP_409_CONFLICT, "Cet enfant est déjà rattaché à ce parent.")
    parents.rattacher(session, eleve, parent.email, _par(admin))
    journal.noter(session, admin, "rattacher", "parent", parent.id, apres={"eleve": eleve.id})
    session.commit()
    return _detail_famille(session, parent)


@router.delete("/parents/{parent_id}/enfants/{eleve_id}", response_model=FamilleDetail | None)
def detacher_enfant(parent_id: int, eleve_id: int, admin: AdminCourant, session: SessionDB) -> FamilleDetail | None:
    """Effet immédiat ; sans plus aucun enfant, le compte parent est supprimé (réponse vide)."""
    parent = _parent(session, parent_id)
    eleve = next((e for e in parent.enfants if e.id == eleve_id), None)
    if eleve is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Cet enfant n'est pas rattaché à ce parent.")
    journal.noter(session, admin, "detacher", "parent", parent_id, avant={"eleve": eleve_id})
    reste = parents.detacher(session, eleve, parent, _par(admin))
    session.commit()
    return _detail_famille(session, session.get(models.Parent, parent_id)) if reste else None


def _iso(d: datetime | None) -> str | None:
    return d.isoformat() if d else None


@router.get("/parents/{parent_id}/export")
def exporter_famille(parent_id: int, admin: AdminCourant, session: SessionDB) -> JSONResponse:
    """Données d'un compte parent (RGPD, EA.12) : compte, enfants rattachés, historique des rattachements.

    Les résultats des enfants n'y figurent pas : ils relèvent de l'export de chaque élève. Accès journalisé.
    """
    p = _parent(session, parent_id)
    historique = session.scalars(
        select(models.RattachementParent)
        .where(models.RattachementParent.parent_id == p.id)
        .order_by(models.RattachementParent.le, models.RattachementParent.id)
    )
    donnees = {
        "exporte_le": datetime.now(UTC).isoformat(),
        "parent": {
            "email": p.email, "cree_le": _iso(p.cree_le), "derniere_connexion": _iso(p.derniere_connexion),
            "mot_de_passe_provisoire": p.mdp_provisoire,
        },
        "enfants": [
            {"prenom": e.prenom, "classe": e.classe.code, "niveau": e.classe.niveau.value}
            for e in sorted(p.enfants, key=lambda e: (e.prenom, e.classe.code))
        ],
        "historique_des_rattachements": [
            {"le": _iso(r.le), "action": r.action, "par": r.par, "enfant": f"{r.eleve.prenom} ({r.eleve.classe.code})"}
            for r in historique
        ],
    }
    journal.noter(session, admin, "exporter", "parent", p.id)
    session.commit()
    return JSONResponse(donnees, headers={"Content-Disposition": f'attachment; filename="pkp-famille-{p.id}.json"'})


@router.post("/parents/{parent_id}/reinitialiser", response_model=ParentCree)
def reinitialiser_parent(parent_id: int, admin: AdminCourant, session: SessionDB) -> ParentCree:
    """Nouveau mot de passe provisoire ; les sessions ouvertes du parent sont fermées."""
    parent = _parent(session, parent_id)
    provisoire = parents.reinitialiser(parent)
    journal.noter(session, admin, "reinitialiser-mot-de-passe", "parent", parent.id)
    session.commit()
    return ParentCree(parent=parents.vue(parent), mot_de_passe_provisoire=provisoire)


@router.delete("/parents/{parent_id}", status_code=status.HTTP_204_NO_CONTENT)
def supprimer_famille(parent_id: int, confirmation: str, admin: AdminCourant, session: SessionDB) -> Response:
    """À la demande du parent (RGPD), après saisie de son e-mail : les enfants ne sont pas touchés (EA.12)."""
    parent = _parent(session, parent_id)
    if confirmation.strip().lower() != parent.email:
        raise HTTPException(422, "Saisissez l'adresse e-mail du compte pour confirmer.")
    journal.noter(session, admin, "supprimer", "parent", parent.id, avant={"enfants": [e.id for e in parent.enfants]})
    session.delete(parent)
    session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/classes", response_model=list[ClasseAdmin])
def classes(
    _: AdminCourant, session: SessionDB, domaine: FiltreDomaine, enseignant_id: int | None = None
) -> list[ClasseAdmin]:
    requete = select(models.Classe).order_by(models.Classe.code)
    if domaine:
        requete = requete.where(models.Classe.domaine_code == domaine)
    if enseignant_id is not None:
        requete = requete.where(models.Classe.enseignant_id == enseignant_id)
    return [
        ClasseAdmin(
            id=c.id, code=c.code, niveau=c.niveau, parcours=c.parcours, domaine_code=c.domaine_code,
            enseignant_id=c.enseignant_id,
            enseignant=c.enseignant.nom, nb_eleves=len(c.eleves), nb_chapitres_ouverts=len(c.chapitres_proposes),
        )
        for c in session.scalars(requete)
    ]


# --- PKP Anglais : groupes et séances ---------------------------------------------------
# Les groupes d'anglais (4e, 3e) sont séparés des classes de maths : vues et actions dédiées.


def _vue_groupe(g: models.GroupeAnglais) -> GroupeAnglaisAdmin:
    return GroupeAnglaisAdmin(
        id=g.id, nom=g.nom, niveau=g.niveau, enseignant_id=g.enseignant_id, enseignant=g.enseignant.nom,
        eleves=[
            EleveAnglaisAdmin(id=e.id, prenom=e.prenom, identifiant=anglais.identifiant_de(e), a_un_code=e.code_hash is not None)
            for e in sorted(g.eleves, key=lambda e: e.prenom.lower())
        ],
    )


def _groupe_anglais(session: SessionDB, groupe_id: int) -> models.GroupeAnglais:
    g = session.get(models.GroupeAnglais, groupe_id)
    if g is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Groupe introuvable.")
    return g


@router.get("/anglais/groupes", response_model=list[GroupeAnglaisAdmin])
def groupes_anglais(_: AdminCourant, session: SessionDB, domaine: FiltreDomaine) -> list[GroupeAnglaisAdmin]:
    requete = select(models.GroupeAnglais)
    if domaine:
        requete = requete.where(models.GroupeAnglais.domaine_code == domaine)
    groupes = session.scalars(requete)
    return [_vue_groupe(g) for g in sorted(
        groupes, key=lambda g: (models.NIVEAUX_ANGLAIS.index(g.niveau), g.enseignant.nom.lower(), g.nom.lower())
    )]


class GroupeAnglaisCreation(anglais.GroupeCreation):
    enseignant_id: int


@router.post("/anglais/groupes", response_model=GroupeAnglaisAdmin, status_code=status.HTTP_201_CREATED)
def creer_groupe_anglais(corps: GroupeAnglaisCreation, admin: AdminCourant, session: SessionDB) -> GroupeAnglaisAdmin:
    """L'administrateur crée un groupe pour un professeur d'anglais, comme une classe pour un professeur de maths."""
    enseignant = _enseignant(session, corps.enseignant_id)
    if not (enseignant.actif and enseignant.enseigne_anglais):
        raise HTTPException(422, "Choisissez un professeur d'anglais actif.")
    groupe = anglais.ouvrir_groupe(session, enseignant, corps)
    journal.noter(session, admin, "creer", "groupe_anglais", groupe.id, apres={"nom": groupe.nom, "enseignant": enseignant.id})
    session.commit()
    return _vue_groupe(groupe)


@router.patch("/anglais/groupes/{groupe_id}", response_model=GroupeAnglaisAdmin)
def renommer_groupe_anglais(
    groupe_id: int, corps: anglais.GroupeRenommage, admin: AdminCourant, session: SessionDB
) -> GroupeAnglaisAdmin:
    groupe = _groupe_anglais(session, groupe_id)
    if any(g.id != groupe.id and g.nom.lower() == corps.nom.lower() for g in groupe.enseignant.groupes_anglais):
        raise HTTPException(status.HTTP_409_CONFLICT, "Ce professeur a déjà un groupe de ce nom.")
    journal.noter(session, admin, "modifier", "groupe_anglais", groupe.id, avant={"nom": groupe.nom}, apres={"nom": corps.nom})
    groupe.nom = corps.nom
    session.commit()
    return _vue_groupe(groupe)


@router.post("/anglais/eleves/{eleve_id}/code", response_model=anglais.CodeEleveAnglais)
def nouveau_code_anglais(eleve_id: int, admin: AdminCourant, session: SessionDB) -> anglais.CodeEleveAnglais:
    """Carte perdue : nouveau code (celui de l'enfant, valable dans toutes ses matières)."""
    eleve = session.get(models.EleveAnglais, eleve_id)
    if eleve is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Élève introuvable.")
    carte = anglais.attribuer_code(session, eleve)
    journal.noter(session, admin, "nouveau-code", "eleve_anglais", eleve.id)
    session.commit()
    return carte


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
def seances_anglais(_: AdminCourant, session: SessionDB, domaine: FiltreDomaine):
    """Catalogue : version courante de chaque séance, son statut et la version publiée."""
    return [anglais_contenu.resume(s) for s in anglais_contenu.toutes(session) if not domaine or s.domaine_code == domaine]


@router.get("/anglais/seances/{code}")
def seance_anglais(code: str, _: AdminCourant, session: SessionDB):
    """Version courante telle qu'elle s'édite (séance, cahier, QCM de grammaire) et son historique."""
    seance = anglais.seance_ou_404(session, code)
    c = seance.courante
    vocabulaire = anglais_contenu.quiz_complet(c)[: -len(c.quiz) or None]
    return {**anglais_contenu.resume(seance), "contenu": c.contenu, "cahier": c.cahier, "quiz": c.quiz,
            "quiz_vocabulaire": vocabulaire, "historique": anglais_contenu.historique(seance)}


@router.put("/anglais/seances/{code}")
def modifier_seance_anglais(code: str, corps: SeanceAnglaisEdition, admin: AdminCourant, session: SessionDB):
    """Enregistre en brouillon ; une version validée reste publiée jusqu'à la validation de la suivante."""
    seance = anglais.seance_ou_404(session, code)
    erreurs = anglais_contenu.verifier_version(code, corps.contenu, corps.cahier, corps.quiz)
    if erreurs:
        raise HTTPException(422, "Contenu incomplet : " + " ; ".join(erreurs))
    avant = {"code": code, "version": seance.courante.numero, "statut": seance.courante.statut}
    version = anglais_contenu.enregistrer(seance, admin, corps.contenu, corps.cahier, corps.quiz)
    session.flush()
    journal.noter(session, admin, "modifier", "seance_anglais", seance.id, avant,
                  {"code": code, "version": version.numero, "statut": version.statut})
    session.commit()
    return seance_anglais(code, admin, session)


@router.post("/anglais/seances/{code}/soumettre")
def soumettre_seance_anglais(code: str, admin: AdminCourant, session: SessionDB):
    """Brouillon, ou version refusée puis corrigée : envoyée aux référents."""
    seance = anglais.seance_ou_404(session, code)
    courante = seance.courante
    if courante.statut not in ("brouillon", "refuse"):
        raise HTTPException(status.HTTP_409_CONFLICT, "Seul un brouillon ou une version refusée peut être soumis.")
    avant = {"code": code, "version": courante.numero, "statut": courante.statut}
    courante.statut = "soumis"
    journal.noter(session, admin, "soumettre", "seance_anglais", seance.id, avant,
                  {"code": code, "version": courante.numero, "statut": "soumis"})
    session.commit()
    return anglais_contenu.resume(seance)


@router.post("/anglais/seances/{code}/valider")
def valider_seance_anglais(code: str, admin: AdminCourant, session: SessionDB):
    return anglais.decider(anglais.seance_ou_404(session, code), admin, session, None)


@router.post("/anglais/seances/{code}/refuser")
def refuser_seance_anglais(code: str, corps: anglais.Refus, admin: AdminCourant, session: SessionDB):
    return anglais.decider(anglais.seance_ou_404(session, code), admin, session, corps.motif)


@router.get("/anglais/seances/{code}/pdf/{public}")
def pdf_seance_anglais(code: str, public: str, _: AdminCourant, session: SessionDB):
    """PDF de la version courante, avec la mention NON VALIDÉ tant qu'elle n'est pas validée."""
    return anglais.reponse_pdf(anglais.seance_ou_404(session, code).courante, code, public)


# --- Domaines pédagogiques (configuration) ------------------------------------------------


def _vues_domaines(session: SessionDB) -> list[DomaineAdmin]:
    comptes = {
        (domaine, role): nombre
        for domaine, role, nombre in session.execute(
            select(models.Habilitation.domaine_code, models.Habilitation.role,
                   func.count(func.distinct(models.Habilitation.enseignant_id)))
            .group_by(models.Habilitation.domaine_code, models.Habilitation.role)
        )
    }
    return [
        DomaineAdmin(
            code=d.code, matiere=d.matiere, cycle=d.cycle, libelle=d.libelle, niveaux=d.niveaux, actif=d.actif, public=d.public,
            nb_professeurs=comptes.get((d.code, permissions.PROFESSEUR), 0),
            nb_validateurs=comptes.get((d.code, permissions.VALIDATEUR), 0),
        )
        for d in session.scalars(select(models.DomainePedagogique).order_by(models.DomainePedagogique.ordre))
    ]


@router.get("/domaines", response_model=list[DomaineAdmin])
def domaines(_: AdminCourant, session: SessionDB) -> list[DomaineAdmin]:
    return _vues_domaines(session)


@router.post("/domaines/{code}", response_model=list[DomaineAdmin])
def regler_domaine(code: str, corps: DomaineEdition, admin: AdminCourant, session: SessionDB) -> list[DomaineAdmin]:
    """Fermer au public bloque les nouvelles séances sans rien supprimer (EX.4) ; désactiver exige qu'aucun
    compte n'y soit plus habilité."""
    d = session.get(models.DomainePedagogique, code)
    if d is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Domaine introuvable.")
    if d.actif and not corps.actif:
        habilites = session.scalar(select(func.count(models.Habilitation.id)).where(models.Habilitation.domaine_code == code))
        if habilites:
            raise HTTPException(status.HTTP_409_CONFLICT,
                                f"{habilites} habilitation(s) portent sur {d.libelle} : retirez-les avant de le désactiver.")
    avant = {"code": code, "actif": d.actif, "public": d.public}
    d.actif, d.public = corps.actif, corps.public
    journal.noter(session, admin, "regler", "domaine", None, avant, {"code": code, **corps.model_dump()})
    session.commit()
    return _vues_domaines(session)


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


# --- Recherche globale (CDC V2, EA.1) ------------------------------------------------------------------

PAR_TYPE = 5  # quelques résultats par type : la page ouverte affiche ensuite la liste complète


def _vers(page: str, **params) -> str:
    return f"/admin/{page}?{urlencode(params)}" if params else f"/admin/{page}"


@router.get("/recherche", response_model=list[ResultatRecherche])
def recherche(_: AdminCourant, session: SessionDB, domaine: FiltreDomaine, q: str = "") -> list[ResultatRecherche]:
    """Comptes, familles, élèves, classes, groupes et contenus dont le nom, l'e-mail, le code ou le titre contient `q`.

    Les familles ne sortent qu'à partir de 3 caractères de leur e-mail, comme dans leur écran (EA.8).
    """
    q = " ".join(q.split()).lower()
    if len(q) < 2:
        raise HTTPException(422, "Saisissez au moins 2 caractères.")
    motif = f"%{q}%"
    maths = domaine is None or permissions.MATIERES.get(domaine) == "maths"
    anglais = domaine is None or permissions.MATIERES.get(domaine) == "anglais"
    trouves: list[ResultatRecherche] = []

    requete = select(models.Enseignant).where(
        or_(func.lower(models.Enseignant.nom).like(motif), func.lower(models.Enseignant.email).like(motif))
    )
    if domaine:
        requete = requete.where(models.Enseignant.habilitations.any(models.Habilitation.domaine_code == domaine))
    for e in session.scalars(requete.order_by(models.Enseignant.nom).limit(PAR_TYPE)):
        trouves.append(ResultatRecherche(type="Équipe", libelle=e.nom, detail=e.email, vers=_vers("professeurs", q=e.email)))

    if len(q) >= 3:
        requete = select(models.Parent).where(models.Parent.email.like(motif))
        if domaine:
            requete = requete.where(
                models.Parent.enfants.any(models.Eleve.classe.has(models.Classe.domaine_code == domaine))
            )
        for p in session.scalars(requete.order_by(models.Parent.email).limit(PAR_TYPE)):
            enfants = ", ".join(sorted(e.prenom for e in p.enfants)) or "aucun enfant rattaché"
            trouves.append(ResultatRecherche(type="Famille", libelle=p.email, detail=enfants, vers=_vers("familles", q=p.email)))

    if maths:
        filtre_classe = [models.Classe.domaine_code == domaine] if domaine else []
        requete = (
            select(models.Eleve).join(models.Classe)
            .where(or_(func.lower(models.Eleve.prenom).like(motif), func.lower(models.Eleve.identifiant).like(motif)))
            .where(*filtre_classe)
        )
        for e in session.scalars(requete.order_by(models.Eleve.prenom).limit(PAR_TYPE)):
            trouves.append(ResultatRecherche(
                type="Élève", libelle=e.prenom, detail=f"{e.classe.code} · {e.classe.enseignant.nom}",
                vers=_vers("eleves", q=e.prenom),
            ))
        requete = select(models.Classe).where(func.lower(models.Classe.code).like(motif)).where(*filtre_classe)
        for c in session.scalars(requete.order_by(models.Classe.code).limit(PAR_TYPE)):
            trouves.append(ResultatRecherche(
                type="Classe", libelle=c.code, detail=f"{c.enseignant.nom} · {len(c.eleves)} élève(s)",
                vers=_vers("eleves", onglet="classes"),
            ))
        filtre_chapitre = [models.Chapitre.domaine_code == domaine] if domaine else []
        requete = select(models.Chapitre).where(
            or_(func.lower(models.Chapitre.titre).like(motif), func.lower(models.Chapitre.code).like(motif))
        ).where(*filtre_chapitre)
        for ch in session.scalars(requete.order_by(models.Chapitre.niveau, models.Chapitre.ordre).limit(PAR_TYPE)):
            trouves.append(ResultatRecherche(
                type="Chapitre", libelle=ch.titre, detail=f"{ch.code} · {ch.niveau.value}",
                vers=_vers("cours", niveau=ch.niveau.value),
            ))
        requete = (
            select(models.Question).join(models.Competence).join(models.Chapitre)
            .where(func.lower(models.Question.code).like(motif), models.Question.archivee.is_(False))
            .where(*filtre_chapitre)
        )
        for qu in session.scalars(requete.order_by(models.Question.code).limit(PAR_TYPE)):
            trouves.append(ResultatRecherche(
                type="Exercice", libelle=qu.code, detail=qu.competence.chapitre.titre, vers=_vers("exercices", q=qu.code),
            ))

    if anglais:
        requete = select(models.GroupeAnglais).where(func.lower(models.GroupeAnglais.nom).like(motif))
        if domaine:
            requete = requete.where(models.GroupeAnglais.domaine_code == domaine)
        for g in session.scalars(requete.order_by(models.GroupeAnglais.nom).limit(PAR_TYPE)):
            trouves.append(ResultatRecherche(
                type="Groupe d'anglais", libelle=g.nom, detail=f"{g.niveau} · {g.enseignant.nom}", vers=_vers("anglais"),
            ))
        requete = (
            select(models.EleveAnglais).join(models.GroupeAnglais)
            .where(or_(
                func.lower(models.EleveAnglais.prenom).like(motif), func.lower(models.EleveAnglais.identifiant).like(motif)
            ))
        )
        if domaine:
            requete = requete.where(models.GroupeAnglais.domaine_code == domaine)
        for e in session.scalars(requete.order_by(models.EleveAnglais.prenom).limit(PAR_TYPE)):
            trouves.append(ResultatRecherche(
                type="Élève d'anglais", libelle=e.prenom, detail=e.groupe.nom, vers=_vers("anglais"),
            ))
        seances = [
            s for s in anglais_contenu.toutes(session)
            if (not domaine or s.domaine_code == domaine)
            and (q in s.code.lower() or q in s.courante.contenu["title"].lower())
        ]
        for s in seances[:PAR_TYPE]:
            trouves.append(ResultatRecherche(
                type="Séance d'anglais", libelle=f"{s.code} · {s.courante.contenu['title']}", detail=s.niveau,
                vers=_vers("anglais", onglet="seances"),
            ))
    return trouves
