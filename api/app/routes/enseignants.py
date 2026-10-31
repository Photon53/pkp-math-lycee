"""Espace enseignant : classes, suivi des élèves, banque de questions.

Un enseignant ne voit que ses classes et leurs élèves (404 sinon, pour ne pas
révéler l'existence des autres). La banque de questions est commune.
"""

import secrets
from datetime import UTC, datetime
from functools import cache

from fastapi import APIRouter, HTTPException, Request, Response, status
from fastapi.responses import JSONResponse
from pkp_engine import Niveau
from sqlalchemy import func, select

from app import limitation
from app.auth import ENSEIGNANT, EnseignantAuthentifie, EnseignantCourant, SessionDB
from app.config import settings
from app.db import models
from app.progression import (
    chapitres_du_programme,
    export_eleve,
    historique_reponses,
    nb_questions_servables,
    progression_eleve,
    resume_eleve,
)
from app import inscriptions
from app.referentiel import ABREVIATIONS_PARCOURS
from app.schemas import (
    ChangementMotDePasse,
    ChapitreProgramme,
    ChoixChapitres,
    ClasseCreation,
    ClasseResume,
    CodeEleve,
    CompetenceInfo,
    ConnexionEnseignant,
    CreationEleves,
    EleveResume,
    JetonEnseignant,
    LienCreation,
    LiensEleve,
    PageHistorique,
    ProgressionCompetence,
    QuestionEnseignant,
    ResultatCreationEleves,
)
from app.security import (
    ALPHABET_CODE,
    creer_jeton,
    doit_rehacher,
    generer_code_eleve,
    hacher_code_eleve,
    hacher_mot_de_passe,
    verifier_mot_de_passe,
    version_mot_de_passe,
)

router = APIRouter(prefix="/enseignants", tags=["enseignant"])

PREFIXES_CODE = {Niveau.SECONDE: "2NDE", Niveau.PREMIERE: "1RE", Niveau.TERMINALE: "TLE"}
# Sans 0/O ni 1/I/L : le code est recopié à la main par des élèves.


@cache
def _empreinte_leurre() -> str:
    return hacher_mot_de_passe(secrets.token_hex(16))


def verifier_identifiants(corps: ConnexionEnseignant, request: Request, session: SessionDB) -> models.Enseignant:
    """Email + mot de passe, avec limitation des tentatives. Partagé avec la connexion administrateur."""
    ip = limitation.adresse_ip(request)
    compte = f"email:{corps.email}"
    # Le compte est bloqué même si le mot de passe est enfin le bon : sinon
    # l'attaquant saurait qu'il a trouvé.
    limitation.verifier((limitation.par_ip, ip), (limitation.echecs_enseignant, compte))
    limitation.par_ip.enregistrer(ip)

    enseignant = session.scalar(select(models.Enseignant).where(models.Enseignant.email == corps.email))
    # Même calcul (et même durée) que l'email existe ou non : on ne révèle pas les comptes.
    empreinte = enseignant.mot_de_passe_hash if enseignant else _empreinte_leurre()
    if not verifier_mot_de_passe(corps.mot_de_passe, empreinte) or enseignant is None:
        limitation.echecs_enseignant.enregistrer(compte)
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Email ou mot de passe incorrect.")
    limitation.echecs_enseignant.effacer(compte)
    if not enseignant.actif:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Ce compte est désactivé. Contactez l'équipe PKP.")
    if doit_rehacher(enseignant.mot_de_passe_hash):
        # Empreinte calculée avec un coût plus faible que l'actuel (audit A-06) : on la
        # renforce maintenant que le mot de passe est connu. Les anciens jetons deviennent invalides.
        enseignant.mot_de_passe_hash = hacher_mot_de_passe(corps.mot_de_passe)
    enseignant.derniere_connexion = datetime.now(UTC)
    session.commit()
    return enseignant


def _jeton(enseignant: models.Enseignant) -> JetonEnseignant:
    version = version_mot_de_passe(enseignant.mot_de_passe_hash)
    return JetonEnseignant(
        jeton=creer_jeton(ENSEIGNANT, enseignant.id, settings.duree_jeton_enseignant_h, version),
        nom=enseignant.nom,
        role=enseignant.role,
        mdp_provisoire=enseignant.mdp_provisoire,
    )


@router.post("/connexion", response_model=JetonEnseignant)
def connexion(corps: ConnexionEnseignant, request: Request, session: SessionDB) -> JetonEnseignant:
    return _jeton(verifier_identifiants(corps, request, session))


@router.post("/mot-de-passe", response_model=JetonEnseignant)
def changer_mot_de_passe(corps: ChangementMotDePasse, enseignant: EnseignantAuthentifie, session: SessionDB) -> JetonEnseignant:
    """Change le mot de passe (obligatoire après un mot de passe provisoire). Renvoie un nouveau jeton :
    l'ancien, comme toutes les autres sessions ouvertes, cesse de fonctionner."""
    if not verifier_mot_de_passe(corps.actuel, enseignant.mot_de_passe_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Mot de passe actuel incorrect.")
    if corps.nouveau == corps.actuel:
        raise HTTPException(422, "Le nouveau mot de passe doit être différent de l'actuel.")
    enseignant.mot_de_passe_hash = hacher_mot_de_passe(corps.nouveau)
    enseignant.mdp_provisoire = False
    session.commit()
    return _jeton(enseignant)


# --- Classes et élèves ------------------------------------------------------


def _resume_classe(session: SessionDB, classe: models.Classe) -> ClasseResume:
    nb = session.scalar(select(func.count()).select_from(models.Eleve).where(models.Eleve.classe_id == classe.id))
    return ClasseResume(id=classe.id, code=classe.code, niveau=classe.niveau, parcours=classe.parcours, nb_eleves=nb)


@router.get("/classes", response_model=list[ClasseResume])
def mes_classes(enseignant: EnseignantCourant, session: SessionDB) -> list[ClasseResume]:
    classes = session.scalars(
        select(models.Classe).where(models.Classe.enseignant_id == enseignant.id).order_by(models.Classe.code)
    )
    return [_resume_classe(session, c) for c in classes]


@router.post("/classes", response_model=ClasseResume, status_code=status.HTTP_201_CREATED)
def creer_classe(corps: ClasseCreation, enseignant: EnseignantCourant, session: SessionDB) -> ClasseResume:
    while True:
        prefixe = f"{PREFIXES_CODE[corps.niveau]}-{ABREVIATIONS_PARCOURS[corps.parcours]}"
        code = f"{prefixe}-" + "".join(secrets.choice(ALPHABET_CODE) for _ in range(5))
        if not session.scalar(select(models.Classe).where(models.Classe.code == code)):
            break
    classe = models.Classe(code=code, niveau=corps.niveau, parcours=corps.parcours, enseignant=enseignant)
    session.add(classe)
    # Par défaut, tout le programme est ouvert ; l'enseignant ferme ce qu'il ne veut pas encore proposer.
    classe.chapitres_proposes = chapitres_du_programme(session, classe)
    session.commit()
    return _resume_classe(session, classe)


def _ma_classe(session: SessionDB, classe_id: int, enseignant: models.Enseignant) -> models.Classe:
    classe = session.get(models.Classe, classe_id)
    if classe is None or classe.enseignant_id != enseignant.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Classe introuvable.")
    return classe


def _mon_eleve(session: SessionDB, eleve_id: int, enseignant: models.Enseignant) -> models.Eleve:
    eleve = session.get(models.Eleve, eleve_id)
    if eleve is None or eleve.classe.enseignant_id != enseignant.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Élève introuvable.")
    return eleve


@router.get("/classes/{classe_id}/eleves", response_model=list[EleveResume])
def eleves_de_la_classe(classe_id: int, enseignant: EnseignantCourant, session: SessionDB) -> list[EleveResume]:
    classe = _ma_classe(session, classe_id, enseignant)
    return [resume_eleve(session, e) for e in sorted(classe.eleves, key=lambda e: e.prenom)]


# --- Chapitres proposés à une classe ------------------------------------------


def _programme_de_la_classe(session: SessionDB, classe: models.Classe) -> list[ChapitreProgramme]:
    chapitres = chapitres_du_programme(session, classe)
    ouverts = {c.id for c in classe.chapitres_proposes}
    nb = nb_questions_servables(session, [c.id for c in chapitres])
    return [
        ChapitreProgramme(
            id=c.id, code=c.code, titre=c.titre, ordre=c.ordre, propose=c.id in ouverts,
            nb_competences=len(c.competences), nb_questions=nb.get(c.id, 0),
        )
        for c in chapitres
    ]


@router.get("/classes/{classe_id}/chapitres", response_model=list[ChapitreProgramme])
def chapitres_de_la_classe(classe_id: int, enseignant: EnseignantCourant, session: SessionDB) -> list[ChapitreProgramme]:
    """Programme de la classe (niveau + spécialité) : chapitres ouverts ou non aux élèves."""
    return _programme_de_la_classe(session, _ma_classe(session, classe_id, enseignant))


@router.put("/classes/{classe_id}/chapitres", response_model=list[ChapitreProgramme])
def proposer_chapitres(
    classe_id: int, corps: ChoixChapitres, enseignant: EnseignantCourant, session: SessionDB
) -> list[ChapitreProgramme]:
    """Remplace la liste des chapitres ouverts aux élèves de la classe."""
    classe = _ma_classe(session, classe_id, enseignant)
    programme = {c.id: c for c in chapitres_du_programme(session, classe)}
    if any(i not in programme for i in corps.chapitre_ids):
        raise HTTPException(422, "Chapitre hors du programme de cette classe (niveau et spécialité).")
    classe.chapitres_proposes = [programme[i] for i in dict.fromkeys(corps.chapitre_ids)]
    session.commit()
    return _programme_de_la_classe(session, classe)


# --- Codes personnels des élèves (audit A-07, décision D1) --------------------
# Le code n'est stocké que haché : il est renvoyé en clair une seule fois, à sa génération,
# pour que l'enseignant l'imprime ou le recopie. Perdu : on en génère un nouveau.


def _attribuer_code(eleve: models.Eleve) -> CodeEleve:
    code = generer_code_eleve()
    eleve.code_hash = hacher_code_eleve(code)  # invalide aussi les jetons émis avec l'ancien code
    return CodeEleve(id=eleve.id, prenom=eleve.prenom, code=code)


@router.post("/classes/{classe_id}/eleves", response_model=ResultatCreationEleves, status_code=status.HTTP_201_CREATED)
def inscrire_eleves(
    classe_id: int, corps: CreationEleves, enseignant: EnseignantCourant, session: SessionDB
) -> ResultatCreationEleves:
    """Inscrit des élèves (un prénom chacun) et leur attribue un code personnel."""
    classe = _ma_classe(session, classe_id, enseignant)
    existants = {e.prenom for e in classe.eleves}
    nouveaux = [models.Eleve(prenom=p, classe=classe) for p in corps.prenoms if p not in existants]
    session.add_all(nouveaux)
    session.flush()
    crees = [_attribuer_code(e) for e in nouveaux]
    session.commit()
    return ResultatCreationEleves(crees=crees, deja_presents=[p for p in corps.prenoms if p in existants])


@router.post("/classes/{classe_id}/codes-manquants", response_model=list[CodeEleve])
def generer_codes_manquants(classe_id: int, enseignant: EnseignantCourant, session: SessionDB) -> list[CodeEleve]:
    """Pour les élèves inscrits avant les codes personnels : leur en attribuer un."""
    classe = _ma_classe(session, classe_id, enseignant)
    codes = [_attribuer_code(e) for e in sorted(classe.eleves, key=lambda e: e.prenom) if e.code_hash is None]
    session.commit()
    return codes


@router.post("/eleves/{eleve_id}/code", response_model=CodeEleve)
def nouveau_code(eleve_id: int, enseignant: EnseignantCourant, session: SessionDB) -> CodeEleve:
    """Code oublié ou divulgué : en génère un nouveau ; l'ancien et ses sessions cessent de fonctionner.
    Il vaut pour toutes les inscriptions reliées du même élève (un seul code à retenir)."""
    eleve = _mon_eleve(session, eleve_id, enseignant)
    code = _attribuer_code(eleve)
    for autre in inscriptions.liees(session, eleve):
        autre.code_hash = eleve.code_hash
    session.commit()
    return code


# --- Même élève dans plusieurs parcours ----------------------------------------


def _liens(session: SessionDB, eleve: models.Eleve) -> LiensEleve:
    return LiensEleve(
        liees=[inscriptions.decrire(e) for e in inscriptions.liees(session, eleve)],
        suggestions=[inscriptions.decrire(e) for e in inscriptions.suggestions(session, eleve)],
    )


@router.get("/eleves/{eleve_id}/liens", response_model=LiensEleve)
def liens_eleve(eleve_id: int, enseignant: EnseignantCourant, session: SessionDB) -> LiensEleve:
    """Autres inscriptions du même élève, et inscriptions du même prénom dans vos autres classes."""
    return _liens(session, _mon_eleve(session, eleve_id, enseignant))


@router.post("/eleves/{eleve_id}/liens", response_model=LiensEleve)
def relier_eleve(eleve_id: int, corps: LienCreation, enseignant: EnseignantCourant, session: SessionDB) -> LiensEleve:
    """Relie deux inscriptions du même élève (vos deux classes) : il passe de l'une à l'autre avec un seul code,
    celui de l'inscription `eleve_id`."""
    eleve = _mon_eleve(session, eleve_id, enseignant)
    try:
        inscriptions.relier(session, eleve, _mon_eleve(session, corps.eleve_id, enseignant))
    except inscriptions.LienImpossible as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc
    session.commit()
    return _liens(session, eleve)


@router.delete("/eleves/{eleve_id}/liens", response_model=LiensEleve)
def delier_eleve(eleve_id: int, enseignant: EnseignantCourant, session: SessionDB) -> LiensEleve:
    """Détache cette inscription des autres parcours de l'élève."""
    eleve = _mon_eleve(session, eleve_id, enseignant)
    inscriptions.delier(session, eleve)
    session.commit()
    return _liens(session, eleve)


@router.get("/eleves/{eleve_id}/progression", response_model=list[ProgressionCompetence])
def progression(eleve_id: int, enseignant: EnseignantCourant, session: SessionDB) -> list[ProgressionCompetence]:
    return progression_eleve(session, _mon_eleve(session, eleve_id, enseignant))


@router.get("/eleves/{eleve_id}/historique", response_model=PageHistorique)
def historique(
    eleve_id: int, enseignant: EnseignantCourant, session: SessionDB, page: int = 1, erreurs: bool = False
) -> PageHistorique:
    """Suivi par le professeur : les réponses de son élève, avec les corrections."""
    return historique_reponses(session, _mon_eleve(session, eleve_id, enseignant), page, erreurs)


@router.get("/eleves/{eleve_id}/export")
def exporter_eleve(eleve_id: int, enseignant: EnseignantCourant, session: SessionDB) -> JSONResponse:
    """Droit d'accès et de portabilité (RGPD) : toutes les données d'un élève, en JSON."""
    return export_eleve(session, _mon_eleve(session, eleve_id, enseignant))


@router.delete("/classes/{classe_id}", status_code=status.HTTP_204_NO_CONTENT)
def supprimer_classe(classe_id: int, enseignant: EnseignantCourant, session: SessionDB) -> Response:
    """Fin d'année : supprime la classe, ses élèves, leurs séances et réponses."""
    classe = _ma_classe(session, classe_id, enseignant)
    for eleve in classe.eleves:
        inscriptions.delier(session, eleve)  # leurs autres parcours restent, sans ce lien
    session.delete(classe)
    session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.delete("/eleves/{eleve_id}", status_code=status.HTTP_204_NO_CONTENT)
def supprimer_eleve(eleve_id: int, enseignant: EnseignantCourant, session: SessionDB) -> Response:
    """Droit à l'effacement (RGPD) : supprime l'élève, ses séances et ses réponses."""
    eleve = _mon_eleve(session, eleve_id, enseignant)
    inscriptions.delier(session, eleve)
    session.delete(eleve)
    session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# --- Banque de questions ----------------------------------------------------


@router.get("/competences", response_model=list[CompetenceInfo])
def competences(_: EnseignantCourant, session: SessionDB) -> list[CompetenceInfo]:
    lignes = session.scalars(
        select(models.Competence)
        .join(models.Chapitre)
        .order_by(models.Chapitre.niveau, models.Chapitre.parcours, models.Chapitre.ordre, models.Competence.ordre)
    )
    return [
        CompetenceInfo(
            id=c.id,
            code=c.code,
            libelle=c.libelle,
            chapitre=c.chapitre.titre,
            niveau=c.chapitre.niveau,
            parcours=c.chapitre.parcours,
        )
        for c in lignes
    ]


@router.get("/questions", response_model=list[QuestionEnseignant])
def questions(
    _: EnseignantCourant, session: SessionDB, competence_id: int | None = None, archivees: bool = False
) -> list[models.Question]:
    requete = select(models.Question).order_by(models.Question.competence_id, models.Question.difficulte, models.Question.id)
    if competence_id is not None:
        requete = requete.where(models.Question.competence_id == competence_id)
    if not archivees:
        requete = requete.where(models.Question.archivee.is_(False))
    return list(session.scalars(requete))
