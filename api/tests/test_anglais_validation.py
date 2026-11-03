"""PKP Anglais : codes de connexion des élèves, espace élève, édition et validation des séances."""
import io

import pypdf
from conftest import connecter_admin, connecter_enseignant, entete

from app.db.seed import EMAIL_ANGLAIS_DEMO


def connecter_anglais(client) -> dict[str, str]:
    return connecter_enseignant(client, email=EMAIL_ANGLAIS_DEMO)


def _groupe_avec_eleve(client, h, niveau="4e"):
    gid = client.post("/anglais/groupes", headers=h, json={"nom": "Groupe " + niveau, "niveau": niveau}).json()["id"]
    r = client.post(f"/anglais/groupes/{gid}/eleves", headers=h, json={"prenoms": ["Lina"]})
    assert r.status_code == 201
    return gid, r.json()["crees"][0]


def _connecter_eleve(client, carte):
    r = client.post("/anglais/eleve/connexion", json={"identifiant": carte["identifiant"], "code_personnel": carte["code"]})
    assert r.status_code == 200, r.text
    return entete(r.json()["jeton"])


def _texte_pdf(contenu: bytes) -> str:
    return " ".join(p.extract_text() for p in pypdf.PdfReader(io.BytesIO(contenu)).pages)


def test_l_inscription_donne_identifiant_et_code(client):
    h = connecter_anglais(client)
    gid, carte = _groupe_avec_eleve(client, h)
    assert carte["identifiant"].startswith("lina-") and len(carte["code"]) == 6
    eleve = client.get("/anglais/groupes", headers=h).json()[0]["eleves"][0]
    assert eleve["identifiant"] == carte["identifiant"] and eleve["a_un_code"] is True
    assert "code" not in eleve  # seule l'empreinte est gardée

    entree = _connecter_eleve(client, carte)
    assert client.get("/anglais/eleve/moi", headers=entree).json() == {"prenom": "Lina", "niveau": "4e", "groupe": "Groupe 4e"}

    # Code perdu : le nouveau code remplace l'ancien et ferme la session ouverte.
    nouveau = client.post(f"/anglais/groupes/{gid}/eleves/{carte['id']}/code", headers=h).json()
    assert nouveau["identifiant"] == carte["identifiant"] and nouveau["code"] != carte["code"]
    assert client.get("/anglais/eleve/moi", headers=entree).status_code == 401
    r = client.post("/anglais/eleve/connexion", json={"identifiant": carte["identifiant"], "code_personnel": carte["code"]})
    assert r.status_code == 401
    _connecter_eleve(client, nouveau)
    assert len(client.post(f"/anglais/groupes/{gid}/codes", headers=h, params={"tous": True}).json()) == 1


def test_un_eleve_d_anglais_n_ouvre_pas_l_espace_de_maths(client):
    h = connecter_anglais(client)
    _, carte = _groupe_avec_eleve(client, h)
    entree = _connecter_eleve(client, carte)
    assert client.get("/eleves/moi", headers=entree).status_code == 401
    assert client.get("/anglais/seances", headers=entree).status_code == 401


def test_rien_n_est_ouvert_aux_eleves_avant_validation(client):
    h = connecter_anglais(client)
    _, carte = _groupe_avec_eleve(client, h)
    entree = _connecter_eleve(client, carte)
    assert client.get("/anglais/eleve/seances", headers=entree).json() == []
    assert client.get("/anglais/eleve/seances/4E-01", headers=entree).status_code == 404

    # Le professeur voit la séance avec la mention NON VALIDÉ, PDF compris.
    seances = client.get("/anglais/seances", headers=h).json()
    assert all(s["statut"] == "soumis" and not s["validee"] for s in seances)
    pdf = client.get("/anglais/seances/4E-01/pdf/eleve", headers=h)
    assert "NON-VALIDE" in pdf.headers["content-disposition"]
    assert "NON VALIDÉ" in _texte_pdf(pdf.content)


def test_le_referent_valide_puis_l_eleve_fait_le_quiz(client):
    h = connecter_anglais(client)
    _, carte = _groupe_avec_eleve(client, h)
    a_valider = client.get("/anglais/validation", headers=h).json()
    assert len(a_valider) == 20 and not any(s["est_auteur"] for s in a_valider)
    r = client.post("/anglais/validation/4E-01/valider", headers=h)
    assert r.status_code == 200 and r.json()["statut"] == "valide"
    assert client.post("/anglais/validation/3E-01/refuser", headers=h, json={"motif": "  "}).status_code == 422
    pdf = client.get("/anglais/seances/4E-01/pdf/animateur", headers=h)
    assert "NON-VALIDE" not in pdf.headers["content-disposition"] and "NON VALIDÉ" not in _texte_pdf(pdf.content)

    entree = _connecter_eleve(client, carte)
    liste = client.get("/anglais/eleve/seances", headers=entree).json()
    assert [s["code"] for s in liste] == ["4E-01"] and liste[0]["score"] is None
    seance = client.get("/anglais/eleve/seances/4E-01", headers=entree).json()
    # Aucun corrigé ni consigne animateur côté élève.
    assert "practice_answers" not in seance["cahier"] and "answers" not in seance["cahier"]["listening"]
    assert all("corrige" not in f for f in seance["fiches"]) and all("reponse" not in q for q in seance["quiz"])
    assert len(seance["quiz"]) >= 8  # 6 QCM de vocabulaire + 2 de grammaire

    vides = client.post("/anglais/eleve/seances/4E-01/corriger", headers=entree, json={"reponses": []}).json()
    assert vides["score"] == 0 and vides["total"] == len(seance["quiz"]) and vides["practice_answers"]
    bonnes = [d["reponse"] for d in vides["details"]]
    r = client.post("/anglais/eleve/seances/4E-01/corriger", headers=entree, json={"reponses": bonnes}).json()
    assert r["score"] == r["total"] == r["meilleur_score"]

    nb = len(liste[0]["can_do"])
    assert client.put("/anglais/eleve/seances/4E-01/i-can", headers=entree, json={"i_can": ["autonome"]}).status_code == (
        200 if nb == 1 else 422)
    r = client.put("/anglais/eleve/seances/4E-01/i-can", headers=entree, json={"i_can": ["en_cours"] * nb})
    assert r.status_code == 200
    suivi = client.get("/anglais/eleve/seances", headers=entree).json()[0]
    assert (suivi["score"], suivi["tentatives"], suivi["i_can"]) == (suivi["total"], 2, ["en_cours"] * nb)

    # Le professeur suit la progression ; un élève de 4e ne voit pas les séances de 3e.
    gid = client.get("/anglais/groupes", headers=h).json()[0]["id"]
    prog = client.get(f"/anglais/groupes/{gid}/progression", headers=h).json()
    assert prog[0]["seances"]["4E-01"]["tentatives"] == 2
    client.post("/anglais/validation/3E-01/valider", headers=h)
    assert client.get("/anglais/eleve/seances/3E-01", headers=entree).status_code == 404


def test_reserve_aux_referents(client):
    admin = connecter_admin(client)
    prof = next(e for e in client.get("/admin/enseignants", headers=admin).json() if e["email"] == EMAIL_ANGLAIS_DEMO)
    assert prof["referent_anglais"] is True
    corps = {"nom": prof["nom"], "email": prof["email"], "enseigne_maths": False, "enseigne_anglais": True,
             "referent_anglais": False}
    assert client.post(f"/admin/enseignants/{prof['id']}", headers=admin, json=corps).status_code == 200
    h = connecter_anglais(client)
    assert client.get("/anglais/validation", headers=h).status_code == 403
    assert client.post("/anglais/validation/4E-01/valider", headers=h).status_code == 403
    # Un référent doit enseigner l'anglais.
    demo = next(e for e in client.get("/admin/enseignants", headers=admin).json() if e["email"] == "demo@pkp.test")
    corps = {"nom": demo["nom"], "email": demo["email"], "enseigne_maths": True, "referent_anglais": True}
    assert client.post(f"/admin/enseignants/{demo['id']}", headers=admin, json=corps).status_code == 422


def test_l_administrateur_edite_et_un_autre_valide(client):
    admin = connecter_admin(client)
    h = connecter_anglais(client)
    client.post("/anglais/validation/4E-02/valider", headers=h)

    seance = client.get("/admin/anglais/seances/4E-02", headers=admin).json()
    assert seance["statut"] == "valide" and seance["version_publiee"] == 1 and len(seance["quiz_vocabulaire"]) == 6
    contenu, cahier, quiz = seance["contenu"], seance["cahier"], seance["quiz"]

    # Contenu incomplet refusé : 90 minutes, code inchangé, QCM cohérent.
    mauvais = {**contenu, "steps": contenu["steps"][:-1]}
    r = client.put("/admin/anglais/seances/4E-02", headers=admin, json={"contenu": mauvais, "cahier": cahier, "quiz": quiz})
    assert r.status_code == 422 and "90 minutes" in r.json()["detail"]
    faux_quiz = [{"question": "?", "choix": ["a", "b"], "reponse": 5}]
    r = client.put("/admin/anglais/seances/4E-02", headers=admin, json={"contenu": contenu, "cahier": cahier, "quiz": faux_quiz})
    assert r.status_code == 422

    # Modifier une séance validée crée la version 2 en brouillon ; la version 1 reste publiée.
    nouveau = {**contenu, "title": "Weekend plans (révisé)"}
    r = client.put("/admin/anglais/seances/4E-02", headers=admin, json={"contenu": nouveau, "cahier": cahier, "quiz": quiz})
    assert r.status_code == 200
    assert (r.json()["version"], r.json()["statut"], r.json()["version_publiee"]) == (2, "brouillon", 1)
    assert client.get("/anglais/seances/4E-02", headers=h).json()["titre"] != "Weekend plans (révisé)"
    assert client.post("/admin/anglais/seances/4E-02/valider", headers=admin).status_code == 409  # pas encore soumise
    assert client.post("/admin/anglais/seances/4E-02/soumettre", headers=admin).json()["statut"] == "soumis"
    # L'auteur ne valide pas son propre contenu ; un référent le refuse avec un motif, puis le valide.
    r = client.post("/admin/anglais/seances/4E-02/valider", headers=admin)
    assert r.status_code == 409 and "propre contenu" in r.json()["detail"]
    r = client.post("/anglais/validation/4E-02/refuser", headers=h, json={"motif": "Titre en français"})
    assert r.json()["statut"] == "refuse" and r.json()["motif_refus"] == "Titre en français"
    client.put("/admin/anglais/seances/4E-02", headers=admin, json={"contenu": nouveau, "cahier": cahier, "quiz": quiz})
    client.post("/admin/anglais/seances/4E-02/soumettre", headers=admin)
    assert client.post("/anglais/validation/4E-02/valider", headers=h).json()["version_publiee"] == 2

    historique = client.get("/admin/anglais/seances/4E-02", headers=admin).json()["historique"]
    assert [(v["numero"], v["statut"]) for v in historique] == [(2, "valide"), (1, "archive")]
    assert client.get("/anglais/seances/4E-02", headers=h).json()["titre"] == "Weekend plans (révisé)"
    journal = client.get("/admin/journal", headers=admin).json()["elements"]
    assert {(j["action"], j["objet"]) for j in journal} >= {
        ("modifier", "seance_anglais"), ("soumettre", "seance_anglais"), ("valider", "seance_anglais"),
        ("refuser", "seance_anglais"),
    }


def test_carte_d_anglais_saisie_sur_la_page_de_maths(client):
    """L'élève d'anglais qui se trompe de page est renvoyé vers la sienne, seulement avec le bon code."""
    _, carte = _groupe_avec_eleve(client, connecter_anglais(client))
    r = client.post("/eleves/connexion/identifiant", json={"identifiant": carte["identifiant"], "code_personnel": carte["code"]})
    assert r.status_code == 409 and "PKP Anglais" in r.json()["detail"]
    r = client.post("/eleves/connexion/identifiant", json={"identifiant": carte["identifiant"], "code_personnel": "XXXXXX"})
    assert r.status_code == 401
