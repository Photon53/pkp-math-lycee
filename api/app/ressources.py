"""Ressources rattachées aux cours : liens vers des sites et fichiers PDF (cahier des charges V2, § 5).

Qui voit quoi :
- élève : ressources non masquées, destinées aux élèves, d'un chapitre ouvert de sa classe ;
  communes, ou de portée « classe » visant sa classe ; un lien en échec deux contrôles de suite est caché ;
- enseignant : ressources communes destinées aux enseignants, et les siennes (même masquées) ;
- administrateur : toutes.

Usage du contrôle hebdomadaire des liens, depuis `api/` : `python -m app.ressources verifier-liens`
"""

import argparse
import secrets
import urllib.error
import urllib.request
from datetime import UTC, date, datetime
from pathlib import Path
from urllib.parse import urlsplit

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import settings
from app.db import models
from app.progression import ids_ouverts
from app.referentiel import PorteeRessource, PublicRessource, TypeRessource
from app.schemas import RessourceCreation, RessourceDetail, RessourceVue

ECHECS_AVANT_MASQUAGE = 2


def vue(r: models.Ressource) -> RessourceVue:
    return RessourceVue(
        id=r.id, type=r.type.value, titre=r.titre, description=r.description, url=r.url,
        domaine=r.domaine, taille_octets=r.taille_octets, portee=r.portee.value,
    )


def detail(session: Session, r: models.Ressource) -> RessourceDetail:
    consultations = session.scalar(
        select(func.coalesce(func.sum(models.RessourceConsultation.nombre), 0)).where(
            models.RessourceConsultation.ressource_id == r.id
        )
    )
    rattachement = r.chapitre.titre if r.chapitre_id is not None else f"{r.competence.chapitre.titre} › {r.competence.libelle}"
    return RessourceDetail(
        **vue(r).model_dump(),
        source=r.source, licence=r.licence, chapitre_id=r.chapitre_id, competence_id=r.competence_id,
        rattachement=rattachement, public=r.public.value, auteur=r.auteur.nom,
        classes=sorted(c.code for c in r.classes), masquee=r.masquee, motif_masquage=r.motif_masquage,
        echecs_lien=r.echecs_lien, a_un_fichier=r.fichier is not None, consultations=consultations, cree_le=r.cree_le,
    )


def appliquer(session: Session, r: models.Ressource, corps: RessourceCreation, auteur: models.Enseignant) -> None:
    """Remplit une ressource depuis le formulaire (création ou modification), après contrôles."""
    if corps.chapitre_id is not None and session.get(models.Chapitre, corps.chapitre_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Chapitre introuvable.")
    if corps.competence_id is not None and session.get(models.Competence, corps.competence_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Compétence introuvable.")
    if r.portee == PorteeRessource.CLASSE and corps.type == TypeRessource.PDF and not corps.droits_declares:
        raise HTTPException(422, "Confirmez détenir les droits de diffusion de ce PDF à vos élèves.")
    if corps.type == TypeRessource.LIEN:
        domaine = valider_url(session, corps.url)
        if settings.verifier_liens and corps.url != r.url and not lien_repond(corps.url):
            raise HTTPException(422, "Ce lien ne répond pas. Vérifiez l'adresse.")
        r.domaine, r.echecs_lien = domaine, 0
        if r.fichier:
            supprimer_fichier(r.fichier)
            r.fichier, r.taille_octets = None, None
    else:
        r.domaine = None
    r.type, r.titre, r.description, r.url = corps.type, corps.titre.strip(), corps.description.strip(), corps.url
    r.source, r.licence, r.public, r.ordre = corps.source, corps.licence, corps.public, corps.ordre
    r.chapitre_id, r.competence_id = corps.chapitre_id, corps.competence_id
    r.auteur = r.auteur or auteur
    if r.portee == PorteeRessource.CLASSE:
        classes = [session.get(models.Classe, i) for i in dict.fromkeys(corps.classe_ids)]
        if not classes or any(c is None or c.enseignant_id != auteur.id for c in classes):
            raise HTTPException(422, "Choisissez au moins une de vos classes.")
        r.classes = classes


def chapitre_de(r: models.Ressource) -> models.Chapitre:
    return r.chapitre if r.chapitre_id is not None else r.competence.chapitre


def _rattachees(session: Session, chapitre_id: int | None, competence_id: int | None) -> list[models.Ressource]:
    requete = select(models.Ressource).order_by(models.Ressource.ordre, models.Ressource.id)
    if competence_id is not None:
        requete = requete.where(models.Ressource.competence_id == competence_id)
    if chapitre_id is not None:
        requete = requete.where(models.Ressource.chapitre_id == chapitre_id)
    return list(session.scalars(requete))


def visible_par_eleve(r: models.Ressource, eleve: models.Eleve) -> bool:
    if r.masquee or r.public == PublicRessource.ENSEIGNANTS or r.echecs_lien >= ECHECS_AVANT_MASQUAGE:
        return False
    if chapitre_de(r).id not in ids_ouverts(eleve.classe):
        return False
    return r.portee == PorteeRessource.COMMUNE or any(c.id == eleve.classe_id for c in r.classes)


def visible_par_enseignant(r: models.Ressource, enseignant: models.Enseignant) -> bool:
    if r.auteur_id == enseignant.id:
        return True
    return r.portee == PorteeRessource.COMMUNE and not r.masquee and r.public != PublicRessource.ELEVES


def pour_eleve(session: Session, eleve: models.Eleve, chapitre_id: int | None, competence_id: int | None) -> list[RessourceVue]:
    return [vue(r) for r in _rattachees(session, chapitre_id, competence_id) if visible_par_eleve(r, eleve)]


def pour_enseignant(
    session: Session, enseignant: models.Enseignant, chapitre_id: int | None, competence_id: int | None
) -> list[RessourceVue]:
    return [vue(r) for r in _rattachees(session, chapitre_id, competence_id) if visible_par_enseignant(r, enseignant)]


def compter_consultation(session: Session, r: models.Ressource) -> None:
    """Un compteur par ressource et par jour : on ne sait pas qui a ouvert (EA5.9)."""
    jour = date.today()
    ligne = session.get(models.RessourceConsultation, (r.id, jour))
    if ligne is None:
        session.add(models.RessourceConsultation(ressource_id=r.id, jour=jour, nombre=1))
    else:
        ligne.nombre += 1
    session.commit()


# --- Liens ----------------------------------------------------------------------


def domaine_de(url: str) -> str:
    return (urlsplit(url).hostname or "").lower().removeprefix("www.")


def valider_url(session: Session, url: str) -> str:
    """URL https uniquement, hors domaines interdits. Renvoie le domaine affiché à côté du titre."""
    morceaux = urlsplit(url)
    if morceaux.scheme != "https" or not morceaux.hostname or morceaux.username or morceaux.password:
        raise HTTPException(422, "Le lien doit commencer par https:// et ne pas contenir d'identifiants.")
    domaine = domaine_de(url)
    interdits = set(session.scalars(select(models.DomaineInterdit.domaine)))
    if any(domaine == d or domaine.endswith("." + d) for d in interdits):
        raise HTTPException(422, f"Le domaine {domaine} n'est pas autorisé.")
    return domaine


def lien_repond(url: str, delai_s: float = 8) -> bool:
    """Le lien répond-il (2xx ou 3xx) ? HEAD d'abord, GET si le site refuse HEAD."""
    for methode in ("HEAD", "GET"):
        requete = urllib.request.Request(url, method=methode, headers={"User-Agent": "PKP-Math-Lycee-verification-liens"})
        try:
            with urllib.request.urlopen(requete, timeout=delai_s) as reponse:  # noqa: S310 (https contrôlé)
                return reponse.status < 400
        except urllib.error.HTTPError as erreur:
            if erreur.code not in (403, 405, 501):
                return False
        except (urllib.error.URLError, TimeoutError, ValueError):
            return False
    return False


def verifier_liens(session: Session) -> list[models.Ressource]:
    """Contrôle tous les liens ; renvoie ceux qui viennent de passer en échec répété."""
    nouvellement_caches = []
    for r in session.scalars(select(models.Ressource).where(models.Ressource.type == TypeRessource.LIEN)):
        if lien_repond(r.url):
            r.echecs_lien = 0
        else:
            r.echecs_lien += 1
            if r.echecs_lien == ECHECS_AVANT_MASQUAGE:
                nouvellement_caches.append(r)
        r.lien_verifie_le = datetime.now(UTC)
    session.commit()
    return nouvellement_caches


# --- Fichiers PDF -----------------------------------------------------------------


def dossier() -> Path:
    chemin = Path(settings.dossier_fichiers)
    chemin.mkdir(parents=True, exist_ok=True)
    return chemin


def valider_pdf(contenu: bytes) -> None:
    """Signature %PDF-, taille, ni chiffrement ni JavaScript (EA5.5)."""
    if len(contenu) > settings.pdf_taille_max_mo * 1024 * 1024:
        raise HTTPException(413, f"Le PDF dépasse {settings.pdf_taille_max_mo} Mo.")
    if not contenu.startswith(b"%PDF-"):
        raise HTTPException(422, "Ce fichier n'est pas un PDF.")
    if b"/Encrypt" in contenu:
        raise HTTPException(422, "Les PDF protégés par mot de passe ne sont pas acceptés.")
    if b"/JavaScript" in contenu or b"/JS" in contenu:
        raise HTTPException(422, "Les PDF contenant du JavaScript ne sont pas acceptés.")


def enregistrer_pdf(r: models.Ressource, contenu: bytes) -> None:
    valider_pdf(contenu)
    ancien = r.fichier
    nom = secrets.token_hex(16) + ".pdf"
    (dossier() / nom).write_bytes(contenu)
    r.fichier, r.taille_octets = nom, len(contenu)
    if ancien:
        supprimer_fichier(ancien)


def chemin_pdf(r: models.Ressource) -> Path:
    if not r.fichier:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Aucun fichier pour cette ressource.")
    chemin = dossier() / r.fichier
    if not chemin.is_file():
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Fichier introuvable.")
    return chemin


def supprimer_fichier(nom: str | None) -> None:
    if nom:
        (dossier() / nom).unlink(missing_ok=True)


def main() -> None:
    parser = argparse.ArgumentParser(description="Ressources PKP Math Lycée")
    parser.add_argument("commande", choices=["verifier-liens"])
    parser.parse_args()

    from app.db.session import SessionLocale

    with SessionLocale() as session:
        caches = verifier_liens(session)
        for r in caches:
            print(f"Lien en échec, caché aux élèves : « {r.titre} » ({r.url}), auteur {r.auteur.email}")
        print(f"Contrôle terminé : {len(caches)} lien(s) nouvellement caché(s).")


if __name__ == "__main__":
    main()
