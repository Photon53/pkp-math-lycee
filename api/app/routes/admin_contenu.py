"""Espace administrateur : cours, exercices et ressources.

Décision DA2 : après l'import initial, la base est la source de vérité. Une leçon ou une question
modifiée ici porte `modifiee_admin_le` ; l'import YAML ne l'écrase plus sans `--forcer`.
"""

from datetime import UTC, date, datetime

from fastapi import APIRouter, HTTPException, Request, Response, status
from pkp_engine import ExpressionInvalide, Niveau, TypeQuestion, corriger
from sqlalchemy import case, func, or_, select
from sqlalchemy.orm import selectinload

from app import journal, ressources
from app.auth import AdminCourant, SessionDB
from app.contenu import _dollars_equilibres as dollars_equilibres
from app.db import models
from app.db.conversions import question_vers_domaine
from app.referentiel import Parcours, PorteeRessource, StatutValidation, TypeRessource
from app.routes.enseignants_contenu import _lire_corps
from app.schemas import RessourceCreation, RessourceDetail
from app.schemas_admin import (
    TAILLE_PAGE,
    Archivage,
    ChapitreArbre,
    ChapitreCreation,
    ChapitreEdition,
    CompetenceArbre,
    CompetenceCreation,
    CompetenceEdition,
    DomaineInterditCreation,
    DomaineInterditInfo,
    EssaiReponse,
    LeconAdmin,
    LeconEdition,
    Masquage,
    Ordre,
    PageQuestions,
    QuestionAdmin,
    QuestionEdition,
    ResultatEssai,
    Validation,
    VersionLecon,
    VersionLeconDetail,
)

router = APIRouter(prefix="/admin", tags=["administration"])

CHAMPS_QUESTION = (
    "competence_id", "enonce", "type", "solution", "difficulte", "source", "source_url", "licence_source",
    "adaptation", "auteur", "archivee", "statut_validation", "valide_par", "valide_le",
)
# Le fond d'une question déjà répondue ne change pas : les statistiques resteraient fausses (EA3.18).
CHAMPS_DE_FOND = ("enonce", "type", "solution", "competence_id")


def _maintenant() -> datetime:
    return datetime.now(UTC)


# --- Arborescence, chapitres et compétences ------------------------------------------------------


@router.get("/contenu", response_model=list[ChapitreArbre])
def arbre(_: AdminCourant, session: SessionDB, niveau: Niveau | None = None) -> list[ChapitreArbre]:
    nb_questions = dict(
        session.execute(
            select(models.Question.competence_id, func.count())
            .where(models.Question.archivee.is_(False))
            .group_by(models.Question.competence_id)
        ).all()
    )
    requete = (
        select(models.Chapitre)
        .options(selectinload(models.Chapitre.competences).selectinload(models.Competence.lecon))
        .order_by(models.Chapitre.niveau, models.Chapitre.parcours, models.Chapitre.ordre)
    )
    if niveau is not None:
        requete = requete.where(models.Chapitre.niveau == niveau)
    return [
        ChapitreArbre(
            id=ch.id, code=ch.code, niveau=ch.niveau, parcours=ch.parcours, titre=ch.titre, ordre=ch.ordre, masque=ch.masque,
            competences=[
                CompetenceArbre(
                    id=c.id, code=c.code, libelle=c.libelle, ordre=c.ordre, masque=c.masque,
                    a_une_lecon=c.lecon is not None, lecon_maj_le=c.lecon.maj_le if c.lecon else None,
                    nb_questions=nb_questions.get(c.id, 0),
                )
                for c in sorted(ch.competences, key=lambda c: (c.ordre, c.code))
            ],
        )
        for ch in session.scalars(requete)
    ]


def _code_libre(session: SessionDB, modele, code: str) -> None:
    if session.scalar(select(modele).where(modele.code == code)):
        raise HTTPException(status.HTTP_409_CONFLICT, f"Le code {code} existe déjà.")


@router.post("/chapitres", response_model=ChapitreArbre, status_code=status.HTTP_201_CREATED)
def creer_chapitre(corps: ChapitreCreation, admin: AdminCourant, session: SessionDB) -> ChapitreArbre:
    _code_libre(session, models.Chapitre, corps.code)
    dernier = session.scalar(
        select(func.max(models.Chapitre.ordre)).where(
            models.Chapitre.niveau == corps.niveau, models.Chapitre.parcours == corps.parcours
        )
    )
    ch = models.Chapitre(code=corps.code, niveau=corps.niveau, parcours=corps.parcours, titre=corps.titre.strip(), ordre=(dernier or 0) + 1)
    session.add(ch)
    session.flush()
    journal.noter(session, admin, "creer", "chapitre", ch.id, apres={"code": ch.code, "titre": ch.titre})
    session.commit()
    return ChapitreArbre(
        id=ch.id, code=ch.code, niveau=ch.niveau, parcours=ch.parcours, titre=ch.titre, ordre=ch.ordre, masque=False, competences=[]
    )


def _chapitre(session: SessionDB, chapitre_id: int) -> models.Chapitre:
    ch = session.get(models.Chapitre, chapitre_id)
    if ch is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Chapitre introuvable.")
    return ch


def _competence(session: SessionDB, competence_id: int) -> models.Competence:
    c = session.get(models.Competence, competence_id)
    if c is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Compétence introuvable.")
    return c


@router.post("/chapitres/{chapitre_id}", status_code=status.HTTP_204_NO_CONTENT)
def modifier_chapitre(chapitre_id: int, corps: ChapitreEdition, admin: AdminCourant, session: SessionDB) -> Response:
    """Renommer, masquer ou réafficher. Un chapitre ne se supprime pas : il se masque (EA3.13)."""
    ch = _chapitre(session, chapitre_id)
    avant = journal.instantane(ch, ("titre", "masque"))
    ch.titre, ch.masque = corps.titre.strip(), corps.masque
    journal.noter(session, admin, "modifier", "chapitre", ch.id, avant, journal.instantane(ch, ("titre", "masque")))
    session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/chapitres/ordre/{niveau}/{parcours}", status_code=status.HTTP_204_NO_CONTENT)
def ordonner_chapitres(niveau: Niveau, parcours: Parcours, corps: Ordre, admin: AdminCourant, session: SessionDB) -> Response:
    chapitres = {
        c.id: c
        for c in session.scalars(
            select(models.Chapitre).where(models.Chapitre.niveau == niveau, models.Chapitre.parcours == parcours)
        )
    }
    if sorted(corps.ids) != sorted(chapitres):
        raise HTTPException(422, "La liste doit contenir exactement les chapitres de ce niveau et de ce parcours.")
    # Ordres provisoirement négatifs : la contrainte unique (niveau, parcours, ordre) ne doit pas gêner l'échange.
    for c in chapitres.values():
        c.ordre = -c.id
    session.flush()
    for rang, i in enumerate(corps.ids, start=1):
        chapitres[i].ordre = rang
    journal.noter(session, admin, "ordonner", "chapitre", None, apres={"niveau": niveau.value, "parcours": parcours.value, "ids": corps.ids})
    session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/competences", response_model=CompetenceArbre, status_code=status.HTTP_201_CREATED)
def creer_competence(corps: CompetenceCreation, admin: AdminCourant, session: SessionDB) -> CompetenceArbre:
    ch = _chapitre(session, corps.chapitre_id)
    _code_libre(session, models.Competence, corps.code)
    c = models.Competence(chapitre=ch, code=corps.code, libelle=corps.libelle.strip(), ordre=len(ch.competences) + 1)
    session.add(c)
    session.flush()
    journal.noter(session, admin, "creer", "competence", c.id, apres={"code": c.code, "libelle": c.libelle})
    session.commit()
    return CompetenceArbre(
        id=c.id, code=c.code, libelle=c.libelle, ordre=c.ordre, masque=False, a_une_lecon=False, lecon_maj_le=None, nb_questions=0
    )


@router.post("/competences/{competence_id}", status_code=status.HTTP_204_NO_CONTENT)
def modifier_competence(competence_id: int, corps: CompetenceEdition, admin: AdminCourant, session: SessionDB) -> Response:
    c = _competence(session, competence_id)
    avant = journal.instantane(c, ("libelle", "masque"))
    c.libelle, c.masque = corps.libelle.strip(), corps.masque
    journal.noter(session, admin, "modifier", "competence", c.id, avant, journal.instantane(c, ("libelle", "masque")))
    session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/chapitres/{chapitre_id}/competences/ordre", status_code=status.HTTP_204_NO_CONTENT)
def ordonner_competences(chapitre_id: int, corps: Ordre, admin: AdminCourant, session: SessionDB) -> Response:
    ch = _chapitre(session, chapitre_id)
    competences = {c.id: c for c in ch.competences}
    if sorted(corps.ids) != sorted(competences):
        raise HTTPException(422, "La liste doit contenir exactement les compétences du chapitre.")
    for rang, i in enumerate(corps.ids, start=1):
        competences[i].ordre = rang
    journal.noter(session, admin, "ordonner", "competence", ch.id, apres={"ids": corps.ids})
    session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# --- Leçons et versions -------------------------------------------------------------------


def _vue_lecon(c: models.Competence) -> LeconAdmin:
    lecon = c.lecon
    return LeconAdmin(
        competence_id=c.id, code=c.code, libelle=c.libelle, chapitre=c.chapitre.titre,
        cours=lecon.cours if lecon else "", resume=lecon.resume if lecon else "",
        maj_le=lecon.maj_le if lecon else None, modifiee_admin_le=lecon.modifiee_admin_le if lecon else None,
        versions=[
            VersionLecon(id=v.id, le=v.le, auteur=v.auteur.nom if v.auteur else None)
            for v in reversed(lecon.versions if lecon else [])
        ],
    )


@router.get("/lecons/{competence_id}", response_model=LeconAdmin)
def lire_lecon(competence_id: int, _: AdminCourant, session: SessionDB) -> LeconAdmin:
    return _vue_lecon(_competence(session, competence_id))


def _enregistrer_lecon(session: SessionDB, admin: models.Enseignant, c: models.Competence, cours: str, resume: str, action: str) -> None:
    for texte, nom in ((cours, "cours"), (resume, "résumé")):
        if not dollars_equilibres(texte):
            raise HTTPException(422, f"Formule mal fermée dans le {nom} : un « $ » est seul.")
    lecon = c.lecon
    if lecon is None:
        lecon = models.Lecon(competence=c, cours=cours, resume=resume)
        session.add(lecon)
    else:
        # L'état précédent est conservé : on peut comparer et restaurer (EA3.14).
        session.add(models.LeconVersion(lecon=lecon, cours=lecon.cours, resume=lecon.resume, auteur_id=admin.id))
        lecon.cours, lecon.resume = cours, resume
    lecon.modifiee_admin_le = _maintenant()
    session.flush()
    journal.noter(session, admin, action, "lecon", c.id)


@router.post("/lecons/{competence_id}", response_model=LeconAdmin)
def enregistrer_lecon(competence_id: int, corps: LeconEdition, admin: AdminCourant, session: SessionDB) -> LeconAdmin:
    c = _competence(session, competence_id)
    _enregistrer_lecon(session, admin, c, corps.cours.strip(), corps.resume.strip(), "modifier")
    session.commit()
    session.refresh(c)
    return _vue_lecon(c)


def _version(session: SessionDB, version_id: int) -> models.LeconVersion:
    v = session.get(models.LeconVersion, version_id)
    if v is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Version introuvable.")
    return v


@router.get("/lecons/versions/{version_id}", response_model=VersionLeconDetail)
def lire_version(version_id: int, _: AdminCourant, session: SessionDB) -> VersionLeconDetail:
    v = _version(session, version_id)
    return VersionLeconDetail(id=v.id, le=v.le, auteur=v.auteur.nom if v.auteur else None, cours=v.cours, resume=v.resume)


@router.post("/lecons/versions/{version_id}/restaurer", response_model=LeconAdmin)
def restaurer_version(version_id: int, admin: AdminCourant, session: SessionDB) -> LeconAdmin:
    v = _version(session, version_id)
    c = v.lecon.competence
    _enregistrer_lecon(session, admin, c, v.cours, v.resume, "restaurer")
    session.commit()
    session.refresh(c)
    return _vue_lecon(c)


# --- Exercices ----------------------------------------------------------------------------


def _requete_stats():
    correcte = func.sum(case((models.Reponse.correcte, 1), else_=0))
    return (
        select(models.Reponse.question_id, func.count(models.Reponse.id).label("n"), correcte.label("c"))
        .group_by(models.Reponse.question_id)
        .subquery()
    )


def _vue_question(q: models.Question, n: int | None, c: int | None) -> QuestionAdmin:
    return QuestionAdmin(
        id=q.id, code=q.code, competence_id=q.competence_id, competence=q.competence.libelle,
        chapitre=q.competence.chapitre.titre, niveau=q.competence.chapitre.niveau, enonce=q.enonce, type=q.type,
        solution=q.solution, difficulte=q.difficulte, archivee=q.archivee, source=q.source, source_url=q.source_url,
        licence_source=q.licence_source, adaptation=q.adaptation, statut_validation=q.statut_validation,
        valide_par=q.valide_par, valide_le=q.valide_le, auteur=q.auteur, nb_reponses=n or 0,
        taux_reussite=(c or 0) / n if n else None,
    )


@router.get("/questions", response_model=PageQuestions)
def questions(
    _: AdminCourant,
    session: SessionDB,
    niveau: Niveau | None = None,
    chapitre_id: int | None = None,
    competence_id: int | None = None,
    type: TypeQuestion | None = None,
    difficulte: int | None = None,
    statut: StatutValidation | None = None,
    archivees: bool = False,
    q: str | None = None,
    page: int = 1,
) -> PageQuestions:
    filtres = [] if archivees else [models.Question.archivee.is_(False)]
    if niveau is not None:
        filtres.append(models.Chapitre.niveau == niveau)
    if chapitre_id is not None:
        filtres.append(models.Chapitre.id == chapitre_id)
    if competence_id is not None:
        filtres.append(models.Question.competence_id == competence_id)
    if type is not None:
        filtres.append(models.Question.type == type)
    if difficulte is not None:
        filtres.append(models.Question.difficulte == difficulte)
    if statut is not None:
        filtres.append(models.Question.statut_validation == statut)
    if q:
        motif = f"%{q.strip().lower()}%"
        filtres.append(or_(func.lower(models.Question.enonce).like(motif), func.lower(models.Question.code).like(motif)))
    jointure = select(models.Question).join(models.Competence).join(models.Chapitre).where(*filtres)
    total = session.scalar(select(func.count()).select_from(jointure.subquery()))
    stats = _requete_stats()
    lignes = session.execute(
        select(models.Question, stats.c.n, stats.c.c)
        .join(models.Competence)
        .join(models.Chapitre)
        .outerjoin(stats, stats.c.question_id == models.Question.id)
        .where(*filtres)
        .order_by(models.Chapitre.niveau, models.Chapitre.ordre, models.Competence.ordre, models.Question.difficulte, models.Question.id)
        .offset((max(page, 1) - 1) * TAILLE_PAGE)
        .limit(TAILLE_PAGE)
    ).all()
    return PageQuestions(total=total, elements=[_vue_question(qu, n, c) for qu, n, c in lignes])


def _question(session: SessionDB, question_id: int) -> models.Question:
    q = session.get(models.Question, question_id)
    if q is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Question introuvable.")
    return q


def _vue_question_seule(session: SessionDB, q: models.Question) -> QuestionAdmin:
    stats = _requete_stats()
    ligne = session.execute(select(stats.c.n, stats.c.c).where(stats.c.question_id == q.id)).first()
    return _vue_question(q, *(ligne or (0, 0)))


def _solution_lisible(type_: TypeQuestion, solution: str, reponse: str | None = None) -> bool:
    question = models.Question(id=0, competence_id=0, enonce="", type=type_, solution=solution, difficulte=1, archivee=False)
    try:
        return corriger(question_vers_domaine(question), solution if reponse is None else reponse)
    except ExpressionInvalide:
        return False


@router.post("/questions/tester", response_model=ResultatEssai)
def tester(corps: EssaiReponse, _: AdminCourant) -> ResultatEssai:
    """Le moteur accepte-t-il cette réponse pour cette solution ? (bouton « Tester », EA3.16)"""
    return ResultatEssai(
        correcte=_solution_lisible(corps.type, corps.solution, corps.reponse),
        solution_lisible=_solution_lisible(corps.type, corps.solution),
    )


@router.post("/questions", response_model=QuestionAdmin, status_code=status.HTTP_201_CREATED)
def creer_question(corps: QuestionEdition, admin: AdminCourant, session: SessionDB) -> QuestionAdmin:
    _competence(session, corps.competence_id)
    if not _solution_lisible(corps.type, corps.solution):
        raise HTTPException(422, "Solution illisible par le moteur de correction.")
    q = models.Question(**corps.model_dump(exclude={"auteur"}), auteur=corps.auteur or admin.nom, modifiee_admin_le=_maintenant())
    session.add(q)
    session.flush()
    journal.noter(session, admin, "creer", "question", q.id, apres=journal.instantane(q, CHAMPS_QUESTION))
    session.commit()
    return _vue_question_seule(session, q)


@router.post("/questions/{question_id}", response_model=QuestionAdmin)
def modifier_question(question_id: int, corps: QuestionEdition, admin: AdminCourant, session: SessionDB) -> QuestionAdmin:
    q = _question(session, question_id)
    _competence(session, corps.competence_id)
    deja_repondue = session.scalar(select(func.count(models.Reponse.id)).where(models.Reponse.question_id == q.id)) > 0
    valeurs = corps.model_dump()
    if deja_repondue and any(valeurs[c] != getattr(q, c) for c in CHAMPS_DE_FOND):
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Cette question a déjà reçu des réponses : son énoncé, son type, sa solution et sa compétence ne changent plus. "
            "Archivez-la et créez-en une nouvelle.",
        )
    if not _solution_lisible(corps.type, corps.solution):
        raise HTTPException(422, "Solution illisible par le moteur de correction.")
    avant = journal.instantane(q, CHAMPS_QUESTION)
    for cle, valeur in valeurs.items():
        setattr(q, cle, valeur)
    q.modifiee_admin_le = _maintenant()
    journal.noter(session, admin, "modifier", "question", q.id, avant, journal.instantane(q, CHAMPS_QUESTION))
    session.commit()
    return _vue_question_seule(session, q)


@router.post("/questions/{question_id}/validation", response_model=QuestionAdmin)
def valider(question_id: int, corps: Validation, admin: AdminCourant, session: SessionDB) -> QuestionAdmin:
    """Le relecteur est l'administrateur connecté ; il ne peut pas être l'auteur (règle E0.2)."""
    q = _question(session, question_id)
    if corps.statut == StatutValidation.VALIDEE and q.auteur and q.auteur.strip().lower() == admin.nom.strip().lower():
        raise HTTPException(422, "Vous êtes l'auteur de cette question : un autre professeur doit la valider.")
    avant = journal.instantane(q, ("statut_validation", "valide_par", "valide_le"))
    q.statut_validation = corps.statut
    if corps.statut == StatutValidation.A_VALIDER:
        q.valide_par, q.valide_le = None, None
    else:
        q.valide_par, q.valide_le = admin.nom, date.today()
    q.modifiee_admin_le = _maintenant()
    journal.noter(session, admin, "valider", "question", q.id, avant, journal.instantane(q, ("statut_validation", "valide_par", "valide_le")))
    session.commit()
    return _vue_question_seule(session, q)


@router.post("/questions/{question_id}/archivage", response_model=QuestionAdmin)
def archiver(question_id: int, corps: Archivage, admin: AdminCourant, session: SessionDB) -> QuestionAdmin:
    """Retire la question des tirages, ou l'y remet. Jamais de suppression (`SuppressionInterdite`)."""
    q = _question(session, question_id)
    q.archivee = corps.archivee
    q.modifiee_admin_le = _maintenant()
    journal.noter(session, admin, "archiver" if corps.archivee else "desarchiver", "question", q.id)
    session.commit()
    return _vue_question_seule(session, q)


# --- Ressources communes et modération -------------------------------------------------------


def _ressource(session: SessionDB, ressource_id: int) -> models.Ressource:
    r = session.get(models.Ressource, ressource_id)
    if r is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Ressource introuvable.")
    return r


@router.get("/ressources", response_model=list[RessourceDetail])
def lister_ressources(
    _: AdminCourant, session: SessionDB, portee: PorteeRessource | None = None, masquees: bool | None = None
) -> list[RessourceDetail]:
    requete = select(models.Ressource).order_by(models.Ressource.cree_le.desc())
    if portee is not None:
        requete = requete.where(models.Ressource.portee == portee)
    if masquees is not None:
        requete = requete.where(models.Ressource.masquee.is_(masquees))
    return [ressources.detail(session, r) for r in session.scalars(requete)]


@router.post("/ressources", response_model=RessourceDetail, status_code=status.HTTP_201_CREATED)
def creer_ressource(corps: RessourceCreation, admin: AdminCourant, session: SessionDB) -> RessourceDetail:
    """Ressource commune, visible de tous (EA5.1)."""
    r = models.Ressource(portee=PorteeRessource.COMMUNE, auteur=admin)
    ressources.appliquer(session, r, corps, admin)
    session.add(r)
    session.flush()
    journal.noter(session, admin, "creer", "ressource", r.id, apres={"titre": r.titre, "type": r.type.value})
    session.commit()
    return ressources.detail(session, r)


@router.post("/ressources/{ressource_id}", response_model=RessourceDetail)
def modifier_ressource(ressource_id: int, corps: RessourceCreation, admin: AdminCourant, session: SessionDB) -> RessourceDetail:
    r = _ressource(session, ressource_id)
    if r.portee != PorteeRessource.COMMUNE:
        raise HTTPException(422, "Une ressource de professeur se modère (masquer), elle ne se modifie pas.")
    ressources.appliquer(session, r, corps, admin)
    journal.noter(session, admin, "modifier", "ressource", r.id, apres={"titre": r.titre})
    session.commit()
    return ressources.detail(session, r)


@router.put("/ressources/{ressource_id}/fichier", response_model=RessourceDetail)
async def envoyer_pdf(ressource_id: int, request: Request, admin: AdminCourant, session: SessionDB) -> RessourceDetail:
    r = _ressource(session, ressource_id)
    if r.type != TypeRessource.PDF or r.portee != PorteeRessource.COMMUNE:
        raise HTTPException(422, "Seul le PDF d'une ressource commune s'envoie ici.")
    ressources.enregistrer_pdf(r, await _lire_corps(request))
    journal.noter(session, admin, "envoyer-pdf", "ressource", r.id)
    session.commit()
    return ressources.detail(session, r)


@router.post("/ressources/{ressource_id}/masquage", response_model=RessourceDetail)
def masquer(ressource_id: int, corps: Masquage, admin: AdminCourant, session: SessionDB) -> RessourceDetail:
    """Modération : le motif est visible du professeur auteur (EA5.8)."""
    r = _ressource(session, ressource_id)
    if corps.masquee and not (corps.motif and corps.motif.strip()):
        raise HTTPException(422, "Indiquez le motif du masquage : le professeur le verra.")
    r.masquee, r.motif_masquage = corps.masquee, corps.motif.strip() if corps.masquee and corps.motif else None
    journal.noter(session, admin, "masquer" if corps.masquee else "demasquer", "ressource", r.id, apres={"motif": r.motif_masquage})
    session.commit()
    return ressources.detail(session, r)


@router.delete("/ressources/{ressource_id}", status_code=status.HTTP_204_NO_CONTENT)
def supprimer_ressource(ressource_id: int, admin: AdminCourant, session: SessionDB) -> Response:
    r = _ressource(session, ressource_id)
    fichier = r.fichier
    journal.noter(session, admin, "supprimer", "ressource", r.id, avant={"titre": r.titre, "auteur": r.auteur.email})
    session.delete(r)
    session.commit()
    ressources.supprimer_fichier(fichier)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/domaines-interdits", response_model=list[DomaineInterditInfo])
def domaines(_: AdminCourant, session: SessionDB) -> list[models.DomaineInterdit]:
    return list(session.scalars(select(models.DomaineInterdit).order_by(models.DomaineInterdit.domaine)))


@router.post("/domaines-interdits", response_model=DomaineInterditInfo, status_code=status.HTTP_201_CREATED)
def interdire(corps: DomaineInterditCreation, admin: AdminCourant, session: SessionDB) -> models.DomaineInterdit:
    if session.scalar(select(models.DomaineInterdit).where(models.DomaineInterdit.domaine == corps.domaine)):
        raise HTTPException(status.HTTP_409_CONFLICT, "Ce domaine est déjà interdit.")
    d = models.DomaineInterdit(domaine=corps.domaine)
    session.add(d)
    session.flush()
    journal.noter(session, admin, "interdire", "domaine", d.id, apres={"domaine": d.domaine})
    session.commit()
    return d


@router.delete("/domaines-interdits/{domaine_id}", status_code=status.HTTP_204_NO_CONTENT)
def autoriser(domaine_id: int, admin: AdminCourant, session: SessionDB) -> Response:
    d = session.get(models.DomaineInterdit, domaine_id)
    if d is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Domaine introuvable.")
    journal.noter(session, admin, "autoriser", "domaine", d.id, avant={"domaine": d.domaine})
    session.delete(d)
    session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
