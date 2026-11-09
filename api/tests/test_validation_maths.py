"""Ticket #29 : un professeur validateur consulte, modifie et valide les cours et exercices de son périmètre."""

from sqlalchemy import select

from app import permissions
from app.db import models
from app.referentiel import Niveau, StatutValidation
from tests.conftest import connecter_admin, connecter_enseignant

BASE = "/enseignants/validation"


def habiliter(session, portees, email="demo@pkp.test") -> models.Enseignant:
    prof = session.scalar(select(models.Enseignant).where(models.Enseignant.email == email))
    garder = [p for p in permissions.portees(prof) if p.role != permissions.VALIDATEUR]
    permissions.appliquer(session, prof, [*garder, *portees], None)
    session.commit()
    return prof


def validateur_2nde(session):
    return habiliter(session, [permissions.Portee(permissions.VALIDATEUR, "maths-lycee", "2nde")])


def question_de(session, niveau: Niveau) -> models.Question:
    return session.scalars(
        select(models.Question).join(models.Competence).join(models.Chapitre)
        .where(models.Chapitre.niveau == niveau, models.Question.archivee.is_(False),
               models.Question.statut_validation != StatutValidation.VALIDEE)
        .order_by(models.Question.id)
    ).first()


def corps_de(q: models.Question, **changements) -> dict:
    corps = {
        "competence_id": q.competence_id, "enonce": q.enonce, "type": q.type.value, "solution": q.solution,
        "difficulte": q.difficulte, "forme": q.forme.value if q.forme else None, "source": q.source,
        "source_url": q.source_url, "licence_source": q.licence_source, "adaptation": q.adaptation.value, "auteur": q.auteur,
    }
    return {**corps, **changements}


class TestAcces:
    def test_le_jeton_ouvre_la_page_validation(self, client, session):
        r = client.post("/enseignants/connexion", json={"email": "demo@pkp.test", "mot_de_passe": "demo-pkp-2026"})
        assert r.json()["validateur_maths"] is False
        validateur_2nde(session)
        r = client.post("/enseignants/connexion", json={"email": "demo@pkp.test", "mot_de_passe": "demo-pkp-2026"})
        assert r.json()["validateur_maths"] is True

    def test_refuse_a_qui_n_est_pas_validateur(self, client):
        h = connecter_enseignant(client)
        assert client.get(f"{BASE}/questions", headers=h).status_code == 403
        assert client.get(f"{BASE}/contenu", headers=h).status_code == 403

    def test_perimetre_limite_au_niveau(self, client, session):
        validateur_2nde(session)
        h = connecter_enseignant(client)
        assert client.get(f"{BASE}/perimetre", headers=h).json() == [
            {"domaine": "maths-lycee", "libelle": "Maths lycée", "niveau": "2nde"}
        ]
        page = client.get(f"{BASE}/questions", headers=h).json()
        assert page["total"] > 0 and {q["niveau"] for q in page["elements"]} == {"2nde"}
        assert all(q["peut_valider"] for q in page["elements"])
        assert {ch["niveau"] for ch in client.get(f"{BASE}/contenu", headers=h).json()} == {"2nde"}
        # Hors périmètre : la question n'existe pas pour lui.
        autre = question_de(session, Niveau.PREMIERE)
        assert client.post(f"{BASE}/questions/{autre.id}/validation", headers=h, json={"statut": "validee"}).status_code == 404
        assert client.get(f"{BASE}/lecons/{autre.competence_id}", headers=h).status_code == 404


class TestValidation:
    def test_valider_persiste_et_est_journalise(self, client, session):
        prof = validateur_2nde(session)
        h = connecter_enseignant(client)
        q = question_de(session, Niveau.SECONDE)
        r = client.post(f"{BASE}/questions/{q.id}/validation", headers=h, json={"statut": "validee"})
        assert r.status_code == 200, r.text
        assert r.json()["statut_validation"] == "validee" and r.json()["valide_par"] == prof.nom
        session.expire_all()
        assert session.get(models.Question, q.id).statut_validation == StatutValidation.VALIDEE
        trace = session.scalars(select(models.JournalAdmin).where(
            models.JournalAdmin.action == "valider", models.JournalAdmin.objet_id == q.id,
            models.JournalAdmin.admin_id == prof.id)).first()
        assert trace is not None
        r = client.post(f"{BASE}/questions/{q.id}/validation", headers=h, json={"statut": "a-corriger"})
        assert r.json()["statut_validation"] == "a-corriger"

    def test_l_auteur_ne_valide_pas_sa_question(self, client, session):
        prof = validateur_2nde(session)
        q = question_de(session, Niveau.SECONDE)
        q.auteur = prof.nom
        session.commit()
        r = client.post(f"{BASE}/questions/{q.id}/validation", headers=connecter_enseignant(client), json={"statut": "validee"})
        assert r.status_code == 422 and "auteur" in r.json()["detail"]


class TestModification:
    def test_modifier_une_question_validee_la_renvoie_en_relecture(self, client, session):
        validateur_2nde(session)
        h = connecter_enseignant(client)
        q = question_de(session, Niveau.SECONDE)
        client.post(f"{BASE}/questions/{q.id}/validation", headers=h, json={"statut": "validee"})
        session.expire_all()
        q = session.get(models.Question, q.id)
        nouvelle = 5 if q.difficulte != 5 else 4
        r = client.post(f"{BASE}/questions/{q.id}", headers=h, json=corps_de(q, difficulte=nouvelle))
        assert r.status_code == 200, r.text
        assert r.json()["difficulte"] == nouvelle and r.json()["statut_validation"] == "a-valider"
        assert r.json()["valide_par"] is None

    def test_pas_de_deplacement_hors_du_perimetre(self, client, session):
        validateur_2nde(session)
        q = question_de(session, Niveau.SECONDE)
        ailleurs = question_de(session, Niveau.PREMIERE)
        r = client.post(f"{BASE}/questions/{q.id}", headers=connecter_enseignant(client),
                        json=corps_de(q, competence_id=ailleurs.competence_id))
        assert r.status_code == 404

    def test_modifier_un_cours(self, client, session):
        validateur_2nde(session)
        h = connecter_enseignant(client)
        q = question_de(session, Niveau.SECONDE)
        lecon = client.get(f"{BASE}/lecons/{q.competence_id}", headers=h).json()
        r = client.post(f"{BASE}/lecons/{q.competence_id}", headers=h,
                        json={"cours": lecon["cours"] + "\n\nAjout du validateur.", "resume": lecon["resume"] or "Résumé."})
        assert r.status_code == 200, r.text
        assert r.json()["cours"].endswith("Ajout du validateur.") and r.json()["versions"]


class TestAdministration:
    def test_admin_sans_habilitation_ne_voit_pas_le_bouton(self, client, session):
        """Cause du constat pilote : le bouton s'affichait, l'API refusait, le message restait hors de l'écran."""
        habiliter(session, [], email="admin@pkp.test")
        admin = connecter_admin(client)
        page = client.get("/admin/questions?niveau=2nde", headers=admin).json()
        assert page["elements"] and not any(q["peut_valider"] for q in page["elements"])
        r = client.post(f"/admin/questions/{page['elements'][0]['id']}/validation", headers=admin, json={"statut": "validee"})
        assert r.status_code == 403 and "pas validateur" in r.json()["detail"]

    def test_admin_validateur_voit_le_bouton(self, client):
        page = client.get("/admin/questions?niveau=2nde", headers=connecter_admin(client)).json()
        assert page["elements"] and all(q["peut_valider"] for q in page["elements"])
