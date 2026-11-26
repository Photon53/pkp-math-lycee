"""Classes pilotes (issue #176, décision SEC-D6) : un domaine actif mais fermé au public n'est accessible qu'aux élèves
des classes pilotes, route par route et par URL directe ; la révocation coupe l'accès sans rien supprimer."""
# Issue #176 — Accès au français réservé aux classes pilotes (Claude)

import pytest
from sqlalchemy import select

from app import permissions
from app.db import models
from tests.conftest import connecter_admin, connecter_eleve, connecter_enseignant, entete, inscrire_eleves
from tests.test_francais_classes import importer_chapitre_fr

CLASSE_FR = {"matiere": "francais", "niveau": "5e"}


def _preparer(client, session, tmp_path) -> dict:
    """Chapitre de français de 5e, Français collège actif mais fermé, professeur de démo habilité en français."""
    importer_chapitre_fr(session, tmp_path)
    admin = connecter_admin(client)
    r = client.post("/admin/domaines/francais-college", headers=admin, json={"actif": True, "public": False})
    assert r.status_code == 200, r.text
    session.expire_all()
    prof = session.scalar(select(models.Enseignant).where(models.Enseignant.email == "demo@pkp.test"))
    permissions.appliquer(session, prof, [*permissions.portees(prof), permissions.Portee(permissions.PROFESSEUR, "francais-college")], None)
    session.commit()
    chapitre = session.scalar(select(models.Chapitre).where(models.Chapitre.code == "FR5-CH"))
    # Une leçon : sans elle, /cours/{id} répondrait 404 à tout le monde et le test du refus ne prouverait rien.
    session.add(models.Lecon(competence_id=chapitre.competences[0].id, cours="Le présent de l'indicatif.", resume="Résumé."))
    session.commit()
    return {"admin": admin, "prof_id": prof.id, "chapitre": chapitre.id, "competence": chapitre.competences[0].id}


def _classe_pilote(client, ctx, prenom: str) -> tuple[int, dict]:
    """Crée une classe pilote pour le professeur de démo, y inscrit un élève et le connecte."""
    r = client.post("/admin/classes-pilotes", headers=ctx["admin"],
                    json={**CLASSE_FR, "enseignant_id": ctx["prof_id"], "motif": "Pilote de janvier 2027"})
    assert r.status_code == 201, r.text
    code = r.json()["code"]
    codes = inscrire_eleves(client, code, [prenom])
    return r.json()["classe_id"], connecter_eleve(client, prenom, code, codes[prenom])


@pytest.fixture
def pilote(client, session, tmp_path):
    """Une classe pilote (élève Lina) et une autre classe de français du même niveau, révoquée (élève Noé)."""
    ctx = _preparer(client, session, tmp_path)
    ctx["classe"], ctx["lina"] = _classe_pilote(client, ctx, "Lina")
    ctx["autre"], ctx["noe"] = _classe_pilote(client, ctx, "Noé")
    assert client.delete(f"/admin/classes-pilotes/{ctx['autre']}", headers=ctx["admin"]).status_code == 204
    return ctx


def _repondre(client, h, seance: int) -> int:
    question = client.get(f"/seances/{seance}/question", headers=h)
    assert question.status_code == 200, question.text
    r = client.post(f"/seances/{seance}/reponses", headers=h, json={"question_id": question.json()["id"], "reponse_donnee": "finissent"})
    assert r.status_code == 200, r.text
    return question.json()["id"]


def test_la_classe_pilote_accede_a_ses_contenus(client, pilote):
    h, chapitre, competence = pilote["lina"], pilote["chapitre"], pilote["competence"]
    assert [c["code"] for c in client.get("/eleves/moi/chapitres", headers=h).json()] == ["FR5-CH"]
    assert [c["id"] for c in client.get("/cours", headers=h).json()] == [chapitre]
    assert client.get(f"/cours/{competence}", headers=h).status_code == 200
    assert client.get(f"/eleves/moi/competences/{competence}/avancement", headers=h).status_code == 200
    assert chapitre in {c["id"] for c in client.get("/pkp-math/catalogue", headers=h).json()}
    assert client.get(f"/pkp-math/chapitres/{chapitre}", headers=h).status_code == 200
    seance = client.post("/seances", headers=h)
    assert seance.status_code == 201, seance.text
    _repondre(client, h, seance.json()["id"])


def test_une_autre_classe_du_meme_niveau_est_refusee_par_url_directe(client, pilote):
    """Classe de français ordinaire (autorisation révoquée) : rien n'est servi, même en tapant l'adresse."""
    h, chapitre, competence = pilote["noe"], pilote["chapitre"], pilote["competence"]
    assert client.get("/eleves/moi/chapitres", headers=h).json() == []
    assert client.get("/cours", headers=h).json() == []
    assert client.get(f"/cours/{competence}", headers=h).status_code == 404
    assert client.get(f"/eleves/moi/competences/{competence}/avancement", headers=h).status_code == 404
    assert chapitre not in {c["id"] for c in client.get("/pkp-math/catalogue", headers=h).json()}
    assert client.get(f"/pkp-math/chapitres/{chapitre}", headers=h).status_code == 404
    assert client.get(f"/pkp-math/chapitres/{chapitre}?version=eleve", headers=h).status_code == 404
    refus = client.post("/seances", headers=h)
    assert refus.status_code == 403 and "pas ouvert à ta classe" in refus.json()["detail"]


def test_la_revocation_coupe_la_seance_en_cours_et_conserve_les_donnees(client, session, pilote):
    h = pilote["lina"]
    seance = client.post("/seances", headers=h).json()["id"]
    question = _repondre(client, h, seance)
    assert client.delete(f"/admin/classes-pilotes/{pilote['classe']}", headers=pilote["admin"]).status_code == 204
    assert client.get(f"/seances/{seance}/question", headers=h).status_code == 403
    assert client.post(f"/seances/{seance}/reponses", headers=h, json={"question_id": question, "reponse_donnee": "x"}).status_code == 403
    assert client.post(f"/seances/{seance}/aide", headers=h, json={"question_id": question, "objet": "exercice"}).status_code == 403
    assert client.get(f"/eleves/moi/comprehension/{pilote['competence']}", headers=h).status_code == 404
    # Clore la séance reste permis : elle ne reste pas ouverte indéfiniment, et rien n'est servi.
    assert client.post(f"/seances/{seance}/fin", headers=h).status_code == 200
    assert client.get("/cours", headers=h).json() == []
    # Rien n'est supprimé : la classe, l'élève, la séance et sa réponse restent ; le professeur voit toujours sa classe.
    session.expire_all()
    assert session.get(models.Classe, pilote["classe"]) is not None
    assert session.scalar(select(models.Reponse).where(models.Reponse.seance_id == seance)) is not None
    codes = {c["code"] for c in client.get("/enseignants/classes", headers=connecter_enseignant(client)).json()}
    assert session.get(models.Classe, pilote["classe"]).code in codes
    # Réautoriser rend l'accès.
    r = client.post(f"/admin/classes-pilotes/{pilote['classe']}", headers=pilote["admin"], json={"motif": "Reprise du pilote"})
    assert r.status_code == 201, r.text
    assert client.get("/cours", headers=h).json() != []


def test_enfant_de_famille_parent_et_visiteur_ne_voient_rien(client, pilote):
    """Accès par niveau : domaines publics seulement, d'après le domaine du chapitre, même si les maths sont ouvertes."""
    admin, chapitre = pilote["admin"], pilote["chapitre"]
    assert client.post("/admin/domaines/maths-college", headers=admin, json={"actif": True, "public": True}).status_code == 200
    f = client.post("/admin/familles", headers=admin, json={"email": "f@x.test", "enfants": [{"prenom": "Lou", "niveau": "5e"}]}).json()
    carte = f["cartes"][0]
    enfant = entete(client.post("/enfants/connexion", json={"identifiant": carte["identifiant"], "code_personnel": carte["code"]}).json()["jeton"])
    j = client.post("/parents/connexion", json={"email": "f@x.test", "mot_de_passe": f["mot_de_passe_provisoire"]}).json()
    parent = entete(client.post("/parents/mot-de-passe", headers=entete(j["jeton"]),
                                json={"actuel": f["mot_de_passe_provisoire"], "nouveau": "un-nouveau-mdp-2026"}).json()["jeton"])
    for h in (enfant, parent):
        vus = client.get("/pkp-math/catalogue", headers=h).json()
        assert vus and chapitre not in {c["id"] for c in vus}  # les maths de 5e sont servies, pas le français
        assert client.get(f"/pkp-math/chapitres/{chapitre}", headers=h).status_code == 404
    assert client.get(f"/pkp-math/chapitres/{chapitre}").status_code == 401
    assert client.get("/cours").status_code == 401


def test_regles_de_l_administration(client, session, tmp_path):
    ctx = _preparer(client, session, tmp_path)
    admin, corps = ctx["admin"], {**CLASSE_FR, "enseignant_id": ctx["prof_id"], "motif": "Pilote de janvier 2027"}
    # Un professeur ne crée toujours pas de classe dans un domaine fermé (EX.4).
    prof = connecter_enseignant(client)
    assert client.post("/enseignants/classes", headers=prof, json=CLASSE_FR).status_code == 403
    # Réservé à l'administrateur.
    assert client.post("/admin/classes-pilotes", headers=prof, json=corps).status_code in (401, 403)
    assert client.get("/admin/classes-pilotes", headers=prof).status_code in (401, 403)
    # Motif obligatoire ; domaine inactif refusé ; professeur non habilité refusé.
    assert client.post("/admin/classes-pilotes", headers=admin, json={**corps, "motif": ""}).status_code == 422
    assert client.post("/admin/classes-pilotes", headers=admin, json={**corps, "niveau": "2nde"}).status_code == 409
    autre = models.Enseignant(nom="M. Maths", email="maths@pkp.test", mot_de_passe_hash="h")
    session.add(autre)
    session.commit()
    assert client.post("/admin/classes-pilotes", headers=admin, json={**corps, "enseignant_id": autre.id}).status_code == 403
    # Création, liste, double autorisation, révocation, journal.
    r = client.post("/admin/classes-pilotes", headers=admin, json=corps)
    assert r.status_code == 201 and r.json()["domaine_code"] == "francais-college" and r.json()["accordee_par"]
    classe = r.json()["classe_id"]
    assert [p["classe_id"] for p in client.get("/admin/classes-pilotes", headers=admin).json()] == [classe]
    assert client.post(f"/admin/classes-pilotes/{classe}", headers=admin, json={"motif": "Encore"}).status_code == 409
    assert client.delete(f"/admin/classes-pilotes/{classe}", headers=admin).status_code == 204
    assert client.delete(f"/admin/classes-pilotes/{classe}", headers=admin).status_code == 404
    actions = set(session.scalars(select(models.JournalAdmin.action).where(models.JournalAdmin.objet == "classe-pilote")))
    assert actions == {"creer", "revoquer"}
    # Domaine devenu public : la classe pilote est inutile, une classe ordinaire suffit.
    client.post("/admin/domaines/francais-college", headers=admin, json={"actif": True, "public": True})
    assert client.post("/admin/classes-pilotes", headers=admin, json=corps).status_code == 409


def test_regle_d_acces(session, client, tmp_path):
    """Domaine public : comportement inchangé ; fermé : seulement une classe pilote non archivée d'un domaine actif."""
    ctx = _preparer(client, session, tmp_path)
    classe_id, _ = _classe_pilote(client, ctx, "Lina")
    session.expire_all()
    classe = session.get(models.Classe, classe_id)
    assert permissions.refus_acces_classe(session, classe) is None
    classe.archivee_le = models._maintenant()
    assert permissions.refus_acces_classe(session, classe) is not None
    classe.archivee_le = None
    session.get(models.DomainePedagogique, "francais-college").actif = False
    assert permissions.refus_acces_classe(session, classe) is not None
    maths = session.scalar(select(models.Classe).where(models.Classe.code == "2NDE-A-DEMO"))
    assert permissions.refus_acces_classe(session, maths) is None  # Maths lycée public
    session.rollback()


def test_ressources_et_avis_de_comprehension(client, pilote):
    """Une ressource de la classe et l'avis « j'ai compris » suivent la même règle, par URL directe aussi."""
    prof = connecter_enseignant(client)
    r = client.post("/enseignants/ressources", headers=prof, json={
        "type": "lien", "titre": "Tableau de conjugaison", "url": "https://fr.wikipedia.org/wiki/Conjugaison",
        "chapitre_id": pilote["chapitre"], "classe_ids": [pilote["classe"], pilote["autre"]],
    })
    assert r.status_code == 201, r.text
    ressource = r.json()["id"]
    lecon = client.get(f"/cours/{pilote['competence']}", headers=pilote["lina"]).json()
    assert ressource in {x["id"] for x in lecon["ressources"]}
    assert client.post(f"/ressources/{ressource}/ouverture", headers=pilote["lina"]).status_code == 204
    assert client.post(f"/ressources/{ressource}/ouverture", headers=pilote["noe"]).status_code == 404
    assert client.get(f"/eleves/moi/comprehension/{pilote['competence']}", headers=pilote["lina"]).status_code == 200
    assert client.get(f"/eleves/moi/comprehension/{pilote['competence']}", headers=pilote["noe"]).status_code == 404
    avis = {"competence_id": pilote["competence"], "compris": False}
    assert client.post("/eleves/moi/comprehension", headers=pilote["noe"], json=avis).status_code == 404


def test_regle_uniforme_pour_une_classe_de_maths(client, session):
    """Option a : une classe de maths existante dont le domaine est refermé perd l'accès, puis le retrouve en pilote."""
    admin, prof = connecter_admin(client), connecter_enseignant(client)
    assert client.post("/admin/domaines/maths-college", headers=admin, json={"actif": True, "public": True}).status_code == 200
    classe = client.post("/enseignants/classes", headers=prof, json={"niveau": "5e"}).json()
    codes = inscrire_eleves(client, classe["code"], ["Sam"])
    h = connecter_eleve(client, "Sam", classe["code"], codes["Sam"])
    assert client.get("/cours", headers=h).json() != []
    assert client.post("/admin/domaines/maths-college", headers=admin, json={"actif": True, "public": False}).status_code == 200
    assert client.get("/cours", headers=h).json() == []
    assert client.get("/eleves/moi/chapitres", headers=h).json() == []
    assert client.post("/seances", headers=h).status_code == 403
    assert client.post("/eleves/moi/diagnostic", headers=h).status_code == 403
    # L'administrateur l'autorise comme classe pilote : l'accès revient.
    r = client.post(f"/admin/classes-pilotes/{classe['id']}", headers=admin, json={"motif": "Classe en cours d'année"})
    assert r.status_code == 201, r.text
    assert client.get("/cours", headers=h).json() != []
    assert client.post("/seances", headers=h).status_code == 201


def test_autorisation_refusee_si_le_professeur_n_est_plus_habilite(client, session, tmp_path):
    ctx = _preparer(client, session, tmp_path)
    classe_id, _ = _classe_pilote(client, ctx, "Lina")
    assert client.delete(f"/admin/classes-pilotes/{classe_id}", headers=ctx["admin"]).status_code == 204
    session.expire_all()
    prof = session.get(models.Enseignant, ctx["prof_id"])
    permissions.appliquer(session, prof, [p for p in permissions.portees(prof) if p.domaine != "francais-college"], None)
    session.commit()
    r = client.post(f"/admin/classes-pilotes/{classe_id}", headers=ctx["admin"], json={"motif": "Reprise"})
    assert r.status_code == 409 and "plus habilité" in r.json()["detail"]


def test_parent_et_progression_apres_revocation(client, session, pilote):
    """Décisions du 19/11 : le parent ne voit plus énoncé, solution ni correction ; la progression de l'élève se
    limite à ce qu'il a déjà travaillé ; le professeur garde sa vue complète."""
    h = pilote["lina"]
    seance = client.post("/seances", headers=h).json()["id"]
    _repondre(client, h, seance)
    lina = session.scalar(select(models.Eleve).where(models.Eleve.classe_id == pilote["classe"]))
    # Un parent rattaché à Lina par son professeur.
    admin = pilote["admin"]
    p = client.post(f"/enseignants/eleves/{lina.id}/parents", headers=connecter_enseignant(client), json={"email": "p@x.test"})
    assert p.status_code == 201, p.text
    j = client.post("/parents/connexion", json={"email": "p@x.test", "mot_de_passe": p.json()["mot_de_passe_provisoire"]}).json()
    hp = entete(client.post("/parents/mot-de-passe", headers=entete(j["jeton"]),
                            json={"actuel": p.json()["mot_de_passe_provisoire"], "nouveau": "un-nouveau-mdp-2026"}).json()["jeton"])
    avant = client.get(f"/parents/enfants/{lina.id}/historique", headers=hp).json()["elements"]
    assert avant[0]["enonce"] and avant[0]["solution"] and avant[0]["contenu_masque"] is False

    assert client.delete(f"/admin/classes-pilotes/{pilote['classe']}", headers=admin).status_code == 204
    reponse = client.get(f"/parents/enfants/{lina.id}/historique", headers=hp)
    apres = reponse.json()["elements"]
    assert apres[0]["contenu_masque"] is True and apres[0]["enonce"] == "" and apres[0]["solution"] == ""
    assert apres[0]["correction"] is None and apres[0]["reponse_donnee"] == "finissent"
    assert "finir, ils" not in reponse.text and "ils finissent" not in reponse.text
    # Le professeur garde l'énoncé et la correction dans sa vue.
    prof = client.get(f"/enseignants/eleves/{lina.id}/historique", headers=connecter_enseignant(client)).json()["elements"]
    assert prof[0]["enonce"] and prof[0]["contenu_masque"] is False

    # Progression : Noé (jamais rien fait, classe révoquée) ne voit plus le programme ; Lina, seulement ce qu'elle a travaillé.
    assert client.get("/eleves/moi/progression", headers=pilote["noe"]).json() == []
    assert [c["nb_reponses"] > 0 for c in client.get("/eleves/moi/progression", headers=h).json()] == [True]
    assert client.get(f"/enseignants/eleves/{lina.id}/progression", headers=connecter_enseignant(client)).json() != []
