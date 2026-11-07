"""Actions en masse de l'administrateur : inscription par fichier Excel, blocage temporaire et suppression
de plusieurs enfants, familles, classes ou groupes d'anglais cochés dans les listes."""

from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Body, HTTPException, Response
from pydantic import BaseModel, Field
from sqlalchemy import select

from app import archives, import_familles, import_professeurs, inscriptions, journal, parents
from app.auth import AdminCourant, SessionDB
from app.db import models

router = APIRouter(prefix="/admin", tags=["admin"])

MIME_XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
MOT_DE_CONFIRMATION = "SUPPRIMER"

Ids = Annotated[list[int], Field(min_length=1, max_length=500)]


class Selection(BaseModel):
    ids: Ids


class Blocage(Selection):
    bloque: bool


class Suppression(Selection):
    confirmation: str


class SuppressionFamilles(Suppression):
    # Vrai : les enfants qui n'ont pas d'autre parent sont effacés avec la famille (sinon ils restent).
    avec_enfants: bool = False


class ResultatMasse(BaseModel):
    traites: int


# --- Inscription par fichier Excel ---------------------------------------------------------------------


@router.get("/import/modele")
def modele_import(_: AdminCourant, session: SessionDB) -> Response:
    """Modèle à remplir, avec les listes des classes et des groupes existants."""
    return Response(
        import_familles.modele(session), media_type=MIME_XLSX,
        headers={"Content-Disposition": 'attachment; filename="pkp-modele-inscriptions.xlsx"'},
    )


@router.post("/import", response_model=import_familles.RapportImport)
def importer(
    admin: AdminCourant, session: SessionDB, fichier: Annotated[bytes, Body(media_type=MIME_XLSX)],
    simulation: bool = True,
) -> import_familles.RapportImport:
    """Corps : le classeur rempli. `simulation` (par défaut) vérifie sans rien écrire ; sinon tout est créé,
    ou rien si une ligne est en erreur. Les mots de passe provisoires et les codes ne sont donnés qu'ici."""
    try:
        rapport = import_familles.importer(session, fichier, simulation)
    except import_familles.FichierInvalide as e:
        raise HTTPException(422, str(e)) from e
    if not simulation and not rapport.nb_erreurs:
        journal.noter(session, admin, "importer", "familles", None,
                      apres={"enfants": rapport.nb_enfants, "comptes_crees": rapport.nb_comptes_nouveaux})
        session.commit()
    return rapport


@router.get("/import/professeurs/modele")
def modele_import_professeurs(_: AdminCourant) -> Response:
    """Modèle à remplir : une ligne par professeur (nom, e-mail, matières)."""
    return Response(
        import_professeurs.modele(), media_type=MIME_XLSX,
        headers={"Content-Disposition": 'attachment; filename="boussole-modele-professeurs.xlsx"'},
    )


@router.post("/import/professeurs", response_model=import_professeurs.RapportProfesseurs)
def importer_professeurs(
    admin: AdminCourant, session: SessionDB, fichier: Annotated[bytes, Body(media_type=MIME_XLSX)],
    simulation: bool = True,
) -> import_professeurs.RapportProfesseurs:
    """Corps : le classeur rempli. `simulation` (par défaut) vérifie sans rien écrire ; sinon tous les comptes
    sont créés, ou aucun. Les mots de passe provisoires ne sont donnés qu'ici, jamais journalisés."""
    try:
        rapport = import_professeurs.importer(session, fichier, simulation, admin)
    except import_familles.FichierInvalide as e:
        raise HTTPException(422, str(e)) from e
    if not simulation and not rapport.nb_erreurs and rapport.comptes:
        for c in rapport.comptes:
            journal.noter(session, admin, "creer", "enseignant", c.id, apres={"nom": c.nom, "email": c.email, "import": True})
        journal.noter(session, admin, "importer", "professeurs", None, apres={"comptes_crees": len(rapport.comptes)})
        session.commit()
    return rapport


# --- Blocage temporaire ----------------------------------------------------------------------------------


def _trouver(session: SessionDB, modele, ids: list[int], libelle: str) -> list:
    trouves = list(session.scalars(select(modele).where(modele.id.in_(ids))))
    if len(trouves) != len(set(ids)):
        raise HTTPException(404, f"{libelle} introuvable : actualisez la liste.")
    return trouves


def _bloquer(session: SessionDB, admin, objets: list, corps: Blocage, objet: str) -> ResultatMasse:
    maintenant = datetime.now(UTC)
    changes = [o for o in objets if (o.bloque_le is not None) != corps.bloque]
    for o in changes:
        o.bloque_le = maintenant if corps.bloque else None
    if changes:
        journal.noter(session, admin, "bloquer" if corps.bloque else "debloquer", objet, None,
                      apres={"ids": [o.id for o in changes]})
    session.commit()
    return ResultatMasse(traites=len(changes))


@router.post("/enfants/blocage", response_model=ResultatMasse)
def bloquer_enfants(corps: Blocage, admin: AdminCourant, session: SessionDB) -> ResultatMasse:
    """Suspend (ou rétablit) la carte des enfants, dans toutes leurs matières ; leurs sessions ouvertes se
    ferment. Rien n'est effacé."""
    return _bloquer(session, admin, _trouver(session, models.Enfant, corps.ids, "Enfant"), corps, "enfant")


@router.post("/parents/blocage", response_model=ResultatMasse)
def bloquer_parents(corps: Blocage, admin: AdminCourant, session: SessionDB) -> ResultatMasse:
    """Suspend (ou rétablit) le compte des parents ; les cartes de leurs enfants ne changent pas."""
    return _bloquer(session, admin, _trouver(session, models.Parent, corps.ids, "Famille"), corps, "parent")


# --- Suppression en masse --------------------------------------------------------------------------------


def _confirmer(corps: Suppression) -> None:
    if corps.confirmation.strip().upper() != MOT_DE_CONFIRMATION:
        raise HTTPException(422, f"Saisissez {MOT_DE_CONFIRMATION} pour confirmer.")


@router.post("/enfants/suppression", response_model=ResultatMasse)
def supprimer_enfants(corps: Suppression, admin: AdminCourant, session: SessionDB) -> ResultatMasse:
    """Efface les enfants et toutes leurs inscriptions (séances et réponses comprises). Un compte parent qui
    n'a plus aucun enfant est supprimé (RGPD)."""
    _confirmer(corps)
    choisis = _trouver(session, models.Enfant, corps.ids, "Enfant")
    journal.noter(session, admin, "supprimer-en-masse", "enfant", None,
                  avant={"ids": [e.id for e in choisis], "identifiants": [e.identifiant for e in choisis]})
    for enfant in choisis:
        session.delete(enfant)
    parents.supprimer_orphelins(session)
    session.commit()
    return ResultatMasse(traites=len(choisis))


@router.post("/parents/suppression", response_model=ResultatMasse)
def supprimer_familles(corps: SuppressionFamilles, admin: AdminCourant, session: SessionDB) -> ResultatMasse:
    """Supprime les comptes parents. Avec `avec_enfants`, les enfants qui n'ont pas d'autre parent sont
    effacés aussi ; sinon ils restent, avec leur travail."""
    _confirmer(corps)
    choisis = _trouver(session, models.Parent, corps.ids, "Famille")
    ids = {p.id for p in choisis}
    effaces = [
        e for e in {e.id: e for p in choisis for e in p.famille}.values()
        if corps.avec_enfants and all(p.id in ids for p in e.parents)
    ]
    journal.noter(session, admin, "supprimer-en-masse", "parent", None,
                  avant={"ids": sorted(ids), "enfants_effaces": [e.id for e in effaces]})
    for objet in (*effaces, *choisis):
        session.delete(objet)
    session.commit()
    return ResultatMasse(traites=len(choisis))


@router.post("/classes/suppression", response_model=ResultatMasse)
def supprimer_classes(corps: Suppression, admin: AdminCourant, session: SessionDB) -> ResultatMasse:
    """Supprime les classes, leurs inscriptions, séances et réponses. Les enfants des familles et leurs
    autres inscriptions restent."""
    _confirmer(corps)
    choisies = _trouver(session, models.Classe, corps.ids, "Classe")
    journal.noter(session, admin, "supprimer-en-masse", "classe", None,
                  avant={"codes": [c.code for c in choisies], "eleves": sum(len(c.eleves) for c in choisies)})
    for classe in choisies:
        archives.archiver_classe(session, classe, archives.par_admin(admin))
        for eleve in classe.eleves:
            inscriptions.delier(session, eleve)
        session.delete(classe)
    parents.supprimer_orphelins(session)
    session.commit()
    return ResultatMasse(traites=len(choisies))


@router.post("/anglais/groupes/suppression", response_model=ResultatMasse)
def supprimer_groupes(corps: Suppression, admin: AdminCourant, session: SessionDB) -> ResultatMasse:
    """Supprime les groupes d'anglais et le travail d'anglais de leurs élèves ; les enfants restent."""
    _confirmer(corps)
    choisis = _trouver(session, models.GroupeAnglais, corps.ids, "Groupe")
    journal.noter(session, admin, "supprimer-en-masse", "groupe_anglais", None,
                  avant={"noms": [g.nom for g in choisis], "eleves": sum(len(g.eleves) for g in choisis)})
    for groupe in choisis:
        archives.archiver_groupe(session, groupe, archives.par_admin(admin))
        session.delete(groupe)
    session.commit()
    return ResultatMasse(traites=len(choisis))
