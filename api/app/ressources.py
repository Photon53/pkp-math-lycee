"""Ressources rattachées aux cours : liens vers des sites et fichiers PDF (cahier des charges V2, § 5).

Qui voit quoi :
- élève : ressources non masquées, destinées aux élèves, d'un chapitre ouvert de sa classe ;
  communes, ou de portée « classe » visant sa classe ; un lien en échec deux contrôles de suite est caché ;
- enseignant : ressources communes destinées aux enseignants, et les siennes (même masquées) ;
- administrateur : toutes.

Usage du contrôle hebdomadaire des liens, depuis `api/` : `python -m app.ressources verifier-liens`
Réanalyse des PDF déjà déposés (#4, lecture seule) : `python -m app.ressources verifier-pdf`
"""

import argparse
import secrets
from datetime import UTC, date, datetime
from pathlib import Path
from urllib.parse import urlsplit

from fastapi import HTTPException, status
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload

from app import controle_pdf, liens_sortants
from app.config import settings
from app.db import models
from app.progression import ids_ouverts_eleve
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


PDF_FRANCAIS_FERME = (
    "En français, le pilote n'accepte que des liens : le dépôt de PDF n'est pas encore ouvert. Ajoutez plutôt un lien."
)


def refus_pdf_francais(
    session: Session, chapitre_id: int | None, competence_id: int | None, classe_ids: list[int] | None
) -> str | None:
    """Issue #180 : un PDF rattaché à un chapitre de français ou destiné à une classe de français est refusé tant
    que `pdf_francais_ouvert` est faux, ou sans le contrôle renforcé des PDF (#4, `config.CONTROLE_PDF_RENFORCE`).
    Les maths ne changent pas."""
    from app import config

    if settings.pdf_francais_ouvert and config.CONTROLE_PDF_RENFORCE:
        return None
    from app.permissions import MATIERES

    chapitre = session.get(models.Chapitre, chapitre_id) if chapitre_id is not None else None
    if chapitre is None and competence_id is not None:
        competence = session.get(models.Competence, competence_id)
        chapitre = competence.chapitre if competence else None
    domaines = {chapitre.domaine_code} if chapitre else set()
    for classe_id in classe_ids or []:
        classe = session.get(models.Classe, classe_id)
        if classe is not None:
            domaines.add(classe.domaine_code)
    return PDF_FRANCAIS_FERME if any(MATIERES.get(d) == "francais" for d in domaines) else None


def appliquer(session: Session, r: models.Ressource, corps: RessourceCreation, auteur: models.Enseignant) -> None:
    """Remplit une ressource depuis le formulaire (création ou modification), après contrôles."""
    if corps.type == TypeRessource.PDF and (refus := refus_pdf_francais(session, corps.chapitre_id, corps.competence_id, corps.classe_ids)):
        raise HTTPException(status.HTTP_403_FORBIDDEN, refus)
    if corps.chapitre_id is not None and session.get(models.Chapitre, corps.chapitre_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Chapitre introuvable.")
    if corps.competence_id is not None and session.get(models.Competence, corps.competence_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Compétence introuvable.")
    if r.portee == PorteeRessource.CLASSE and corps.type == TypeRessource.PDF and not corps.droits_declares:
        raise HTTPException(422, "Confirmez détenir les droits de diffusion de ce PDF à vos élèves.")
    if corps.type == TypeRessource.LIEN:
        domaine = valider_url(session, corps.url)
        if settings.verifier_liens and corps.url != r.url and not lien_repond(corps.url, session):
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


def _id_chapitre(r: models.Ressource) -> int:
    return r.chapitre_id if r.chapitre_id is not None else r.competence.chapitre_id


def _visible(r: models.Ressource, eleve: models.Eleve, ouverts: set[int]) -> bool:
    """Règle de visibilité d'une ressource pour un élève, les chapitres ouverts de sa classe étant déjà calculés."""
    if r.masquee or r.public == PublicRessource.ENSEIGNANTS or r.echecs_lien >= ECHECS_AVANT_MASQUAGE:
        return False
    if _id_chapitre(r) not in ouverts:
        return False
    return r.portee == PorteeRessource.COMMUNE or any(c.id == eleve.classe_id for c in r.classes)


def par_chapitre_pour_eleve(session: Session, eleve: models.Eleve, ouverts: set[int]) -> dict[int, list[RessourceVue]]:
    """Ressources visibles de l'élève, regroupées par chapitre ouvert (« Mon cours », #180).

    Nombre de requêtes fixe, quel que soit le nombre de ressources : une requête pour les ressources des chapitres
    (rattachées au chapitre ou à l'une de ses compétences), deux pour leurs compétences et leurs classes.
    """
    resultat: dict[int, list[RessourceVue]] = {i: [] for i in ouverts}
    if not ouverts:
        return resultat
    competences = select(models.Competence.id).where(models.Competence.chapitre_id.in_(ouverts))
    lignes = session.scalars(
        select(models.Ressource)
        .where(or_(models.Ressource.chapitre_id.in_(ouverts), models.Ressource.competence_id.in_(competences)))
        .options(selectinload(models.Ressource.competence), selectinload(models.Ressource.classes))
        .order_by(models.Ressource.ordre, models.Ressource.id)
    )
    for r in lignes:
        if _visible(r, eleve, ouverts):
            resultat[_id_chapitre(r)].append(vue(r))
    return resultat


def visible_par_eleve(session: Session, r: models.Ressource, eleve: models.Eleve) -> bool:
    if r.masquee or r.public == PublicRessource.ENSEIGNANTS or r.echecs_lien >= ECHECS_AVANT_MASQUAGE:
        return False
    if chapitre_de(r).id not in ids_ouverts_eleve(session, eleve.classe):
        return False
    return r.portee == PorteeRessource.COMMUNE or any(c.id == eleve.classe_id for c in r.classes)


def visible_par_enseignant(r: models.Ressource, enseignant: models.Enseignant) -> bool:
    if r.auteur_id == enseignant.id:
        return True
    return r.portee == PorteeRessource.COMMUNE and not r.masquee and r.public != PublicRessource.ELEVES


def refus_envoi_pdf(session: Session, r: models.Ressource) -> str | None:
    """Envoi du fichier d'un PDF déjà créé : même règle (#180), d'après son rattachement actuel."""
    return refus_pdf_francais(session, r.chapitre_id, r.competence_id, [c.id for c in r.classes])


def pour_eleve(session: Session, eleve: models.Eleve, chapitre_id: int | None, competence_id: int | None) -> list[RessourceVue]:
    return [vue(r) for r in _rattachees(session, chapitre_id, competence_id) if visible_par_eleve(session, r, eleve)]


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


def domaine_autorise(session: Session, url: str) -> bool:
    """Le domaine de l'URL est-il hors de la liste des domaines interdits ?"""
    domaine = domaine_de(url)
    interdits = set(session.scalars(select(models.DomaineInterdit.domaine)))
    return not any(domaine == d or domaine.endswith("." + d) for d in interdits)


def valider_url(session: Session, url: str) -> str:
    """URL https sur le port standard, hors domaines interdits. Renvoie le domaine affiché à côté du titre."""
    try:
        liens_sortants.controler_url(url)
    except liens_sortants.DestinationInterdite:
        raise HTTPException(
            422, "Le lien doit commencer par https://, sans identifiants ni numéro de port."
        ) from None
    domaine = domaine_de(url)
    if not domaine_autorise(session, url):
        raise HTTPException(422, f"Le domaine {domaine} n'est pas autorisé.")
    return domaine


def lien_repond(url: str, session: Session | None = None) -> bool:
    """Le lien répond-il ? Requête protégée contre la SSRF (#3) ; redirections revalidées une à une."""
    controle = (lambda u: domaine_autorise(session, u)) if session is not None else None
    return liens_sortants.lien_repond(url, url_autorisee=controle)


def verifier_liens(session: Session) -> list[models.Ressource]:
    """Contrôle tous les liens ; renvoie ceux qui viennent de passer en échec répété."""
    nouvellement_caches = []
    for r in session.scalars(select(models.Ressource).where(models.Ressource.type == TypeRessource.LIEN)):
        if lien_repond(r.url, session):
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
    """Taille, puis analyse complète dans un processus isolé (#4, EA5.5) : voir `app.controle_pdf`."""
    if len(contenu) > settings.pdf_taille_max_mo * 1024 * 1024:
        raise HTTPException(413, f"Le PDF dépasse {settings.pdf_taille_max_mo} Mo.")
    if not contenu.startswith(b"%PDF-"):
        raise HTTPException(422, "Ce fichier n'est pas un PDF.")
    try:
        controle_pdf.analyser_isole(contenu)
    except controle_pdf.PdfRefuse as refus:
        raise HTTPException(422, str(refus)) from None


def enregistrer_pdf(r: models.Ressource, contenu: bytes) -> None:
    """Contrôle, puis écriture sous un nom aléatoire. Un PDF refusé n'est jamais écrit : rien n'est publié.

    Appel bloquant (l'analyse peut durer plusieurs secondes) : depuis une route asynchrone, passer par
    `run_in_threadpool`."""
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


def verifier_pdf_deposes(session: Session) -> list[tuple[models.Ressource, str]]:
    """Réanalyse les PDF déjà déposés (#4) ; renvoie ceux que le contrôle actuel refuserait, avec le motif.

    Lecture seule : rien n'est masqué ni supprimé ; un administrateur décide de la suite."""
    refuses = []
    for r in session.scalars(select(models.Ressource).where(models.Ressource.fichier.is_not(None)).order_by(models.Ressource.id)):
        chemin = dossier() / r.fichier
        if not chemin.is_file():
            refuses.append((r, "fichier introuvable"))
            continue
        try:
            controle_pdf.analyser_isole(chemin.read_bytes())
        except controle_pdf.PdfRefuse as refus:
            refuses.append((r, str(refus)))
    return refuses


def main() -> None:
    parser = argparse.ArgumentParser(description="Ressources PKP Math Lycée")
    parser.add_argument("commande", choices=["verifier-liens", "verifier-pdf"])
    commande = parser.parse_args().commande

    from app.db.session import SessionLocale

    with SessionLocale() as session:
        if commande == "verifier-pdf":
            refuses = verifier_pdf_deposes(session)
            for r, motif in refuses:
                print(f"PDF refusé par le contrôle actuel : ressource {r.id} « {r.titre} » — {motif}")
            print(f"Contrôle terminé : {len(refuses)} PDF à revoir (rien n'a été modifié).")
            return
        caches = verifier_liens(session)
        for r in caches:
            print(f"Lien en échec, caché aux élèves : « {r.titre} » ({r.url}), auteur {r.auteur.email}")
        print(f"Contrôle terminé : {len(caches)} lien(s) nouvellement caché(s).")


if __name__ == "__main__":
    main()
