"""Dossiers de français : consultation, validation et ouverture aux classes, réservées aux adultes habilités (#98, #212).

Même circuit que l'anglais (#212) :
- consultation : la version validée si elle existe, sinon la version courante, montrée NON VALIDÉE ;
- file de validation (`/francais/validation`) : versions soumises, relues puis validées ou refusées avec motif par un
  validateur habilité dans le domaine et le niveau ou par un administrateur (V2-D15), jamais par leur auteur ; chaque décision est journalisée ;
- ouverture : le professeur ouvre à sa classe un dossier dont une version est validée ; ses élèves n'en lisent que
  la partie élève validée (`app.routes.francais_eleves`), si la classe a accès au domaine (SEC-D6).

Un jeton d'élève, d'enfant ou de parent est refusé (401) partout ici ; la session professeur et la session
d'administration sont acceptées (#217). Un adulte doit être administrateur, ou
professeur/validateur habilité dans le domaine et le niveau du dossier ; le domaine doit être actif. L'ouverture au
public du domaine n'est ni nécessaire ni modifiée.
"""
# Issue #98 — Intégration du premier dossier Français 3e en DEV (Claude)

from typing import Annotated

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel, Field, ValidationError, field_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import correction, francais, francais_pdf, journal, permissions
from app.auth import AdulteAuthentifie, SessionDB
from app.db import models
from app.config import settings
from app.referentiel import Role
from app.routes.francais_eleves import vue_reponse
from app.routes.redactions import FERMEE

router = APIRouter(prefix="/francais", tags=["français"])


def membre_francais(enseignant: AdulteAuthentifie, session: SessionDB) -> models.Enseignant:
    if enseignant.mdp_provisoire:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Choisissez d'abord un nouveau mot de passe.")
    actifs = [code for code in francais.DOMAINES_FRANCAIS if francais.domaine_actif(session, code)]
    if not any(francais.peut_lire(enseignant, code, None) for code in actifs):
        raise HTTPException(status.HTTP_403_FORBIDDEN,
                            "Réservé aux adultes habilités en français, dans un domaine activé pour la préparation.")
    return enseignant


MembreFrancais = Annotated[models.Enseignant, Depends(membre_francais)]


def dossier_ou_404(session: Session, code: str, qui: models.Enseignant) -> models.DossierFrancais:
    """Dossier introuvable, de domaine inactif ou hors des habilitations : même réponse, rien n'est divulgué."""
    d = session.scalar(select(models.DossierFrancais).where(models.DossierFrancais.code == code))
    if d is None or not francais.domaine_actif(session, d.domaine_code) or not francais.peut_lire(qui, d.domaine_code, d.niveau):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Dossier introuvable.")
    return d


def _sans_cache(reponse: Response) -> None:
    # Corrigés et supports professeur : ni cache partagé, ni conservation par le navigateur.
    reponse.headers["Cache-Control"] = "private, no-store"


@router.get("/etat")
def etat(qui: AdulteAuthentifie, session: SessionDB, reponse: Response):
    """Issue #212 : pourquoi la liste est vide ou refusée (import absent, domaine non activé), pour l'administrateur
    seul, y compris quand aucun domaine français n'est actif. Les contrôles d'accès aux dossiers sont inchangés."""
    if qui.mdp_provisoire:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Choisissez d'abord un nouveau mot de passe.")
    if qui.role != Role.ADMIN:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Réservé aux administrateurs.")
    _sans_cache(reponse)
    return francais.etat(session)


@router.get("/dossiers")
def lister(qui: MembreFrancais, session: SessionDB, reponse: Response):
    _sans_cache(reponse)
    return [francais.resume(d, qui) for d in francais.lisibles(session, qui)]


def _affichee(version: models.DossierFrancaisVersion) -> dict:
    return {"version_affichee": version.numero, "validee": version.statut == "valide"}


@router.get("/dossiers/{code}/eleve")
def apercu_eleve(code: str, qui: MembreFrancais, session: SessionDB, reponse: Response):
    """Aperçu, pour l'adulte, de la partie élève (version validée, sinon courante NON VALIDÉE), sans corrigé."""
    _sans_cache(reponse)
    d = dossier_ou_404(session, code, qui)
    v = francais.version_professeur(d)
    return {**francais.resume(d, qui), **_affichee(v), "eleve": francais.vue_eleve(v)}


@router.get("/dossiers/{code}/professeur")
def supports_professeur(code: str, qui: MembreFrancais, session: SessionDB, reponse: Response):
    _sans_cache(reponse)
    d = dossier_ou_404(session, code, qui)
    v = francais.version_professeur(d)
    return {**francais.resume(d, qui), **_affichee(v), "professeur": francais.vue_professeur(v)}


@router.get("/dossiers/{code}/pdf/{public}")
def exporter_pdf(code: str, public: str, qui: MembreFrancais, session: SessionDB) -> Response:
    """Issue #217 : PDF de la version consultée (validée, sinon courante avec la mention NON VALIDÉ).

    « eleve » : partie élève seule, sans corrigé (ARCH-4) ; « professeur » : partie élève, supports et corrigés.
    Mêmes droits que la consultation : adulte habilité dans le domaine et le niveau, domaine actif.
    """
    if public not in francais_pdf.PUBLICS:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Export inconnu.")
    d = dossier_ou_404(session, code, qui)
    v = francais.version_professeur(d)
    suffixe = "" if v.statut == "valide" else "-NON-VALIDE"
    return Response(
        content=francais_pdf.produire_pdf(d, v, public), media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{d.code}-v{v.numero}-{public}{suffixe}.pdf"',
            "Cache-Control": "private, no-store", "X-Content-Type-Options": "nosniff",
        },
    )


@router.get("/dossiers/{code}/historique")
def historique(code: str, qui: MembreFrancais, session: SessionDB, reponse: Response):
    _sans_cache(reponse)
    return francais.historique(dossier_ou_404(session, code, qui))


class Refus(BaseModel):
    motif: Annotated[str, Field(max_length=2000)]

    @field_validator("motif")
    @classmethod
    def _motif(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Le motif du refus est obligatoire.")
        return v


def _decider(code: str, qui: models.Enseignant, session: Session, motif: str | None) -> dict:
    """Décision d'un validateur habilité (domaine et niveau), jamais l'auteur ; journalisée.

    Valider rend la version diffusable : elle remplace l'ancienne version validée dans les classes où le dossier est
    ouvert. Refuser laisse en place la version validée déjà diffusée.
    """
    d = dossier_ou_404(session, code, qui)
    if refus := francais.refus_validation(qui, d.domaine_code, d.niveau):
        raise HTTPException(status.HTTP_403_FORBIDDEN, refus)
    courante = d.courante
    if probleme := francais.peut_decider(courante, qui):
        raise HTTPException(status.HTTP_409_CONFLICT, probleme)
    if motif is None:
        francais.valider(d, qui)
    else:
        francais.refuser(d, qui, motif)
    journal.noter(session, qui, "valider" if motif is None else "refuser", "dossier_francais", d.id,
                  {"code": d.code, "version": courante.numero, "statut": "soumis"},
                  {"code": d.code, "version": courante.numero, "statut": courante.statut, "motif": motif})
    session.commit()
    return francais.resume(d, qui)


@router.post("/dossiers/{code}/valider")
def valider(code: str, qui: MembreFrancais, session: SessionDB):
    return _decider(code, qui, session, None)


@router.post("/dossiers/{code}/refuser")
def refuser(code: str, corps: Refus, qui: MembreFrancais, session: SessionDB):
    return _decider(code, qui, session, corps.motif)


# --- File de validation, comme l'anglais (#212) ------------------------------------------------------------------

def validateur_francais(enseignant: AdulteAuthentifie, session: SessionDB) -> models.Enseignant:
    """Validateur d'un domaine de français actif, qu'il y enseigne ou non (EX.9-bis), ou administrateur (V2-D15)."""
    if enseignant.mdp_provisoire:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Choisissez d'abord un nouveau mot de passe.")
    if not any(d in francais.DOMAINES_FRANCAIS and francais.domaine_actif(session, d)
               for d in permissions.domaines_valides(enseignant)):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Réservé aux validateurs de français.")
    return enseignant


ValidateurFrancais = Annotated[models.Enseignant, Depends(validateur_francais)]


def _a_relire(session: Session, code: str, qui: models.Enseignant) -> models.DossierFrancais:
    d = dossier_ou_404(session, code, qui)
    if refus := francais.refus_validation(qui, d.domaine_code, d.niveau):
        raise HTTPException(status.HTTP_403_FORBIDDEN, refus)
    return d


@router.get("/validation")
def a_valider(qui: ValidateurFrancais, session: SessionDB, reponse: Response):
    """Dossiers soumis que ce validateur peut relire ; les siens sont signalés (`est_auteur`), il ne peut pas les valider."""
    _sans_cache(reponse)
    return [francais.resume(d, qui) for d in francais.a_valider(session, qui)]


@router.get("/validation/{code}")
def version_a_valider(code: str, qui: ValidateurFrancais, session: SessionDB, reponse: Response):
    """La version soumise en entier : partie élève, supports professeur et historique des décisions."""
    _sans_cache(reponse)
    d = _a_relire(session, code, qui)
    c = d.courante
    return {**francais.resume(d, qui), **_affichee(c), "eleve": francais.vue_eleve(c),
            "professeur": francais.vue_professeur(c), "historique": francais.historique(d)}


@router.post("/validation/{code}/valider")
def valider_dossier(code: str, qui: ValidateurFrancais, session: SessionDB):
    return _decider(code, qui, session, None)


@router.post("/validation/{code}/refuser")
def refuser_dossier(code: str, corps: Refus, qui: ValidateurFrancais, session: SessionDB):
    return _decider(code, qui, session, corps.motif)


# --- Ouverture aux classes du professeur (#212) -----------------------------------------------------------------

class ClasseOuverture(BaseModel):
    id: int
    code: str
    niveau: str
    ouvert: bool
    ouvert_le: str | None = None
    # Les élèves ne lisent le dossier que si leur classe a accès au domaine (classe pilote d'un domaine fermé, SEC-D6).
    acces_eleves: bool
    motif_acces: str | None = None


def _classes(session: Session, d: models.DossierFrancais, qui: models.Enseignant) -> list[ClasseOuverture]:
    lignes = []
    for c in francais.classes_compatibles(qui, d):
        o = francais.ouverture(d, c)
        refus = permissions.refus_acces_classe(session, c)
        lignes.append(ClasseOuverture(
            id=c.id, code=c.code, niveau=francais.niveau_de(c), ouvert=o is not None,
            ouvert_le=o.ouvert_le.isoformat() if o and o.ouvert_le else None,
            acces_eleves=refus is None, motif_acces=refus,
        ))
    return lignes


def _ma_classe(session: Session, d: models.DossierFrancais, qui: models.Enseignant, classe_id: int) -> models.Classe:
    """Une classe active du professeur, du domaine et du niveau du dossier ; sinon 404, rien n'est divulgué."""
    classe = next((c for c in francais.classes_compatibles(qui, d) if c.id == classe_id), None)
    if classe is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Classe introuvable.")
    if qui.role != Role.ADMIN and not permissions.enseigne(qui, d.domaine_code, d.niveau):
        raise HTTPException(status.HTTP_403_FORBIDDEN, f"Vous n'enseignez pas le français en {d.niveau}.")
    return classe


@router.get("/dossiers/{code}/classes", response_model=list[ClasseOuverture])
def classes_du_dossier(code: str, qui: MembreFrancais, session: SessionDB) -> list[ClasseOuverture]:
    """Vos classes du niveau du dossier, et pour chacune : dossier ouvert ou non, accès des élèves ou motif du refus."""
    return _classes(session, dossier_ou_404(session, code, qui), qui)


@router.put("/dossiers/{code}/classes/{classe_id}", response_model=list[ClasseOuverture])
def ouvrir(code: str, classe_id: int, qui: MembreFrancais, session: SessionDB) -> list[ClasseOuverture]:
    """Ouvre le dossier à la classe ; seule sa version validée sera servie aux élèves. Sans effet s'il est déjà ouvert."""
    d = dossier_ou_404(session, code, qui)
    classe = _ma_classe(session, d, qui, classe_id)
    if d.validee is None:
        raise HTTPException(status.HTTP_409_CONFLICT,
                            "Aucune version de ce dossier n'est validée : il ne peut pas encore être ouvert aux élèves.")
    if francais.ouverture(d, classe) is None:
        d.ouvertures.append(models.OuvertureDossierFrancais(classe=classe, ouvert_par=qui))
        journal.noter(session, qui, "ouvrir", "dossier_francais", d.id,
                      apres={"code": d.code, "classe": classe.code, "version_validee": d.validee.numero})
        session.commit()
    return _classes(session, d, qui)


@router.delete("/dossiers/{code}/classes/{classe_id}", response_model=list[ClasseOuverture])
def fermer(code: str, classe_id: int, qui: MembreFrancais, session: SessionDB) -> list[ClasseOuverture]:
    """Retire le dossier à la classe : ses élèves ne le voient plus, immédiatement. Rien d'autre n'est supprimé."""
    d = dossier_ou_404(session, code, qui)
    classe = _ma_classe(session, d, qui, classe_id)
    if (o := francais.ouverture(d, classe)) is not None:
        d.ouvertures.remove(o)
        journal.noter(session, qui, "fermer", "dossier_francais", d.id, avant={"code": d.code, "classe": classe.code})
        session.commit()
    return _classes(session, d, qui)


# --- Suivi des classes : progression, mode de correction, réponses rédigées (#217, comme l'anglais) ---------------

def _classe_francais(session: Session, qui: models.Enseignant, classe_id: int) -> models.Classe:
    """Une classe de français active du professeur (ou toute classe de français pour l'administrateur) ; sinon 404."""
    classe = session.get(models.Classe, classe_id)
    if (classe is None or classe.archivee_le is not None or not classe.domaine_code.startswith("francais-")
            or (classe.enseignant_id != qui.id and qui.role != Role.ADMIN)):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Classe introuvable.")
    return classe


def _dossiers_ouverts(session: Session, classe: models.Classe) -> list[models.DossierFrancais]:
    """Dossiers ouverts à la classe et diffusables (version validée), vus par le professeur (même si la classe n'a
    plus accès au domaine : son suivi reste consultable)."""
    return [o.dossier for o in session.scalars(
        select(models.OuvertureDossierFrancais).where(models.OuvertureDossierFrancais.classe_id == classe.id)
    ) if o.dossier.validee is not None]


@router.get("/classes")
def mes_classes(qui: MembreFrancais, session: SessionDB):
    """Classes de français suivies : les siennes, ou toutes pour l'administrateur."""
    requete = select(models.Classe).where(models.Classe.archivee_le.is_(None), models.Classe.domaine_code.like("francais-%"))
    if qui.role != Role.ADMIN:
        requete = requete.where(models.Classe.enseignant_id == qui.id)
    return [
        {"id": c.id, "code": c.code, "niveau": francais.niveau_de(c), "mode_correction": c.mode_correction,
         "acces_eleves": permissions.refus_acces_classe(session, c) is None,
         "dossiers": [{"code": d.code, "titre": d.titre} for d in _dossiers_ouverts(session, c)]}
        for c in session.scalars(requete.order_by(models.Classe.code))
    ]


@router.get("/classes/{classe_id}/progression")
def progression_de_la_classe(classe_id: int, qui: MembreFrancais, session: SessionDB, reponse: Response):
    """Par élève et par dossier : meilleur score au quiz, score du premier essai, essais, auto-évaluation, et
    réponses rédigées remises ou relues (nombres seulement)."""
    _sans_cache(reponse)
    classe = _classe_francais(session, qui, classe_id)
    dossiers = _dossiers_ouverts(session, classe)
    codes = [d.code for d in dossiers]
    eleves = sorted(classe.eleves, key=lambda e: e.prenom.lower())
    ids = [e.id for e in eleves]
    suivi = {(p.eleve_id, p.code): p for p in session.scalars(select(models.ProgressionFrancais).where(
        models.ProgressionFrancais.eleve_id.in_(ids), models.ProgressionFrancais.code.in_(codes)))}
    redigees: dict[tuple[int, str], list[str]] = {}
    for r in session.scalars(select(models.ReponseRedigeeFrancais).where(
            models.ReponseRedigeeFrancais.eleve_id.in_(ids), models.ReponseRedigeeFrancais.statut != "brouillon")):
        redigees.setdefault((r.eleve_id, r.code), []).append(r.statut)
    return {
        "classe": {"id": classe.id, "code": classe.code, "niveau": francais.niveau_de(classe)},
        "dossiers": [{"code": d.code, "titre": d.titre, "nb_quiz": len(d.validee.quiz or []),
                      "je_sais": d.validee.eleve.get("je_sais", [])} for d in dossiers],
        "eleves": [
            {"id": e.id, "prenom": e.prenom, "dossiers": {
                code: {
                    "score": p.meilleur_score if p else None, "premier_score": p.premier_score if p else None,
                    "total": p.total if p else None, "tentatives": p.tentatives if p else 0,
                    "auto_evaluation": p.auto_evaluation if p else [],
                    "a_relire": redigees.get((e.id, code), []).count("remise"),
                    "relues": redigees.get((e.id, code), []).count("corrigee"),
                } for code in codes for p in [suivi.get((e.id, code))]
            }}
            for e in eleves
        ],
    }


class ChoixModeDossier(BaseModel):
    mode: correction.ModeCorrection | None


def _reglage(classe: models.Classe) -> dict:
    return {"mode": classe.mode_correction, "dossiers": {m.code: m.mode for m in classe.modes_dossiers}}


@router.get("/classes/{classe_id}/correction")
def mode_de_correction(classe_id: int, qui: MembreFrancais, session: SessionDB):
    return _reglage(_classe_francais(session, qui, classe_id))


@router.put("/classes/{classe_id}/correction")
def regler_correction(classe_id: int, corps: correction.ChoixMode, qui: MembreFrancais, session: SessionDB):
    classe = _classe_francais(session, qui, classe_id)
    avant, classe.mode_correction = classe.mode_correction, corps.mode
    journal.noter(session, qui, "regler-correction", "classe", classe.id, {"mode": avant}, {"mode": corps.mode})
    session.commit()
    return _reglage(classe)


@router.put("/classes/{classe_id}/dossiers/{code}/correction")
def regler_correction_dossier(classe_id: int, code: str, corps: ChoixModeDossier, qui: MembreFrancais, session: SessionDB):
    """Mode propre à un dossier pour cette classe ; `null` le retire (le dossier suit le mode de la classe)."""
    classe = _classe_francais(session, qui, classe_id)
    if code not in {d.code for d in _dossiers_ouverts(session, classe)}:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Dossier non ouvert à cette classe.")
    actuel = next((m for m in classe.modes_dossiers if m.code == code), None)
    avant = actuel.mode if actuel else None
    if corps.mode is None:
        if actuel is not None:
            classe.modes_dossiers.remove(actuel)
    elif actuel is None:
        classe.modes_dossiers.append(models.ModeCorrectionDossierFrancais(code=code, mode=corps.mode))
    else:
        actuel.mode = corps.mode
    journal.noter(session, qui, "regler-correction", "classe", classe.id, {"dossier": code, "mode": avant},
                  {"dossier": code, "mode": corps.mode})
    session.commit()
    return _reglage(classe)


def _redaction_ouverte() -> None:
    if not settings.redaction_active:
        raise HTTPException(status.HTTP_403_FORBIDDEN, FERMEE)


@router.get("/classes/{classe_id}/reponses")
def reponses_de_la_classe(classe_id: int, qui: MembreFrancais, session: SessionDB, reponse: Response):
    """Réponses rédigées remises ou relues (jamais les brouillons), pour le seul professeur de la classe (RGPD-2)."""
    _redaction_ouverte()
    _sans_cache(reponse)
    classe = _classe_francais(session, qui, classe_id)
    if classe.enseignant_id != qui.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Classe introuvable.")
    eleves = {e.id: e for e in classe.eleves}
    lignes = session.scalars(select(models.ReponseRedigeeFrancais).where(
        models.ReponseRedigeeFrancais.eleve_id.in_(eleves), models.ReponseRedigeeFrancais.statut != "brouillon"
    ).order_by(models.ReponseRedigeeFrancais.code, models.ReponseRedigeeFrancais.question))
    return [{"id": r.id, "eleve_id": r.eleve_id, "prenom": eleves[r.eleve_id].prenom, "dossier": r.code,
             **vue_reponse(r)} for r in lignes]


class Retour(BaseModel):
    commentaire: Annotated[str, Field(min_length=1, max_length=5000)]


@router.put("/reponses/{reponse_id}/retour")
def faire_un_retour(reponse_id: int, corps: Retour, qui: MembreFrancais, session: SessionDB):
    """Retour du professeur de la classe sur une réponse remise ; l'élève peut ensuite la réécrire. Journalisé sans
    le texte de l'élève ni le commentaire."""
    _redaction_ouverte()
    r = session.get(models.ReponseRedigeeFrancais, reponse_id)
    if r is None or r.statut == "brouillon" or r.eleve.classe.enseignant_id != qui.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Réponse introuvable.")
    r.commentaire, r.statut, r.corrigee_le, r.correcteur_id = corps.commentaire.strip(), "corrigee", datetime.now(UTC), qui.id
    journal.noter(session, qui, "retour", "reponse_redigee_francais", r.id,
                  apres={"dossier": r.code, "question": r.question, "eleve": r.eleve_id})
    session.commit()
    return vue_reponse(r)


# --- Édition dans l'application par l'administrateur (#217, comme les séances d'anglais) ---------------------------

def _admin(qui: models.Enseignant) -> None:
    if qui.role != Role.ADMIN:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Réservé aux administrateurs.")


def source(dossier: models.DossierFrancais, version: models.DossierFrancaisVersion) -> dict:
    """Le dossier au format du fichier d'import (docs/francais/FORMAT-IMPORT.md), pour l'éditer."""
    return {**version.meta, "code": dossier.code, "domaine": dossier.domaine_code, "niveau": dossier.niveau,
            "titre": dossier.titre, "eleve": version.eleve, "professeur": version.professeur,
            "quiz": list(version.quiz or [])}


@router.get("/dossiers/{code}/source")
def source_du_dossier(code: str, qui: MembreFrancais, session: SessionDB, reponse: Response):
    _admin(qui)
    _sans_cache(reponse)
    d = dossier_ou_404(session, code, qui)
    return {**_affichee(d.courante), "statut": d.courante.statut, "source": source(d, d.courante)}


@router.put("/dossiers/{code}/brouillon")
def enregistrer_brouillon(code: str, corps: dict, qui: MembreFrancais, session: SessionDB):
    """Même contrat que l'import. Une version validée n'est jamais modifiée : une nouvelle version « brouillon » est
    créée ; un brouillon, une version refusée ou soumise est repris en brouillon (le validateur ne valide pas un
    contenu qui bouge)."""
    _admin(qui)
    d = dossier_ou_404(session, code, qui)
    try:
        fichier = francais.FichierDossier.model_validate(corps)
    except ValidationError as exc:
        erreurs = [f"{'.'.join(map(str, e['loc'])) or 'dossier'} : {e['msg']}" for e in exc.errors()]
        raise HTTPException(422, "Dossier invalide : " + " ; ".join(erreurs[:10])) from exc
    if (fichier.code, fichier.domaine, fichier.niveau) != (d.code, d.domaine_code, d.niveau):
        raise HTTPException(422, "Le code, le domaine et le niveau d'un dossier ne changent pas.")
    donnees = fichier.model_dump(mode="json")
    empreinte = francais.empreinte(donnees)
    courante = d.courante
    if courante.statut in ("valide", "archive"):
        courante = models.DossierFrancaisVersion(numero=courante.numero + 1, empreinte="", meta={}, eleve={}, professeur={})
        d.versions.append(courante)
    if any(v.empreinte == empreinte for v in d.versions if v is not courante):
        raise HTTPException(status.HTTP_409_CONFLICT, "Ce contenu est identique à une version existante.")
    courante.eleve, courante.professeur, courante.quiz = donnees["eleve"], donnees["professeur"], donnees["quiz"]
    courante.meta = {k: donnees[k] for k in ("format", "cible", "competences_locales", "attribution", "registre")}
    courante.empreinte, courante.statut, courante.auteur, courante.motif_refus = empreinte, "brouillon", qui, None
    courante.validateur, courante.decide_le = None, None
    d.titre = fichier.titre
    journal.noter(session, qui, "modifier", "dossier_francais", d.id, apres={"code": d.code, "version": courante.numero})
    session.commit()
    return francais.resume(d, qui)


@router.post("/dossiers/{code}/soumettre")
def soumettre(code: str, qui: MembreFrancais, session: SessionDB):
    """Brouillon → soumis : la version rejoint la file de validation ; son auteur ne pourra pas la valider."""
    _admin(qui)
    d = dossier_ou_404(session, code, qui)
    if d.courante.statut != "brouillon":
        raise HTTPException(status.HTTP_409_CONFLICT, "Seul un brouillon peut être soumis à la validation.")
    d.courante.statut = "soumis"
    journal.noter(session, qui, "soumettre", "dossier_francais", d.id, apres={"code": d.code, "version": d.courante.numero})
    session.commit()
    return francais.resume(d, qui)
