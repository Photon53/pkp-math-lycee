"""Lecture des séances PKP Anglais et génération PDF, réservées aux enseignants authentifiés."""
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response
from pkp_anglais.contenu import charger_seance
from pkp_anglais.seances import generer_pack_animateur, generer_pack_eleve

from app.anglais_pdf import produire_pdf
from app.auth import EnseignantCourant

router = APIRouter(prefix="/anglais", tags=["anglais"])

# Résolution indépendante du répertoire de lancement du processus.
CONTENU = Path(__file__).resolve().parents[3] / "contenu" / "anglais" / "seances"
SEANCES = {"4e-01": ("4e", "4e-01-pilote.json"), "3e-01": ("3e", "3e-01-pilote.json")}


def _seance(code: str):
    if code not in SEANCES:
        raise HTTPException(404, "Séance introuvable.")
    niveau, nom = SEANCES[code]
    try:
        return charger_seance(CONTENU / niveau / nom)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        raise HTTPException(503, "Contenu pédagogique indisponible.") from exc


@router.get("/seances")
def lister_seances(_: EnseignantCourant):
    return [
        {"code": s.code, "niveau": s.niveau, "titre": s.titre, "objectif": s.objectif, "duree_minutes": 90}
        for code in SEANCES for s in [_seance(code)]
    ]


@router.get("/seances/{code}")
def consulter_seance(code: str, _: EnseignantCourant):
    return generer_pack_animateur(_seance(code))


@router.get("/seances/{code}/pdf/{public}")
def telecharger_pdf(code: str, public: str, _: EnseignantCourant):
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
