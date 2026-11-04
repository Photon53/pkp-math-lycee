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
