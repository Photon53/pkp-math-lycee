"""Rédaction en ligne (issue #179, décision RGPD-2) : brouillon, remise, correction par le professeur de la classe,
réécriture ; accès, journal, export, purge, séances, et fermeture tant que la rédaction n'est pas ouverte."""
# Issue #179 — Rédaction en ligne et correction par le professeur (Claude)

from datetime import UTC, date, datetime, timedelta

import pytest
from sqlalchemy import select

from app import purge
from app.config import settings
from app.contenu import charger, importer
from app.db import models
from app.routes.redactions import fin_annee_scolaire
from tests.conftest import connecter_admin, connecter_eleve, connecter_enseignant, entete, inscrire_eleves
from tests.test_classes_pilotes import _classe_pilote, _preparer
from tests.test_contenu import ecrire, erreurs

TEXTE = "Il était une fois un dragon qui n'aimait pas le feu. RÉDACTION-TÉMOIN."
SUJET_REDACTION = """
chapitre: {code: FR5-RED, matiere: francais, rubrique: redaction, niveau: 5e, parcours: tronc-commun, ordre: 2, titre: Raconter}
competences:
  - code: FR5-RED-C
    libelle: Écrire un court récit
    questions:
      - code: FR5-RED-C-01
        difficulte: 2
        type: redaction
        enonce: "Raconte en quinze lignes une aventure imaginaire. N'écris pas de nom ni d'adresse réels."
        solution: "Récit au passé, cohérent, ponctuation correcte."
        auteur: Test
        correction:
          etapes:
            - Vérifier le temps du récit et la cohérence.
"""


@pytest.fixture
def ouverte(monkeypatch):
    monkeypatch.setattr(settings, "redaction_active", True)


@pytest.fixture
def classe(client, session, tmp_path, ouverte):
    """Classe pilote de français (Lina) avec un sujet de rédaction ; classe révoquée (Noé)."""
    ctx = _preparer(client, session, tmp_path)
    ecrire(tmp_path, SUJET_REDACTION, "francais/5e/tronc-commun/02-raconter.yaml")
    importer(session, charger(tmp_path), archiver_absentes=False)
    session.commit()
    ctx["classe"], ctx["lina"] = _classe_pilote(client, ctx, "Lina")
    ctx["autre"], ctx["noe"] = _classe_pilote(client, ctx, "Noé")
    assert client.delete(f"/admin/classes-pilotes/{ctx['autre']}", headers=ctx["admin"]).status_code == 204
    ctx["sujet"] = session.scalar(select(models.Question).where(models.Question.code == "FR5-RED-C-01")).id
    return ctx


def _remettre(client, h, sujet, texte=TEXTE) -> dict:
    assert client.put(f"/eleves/moi/redactions/{sujet}", headers=h, json={"texte": texte}).status_code == 200
    r = client.post(f"/eleves/moi/redactions/{sujet}/remise", headers=h)
    assert r.status_code == 200, r.text
    return r.json()


def test_fin_d_annee_scolaire():
    assert fin_annee_scolaire(date(2026, 11, 19)) == date(2027, 8, 31)
    assert fin_annee_scolaire(date(2027, 3, 1)) == date(2027, 8, 31)
    assert fin_annee_scolaire(date(2027, 8, 31)) == date(2027, 8, 31)
    assert fin_annee_scolaire(date(2027, 9, 1)) == date(2028, 8, 31)


def test_sujet_de_redaction_seulement_dans_la_rubrique_redaction(tmp_path):
    ecrire(tmp_path, SUJET_REDACTION.replace("rubrique: redaction", "rubrique: conjugaison"),
           "francais/5e/tronc-commun/02-raconter.yaml")
    assert "réservés aux chapitres de diagnostic" in erreurs(tmp_path)


def test_fermee_par_defaut(client, session, tmp_path):
    """Tant que PKP_REDACTION_ACTIVE est faux, aucune route ne sert ni n'enregistre de rédaction."""
    ctx = _preparer(client, session, tmp_path)
    _, h = _classe_pilote(client, ctx, "Lina")
    assert client.get("/eleves/moi/redactions", headers=h).status_code == 403
    assert client.put("/eleves/moi/redactions/1", headers=h, json={"texte": "x"}).status_code == 403
    assert client.get("/enseignants/redactions/1", headers=connecter_enseignant(client)).status_code == 403


def test_brouillon_remise_correction_puis_reecriture(client, session, classe):
    h, sujet, prof = classe["lina"], classe["sujet"], connecter_enseignant(client)
    sujets = client.get("/eleves/moi/redactions", headers=h).json()
    assert [(s["question_id"], s["statut"]) for s in sujets] == [(sujet, None)]
    assert client.post(f"/eleves/moi/redactions/{sujet}/remise", headers=h).status_code == 409  # rien d'écrit
    # Brouillon : invisible du professeur.
    client.put(f"/eleves/moi/redactions/{sujet}", headers=h, json={"texte": "Premier jet"})
    assert client.get(f"/enseignants/classes/{classe['classe']}/redactions", headers=prof).json() == []
    brouillon = session.scalar(select(models.Redaction).where(models.Redaction.statut == "brouillon"))
    assert client.get(f"/enseignants/redactions/{brouillon.id}", headers=prof).status_code == 404
    # Remise : le professeur la lit et la corrige ; l'élève ne peut plus la modifier.
    detail = _remettre(client, h, sujet)
    assert detail["versions"][-1]["statut"] == "remise" and detail["conserver_jusqu_au"].endswith("-08-31")
    assert client.put(f"/eleves/moi/redactions/{sujet}", headers=h, json={"texte": "modif"}).status_code == 409
    liste = client.get(f"/enseignants/classes/{classe['classe']}/redactions", headers=prof).json()
    assert [(r["eleve"], r["statut"]) for r in liste] == [("Lina", "remise")]
    lue = client.get(f"/enseignants/redactions/{liste[0]['id']}", headers=prof).json()
    assert lue["texte"] == TEXTE and lue["guide"]
    corrigee = client.post(f"/enseignants/redactions/{liste[0]['id']}/correction", headers=prof,
                           json={"commentaire": "Bon début ; travaille la ponctuation."})
    assert corrigee.status_code == 200 and corrigee.json()["statut"] == "corrigee"
    vue = client.get(f"/eleves/moi/redactions/{sujet}", headers=h).json()["versions"][-1]
    assert vue["commentaire"] == "Bon début ; travaille la ponctuation." and vue["statut"] == "corrigee"
    # Réécriture : nouvelle version ; la correction de la première ne peut plus être reprise.
    deux = client.put(f"/eleves/moi/redactions/{sujet}", headers=h, json={"texte": "Deuxième version"}).json()
    assert [v["version"] for v in deux["versions"]] == [1, 2] and deux["versions"][-1]["statut"] == "brouillon"
    assert client.post(f"/enseignants/redactions/{liste[0]['id']}/correction", headers=prof,
                       json={"commentaire": "Autre"}).status_code == 409


def test_acces_reserve_a_l_eleve_et_au_professeur_de_la_classe(client, session, classe):
    sujet = classe["sujet"]
    _remettre(client, classe["lina"], sujet)
    redaction = session.scalar(select(models.Redaction)).id
    # Classe révoquée : Noé n'a pas le sujet, même par URL directe.
    assert client.get("/eleves/moi/redactions", headers=classe["noe"]).json() == []
    assert client.get(f"/eleves/moi/redactions/{sujet}", headers=classe["noe"]).status_code == 404
    assert client.put(f"/eleves/moi/redactions/{sujet}", headers=classe["noe"], json={"texte": "x"}).status_code == 404
    # Un autre professeur : rien. L'administrateur : aucune route d'accès aux textes.
    admin = connecter_admin(client)
    r = client.post("/admin/enseignants", headers=admin, json={
        "nom": "B", "email": "b@pkp.test", "role": "enseignant",
        "habilitations": [{"role": "professeur", "domaine": "francais-college"}]})
    provisoire = r.json()["mot_de_passe_provisoire"]
    j = client.post("/enseignants/connexion", json={"email": "b@pkp.test", "mot_de_passe": provisoire}).json()["jeton"]
    b = entete(client.post("/enseignants/mot-de-passe", headers=entete(j),
                           json={"actuel": provisoire, "nouveau": "un-mot-de-passe-2026"}).json()["jeton"])
    assert client.get(f"/enseignants/redactions/{redaction}", headers=b).status_code == 404
    assert client.post(f"/enseignants/redactions/{redaction}/correction", headers=b, json={"commentaire": "x"}).status_code == 404
    assert client.get(f"/enseignants/classes/{classe['classe']}/redactions", headers=b).status_code == 404
    assert client.get(f"/enseignants/redactions/{redaction}", headers=admin).status_code in (401, 403)
    assert not [c for c in client.get("/openapi.json").json()["paths"] if c.startswith("/admin") and "redaction" in c]
    # Aucun texte dans le journal d'administration.
    assert not any("RÉDACTION-TÉMOIN" in str(j.avant) + str(j.apres) for j in session.scalars(select(models.JournalAdmin)))


def test_jamais_servie_en_seance(client, session, classe):
    """Une rédaction se rédige dans « Rédaction » : une séance sur son seul chapitre n'a rien à proposer."""
    h = classe["lina"]
    chapitre = session.get(models.Question, classe["sujet"]).competence.chapitre_id
    seance = client.post("/seances", headers=h, json={"chapitre_ids": [chapitre]})
    assert seance.status_code == 201, seance.text
    question = client.get(f"/seances/{seance.json()['id']}/question", headers=h)
    assert question.status_code == 204, question.text
    chapitres = {c["id"]: c["nb_questions"] for c in client.get("/eleves/moi/chapitres", headers=h).json()}
    assert chapitres[chapitre] == 0


def test_export_et_purge(client, session, classe):
    _remettre(client, classe["lina"], classe["sujet"])
    lina = session.scalar(select(models.Eleve).where(models.Eleve.classe_id == classe["classe"]))
    export = client.get(f"/admin/eleves/{lina.id}/export", headers=connecter_admin(client))
    assert export.status_code == 200 and export.json()["redactions"][0]["texte"] == TEXTE
    redaction = session.scalar(select(models.Redaction))
    # Avant le 31 août : conservée ; après : supprimée.
    assert purge.purger_redactions(session, datetime(redaction.conserver_jusqu_au.year, 8, 31, tzinfo=UTC)) == 0
    assert purge.purger_redactions(session, datetime(redaction.conserver_jusqu_au.year, 9, 1, tzinfo=UTC)) == 1
    session.commit()
    assert session.scalar(select(models.Redaction)) is None


def test_purge_trente_jours_apres_l_archivage_de_la_classe(client, session, classe):
    _remettre(client, classe["lina"], classe["sujet"])
    session.expire_all()
    c = session.get(models.Classe, classe["classe"])
    maintenant = datetime.now(UTC)
    c.archivee_le = maintenant - timedelta(days=29)
    session.commit()
    assert purge.purger_redactions(session, maintenant) == 0
    c.archivee_le = maintenant - timedelta(days=31)
    session.commit()
    assert purge.purger_redactions(session, maintenant) == 1


def test_supprimee_avec_l_eleve(client, session, classe):
    _remettre(client, classe["lina"], classe["sujet"])
    session.expire_all()
    lina = session.scalar(select(models.Eleve).where(models.Eleve.classe_id == classe["classe"]))
    session.delete(lina)
    session.commit()
    assert session.scalar(select(models.Redaction)) is None
