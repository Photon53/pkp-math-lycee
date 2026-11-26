"""PKP Math : catalogue et documents de chapitre (résumé, exercices, corrigé) selon qui lit."""

from sqlalchemy import select

from app.db import models
from tests.conftest import connecter_admin, connecter_eleve, connecter_enseignant, entete


def test_professeur_et_admin_voient_tout_le_programme(client):
    for h in (connecter_enseignant(client), connecter_admin(client)):
        chapitres = client.get("/pkp-math/catalogue?niveau=2nde", headers=h).json()
        assert chapitres and {c["niveau"] for c in chapitres} == {"2nde"}
        assert {"tronc-commun", "excellence", "mise-a-niveau"} <= {c["parcours"] for c in chapitres}
        doc = client.get(f"/pkp-math/chapitres/{chapitres[0]['id']}", headers=h).json()
        assert doc["competences"][0]["resume"] and doc["competences"][0]["questions"]
        # Brouillons à valider : le document porte la mention NON VALIDÉ.
        assert doc["valide"] is False
        assert any(q["correction"] for c in doc["competences"] for q in c["questions"])


def test_question_a_gabarit_tiree_de_facon_reproductible(client, session):
    q = session.scalars(select(models.Question).where(models.Question.gabarit.is_not(None))).first()
    h = connecter_enseignant(client)
    chapitre_id = q.competence.chapitre_id
    une = client.get(f"/pkp-math/chapitres/{chapitre_id}", headers=h).json()
    deux = client.get(f"/pkp-math/chapitres/{chapitre_id}", headers=h).json()
    trouvee = next(x for c in une["competences"] for x in c["questions"] if x["id"] == q.id)
    assert "[[" not in trouvee["enonce"] and "[[" not in trouvee["solution"]
    assert une == deux


def test_eleve_ne_voit_que_les_chapitres_ouverts_de_sa_classe(client, session):
    h = connecter_eleve(client)
    eleve_classe = session.scalar(select(models.Classe).where(models.Classe.code == "2NDE-A-DEMO"))
    ouverts = {c.id for c in eleve_classe.chapitres_proposes if not c.masque}
    vus = {c["id"] for c in client.get("/pkp-math/catalogue", headers=h).json()}
    assert vus == ouverts
    ferme = session.scalar(select(models.Chapitre).where(models.Chapitre.niveau == "Tle"))
    assert client.get(f"/pkp-math/chapitres/{ferme.id}", headers=h).status_code == 404


def test_enfant_et_parent_voient_le_niveau_de_l_enfant(client):
    admin = connecter_admin(client)
    f = client.post("/admin/familles", headers=admin,
                    json={"email": "pkp@x.test", "enfants": [{"prenom": "Inès", "niveau": "1re"}]}).json()
    carte = f["cartes"][0]
    jeton = client.post("/enfants/connexion", json={"identifiant": carte["identifiant"], "code_personnel": carte["code"]}).json()["jeton"]
    niveaux = {c["niveau"] for c in client.get("/pkp-math/catalogue", headers=entete(jeton)).json()}
    assert niveaux == {"1re"}
    j = client.post("/parents/connexion", json={"email": "pkp@x.test", "mot_de_passe": f["mot_de_passe_provisoire"]}).json()
    hp = client.post("/parents/mot-de-passe", headers=entete(j["jeton"]),
                     json={"actuel": f["mot_de_passe_provisoire"], "nouveau": "un-nouveau-mdp-2026"}).json()["jeton"]
    assert {c["niveau"] for c in client.get("/pkp-math/catalogue", headers=entete(hp)).json()} == {"1re"}


def test_collège_ferme_au_public_n_est_pas_servi_a_l_enfant(client):
    admin = connecter_admin(client)
    f = client.post("/admin/familles", headers=admin,
                    json={"email": "c@x.test", "enfants": [{"prenom": "Noé", "niveau": "5e"}]}).json()
    carte = f["cartes"][0]
    jeton = client.post("/enfants/connexion", json={"identifiant": carte["identifiant"], "code_personnel": carte["code"]}).json()["jeton"]
    assert client.get("/pkp-math/catalogue", headers=entete(jeton)).json() == []
    client.post("/admin/domaines/maths-college", headers=admin, json={"actif": True, "public": True})
    assert {c["niveau"] for c in client.get("/pkp-math/catalogue", headers=entete(jeton)).json()} == {"5e"}


def test_sans_jeton(client):
    assert client.get("/pkp-math/catalogue").status_code == 401


# --- Version élève de l'export (#178) ---------------------------------------------------------------------------


def _chapitre_avec_corriges(client, h) -> int:
    chapitres = client.get("/pkp-math/catalogue?niveau=2nde", headers=h).json()
    for ch in chapitres:
        doc = client.get(f"/pkp-math/chapitres/{ch['id']}", headers=h).json()
        if any(q["correction"] and q["correction"].get("etapes") for c in doc["competences"] for q in c["questions"]):
            return ch["id"]
    raise AssertionError("aucun chapitre de 2nde avec un corrigé détaillé")


def _parent(client) -> dict:
    admin = connecter_admin(client)
    f = client.post("/admin/familles", headers=admin,
                    json={"email": "v@x.test", "enfants": [{"prenom": "Lou", "niveau": "2nde"}]}).json()
    j = client.post("/parents/connexion", json={"email": "v@x.test", "mot_de_passe": f["mot_de_passe_provisoire"]}).json()
    return entete(client.post("/parents/mot-de-passe", headers=entete(j["jeton"]),
                              json={"actuel": f["mot_de_passe_provisoire"], "nouveau": "un-nouveau-mdp-2026"}).json()["jeton"])


def test_version_eleve_sans_aucun_corrige_meme_pour_un_adulte(client):
    """Fiche à imprimer pour une classe : aucune solution ni aucun corrigé ne quitte le serveur, quel que soit l'adulte."""
    for h in (connecter_enseignant(client), connecter_admin(client), _parent(client)):
        chapitre_id = _chapitre_avec_corriges(client, h)
        complet = client.get(f"/pkp-math/chapitres/{chapitre_id}", headers=h).json()
        reponse = client.get(f"/pkp-math/chapitres/{chapitre_id}?version=eleve", headers=h)
        assert reponse.status_code == 200
        eleve = reponse.json()
        assert complet["version"] == "complete" and eleve["version"] == "eleve"
        questions = [q for c in eleve["competences"] for q in c["questions"]]
        assert questions and len(questions) == sum(len(c["questions"]) for c in complet["competences"])
        assert all(q["solution"] == "" and q["correction"] is None and q["corrige_visible"] is False for q in questions)
        # Les énoncés restent ; les textes des corrigés n'apparaissent nulle part dans la réponse.
        assert [q["enonce"] for q in questions] == [q["enonce"] for c in complet["competences"] for q in c["questions"]]
        etapes = {e for c in complet["competences"] for q in c["questions"] if q["correction"]
                  for e in q["correction"].get("etapes", []) if len(e) >= 12}
        assert etapes and not any(e in reponse.text for e in etapes)


def test_version_complete_par_defaut_et_version_inconnue_refusee(client):
    h = connecter_enseignant(client)
    chapitre_id = _chapitre_avec_corriges(client, h)
    doc = client.get(f"/pkp-math/chapitres/{chapitre_id}", headers=h).json()
    assert doc["version"] == "complete" and doc["matiere"] == "maths"
    assert any(q["correction"] for c in doc["competences"] for q in c["questions"])
    assert client.get(f"/pkp-math/chapitres/{chapitre_id}?version=professeur", headers=h).status_code == 422


def test_version_eleve_ne_donne_pas_plus_a_un_eleve(client, session):
    """Un élève reste soumis à ses droits : chapitres ouverts seulement, aucun corrigé en version élève."""
    h = connecter_eleve(client)
    ouverts = client.get("/pkp-math/catalogue", headers=h).json()
    assert ouverts and all(c["matiere"] == "maths" for c in ouverts)
    eleve = client.get(f"/pkp-math/chapitres/{ouverts[0]['id']}?version=eleve", headers=h).json()
    assert all(q["correction"] is None for c in eleve["competences"] for q in c["questions"])
    ferme = session.scalar(select(models.Chapitre).where(models.Chapitre.niveau == "Tle"))
    assert client.get(f"/pkp-math/chapitres/{ferme.id}?version=eleve", headers=h).status_code == 404


def test_version_eleve_retire_aussi_les_corriges_deja_debloques(client, session):
    """Un élève qui a répondu voit le corrigé de cette question par défaut (ARCH-4), jamais en version élève."""
    h = connecter_eleve(client)
    seance = client.post("/seances", headers=h).json()["id"]
    question = client.get(f"/seances/{seance}/question", headers=h).json()
    reponse = client.post(f"/seances/{seance}/reponses", headers=h,
                          json={"question_id": question["id"], "reponse_donnee": "zzz"})
    assert reponse.status_code == 200, reponse.text
    chapitre_id = session.get(models.Question, question["id"]).competence.chapitre_id

    def la_question(version: str) -> dict:
        doc = client.get(f"/pkp-math/chapitres/{chapitre_id}?version={version}", headers=h).json()
        return next(q for c in doc["competences"] for q in c["questions"] if q["id"] == question["id"])

    assert la_question("complete")["corrige_visible"] is True
    eleve = la_question("eleve")
    assert eleve["corrige_visible"] is False and eleve["solution"] == "" and eleve["correction"] is None
