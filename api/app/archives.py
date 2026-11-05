"""Archives des inscriptions (V3, Lot 0) : avant de supprimer une classe, un groupe d'anglais ou une inscription,
le travail de chaque enfant de famille concerné est copié dans `archive_inscription`.

Règle : seule une inscription rattachée à un enfant est archivée. L'enfant existe toujours, son historique doit
rester consultable sur sa fiche. Une inscription sans enfant (ancien modèle, élève créé par un professeur) est
effacée comme avant : c'est alors le droit à l'effacement. Effacer l'enfant lui-même efface ses archives.

Les écrans et requêtes existants ne changent pas : les classes, groupes et inscriptions supprimés disparaissent
comme avant ; seule leur copie figée reste.
"""

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import models

# Motifs enregistrés avec chaque archive.
CLASSE_SUPPRIMEE = "classe supprimée"
GROUPE_SUPPRIME = "groupe supprimé"
INSCRIPTION_RETIREE = "inscription retirée"


def par_admin(admin: models.Enseignant) -> str:
    return f"Administrateur : {admin.nom}"


def par_professeur(enseignant: models.Enseignant) -> str:
    return f"Professeur : {enseignant.nom}"


def _iso(valeur: datetime | None) -> str | None:
    return valeur.isoformat() if valeur is not None else None


def _valeur(v) -> str | None:
    return None if v is None else getattr(v, "value", v)


def archiver_maths(session: Session, eleve: models.Eleve, motif: str, par: str) -> models.ArchiveInscription | None:
    """Copie figée d'une inscription de maths : chaque séance avec ses réponses. Rien si l'inscription n'a pas
    d'enfant."""
    if eleve.enfant_id is None:
        return None
    seances, nb_reponses, nb_correctes, derniere = [], 0, 0, None
    for s in sorted(eleve.seances, key=lambda s: s.debut):
        reponses = [
            {
                "question": r.question.code or str(r.question_id),
                "competence": r.question.competence.code,
                "reponse": r.reponse_donnee,
                "correcte": r.correcte,
                "duree_s": r.duree_s,
                "le": _iso(r.repondu_le),
            }
            for r in sorted(s.reponses, key=lambda r: r.repondu_le)
        ]
        nb_reponses += len(reponses)
        nb_correctes += sum(1 for r in reponses if r["correcte"])
        derniere = max(filter(None, (derniere, s.fin, s.debut)))
        seances.append({
            "debut": _iso(s.debut), "fin": _iso(s.fin),
            "chapitres": [c.code for c in s.chapitres], "competences": [c.code for c in s.competences],
            "reponses": reponses,
        })
    classe = eleve.classe
    archive = models.ArchiveInscription(
        enfant_id=eleve.enfant_id, matiere="maths", domaine_code=classe.domaine_code, niveau=_valeur(classe.niveau),
        parcours=_valeur(classe.parcours), cours=classe.code, enseignant=classe.enseignant.nom,
        inscrit_le=eleve.cree_le, par=par, motif=motif,
        resume={"seances": len(seances), "reponses": nb_reponses, "correctes": nb_correctes,
                "derniere_activite": _iso(derniere)},
        contenu={"seances": seances},
    )
    session.add(archive)
    return archive


def archiver_anglais(
    session: Session, eleve: models.EleveAnglais, motif: str, par: str
) -> models.ArchiveInscription | None:
    """Copie figée d'une inscription d'anglais : la progression séance par séance. Rien sans enfant."""
    if eleve.enfant_id is None:
        return None
    progression = [
        {"seance": p.code, "meilleur_score": p.meilleur_score, "total": p.total, "tentatives": p.tentatives,
         "i_can": list(p.i_can or []), "maj_le": _iso(p.maj_le)}
        for p in sorted(eleve.progression, key=lambda p: p.code)
    ]
    groupe = eleve.groupe
    derniere = max((p.maj_le for p in eleve.progression if p.maj_le), default=None)
    archive = models.ArchiveInscription(
        enfant_id=eleve.enfant_id, matiere="anglais", domaine_code=groupe.domaine_code, niveau=groupe.niveau,
        parcours=None, cours=groupe.nom, enseignant=groupe.enseignant.nom, inscrit_le=eleve.cree_le,
        par=par, motif=motif,
        resume={"seances": len(progression), "tentatives": sum(p["tentatives"] for p in progression),
                "derniere_activite": _iso(derniere)},
        contenu={"progression": progression},
    )
    session.add(archive)
    return archive


def archiver_classe(session: Session, classe: models.Classe, par: str) -> int:
    """Archive toutes les inscriptions d'enfants de la classe ; renvoie leur nombre."""
    return sum(archiver_maths(session, e, CLASSE_SUPPRIMEE, par) is not None for e in classe.eleves)


def archiver_groupe(session: Session, groupe: models.GroupeAnglais, par: str) -> int:
    return sum(archiver_anglais(session, e, GROUPE_SUPPRIME, par) is not None for e in groupe.eleves)


def de_l_enfant(session: Session, enfant_id: int) -> list[models.ArchiveInscription]:
    """Archives d'un enfant, la plus récente d'abord."""
    return list(session.scalars(
        select(models.ArchiveInscription)
        .where(models.ArchiveInscription.enfant_id == enfant_id)
        .order_by(models.ArchiveInscription.archivee_le.desc(), models.ArchiveInscription.id.desc())
    ))
