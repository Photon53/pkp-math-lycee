"""Suivi en séance (ticket #28).

Côté élève : « J'ai compris » / « Je n'ai pas compris » sur un cours ; « Je n'ai pas compris » sur un exercice ou
sur sa correction, après avoir répondu.
Côté professeur : tableau de bord rafraîchi pendant la séance (réussites, erreurs, non-réponses, notions à
retravailler, demandes d'aide), traitement des demandes, export agrégé sans nom d'élève.

Droits : un professeur ne voit que les élèves de ses classes (non archivées). Pas de classement : les listes
d'élèves sont triées par prénom. Les demandes sont des auto-déclarations, distinctes de la maîtrise mesurée.
"""

import csv
import io
from collections import defaultdict
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import Response
from sqlalchemy import select

from app import exemplaires
from app.auth import EleveCourant, EnseignantCourant, SessionDB
from app.db import models
from app.progression import ids_ouverts
from app.schemas_suivi import (
    AvisCours,
    AvisCoursVue,
    Compteurs,
    DemandeSuivie,
    DemandeVue,
    NotionAPrioriser,
    NouvelleDemande,
    QuestionSuivie,
    TableauSeance,
    Traitement,
)

router = APIRouter(tags=["suivi-seance"])

EN_COURS = ("ouverte", "prise-en-charge")
# Sans période précisée : les deux dernières heures, la durée d'une séance.
PERIODE_PAR_DEFAUT = timedelta(hours=2)


def _maintenant() -> datetime:
    return datetime.now(UTC)


def _utc(d: datetime | None) -> datetime | None:
    if d is None:
        return None
    return d.replace(tzinfo=UTC) if d.tzinfo is None else d.astimezone(UTC)


# ---------------------------------------------------------------------------------------------------- élève


def _competence_ouverte(session: SessionDB, eleve: models.Eleve, competence_id: int) -> models.Competence:
    competence = session.get(models.Competence, competence_id)
    if competence is None or competence.masque or competence.chapitre_id not in ids_ouverts(eleve.classe):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Cours introuvable.")
    return competence


def _avis_courant(session: SessionDB, eleve_id: int, competence_id: int) -> models.DemandeAide | None:
    return session.scalar(
        select(models.DemandeAide)
        .where(
            models.DemandeAide.eleve_id == eleve_id,
            models.DemandeAide.competence_id == competence_id,
            models.DemandeAide.objet == "cours",
        )
        .order_by(models.DemandeAide.cree_le.desc(), models.DemandeAide.id.desc())
        .limit(1)
    )


def _vue_avis(competence_id: int, avis: models.DemandeAide | None) -> AvisCoursVue:
    if avis is None:
        return AvisCoursVue(competence_id=competence_id, compris=None)
    return AvisCoursVue(competence_id=competence_id, compris=avis.statut == "compris", le=_utc(avis.cree_le))


@router.get("/eleves/moi/comprehension/{competence_id}", response_model=AvisCoursVue)
def lire_avis(competence_id: int, eleve: EleveCourant, session: SessionDB) -> AvisCoursVue:
    _competence_ouverte(session, eleve, competence_id)
    return _vue_avis(competence_id, _avis_courant(session, eleve.id, competence_id))


@router.post("/eleves/moi/comprehension", response_model=AvisCoursVue)
def donner_avis(corps: AvisCours, eleve: EleveCourant, session: SessionDB) -> AvisCoursVue:
    """Chaque changement d'avis ajoute une ligne (historique conservé) ; le même avis répété n'ajoute rien."""
    _competence_ouverte(session, eleve, corps.competence_id)
    courant = _avis_courant(session, eleve.id, corps.competence_id)
    deja = courant is not None and (courant.statut == "compris") == corps.compris
    # Une demande résolue par le professeur, puis « Je n'ai pas compris » à nouveau : nouvelle demande.
    if not deja or (not corps.compris and courant.statut == "resolue"):
        courant = models.DemandeAide(
            eleve_id=eleve.id, competence_id=corps.competence_id, objet="cours",
            statut="compris" if corps.compris else "ouverte", cree_le=_maintenant(),
        )
        session.add(courant)
        session.commit()
    return _vue_avis(corps.competence_id, courant)


@router.post("/seances/{seance_id}/aide", response_model=DemandeVue, status_code=status.HTTP_201_CREATED)
def demander_aide(seance_id: int, corps: NouvelleDemande, eleve: EleveCourant, session: SessionDB) -> models.DemandeAide:
    """« Je n'ai pas compris » l'exercice ou sa correction : seulement pour une question déjà répondue dans cette séance."""
    seance = session.get(models.Seance, seance_id)
    if seance is None or seance.eleve_id != eleve.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Séance introuvable.")
    reponse = session.scalar(
        select(models.Reponse).where(models.Reponse.seance_id == seance.id, models.Reponse.question_id == corps.question_id).limit(1)
    )
    if reponse is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "On ne peut demander de l'aide que sur une question à laquelle on a répondu.")
    existante = session.scalar(
        select(models.DemandeAide).where(
            models.DemandeAide.eleve_id == eleve.id,
            models.DemandeAide.question_id == corps.question_id,
            models.DemandeAide.objet == corps.objet,
            models.DemandeAide.statut.in_(EN_COURS),
        )
    )
    if existante is not None:
        return existante
    demande = models.DemandeAide(
        eleve_id=eleve.id, competence_id=reponse.question.competence_id, question_id=corps.question_id,
        seance_id=seance.id, objet=corps.objet, statut="ouverte", cree_le=_maintenant(),
    )
    session.add(demande)
    session.commit()
    return demande


# ---------------------------------------------------------------------------------------------------- professeur


def _mes_classes(session: SessionDB, enseignant: models.Enseignant, classe_id: int | None) -> list[models.Classe]:
    classes = [c for c in enseignant.classes if c.archivee_le is None]
    if classe_id is not None:
        classes = [c for c in classes if c.id == classe_id]
        if not classes:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Classe introuvable.")
    return classes


def _tableau(
    session: SessionDB,
    enseignant: models.Enseignant,
    classe_id: int | None,
    depuis: datetime | None,
    jusqua: datetime | None,
    chapitre_id: int | None,
    competence_id: int | None,
    erreurs_uniquement: bool,
) -> TableauSeance:
    maintenant = _maintenant()
    jusqua = _utc(jusqua) or maintenant
    depuis = _utc(depuis) or jusqua - PERIODE_PAR_DEFAUT
    classes = _mes_classes(session, enseignant, classe_id)
    eleves = {e.id: e for c in classes for e in c.eleves}
    filtres = [
        *([models.Competence.chapitre_id == chapitre_id] if chapitre_id else []),
        *([models.Competence.id == competence_id] if competence_id else []),
    ]

    reponses = session.execute(
        select(models.Reponse.question_id, models.Reponse.correcte, models.Reponse.tirage, models.Seance.eleve_id)
        .join(models.Seance, models.Reponse.seance_id == models.Seance.id)
        .join(models.Question, models.Reponse.question_id == models.Question.id)
        .join(models.Competence, models.Question.competence_id == models.Competence.id)
        .where(
            models.Seance.eleve_id.in_(eleves or [-1]),
            models.Reponse.repondu_le >= depuis,
            models.Reponse.repondu_le <= jusqua,
            *filtres,
        )
        .order_by(models.Reponse.repondu_le, models.Reponse.id)
    ).all()
    # Questions affichées mais pas encore répondues, dans une séance ouverte : non-réponses.
    en_attente = session.execute(
        select(models.Seance.question_courante_id, models.Seance.eleve_id)
        .join(models.Question, models.Seance.question_courante_id == models.Question.id)
        .join(models.Competence, models.Question.competence_id == models.Competence.id)
        .where(
            models.Seance.eleve_id.in_(eleves or [-1]),
            models.Seance.fin.is_(None),
            models.Seance.question_servie_le >= depuis,
            models.Seance.question_servie_le <= jusqua,
            *filtres,
        )
    ).all()

    essais: dict[int, dict[int, list[bool]]] = defaultdict(lambda: defaultdict(list))  # question → élève → verdicts
    dernier_tirage: dict[int, dict | None] = {}
    for question_id, correcte, tirage, eleve_id in reponses:
        essais[question_id][eleve_id].append(correcte)
        dernier_tirage[question_id] = tirage
    sans_reponse: dict[int, set[int]] = defaultdict(set)
    for question_id, eleve_id in en_attente:
        sans_reponse[question_id].add(eleve_id)

    demandes = session.scalars(
        select(models.DemandeAide)
        .join(models.Competence, models.DemandeAide.competence_id == models.Competence.id)
        .where(
            models.DemandeAide.eleve_id.in_(eleves or [-1]),
            models.DemandeAide.cree_le >= depuis,
            models.DemandeAide.cree_le <= jusqua,
            *filtres,
        )
        .order_by(models.DemandeAide.cree_le, models.DemandeAide.id)
    ).all()
    # Cours : seul l'avis le plus récent de chaque élève compte (il a pu changer d'avis).
    avis: dict[tuple[int, int], models.DemandeAide] = {}
    for d in demandes:
        if d.objet == "cours":
            avis[(d.eleve_id, d.competence_id)] = d
    demandes_cours = [d for d in avis.values() if d.statut in EN_COURS]
    demandes_exercices = [d for d in demandes if d.objet != "cours" and d.statut in EN_COURS]

    questions_vues = {q.id: q for q in session.scalars(
        select(models.Question).where(models.Question.id.in_(set(essais) | set(sans_reponse) or [-1]))
    )}

    lignes: list[QuestionSuivie] = []
    par_competence: dict[int, dict] = defaultdict(lambda: {"tentatives": 0, "erreurs": 0, "en_difficulte": set()})
    for qid, q in questions_vues.items():
        par_eleve = essais.get(qid, {})
        verdicts = [v for vs in par_eleve.values() for v in vs]
        nb_erreurs = verdicts.count(False)
        en_echec = sorted(eleves[e].prenom for e, vs in par_eleve.items() if not vs[-1])
        stats = par_competence[q.competence_id]
        stats["tentatives"] += len(verdicts)
        stats["erreurs"] += nb_erreurs
        stats["en_difficulte"] |= {e for e, vs in par_eleve.items() if not vs[-1]}
        if erreurs_uniquement and nb_erreurs == 0:
            continue
        tirage = dernier_tirage.get(qid)
        lignes.append(QuestionSuivie(
            question_id=qid, code=q.code, enonce=exemplaires.enonce(q, tirage), solution=exemplaires.solution(q, tirage),
            correction=exemplaires.correction(q, tirage), competence_id=q.competence_id, competence=q.competence.libelle,
            chapitre=q.competence.chapitre.titre, nb_tentatives=len(verdicts), nb_eleves=len(par_eleve),
            nb_reussites=verdicts.count(True), nb_erreurs=nb_erreurs,
            taux_erreur=round(nb_erreurs / len(verdicts), 2) if verdicts else None,
            eleves_en_echec=en_echec,
            nb_reussies_apres_erreur=sum(1 for vs in par_eleve.values() if vs[-1] and False in vs),
            eleves_sans_reponse=sorted(eleves[e].prenom for e in sans_reponse.get(qid, ())),
        ))
    lignes.sort(key=lambda l: (-(l.taux_erreur or 0), -l.nb_erreurs, l.code or ""))

    nb_demandes = defaultdict(int)
    for d in [*demandes_cours, *demandes_exercices]:
        nb_demandes[d.competence_id] += 1
    competences = {c.id: c for c in session.scalars(
        select(models.Competence).where(models.Competence.id.in_(set(par_competence) | set(nb_demandes) or [-1]))
    )}
    notions = [
        NotionAPrioriser(
            competence_id=cid, competence=c.libelle, chapitre=c.chapitre.titre,
            nb_eleves_en_difficulte=len(par_competence[cid]["en_difficulte"]) if cid in par_competence else 0,
            taux_erreur=(round(par_competence[cid]["erreurs"] / par_competence[cid]["tentatives"], 2)
                         if cid in par_competence and par_competence[cid]["tentatives"] else None),
            nb_demandes=nb_demandes.get(cid, 0),
        )
        for cid, c in competences.items()
    ]
    notions = [n for n in notions if n.nb_eleves_en_difficulte or n.nb_demandes]
    notions.sort(key=lambda n: (-(n.nb_eleves_en_difficulte + n.nb_demandes), -(n.taux_erreur or 0), n.competence))

    def vue(d: models.DemandeAide) -> DemandeSuivie:
        q = d.question
        return DemandeSuivie(
            id=d.id, objet=d.objet, statut=d.statut, eleve=d.eleve.prenom, classe=d.eleve.classe.code,
            competence_id=d.competence_id, competence=d.competence.libelle, chapitre=d.competence.chapitre.titre,
            question_id=d.question_id, question_code=q.code if q else None, enonce=q.enonce if q else None,
            cree_le=_utc(d.cree_le), traitee_par=d.traitee_par.nom if d.traitee_par else None,
        )

    return TableauSeance(
        genere_le=maintenant, depuis=depuis, jusqua=jusqua,
        compteurs=Compteurs(
            demandes_cours=len(demandes_cours),
            demandes_exercices=sum(1 for d in demandes_exercices if d.objet == "exercice"),
            demandes_corriges=sum(1 for d in demandes_exercices if d.objet == "corrige"),
            resolues=sum(1 for d in demandes if d.statut == "resolue"),
            eleves_actifs=len({e for _, _, _, e in reponses} | {e for _, e in en_attente}),
        ),
        notions=notions,
        demandes_cours=sorted((vue(d) for d in demandes_cours), key=lambda v: (v.chapitre, v.competence, v.eleve)),
        demandes_exercices=[vue(d) for d in demandes_exercices],
        questions=lignes,
    )


@router.get("/enseignants/seance-en-direct", response_model=TableauSeance)
def tableau_seance(
    enseignant: EnseignantCourant,
    session: SessionDB,
    classe_id: int | None = None,
    depuis: datetime | None = None,
    jusqua: datetime | None = None,
    chapitre_id: int | None = None,
    competence_id: int | None = None,
    erreurs_uniquement: bool = False,
) -> TableauSeance:
    return _tableau(session, enseignant, classe_id, depuis, jusqua, chapitre_id, competence_id, erreurs_uniquement)


@router.get("/enseignants/seance-en-direct/export.csv")
def exporter_tableau(
    enseignant: EnseignantCourant,
    session: SessionDB,
    classe_id: int | None = None,
    depuis: datetime | None = None,
    jusqua: datetime | None = None,
    chapitre_id: int | None = None,
    competence_id: int | None = None,
) -> Response:
    """Export agrégé, sans aucun prénom d'élève (minimisation des données des mineurs)."""
    t = _tableau(session, enseignant, classe_id, depuis, jusqua, chapitre_id, competence_id, False)
    tampon = io.StringIO()
    ecrivain = csv.writer(tampon, delimiter=";")
    ecrivain.writerow(["Question", "Compétence", "Chapitre", "Tentatives", "Élèves", "Réussites", "Erreurs",
                       "Taux d'erreur", "Réussies après une erreur", "Élèves en échec", "Sans réponse"])
    for q in t.questions:
        ecrivain.writerow([q.code or q.question_id, q.competence, q.chapitre, q.nb_tentatives, q.nb_eleves, q.nb_reussites,
                           q.nb_erreurs, "" if q.taux_erreur is None else q.taux_erreur, q.nb_reussies_apres_erreur,
                           len(q.eleves_en_echec), len(q.eleves_sans_reponse)])
    ecrivain.writerow([])
    ecrivain.writerow(["Notion", "Chapitre", "Élèves en difficulté", "Taux d'erreur", "Demandes d'aide"])
    for n in t.notions:
        ecrivain.writerow([n.competence, n.chapitre, n.nb_eleves_en_difficulte,
                           "" if n.taux_erreur is None else n.taux_erreur, n.nb_demandes])
    return Response(
        "﻿" + tampon.getvalue(), media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="seance-agregee.csv"'},
    )


@router.post("/enseignants/demandes/{demande_id}", response_model=DemandeSuivie)
def traiter_demande(demande_id: int, corps: Traitement, enseignant: EnseignantCourant, session: SessionDB) -> DemandeSuivie:
    demande = session.get(models.DemandeAide, demande_id)
    classe = demande.eleve.classe if demande else None
    if demande is None or classe.enseignant_id != enseignant.id or classe.archivee_le is not None or demande.statut == "compris":
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Demande introuvable.")
    demande.statut = corps.statut
    demande.traitee_le = _maintenant()
    demande.traitee_par_id = enseignant.id
    session.commit()
    q = demande.question
    return DemandeSuivie(
        id=demande.id, objet=demande.objet, statut=demande.statut, eleve=demande.eleve.prenom, classe=classe.code,
        competence_id=demande.competence_id, competence=demande.competence.libelle,
        chapitre=demande.competence.chapitre.titre, question_id=demande.question_id,
        question_code=q.code if q else None, enonce=q.enonce if q else None, cree_le=_utc(demande.cree_le),
        traitee_par=enseignant.nom,
    )
