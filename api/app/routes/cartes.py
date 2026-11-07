"""Export des cartes d'accès en PDF A4 (ticket #23), réservé à l'administration.

Deux chemins, car les codes ne sont gardés que sous forme d'empreinte :
- juste après un import ou une création, les codes encore affichés sont renvoyés, vérifiés contre
  l'empreinte, et imprimés : rien ne change dans les comptes ;
- pour des élèves déjà inscrits, l'export réémet un code par carte (confirmation explicite) : les anciennes
  cartes cessent de fonctionner, la progression et les inscriptions ne bougent pas.
Les codes ne sont jamais journalisés.
"""

import re
from typing import Annotated, Literal

from fastapi import APIRouter, HTTPException, Response
from pkp_engine import Niveau
from pydantic import BaseModel, Field, field_validator, model_validator
from sqlalchemy import select

from app import cartes_pdf, enfants, journal
from app.auth import AdminCourant, SessionDB
from app.db import models
from app.security import verifier_code_eleve

router = APIRouter(prefix="/admin/cartes", tags=["admin"])

MAX_CARTES = 1000
ORDRE_NIVEAUX = {n: i for i, n in enumerate(Niveau)}
_ORIGINE = re.compile(r"^https?://[A-Za-z0-9.\-]+(:\d{1,5})?$")


class _Export(BaseModel):
    par_page: Literal[4, 6, 8] = 8
    # Adresse du site, imprimée sur la carte et dans le QR code (celle de la page d'administration).
    origine: Annotated[str, Field(max_length=200)]

    @field_validator("origine")
    @classmethod
    def _origine(cls, v: str) -> str:
        v = v.strip().rstrip("/")
        if not _ORIGINE.match(v):
            raise ValueError("Adresse du site invalide.")
        return v


class Reemission(_Export):
    """Cartes d'élèves déjà inscrits : une seule façon de les choisir, et la réémission confirmée."""

    ids: Annotated[list[int] | None, Field(min_length=1, max_length=MAX_CARTES)] = None
    niveau: Niveau | None = None
    classe_id: int | None = None
    nouveaux_codes: bool = False

    @model_validator(mode="after")
    def _une_selection(self) -> "Reemission":
        if sum(x is not None for x in (self.ids, self.niveau, self.classe_id)) != 1:
            raise ValueError("Choisissez des élèves, un niveau ou une classe.")
        if not self.nouveaux_codes:
            raise ValueError("Confirmez la création de nouveaux codes : les anciennes cartes ne fonctionneront plus.")
        return self


class CarteConnue(BaseModel):
    id: int
    code: Annotated[str, Field(min_length=1, max_length=40)]


class CartesConnues(_Export):
    cartes: Annotated[list[CarteConnue], Field(min_length=1, max_length=MAX_CARTES)]


def _pdf(cartes: list[cartes_pdf.CarteAImprimer], corps: _Export, nom: str) -> Response:
    contenu = cartes_pdf.generer(cartes, corps.par_page, corps.origine)
    return Response(contenu, media_type="application/pdf",
                    headers={"Content-Disposition": f'attachment; filename="{nom}"', "Cache-Control": "no-store"})


def _a_imprimer(enfant: models.Enfant, code: str) -> cartes_pdf.CarteAImprimer:
    return cartes_pdf.CarteAImprimer(nom=enfants.nom_affiche(enfant), niveau=enfant.niveau.value,
                                     identifiant=enfant.identifiant, code=code)


def _choisis(session: SessionDB, corps: Reemission) -> list[models.Enfant]:
    requete = select(models.Enfant)
    if corps.ids is not None:
        requete = requete.where(models.Enfant.id.in_(corps.ids))
    elif corps.niveau is not None:
        requete = requete.where(models.Enfant.niveau == corps.niveau)
    else:
        if session.get(models.Classe, corps.classe_id) is None:
            raise HTTPException(404, "Classe introuvable : actualisez la liste.")
        requete = requete.where(models.Enfant.inscriptions.any(models.Eleve.classe_id == corps.classe_id))
    choisis = list(session.scalars(requete))
    if corps.ids is not None and len(choisis) != len(set(corps.ids)):
        raise HTTPException(404, "Élève introuvable : actualisez la liste.")
    if not choisis:
        raise HTTPException(422, "Aucun élève à exporter.")
    if len(choisis) > MAX_CARTES:
        raise HTTPException(422, f"Au plus {MAX_CARTES} cartes par export : choisissez une classe ou un niveau.")
    return sorted(choisis, key=lambda e: (ORDRE_NIVEAUX.get(e.niveau, 99), e.nom.casefold(), e.prenom.casefold()))


@router.post("/pdf")
def reemettre(corps: Reemission, admin: AdminCourant, session: SessionDB) -> Response:
    """Nouveau code pour chaque élève choisi, puis le PDF. Tout ou rien : si le PDF échoue, aucun code ne
    change. Les sessions ouvertes avec l'ancien code sont fermées ; inscriptions et progression restent."""
    choisis = _choisis(session, corps)
    cartes = [_a_imprimer(e, enfants.nouveau_code(e)) for e in choisis]
    try:
        reponse = _pdf(cartes, corps, "boussole-cartes-acces.pdf")
    except Exception:
        session.rollback()
        raise
    journal.noter(session, admin, "reemettre-cartes", "enfant", None,
                  apres={"ids": [e.id for e in choisis], "par_page": corps.par_page})
    session.commit()
    return reponse


@router.post("/pdf/connues")
def imprimer_connues(corps: CartesConnues, _: AdminCourant, session: SessionDB) -> Response:
    """Cartes qui viennent d'être créées (import, nouvelle famille) : chaque code est vérifié contre son
    empreinte, rien n'est modifié."""
    ids = [c.id for c in corps.cartes]
    trouves = {e.id: e for e in session.scalars(select(models.Enfant).where(models.Enfant.id.in_(ids)))}
    cartes = []
    for c in corps.cartes:
        enfant = trouves.get(c.id)
        if enfant is None or not enfant.code_hash or not verifier_code_eleve(c.code, enfant.code_hash):
            nom = enfants.nom_affiche(enfant) if enfant else f"n° {c.id}"
            raise HTTPException(
                422, f"Le code de {nom} a changé ou n'existe plus : exportez ses cartes depuis Élèves (nouveaux codes)."
            )
        cartes.append(_a_imprimer(enfant, c.code.strip()))
    return _pdf(cartes, corps, "boussole-cartes-acces.pdf")
