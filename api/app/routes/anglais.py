"""Séances PKP Anglais, génération PDF et groupes d'élèves, réservés aux professeurs d'anglais."""
from pathlib import Path
from typing import Annotated, Literal

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import Response
from pkp_anglais.contenu import charger_seance
from pkp_anglais.seances import generer_pack_animateur, generer_pack_eleve
from pydantic import BaseModel, Field, field_validator

from app.anglais_pdf import charger_ressources, produire_pdf
from app.anglais_pictos import image_svg
from app.auth import EnseignantAnglais, SessionDB
from app.db import models
from app.schemas import CreationEleves

router = APIRouter(prefix="/anglais", tags=["anglais"])

# Résolution indépendante du répertoire de lancement du processus.
CONTENU = Path(__file__).resolve().parents[3] / "contenu" / "anglais" / "seances"
# Les clés reprennent le champ "code" des fichiers : c'est lui que /seances renvoie au front.
# Progression complète : un objectif du référentiel = une séance (10 en 4e, 10 en 3e).
SEANCES = {
    "4E-01": ("4e", "4e-01-pilote.json"),
    "4E-02": ("4e", "4e-02-pilote.json"),
    "4E-03": ("4e", "4e-03.json"),
    "4E-04": ("4e", "4e-04.json"),
    "4E-05": ("4e", "4e-05.json"),
    "4E-06": ("4e", "4e-06.json"),
    "4E-07": ("4e", "4e-07.json"),
    "4E-08": ("4e", "4e-08.json"),
    "4E-09": ("4e", "4e-09.json"),
    "4E-10": ("4e", "4e-10.json"),
    "3E-01": ("3e", "3e-01-pilote.json"),
    "3E-02": ("3e", "3e-02-pilote.json"),
    "3E-03": ("3e", "3e-03.json"),
    "3E-04": ("3e", "3e-04.json"),
    "3E-05": ("3e", "3e-05.json"),
    "3E-06": ("3e", "3e-06.json"),
    "3E-07": ("3e", "3e-07.json"),
    "3E-08": ("3e", "3e-08.json"),
    "3E-09": ("3e", "3e-09.json"),
    "3E-10": ("3e", "3e-10.json"),
}


def _seance(code: str):
    if code not in SEANCES:
        raise HTTPException(404, "Séance introuvable.")
    niveau, nom = SEANCES[code]
    try:
        return charger_seance(CONTENU / niveau / nom)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        raise HTTPException(503, "Contenu pédagogique indisponible.") from exc


@router.get("/seances")
def lister_seances(_: EnseignantAnglais):
    return [
        {"code": s.code, "niveau": s.niveau, "titre": s.titre, "objectif": s.objectif, "duree_minutes": 90}
        for code in SEANCES for s in [_seance(code)]
    ]


@router.get("/seances/{code}")
def consulter_seance(code: str, _: EnseignantAnglais):
    pack = generer_pack_animateur(_seance(code))
    r = charger_ressources().get(code)
    # Tout le contenu du cahier, pour que l'écran du professeur montre le même cours que le PDF.
    # Les écoutes restent de simples liens : rien n'est intégré, donc aucun traceur tiers.
    if r:
        pack["cahier"] = {**r, "visual": [{**v, "image": image_svg(v["picto"])} for v in r["visual"]]}
    return pack


@router.get("/seances/{code}/pdf/{public}")
def telecharger_pdf(code: str, public: str, _: EnseignantAnglais):
    if public not in ("eleve", "animateur"):
        raise HTTPException(404, "Pack inconnu.")
    seance = _seance(code)
    pack = generer_pack_eleve(seance) if public == "eleve" else generer_pack_animateur(seance)
    return Response(
        content=produire_pdf(pack, public),
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="pkp-anglais-{code}-{public}.pdf"',
            "Cache-Control": "private, no-store",
            "X-Content-Type-Options": "nosniff",
        },
    )


# --- Groupes d'élèves (4e, 3e) ------------------------------------------------
# Séparés des classes de maths (niveaux lycée, parcours, chapitres) : le CDC anglais interdit de les détourner.

ELEVES_PAR_GROUPE = 30  # le CDC recommande 8 à 10 élèves ; la limite évite seulement les saisies aberrantes


class GroupeCreation(BaseModel):
    nom: Annotated[str, Field(max_length=60)]
    niveau: Literal["4e", "3e"]

    @field_validator("nom")
    @classmethod
    def _nom(cls, v: str) -> str:
        v = " ".join(v.split())
        if not v:
            raise ValueError("Donnez un nom au groupe.")
        return v


class EleveAnglaisResume(BaseModel):
    id: int
    prenom: str


class GroupeResume(BaseModel):
    id: int
    nom: str
    niveau: str
    eleves: list[EleveAnglaisResume]


class ResultatInscription(BaseModel):
    groupe: GroupeResume
    deja_presents: list[str]


def _resume(groupe: models.GroupeAnglais) -> GroupeResume:
    eleves = sorted(groupe.eleves, key=lambda e: e.prenom.lower())
    return GroupeResume(id=groupe.id, nom=groupe.nom, niveau=groupe.niveau,
                        eleves=[EleveAnglaisResume(id=e.id, prenom=e.prenom) for e in eleves])


def _mon_groupe(session: SessionDB, groupe_id: int, enseignant: models.Enseignant) -> models.GroupeAnglais:
    groupe = session.get(models.GroupeAnglais, groupe_id)
    if groupe is None or groupe.enseignant_id != enseignant.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Groupe introuvable.")
    return groupe


@router.get("/groupes", response_model=list[GroupeResume])
def mes_groupes(enseignant: EnseignantAnglais) -> list[GroupeResume]:
    # 4e avant 3e, comme le programme.
    groupes = sorted(enseignant.groupes_anglais, key=lambda g: (models.NIVEAUX_ANGLAIS.index(g.niveau), g.nom.lower()))
    return [_resume(g) for g in groupes]


@router.post("/groupes", response_model=GroupeResume, status_code=status.HTTP_201_CREATED)
def creer_groupe(corps: GroupeCreation, enseignant: EnseignantAnglais, session: SessionDB) -> GroupeResume:
    if any(g.nom.lower() == corps.nom.lower() for g in enseignant.groupes_anglais):
        raise HTTPException(status.HTTP_409_CONFLICT, "Vous avez déjà un groupe de ce nom.")
    groupe = models.GroupeAnglais(nom=corps.nom, niveau=corps.niveau, enseignant=enseignant)
    session.add(groupe)
    session.commit()
    return _resume(groupe)


@router.post("/groupes/{groupe_id}/eleves", response_model=ResultatInscription, status_code=status.HTTP_201_CREATED)
def inscrire_eleves(
    groupe_id: int, corps: CreationEleves, enseignant: EnseignantAnglais, session: SessionDB
) -> ResultatInscription:
    """Inscrit des élèves par leur seul prénom ; ceux déjà présents sont ignorés."""
    groupe = _mon_groupe(session, groupe_id, enseignant)
    existants = {e.prenom for e in groupe.eleves}
    nouveaux = [p for p in corps.prenoms if p not in existants]
    if len(groupe.eleves) + len(nouveaux) > ELEVES_PAR_GROUPE:
        raise HTTPException(422, f"Un groupe compte au plus {ELEVES_PAR_GROUPE} élèves.")
    groupe.eleves.extend(models.EleveAnglais(prenom=p) for p in nouveaux)
    session.commit()
    return ResultatInscription(groupe=_resume(groupe), deja_presents=[p for p in corps.prenoms if p in existants])


@router.delete("/groupes/{groupe_id}/eleves/{eleve_id}", status_code=status.HTTP_204_NO_CONTENT)
def retirer_eleve(groupe_id: int, eleve_id: int, enseignant: EnseignantAnglais, session: SessionDB) -> Response:
    """Droit à l'effacement (RGPD) : le prénom est supprimé, pas archivé."""
    groupe = _mon_groupe(session, groupe_id, enseignant)
    eleve = session.get(models.EleveAnglais, eleve_id)
    if eleve is None or eleve.groupe_id != groupe.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Élève introuvable.")
    session.delete(eleve)
    session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.delete("/groupes/{groupe_id}", status_code=status.HTTP_204_NO_CONTENT)
def supprimer_groupe(groupe_id: int, enseignant: EnseignantAnglais, session: SessionDB) -> Response:
    """Fin d'année : supprime le groupe et ses élèves."""
    session.delete(_mon_groupe(session, groupe_id, enseignant))
    session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
