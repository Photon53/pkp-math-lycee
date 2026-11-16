"""Mode de correction des quiz d'anglais (#110, PR 1) : réglage par groupe et par séance, réponses enregistrées
par essai, score du premier essai figé."""
# Issue #110 — Mode de correction choisi par le professeur (Claude)

from sqlalchemy import Integer, cast, func, select

from app.db import models
from app.db.seed import EMAIL_ANGLAIS_DEMO
from tests.conftest import connecter_admin, connecter_enseignant, entete

APRES, FIN = "apres_chaque_question", "fin_du_quiz"


def _groupe(client, h, niveau="4e"):
    r = client.post("/anglais/groupes", headers=h, json={"nom": "Groupe " + niveau, "niveau": niveau})
    assert r.status_code == 201, r.text
    gid = r.json()["id"]
    carte = client.post(f"/anglais/groupes/{gid}/eleves", headers=h, json={"prenoms": ["Lina"]}).json()["crees"][0]
    return gid, carte


def _eleve(client, carte):
    r = client.post("/anglais/eleve/connexion", json={"identifiant": carte["identifiant"], "code_personnel": carte["code"]})
    assert r.status_code == 200, r.text
    return entete(r.json()["jeton"])


def _publier(client, h, *codes):
    for code in codes:
        assert client.post(f"/anglais/validation/{code}/valider", headers=h).status_code == 200


def test_mode_par_defaut_apres_chaque_question(client):
    h = connecter_enseignant(client, email=EMAIL_ANGLAIS_DEMO)
    gid, carte = _groupe(client, h)
    _publier(client, h, "4E-01")
    assert client.get(f"/anglais/groupes/{gid}/correction", headers=h).json() == {"mode": APRES, "seances": {}}
    assert client.get("/anglais/eleve/seances/4E-01", headers=_eleve(client, carte)).json()["mode_correction"] == APRES


def test_la_seance_l_emporte_sur_le_groupe(client):
    h = connecter_enseignant(client, email=EMAIL_ANGLAIS_DEMO)
    gid, carte = _groupe(client, h)
    _publier(client, h, "4E-01", "4E-02")
    eleve = _eleve(client, carte)

    def mode(code):
        return client.get(f"/anglais/eleve/seances/{code}", headers=eleve).json()["mode_correction"]

    assert client.put(f"/anglais/groupes/{gid}/correction", headers=h, json={"mode": FIN}).json() == {"mode": FIN, "seances": {}}
    r = client.put(f"/anglais/groupes/{gid}/seances/4E-01/correction", headers=h, json={"mode": APRES})
    assert r.json() == {"mode": FIN, "seances": {"4E-01": APRES}}
    assert (mode("4E-01"), mode("4E-02")) == (APRES, FIN)
    # Le réglage explicite de la séance tient, même si le groupe change ensuite.
    client.put(f"/anglais/groupes/{gid}/correction", headers=h, json={"mode": APRES})
    client.put(f"/anglais/groupes/{gid}/seances/4E-02/correction", headers=h, json={"mode": FIN})
    client.put(f"/anglais/groupes/{gid}/correction", headers=h, json={"mode": FIN})
    assert (mode("4E-01"), mode("4E-02")) == (APRES, FIN)
    # `null` retire le réglage : la séance suit de nouveau le groupe.
    r = client.put(f"/anglais/groupes/{gid}/seances/4E-01/correction", headers=h, json={"mode": None})
    assert r.json() == {"mode": FIN, "seances": {"4E-02": FIN}} and mode("4E-01") == FIN


def test_reglages_refuses(client):
    h = connecter_enseignant(client, email=EMAIL_ANGLAIS_DEMO)
    gid, _ = _groupe(client, h)
    assert client.put(f"/anglais/groupes/{gid}/correction", headers=h, json={"mode": "jamais"}).status_code == 422
    assert client.put(f"/anglais/groupes/{gid}/seances/4E-01/correction", headers=h, json={"mode": "x"}).status_code == 422
    # Séance d'un autre niveau, ou inconnue : 404.
    assert client.put(f"/anglais/groupes/{gid}/seances/3E-01/correction", headers=h, json={"mode": FIN}).status_code == 404
    assert client.put(f"/anglais/groupes/{gid}/seances/ZZ-99/correction", headers=h, json={"mode": FIN}).status_code == 404
    assert client.get(f"/anglais/groupes/{gid}/correction", headers=h).json() == {"mode": APRES, "seances": {}}


def test_l_administrateur_regle_et_c_est_journalise(client):
    h = connecter_enseignant(client, email=EMAIL_ANGLAIS_DEMO)
    gid, _ = _groupe(client, h)
    admin = connecter_admin(client)
    assert client.put(f"/admin/anglais/groupes/{gid}/correction", headers=admin, json={"mode": FIN}).status_code == 200
    r = client.put(f"/admin/anglais/groupes/{gid}/seances/4E-01/correction", headers=admin, json={"mode": APRES})
    assert r.json() == {"mode": FIN, "seances": {"4E-01": APRES}}
    assert client.get(f"/admin/anglais/groupes/{gid}/correction", headers=admin).json() == r.json()
    assert client.get(f"/anglais/groupes/{gid}/correction", headers=h).json() == r.json()  # le professeur le voit
    journal = client.get("/admin/journal", headers=admin, params={"objet": "groupe_anglais", "action": "mode-correction"}).json()
    assert [(e["avant"], e["apres"]) for e in journal["elements"]] == [
        ({"seance": "4E-01", "mode": None}, {"seance": "4E-01", "mode": APRES}),
        ({"mode": APRES}, {"mode": FIN}),
    ]
    assert client.put("/admin/anglais/groupes/999999/correction", headers=admin, json={"mode": FIN}).status_code == 404


def test_premier_score_fige_et_reponses_par_essai(client, fabrique):
    h = connecter_enseignant(client, email=EMAIL_ANGLAIS_DEMO)
    gid, carte = _groupe(client, h)
    _publier(client, h, "4E-01")
    eleve = _eleve(client, carte)
    n = len(client.get("/anglais/eleve/seances/4E-01", headers=eleve).json()["quiz"])

    premier = client.post("/anglais/eleve/seances/4E-01/corriger", headers=eleve, json={"reponses": [0] * n}).json()
    bonnes = [d["reponse"] for d in premier["details"]]
    assert premier["premier_score"] == premier["score"] < n
    second = client.post("/anglais/eleve/seances/4E-01/corriger", headers=eleve, json={"reponses": bonnes}).json()
    # Choix B : le meilleur score monte, le premier essai reste figé.
    assert (second["score"], second["meilleur_score"], second["premier_score"]) == (n, n, premier["score"])

    suivi = client.get(f"/anglais/groupes/{gid}/progression", headers=h).json()[0]["seances"]["4E-01"]
    assert (suivi["premier_score"], suivi["score"], suivi["tentatives"]) == (premier["score"], n, 2)
    with fabrique() as s:
        lignes = s.execute(select(models.ReponseAnglais.essai, func.count(), func.sum(cast(models.ReponseAnglais.juste, Integer)))
                           .group_by(models.ReponseAnglais.essai).order_by(models.ReponseAnglais.essai)).all()
    assert [tuple(lig) for lig in lignes] == [(1, n, premier["score"]), (2, n, n)]


def test_resultats_anterieurs_premier_score_inconnu(client, fabrique):
    h = connecter_enseignant(client, email=EMAIL_ANGLAIS_DEMO)
    gid, carte = _groupe(client, h)
    _publier(client, h, "4E-01")
    eleve = _eleve(client, carte)
    with fabrique() as s:
        inscrit = s.scalar(select(models.EleveAnglais).where(models.EleveAnglais.groupe_id == gid))
        s.add(models.ProgressionAnglais(eleve_id=inscrit.id, code="4E-01", meilleur_score=3, total=8, tentatives=2, i_can=[]))
        s.commit()
    n = len(client.get("/anglais/eleve/seances/4E-01", headers=eleve).json()["quiz"])
    r = client.post("/anglais/eleve/seances/4E-01/corriger", headers=eleve, json={"reponses": [0] * n}).json()
    assert r["premier_score"] is None
    assert client.get(f"/anglais/groupes/{gid}/progression", headers=h).json()[0]["seances"]["4E-01"]["premier_score"] is None


def test_retirer_l_eleve_supprime_ses_reponses(client, fabrique):
    h = connecter_enseignant(client, email=EMAIL_ANGLAIS_DEMO)
    gid, carte = _groupe(client, h)
    _publier(client, h, "4E-01")
    eleve = _eleve(client, carte)
    n = len(client.get("/anglais/eleve/seances/4E-01", headers=eleve).json()["quiz"])
    client.post("/anglais/eleve/seances/4E-01/corriger", headers=eleve, json={"reponses": [0] * n})
    eleve_id = client.get("/anglais/groupes", headers=h).json()[0]["eleves"][0]["id"]
    assert client.delete(f"/anglais/groupes/{gid}/eleves/{eleve_id}", headers=h).status_code == 204
    with fabrique() as s:
        assert s.scalar(select(func.count()).select_from(models.ReponseAnglais)) == 0
