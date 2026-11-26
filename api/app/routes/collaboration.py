# Issue #171 — Candidatures de professeurs et demandes de partenariat (Claude)
"""« Enseigner ou collaborer avec nous » : formulaire public, sans compte.

Deux circuits : professeur candidat (`/collaboration/candidatures`, CV facultatif) et école, institut ou
association (`/collaboration/partenariats`). Chaque envoi devient une demande d'« Accueil et demandes » (#172), dans
la file des candidatures ou des partenariats ; rien d'autre n'est créé : ni compte, ni habilitation, ni contrat, ni
envoi de message. Fermé tant que `PKP_COLLABORATION_ACTIVE` est faux ou qu'une durée de conservation manque.
"""

import json
from typing import Annotated, Literal

from fastapi import APIRouter, HTTPException, Request, status
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel, Field, ValidationError, field_validator

from app import accueil, collaboration, limitation
from app.auth import SessionDB
from app.config import settings

router = APIRouter(tags=["collaboration"])

TypeDemande = Literal["candidature", "partenariat"]
Matiere = Literal["maths", "francais", "anglais"]
NiveauScolaire = Literal["6e", "5e", "4e", "3e", "2nde", "1re", "Tle"]
TypeStructure = Literal["ecole", "institut", "association", "autre"]


class _Formulaire(accueil.CoordonneesAdulte):
    # L'information sur l'usage et la conservation des données doit avoir été affichée et lue.
    information_lue: Literal[True]
    # Piège à robots : champ caché, laissé vide par une personne.
    site_web: Annotated[str, Field(max_length=200)] = ""

    _nettoyage_piege = field_validator("site_web", mode="before")(accueil.nettoyer)


class NouvelleCandidature(_Formulaire):
    matieres: Annotated[list[Matiere], Field(min_length=1, max_length=3)]
    niveaux: Annotated[list[NiveauScolaire], Field(min_length=1, max_length=7)]
    disponibilites: Annotated[str, Field(max_length=500)] | None = None
    message: Annotated[str, Field(max_length=3000)] | None = None
    cv_base64: str | None = None  # PDF encodé en base64, facultatif

    _nettoyage_texte = field_validator("disponibilites", "message", mode="before")(accueil.nettoyer)


class NouveauPartenariat(_Formulaire):
    structure_nom: Annotated[str, Field(min_length=2, max_length=150)]
    structure_type: TypeStructure
    fonction: Annotated[str, Field(max_length=100)] | None = None
    partenariat: Annotated[str, Field(min_length=10, max_length=3000)]

    _nettoyage_texte = field_validator("structure_nom", "fonction", "partenariat", mode="before")(accueil.nettoyer)


class AccuseReception(BaseModel):
    reference: str
    type: TypeDemande


class EtatCollaboration(BaseModel):
    ouvert: bool
    formats_cv: list[str]
    cv_taille_max_mo: int
    conservation_jours: dict[TypeDemande, int]


def _ouvert() -> bool:
    return settings.collaboration_active and all(accueil.conservation(c) for c in ("candidature", "partenariat"))


@router.get("/collaboration/etat", response_model=EtatCollaboration)
def etat() -> EtatCollaboration:
    return EtatCollaboration(
        ouvert=_ouvert(), formats_cv=list(collaboration.FORMATS_CV), cv_taille_max_mo=settings.cv_taille_max_mo,
        conservation_jours={c: j for c in ("candidature", "partenariat") if (j := accueil.conservation(c))},
    )


def _exiger_ouverture() -> None:
    if not _ouvert():
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Les candidatures et demandes de partenariat ne sont pas encore ouvertes.")


def _limiter(request: Request) -> None:
    """Chaque envoi compte, accepté ou non : un robot ne peut pas essayer en boucle."""
    ip = limitation.adresse_ip(request)
    limitation.verifier((limitation.collaboration_par_ip, ip), (limitation.collaboration_globale, "toutes"))
    limitation.collaboration_par_ip.enregistrer(ip)
    limitation.collaboration_globale.enregistrer("toutes")


async def _lire(request: Request, schema: type[BaseModel], limite: int) -> BaseModel:
    """Lit le corps en s'arrêtant dès que la taille maximale est dépassée, puis le valide."""
    morceaux, total = [], 0
    async for morceau in request.stream():
        total += len(morceau)
        if total > limite:
            message = f"Le CV dépasse {settings.cv_taille_max_mo} Mo." if schema is NouvelleCandidature else "Formulaire trop long."
            raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, message)
        morceaux.append(morceau)
    try:
        return schema.model_validate(json.loads(b"".join(morceaux) or b"null"))
    except json.JSONDecodeError:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Formulaire illisible.") from None
    except ValidationError as erreur:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, erreur.errors(include_url=False, include_context=False, include_input=False)) from None


def _accuse_factice(type_demande: str) -> AccuseReception:
    """Réponse au robot qui a rempli le piège : identique en apparence, rien n'est enregistré."""
    return AccuseReception(reference=accueil.PREFIXES[type_demande] + "X" * 8, type=type_demande)


def _coordonnees(corps: _Formulaire) -> dict:
    return {"prenom": corps.prenom, "nom": corps.nom, "email": corps.email, "telephone": corps.telephone or None}


@router.post("/collaboration/candidatures", response_model=AccuseReception, status_code=status.HTTP_201_CREATED)
async def candidater(request: Request, session: SessionDB) -> AccuseReception:
    _exiger_ouverture()
    _limiter(request)
    corps: NouvelleCandidature = await _lire(request, NouvelleCandidature, collaboration.taille_max_corps())
    if corps.site_web:
        return _accuse_factice("candidature")
    contenu = collaboration.decoder_cv(corps.cv_base64) if corps.cv_base64 else None
    if contenu is not None:
        await run_in_threadpool(collaboration.controler_cv, contenu)  # analyse isolée et bloquante (#4)
    demande = accueil.creer_demande(
        session, categorie="candidature", origine="formulaire-collaboration", **_coordonnees(corps),
        message=corps.message or None,
        details={
            "matieres": list(dict.fromkeys(corps.matieres)), "niveaux": list(dict.fromkeys(corps.niveaux)),
            "disponibilites": corps.disponibilites or None,
        },
    )
    if contenu is not None:
        demande.cv_fichier, demande.cv_taille_octets = collaboration.ecrire_cv(contenu), len(contenu)
    try:
        session.commit()
    except Exception:
        collaboration.supprimer_cv(demande.cv_fichier)  # pas de CV sans demande
        raise
    return AccuseReception(reference=demande.reference, type="candidature")


@router.post("/collaboration/partenariats", response_model=AccuseReception, status_code=status.HTTP_201_CREATED)
async def proposer_partenariat(request: Request, session: SessionDB) -> AccuseReception:
    _exiger_ouverture()
    _limiter(request)
    corps: NouveauPartenariat = await _lire(request, NouveauPartenariat, 64 * 1024)
    if corps.site_web:
        return _accuse_factice("partenariat")
    demande = accueil.creer_demande(
        session, categorie="partenariat", origine="formulaire-collaboration", **_coordonnees(corps),
        organisation=corps.structure_nom, message=corps.partenariat,
        details={"structure_type": corps.structure_type, "fonction": corps.fonction or None},
    )
    session.commit()
    return AccuseReception(reference=demande.reference, type="partenariat")
