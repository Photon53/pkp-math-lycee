"""Séances PKP Anglais, génération PDF, groupes d'élèves et validation, réservés aux professeurs d'anglais."""
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import Response
from pkp_anglais.contenu import seance_depuis_dict
from pkp_anglais.seances import generer_pack_animateur, generer_pack_eleve
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import archives, anglais_contenu, journal, permissions
from app.anglais_pdf import produire_pdf
from app.anglais_pictos import image_svg
from app.auth import EnseignantAnglais, EnseignantAuthentifie, SessionDB
from app.db import models
from app.schemas import CreationEleves, EleveRenommage
from app.security import generer_code_eleve, hacher_code_eleve

router = APIRouter(prefix="/anglais", tags=["anglais"])


def seance_ou_404(session: Session, code: str) -> models.SeanceAnglais:
    seance = anglais_contenu.par_code(session, code)
    if seance is None:
        raise HTTPException(404, "Séance introuvable.")
    return seance


def version_professeur(seance: models.SeanceAnglais) -> models.SeanceAnglaisVersion:
    """La version validée si elle existe ; sinon la version courante, montrée avec la mention NON VALIDÉ."""
    return seance.publiee or seance.courante


def pack(version: models.SeanceAnglaisVersion, public: str = "animateur") -> dict:
    try:
        seance = seance_depuis_dict(version.contenu)
    except (ValueError, KeyError, TypeError) as exc:
        raise HTTPException(503, "Contenu pédagogique indisponible.") from exc
    return generer_pack_eleve(seance) if public == "eleve" else generer_pack_animateur(seance)


def detail(version: models.SeanceAnglaisVersion) -> dict:
    """Tout le contenu du cahier, pour que l'écran montre le même cours que le PDF.

    Les écoutes restent de simples liens : rien n'est intégré, donc aucun traceur tiers.
    """
    r = version.cahier
    return {
        **pack(version), "version": version.numero, "statut": version.statut, "validee": version.statut == "valide",
        "cahier": {**r, "visual": [{**v, "image": image_svg(v["picto"])} for v in r["visual"]]},
        "quiz": anglais_contenu.quiz_complet(version),
    }


def reponse_pdf(version: models.SeanceAnglaisVersion, code: str, public: str) -> Response:
    if public not in ("eleve", "animateur"):
        raise HTTPException(404, "Pack inconnu.")
    validee = version.statut == "valide"
    contenu = produire_pdf(pack(version, public), public, version.cahier, validee=validee)
    suffixe = "" if validee else "-NON-VALIDE"
    return Response(
        content=contenu,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="pkp-anglais-{code}-{public}{suffixe}.pdf"',
            "Cache-Control": "private, no-store",
            "X-Content-Type-Options": "nosniff",
        },
    )


@router.get("/seances")
def lister_seances(_: EnseignantAnglais, session: SessionDB):
    return [{**anglais_contenu.resume(s), "validee": s.publiee is not None} for s in anglais_contenu.toutes(session)]


@router.get("/seances/{code}")
def consulter_seance(code: str, _: EnseignantAnglais, session: SessionDB):
    return detail(version_professeur(seance_ou_404(session, code)))


@router.get("/seances/{code}/pdf/{public}")
def telecharger_pdf(code: str, public: str, _: EnseignantAnglais, session: SessionDB):
    return reponse_pdf(version_professeur(seance_ou_404(session, code)), code, public)


# --- Validation par un professeur référent ------------------------------------
# Le référent est coché par un administrateur ; il ne valide jamais son propre contenu (CDC anglais V1.8).

def referent(enseignant: EnseignantAuthentifie) -> models.Enseignant:
    """Validateur d'Anglais collège, qu'il y enseigne ou non : la qualification suffit (EX.9-bis)."""
    if enseignant.mdp_provisoire:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Choisissez d'abord un nouveau mot de passe.")
    if not any(permissions.MATIERES.get(d) == "anglais" for d in permissions.domaines_valides(enseignant)):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Réservé aux validateurs d'anglais.")
    return enseignant


Referent = Annotated[models.Enseignant, Depends(referent)]


class Refus(BaseModel):
    motif: Annotated[str, Field(max_length=2000)]

    @field_validator("motif")
    @classmethod
    def _motif(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Le motif du refus est obligatoire.")
        return v


def decider(seance: models.SeanceAnglais, qui: models.Enseignant, session: Session, motif: str | None) -> dict:
    """Valide (sans motif) ou refuse la version soumise ; la décision est journalisée."""
    courante = seance.courante
    refus = permissions.refus_validation(qui, seance.domaine_code, seance.niveau)
    if refus:
        raise HTTPException(status.HTTP_403_FORBIDDEN, refus)
    probleme = anglais_contenu.peut_decider(courante, qui)
    if probleme:
        raise HTTPException(status.HTTP_409_CONFLICT, probleme)
    if motif is None:
        anglais_contenu.valider(seance, qui)
    else:
        anglais_contenu.refuser(seance, qui, motif)
    journal.noter(session, qui, "valider" if motif is None else "refuser", "seance_anglais", seance.id,
                  {"code": seance.code, "version": courante.numero, "statut": "soumis"},
                  {"code": seance.code, "version": courante.numero, "statut": courante.statut, "motif": motif})
    session.commit()
    return anglais_contenu.resume(seance)


@router.get("/validation")
def a_valider(qui: Referent, session: SessionDB):
    """Séances soumises, en signalant celles que ce référent a écrites (il ne peut pas les valider)."""
    return [
        {**anglais_contenu.resume(s), "est_auteur": s.courante.auteur_id == qui.id}
        for s in anglais_contenu.toutes(session)
        if s.courante.statut == "soumis" and permissions.peut_valider(qui, s.domaine_code, s.niveau)
    ]


@router.get("/validation/{code}")
def version_a_valider(code: str, _: Referent, session: SessionDB):
    seance = seance_ou_404(session, code)
    return {**detail(seance.courante), "historique": anglais_contenu.historique(seance)}


@router.get("/validation/{code}/pdf/{public}")
def pdf_a_valider(code: str, public: str, _: Referent, session: SessionDB):
    return reponse_pdf(seance_ou_404(session, code).courante, code, public)


@router.post("/validation/{code}/valider")
def valider_seance(code: str, qui: Referent, session: SessionDB):
    return decider(seance_ou_404(session, code), qui, session, None)


@router.post("/validation/{code}/refuser")
def refuser_seance(code: str, corps: Refus, qui: Referent, session: SessionDB):
    return decider(seance_ou_404(session, code), qui, session, corps.motif)


# --- Groupes d'élèves (4e, 3e) ------------------------------------------------
# Séparés des classes de maths (niveaux lycée, parcours, chapitres) : le CDC anglais interdit de les détourner.

ELEVES_PAR_GROUPE = 30  # le CDC recommande 8 à 10 élèves ; la limite évite seulement les saisies aberrantes


class GroupeRenommage(BaseModel):
    nom: Annotated[str, Field(max_length=60)]

    @field_validator("nom")
    @classmethod
    def _nom(cls, v: str) -> str:
        v = " ".join(v.split())
        if not v:
            raise ValueError("Donnez un nom au groupe.")
        return v


class GroupeCreation(GroupeRenommage):
    niveau: Annotated[str, Field(max_length=4)]


class EleveAnglaisResume(BaseModel):
    id: int
    prenom: str
    identifiant: str | None = None
    # Le code lui-même n'est jamais relu : seule son empreinte est stockée.
    a_un_code: bool = False


class CodeEleveAnglais(BaseModel):
    """Montré une seule fois, à imprimer ou distribuer : le serveur n'en garde que l'empreinte."""

    id: int
    prenom: str
    identifiant: str
    code: str


class GroupeResume(BaseModel):
    id: int
    nom: str
    niveau: str
    eleves: list[EleveAnglaisResume]


class ResultatInscription(BaseModel):
    groupe: GroupeResume
    crees: list[CodeEleveAnglais] = []
    deja_presents: list[str]


def identifiant_de(eleve: models.EleveAnglais) -> str | None:
    """L'enfant d'une famille garde l'identifiant de sa carte, comme en maths."""
    return eleve.enfant.identifiant if eleve.enfant is not None else eleve.identifiant


def resume_eleve(e: models.EleveAnglais) -> EleveAnglaisResume:
    return EleveAnglaisResume(id=e.id, prenom=e.prenom, identifiant=identifiant_de(e), a_un_code=e.code_hash is not None)


def _resume(groupe: models.GroupeAnglais) -> GroupeResume:
    eleves = sorted(groupe.eleves, key=lambda e: e.prenom.lower())
    return GroupeResume(id=groupe.id, nom=groupe.nom, niveau=groupe.niveau, eleves=[resume_eleve(e) for e in eleves])


def identifiant_libre(session: Session, prenom: str) -> str:
    """Identifiant unique sur toute la plateforme : un élève de maths et un d'anglais ne le partagent jamais."""
    from app import enfants

    return enfants.identifiant_libre(session, prenom)


def attribuer_code(session: Session, eleve: models.EleveAnglais) -> CodeEleveAnglais:
    if eleve.enfant is not None:  # enfant d'une famille : sa carte unique change pour toutes ses inscriptions
        from app import enfants

        code = enfants.nouveau_code(eleve.enfant)
        return CodeEleveAnglais(id=eleve.id, prenom=eleve.prenom, identifiant=eleve.enfant.identifiant, code=code)
    code = generer_code_eleve()
    eleve.code_hash = hacher_code_eleve(code)  # invalide aussi les jetons émis avec l'ancien code
    if not eleve.identifiant:
        eleve.identifiant = identifiant_libre(session, eleve.prenom)
        session.flush()  # deux élèves créés ensemble ne tirent pas le même identifiant
    return CodeEleveAnglais(id=eleve.id, prenom=eleve.prenom, identifiant=eleve.identifiant, code=code)


def groupes_actifs(enseignant: models.Enseignant) -> list[models.GroupeAnglais]:
    """Groupes non archivés : un groupe de l'an dernier ne bloque pas le même nom cette année (V3, Lot 3)."""
    return [g for g in enseignant.groupes_anglais if g.archivee_le is None]


def _mon_groupe(session: SessionDB, groupe_id: int, enseignant: models.Enseignant) -> models.GroupeAnglais:
    groupe = session.get(models.GroupeAnglais, groupe_id)
    if groupe is None or groupe.enseignant_id != enseignant.id or groupe.archivee_le is not None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Groupe introuvable.")
    return groupe


def _mon_eleve(session: Session, groupe: models.GroupeAnglais, eleve_id: int) -> models.EleveAnglais:
    eleve = session.get(models.EleveAnglais, eleve_id)
    if eleve is None or eleve.groupe_id != groupe.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Élève introuvable.")
    return eleve


@router.get("/groupes", response_model=list[GroupeResume])
def mes_groupes(enseignant: EnseignantAnglais) -> list[GroupeResume]:
    # 4e avant 3e, comme le programme.
    groupes = sorted(groupes_actifs(enseignant), key=lambda g: (models.NIVEAUX_ANGLAIS.index(g.niveau), g.nom.lower()))
    return [_resume(g) for g in groupes]


@router.post("/groupes", response_model=GroupeResume, status_code=status.HTTP_201_CREATED)
def creer_groupe(corps: GroupeCreation, enseignant: EnseignantAnglais, session: SessionDB) -> GroupeResume:
    groupe = ouvrir_groupe(session, enseignant, corps)
    session.commit()
    return _resume(groupe)


def ouvrir_groupe(session: Session, enseignant: models.Enseignant, corps: GroupeCreation) -> models.GroupeAnglais:
    """Crée le groupe d'un professeur d'anglais ; sert aussi à l'administrateur."""
    if any(g.nom.lower() == corps.nom.lower() for g in groupes_actifs(enseignant)):
        raise HTTPException(status.HTTP_409_CONFLICT, "Vous avez déjà un groupe de ce nom.")
    domaine = permissions.domaine_anglais(corps.niveau)
    refus = permissions.refus_niveau(session, domaine, corps.niveau)
    if refus:
        raise HTTPException(422, refus)
    refus = permissions.refus_domaine_ferme(session, domaine)
    if refus:
        raise HTTPException(status.HTTP_403_FORBIDDEN, refus)
    # Le collège reste ouvert à tout professeur d'anglais (case historique) ; le lycée demande son habilitation.
    if domaine != permissions.ANGLAIS_COLLEGE and not permissions.enseigne(enseignant, domaine, corps.niveau):
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            f"{enseignant.nom} n'est pas habilité pour {permissions.LIBELLES[domaine]} : accordez-le dans « Équipe ».",
        )
    groupe = models.GroupeAnglais(nom=corps.nom, niveau=corps.niveau, enseignant=enseignant, domaine_code=domaine)
    session.add(groupe)
    session.flush()
    return groupe


@router.patch("/groupes/{groupe_id}", response_model=GroupeResume)
def renommer_groupe(groupe_id: int, corps: GroupeRenommage, enseignant: EnseignantAnglais, session: SessionDB) -> GroupeResume:
    groupe = _mon_groupe(session, groupe_id, enseignant)
    if any(g.id != groupe.id and g.nom.lower() == corps.nom.lower() for g in groupes_actifs(enseignant)):
        raise HTTPException(status.HTTP_409_CONFLICT, "Vous avez déjà un groupe de ce nom.")
    groupe.nom = corps.nom
    session.commit()
    return _resume(groupe)


@router.patch("/groupes/{groupe_id}/eleves/{eleve_id}", response_model=EleveAnglaisResume)
def renommer_eleve(
    groupe_id: int, eleve_id: int, corps: EleveRenommage, enseignant: EnseignantAnglais, session: SessionDB
) -> EleveAnglaisResume:
    from app import enfants

    eleve = _mon_eleve(session, _mon_groupe(session, groupe_id, enseignant), eleve_id)
    try:
        enfants.renommer_inscription(eleve, corps.prenom, enseignant.id)
    except enfants.RenommageRefuse as e:
        raise HTTPException(status.HTTP_403_FORBIDDEN, str(e)) from e
    except enfants.InscriptionImpossible as e:
        raise HTTPException(status.HTTP_409_CONFLICT, str(e)) from e
    session.commit()
    return resume_eleve(eleve)


@router.post("/groupes/{groupe_id}/eleves", response_model=ResultatInscription, status_code=status.HTTP_201_CREATED)
def inscrire_eleves(
    groupe_id: int, corps: CreationEleves, enseignant: EnseignantAnglais, session: SessionDB
) -> ResultatInscription:
    """Inscrit des élèves par leur seul prénom et leur attribue identifiant et code ; les présents sont ignorés."""
    groupe = _mon_groupe(session, groupe_id, enseignant)
    existants = {e.prenom for e in groupe.eleves}
    nouveaux = [p for p in corps.prenoms if p not in existants]
    if len(groupe.eleves) + len(nouveaux) > ELEVES_PAR_GROUPE:
        raise HTTPException(422, f"Un groupe compte au plus {ELEVES_PAR_GROUPE} élèves.")
    crees = [models.EleveAnglais(prenom=p) for p in nouveaux]
    groupe.eleves.extend(crees)
    session.flush()
    codes = [attribuer_code(session, e) for e in crees]
    session.commit()
    return ResultatInscription(groupe=_resume(groupe), crees=codes,
                               deja_presents=[p for p in corps.prenoms if p in existants])


@router.post("/groupes/{groupe_id}/codes", response_model=list[CodeEleveAnglais])
def nouveaux_codes(groupe_id: int, enseignant: EnseignantAnglais, session: SessionDB,
                   tous: bool = False) -> list[CodeEleveAnglais]:
    """Codes des élèves qui n'en ont pas, ou de tous (les anciens codes cessent alors de fonctionner)."""
    groupe = _mon_groupe(session, groupe_id, enseignant)
    eleves = sorted((e for e in groupe.eleves if tous or e.code_hash is None), key=lambda e: e.prenom.lower())
    codes = [attribuer_code(session, e) for e in eleves]
    session.commit()
    return codes


@router.post("/groupes/{groupe_id}/eleves/{eleve_id}/code", response_model=CodeEleveAnglais)
def regenerer_code(groupe_id: int, eleve_id: int, enseignant: EnseignantAnglais, session: SessionDB) -> CodeEleveAnglais:
    """Code perdu : un nouveau code remplace l'ancien et déconnecte l'élève partout."""
    eleve = _mon_eleve(session, _mon_groupe(session, groupe_id, enseignant), eleve_id)
    code = attribuer_code(session, eleve)
    session.commit()
    return code


@router.get("/groupes/{groupe_id}/progression")
def progression_du_groupe(groupe_id: int, enseignant: EnseignantAnglais, session: SessionDB):
    """Meilleur score au quiz et auto-évaluation « I can » de chaque élève, séance par séance."""
    groupe = _mon_groupe(session, groupe_id, enseignant)
    return [
        {"id": e.id, "prenom": e.prenom,
         "seances": {p.code: {"score": p.meilleur_score, "total": p.total, "tentatives": p.tentatives,
                              "i_can": p.i_can} for p in e.progression}}
        for e in sorted(groupe.eleves, key=lambda e: e.prenom.lower())
    ]


@router.delete("/groupes/{groupe_id}/eleves/{eleve_id}", status_code=status.HTTP_204_NO_CONTENT)
def retirer_eleve(groupe_id: int, eleve_id: int, enseignant: EnseignantAnglais, session: SessionDB) -> Response:
    """Retire l'élève du groupe. Un enfant de famille garde une copie archivée de sa progression ; sans enfant,
    c'est le droit à l'effacement (RGPD) : prénom et progression sont supprimés."""
    eleve = _mon_eleve(session, _mon_groupe(session, groupe_id, enseignant), eleve_id)
    archives.archiver_anglais(session, eleve, archives.INSCRIPTION_RETIREE, archives.par_professeur(enseignant))
    session.delete(eleve)
    session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.delete("/groupes/{groupe_id}", status_code=status.HTTP_204_NO_CONTENT)
def supprimer_groupe(groupe_id: int, enseignant: EnseignantAnglais, session: SessionDB) -> Response:
    """Fin d'année : supprime le groupe et ses élèves ; le travail des enfants de famille est archivé."""
    groupe = _mon_groupe(session, groupe_id, enseignant)
    archives.archiver_groupe(session, groupe, archives.par_professeur(enseignant))
    session.delete(groupe)
    session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
