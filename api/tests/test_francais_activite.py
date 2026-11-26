"""Parcours du français au niveau de l'anglais (#217) : quiz corrigé et mode de correction, auto-évaluation, réponses
rédigées relues par le professeur (RGPD-2), progression de la classe et édition des dossiers par l'administrateur."""
# Issue #217 — Parcours du français au niveau de l'anglais (Claude)

import copy
from datetime import UTC, datetime

import pytest
from sqlalchemy import func, select

from app import francais, purge
from app.config import settings
from app.db import models
from tests.conftest import connecter_enseignant
from tests.test_francais import (  # noqa: F401 (fixtures)
    CODE, DOMAINE, _brut, _creer, _ecrire, _importer, circuit, prepare,
)

QUIZ = [
    {"question": "Qui raconte l'histoire ?", "texte": "TEXTE-1", "choix": ["Le narrateur", "L'auteur", "Le lecteur"],
     "reponse": 0, "explication": "Le narrateur est la voix qui raconte dans le texte. EXPLICATION-TEMOIN"},
    {"question": "Une information implicite est…", "choix": ["écrite mot pour mot", "à déduire d'indices"],
     "reponse": 1, "explication": "On la déduit d'indices du texte."},
    {"question": "Pour justifier, on cite…", "choix": ["un passage précis", "un souvenir personnel"],
     "reponse": 0, "explication": "Une citation précise appuie la réponse."},
]
JE_SAIS = ["Je sais repérer une information explicite.", "Je sais justifier par une citation."]


def _avec_quiz() -> dict:
    d = copy.deepcopy(_brut())
    d["quiz"] = copy.deepcopy(QUIZ)
    d["eleve"]["je_sais"] = list(JE_SAIS)
    return d


@pytest.fixture
def actif(client, circuit, fabrique, tmp_path):
    """Dossier avec quiz et « Je sais », validé (v2) et ouvert à la classe pilote de Lina."""
    assert _importer(fabrique, _ecrire(tmp_path, _avec_quiz())).nouvelles_versions == [CODE]
    assert client.post(f"/francais/validation/{CODE}/valider", headers=circuit["val"]).status_code == 200
    assert client.put(f"/francais/dossiers/{CODE}/classes/{circuit['pilote'][0]}", headers=circuit["prof"]).status_code == 200
    return circuit


def _regler(client, ctx, mode, dossier=False):
    classe = ctx["pilote"][0]
    route = f"/francais/classes/{classe}/dossiers/{CODE}/correction" if dossier else f"/francais/classes/{classe}/correction"
    r = client.put(route, headers=ctx["prof"], json={"mode": mode})
    assert r.status_code == 200, r.text
    return r.json()


# --- Contrat --------------------------------------------------------------------------------------------------

class TestContrat:
    def test_un_dossier_sans_quiz_garde_son_empreinte(self):
        """Les dossiers importés avant #217 ne créent pas de version fantôme au déploiement."""
        brut = _brut()
        brut.pop("quiz", None)
        brut["eleve"].pop("je_sais", None)
        f = francais.FichierDossier.model_validate(brut)
        donnees = f.model_dump(mode="json")
        sans = {k: v for k, v in donnees.items() if k != "quiz"}
        sans["eleve"] = {k: v for k, v in sans["eleve"].items() if k != "je_sais"}
        assert francais.empreinte(donnees) == francais.empreinte(sans)

    @pytest.mark.parametrize("modifier, message", [
        (lambda q: q.update(reponse=5), "désigner un des choix"),
        (lambda q: q.update(choix=["A"]), "at least 2"),
        (lambda q: q.update(texte="TEXTE-9"), "texte inconnu cité par le quiz"),
        (lambda q: q.update(choix=["oui", "Oui"]), "deux choix identiques"),
    ])
    def test_quiz_controle(self, tmp_path, modifier, message):
        d = _avec_quiz()
        modifier(d["quiz"][0])
        with pytest.raises(francais.DossierInvalide) as exc:
            francais.charger(_ecrire(tmp_path, d))
        assert message in str(exc.value)


# --- Quiz et mode de correction ----------------------------------------------------------------------------------

class TestQuiz:
    def test_vue_eleve_sans_reponse_ni_explication(self, client, actif):
        r = client.get(f"/francais/eleve/dossiers/{CODE}", headers=actif["pilote"][1])
        corps = r.json()
        assert [set(q) for q in corps["eleve"]["quiz"]] == [{"question", "texte", "choix"}] * 3
        assert "EXPLICATION-TEMOIN" not in r.text and corps["mode_correction"] == "apres_chaque_question"
        assert corps["eleve"]["je_sais"] == JE_SAIS and corps["nb_quiz"] == 3

    def test_correction_apres_chaque_question_la_premiere_reponse_compte(self, client, actif):
        h = actif["pilote"][1]
        r = client.post(f"/francais/eleve/dossiers/{CODE}/quiz/0", headers=h, json={"reponse": 1})
        assert r.status_code == 200 and r.json()["juste"] is False and r.json()["reponse"] == 0
        assert "EXPLICATION-TEMOIN" in r.json()["explication"]
        # Une seconde réponse à la même question ne remplace pas la première.
        assert client.post(f"/francais/eleve/dossiers/{CODE}/quiz/0", headers=h, json={"reponse": 0}).json()["choix"] == 1
        fin = client.post(f"/francais/eleve/dossiers/{CODE}/corriger", headers=h, json={"reponses": [0, 1, 0]}).json()
        assert (fin["score"], fin["total"], fin["premier_score"], fin["tentatives"]) == (2, 3, 2, 1)
        assert fin["details"][0]["choix"] == 1  # la réponse déjà corrigée est conservée
        assert client.post(f"/francais/eleve/dossiers/{CODE}/quiz/9", headers=h, json={"reponse": 0}).status_code == 422

    def test_correction_en_fin_de_quiz(self, client, actif):
        h = actif["pilote"][1]
        _regler(client, actif, "fin_du_quiz")
        assert client.get(f"/francais/eleve/dossiers/{CODE}", headers=h).json()["mode_correction"] == "fin_du_quiz"
        assert client.post(f"/francais/eleve/dossiers/{CODE}/quiz/0", headers=h, json={"reponse": 0}).status_code == 409
        r = client.post(f"/francais/eleve/dossiers/{CODE}/corriger", headers=h, json={"reponses": [0, None, 0]})
        assert r.status_code == 422  # ARCH-4 : pas de corrigé avant une réponse à chaque question
        premier = client.post(f"/francais/eleve/dossiers/{CODE}/corriger", headers=h, json={"reponses": [1, 0, 1]}).json()
        second = client.post(f"/francais/eleve/dossiers/{CODE}/corriger", headers=h, json={"reponses": [0, 1, 0]}).json()
        assert (premier["score"], second["score"], second["meilleur_score"], second["premier_score"], second["tentatives"]) == (0, 3, 3, 0, 2)

    def test_le_reglage_du_dossier_l_emporte_sur_la_classe(self, client, actif):
        _regler(client, actif, "fin_du_quiz")
        reglage = _regler(client, actif, "apres_chaque_question", dossier=True)
        assert reglage == {"mode": "fin_du_quiz", "dossiers": {CODE: "apres_chaque_question"}}
        h = actif["pilote"][1]
        assert client.get(f"/francais/eleve/dossiers/{CODE}", headers=h).json()["mode_correction"] == "apres_chaque_question"
        assert _regler(client, actif, None, dossier=True)["dossiers"] == {}
        r = client.put(f"/francais/classes/{actif['pilote'][0]}/dossiers/FR-INCONNU/correction", headers=actif["prof"],
                       json={"mode": "fin_du_quiz"})
        assert r.status_code == 404

    def test_hors_pilote_et_dossier_ferme(self, client, actif):
        noe = actif["hors_pilote"][1]
        r = client.post(f"/francais/eleve/dossiers/{CODE}/corriger", headers=noe, json={"reponses": [0, 1, 0]})
        assert r.status_code == 403
        assert client.delete(f"/francais/dossiers/{CODE}/classes/{actif['pilote'][0]}", headers=actif["prof"]).status_code == 200
        r = client.post(f"/francais/eleve/dossiers/{CODE}/quiz/0", headers=actif["pilote"][1], json={"reponse": 0})
        assert r.status_code == 404


# --- Auto-évaluation -----------------------------------------------------------------------------------------------

def test_auto_evaluation(client, actif):
    h = actif["pilote"][1]
    route = f"/francais/eleve/dossiers/{CODE}/auto-evaluation"
    assert client.put(route, headers=h, json={"niveaux": ["autonome"]}).status_code == 422
    assert client.put(route, headers=h, json={"niveaux": ["autonome", "inconnu"]}).status_code == 422
    assert client.put(route, headers=h, json={"niveaux": ["autonome", "avec_aide"]}).status_code == 200
    assert client.get(f"/francais/eleve/dossiers/{CODE}", headers=h).json()["auto_evaluation"] == ["autonome", "avec_aide"]


# --- Progression de la classe --------------------------------------------------------------------------------------

def test_progression_de_la_classe(client, actif):
    h, classe = actif["pilote"][1], actif["pilote"][0]
    client.post(f"/francais/eleve/dossiers/{CODE}/corriger", headers=h, json={"reponses": [0, 1, 1]})
    client.put(f"/francais/eleve/dossiers/{CODE}/auto-evaluation", headers=h, json={"niveaux": ["en_cours", "autonome"]})
    r = client.get(f"/francais/classes/{classe}/progression", headers=actif["prof"])
    assert r.status_code == 200 and r.headers["cache-control"] == "private, no-store"
    corps = r.json()
    assert corps["dossiers"] == [{"code": CODE, "titre": _brut()["titre"], "nb_quiz": 3, "je_sais": JE_SAIS}]
    [lina] = corps["eleves"]
    assert lina["prenom"] == "Lina" and lina["dossiers"][CODE] == {
        "score": 2, "premier_score": 2, "total": 3, "tentatives": 1, "auto_evaluation": ["en_cours", "autonome"],
        "a_relire": 0, "relues": 0}
    classes = {c["id"]: c for c in client.get("/francais/classes", headers=actif["prof"]).json()}
    assert set(classes) == {classe, actif["hors_pilote"][0]}
    assert classes[classe]["dossiers"] == [{"code": CODE, "titre": _brut()["titre"]}] and classes[classe]["acces_eleves"]
    # Un autre professeur ne voit pas la classe ; l'administrateur la voit.
    _, autre = _creer(client, actif["admin"], "autre3@pkp.test", [{"role": "professeur", "domaine": DOMAINE, "niveau": "3e"}])
    assert client.get(f"/francais/classes/{classe}/progression", headers=autre).status_code == 404
    admin = connecter_enseignant(client, email="admin@pkp.test")
    assert client.get(f"/francais/classes/{classe}/progression", headers=admin).status_code == 200


# --- Réponses rédigées (RGPD-2) -------------------------------------------------------------------------------------

TEXTE = "Le narrateur est inquiet : il hésite devant la porte (ligne 3). REPONSE-TEMOIN"


class TestReponsesRedigees:
    def test_fermees_par_defaut(self, client, actif):
        h = actif["pilote"][1]
        assert client.put(f"/francais/eleve/dossiers/{CODE}/reponses/Q1", headers=h, json={"texte": "x"}).status_code == 403
        assert client.get(f"/francais/classes/{actif['pilote'][0]}/reponses", headers=actif["prof"]).status_code == 403
        assert client.get(f"/francais/eleve/dossiers/{CODE}", headers=h).json()["saisie_ouverte"] is False

    def test_brouillon_remise_retour_reecriture(self, client, actif, monkeypatch, session):
        monkeypatch.setattr(settings, "redaction_active", True)
        h, classe, prof = actif["pilote"][1], actif["pilote"][0], actif["prof"]
        route = f"/francais/eleve/dossiers/{CODE}/reponses/Q1"
        assert client.put(f"/francais/eleve/dossiers/{CODE}/reponses/Z9", headers=h, json={"texte": "x"}).status_code == 404
        assert client.post(f"{route}/remise", headers=h).status_code == 409  # rien d'écrit
        assert client.put(route, headers=h, json={"texte": TEXTE}).json()["statut"] == "brouillon"
        # Brouillon : invisible du professeur.
        assert client.get(f"/francais/classes/{classe}/reponses", headers=prof).json() == []
        assert client.post(f"{route}/remise", headers=h).json()["statut"] == "remise"
        assert client.put(route, headers=h, json={"texte": "modif"}).status_code == 409
        [ligne] = client.get(f"/francais/classes/{classe}/reponses", headers=prof).json()
        assert (ligne["prenom"], ligne["question"], ligne["texte"]) == ("Lina", "Q1", TEXTE)
        assert client.get(f"/francais/classes/{classe}/progression", headers=prof).json()["eleves"][0]["dossiers"][CODE]["a_relire"] == 1
        # L'administrateur et un autre professeur n'accèdent pas aux textes (RGPD-2).
        admin = connecter_enseignant(client, email="admin@pkp.test")
        assert client.get(f"/francais/classes/{classe}/reponses", headers=admin).status_code == 404
        assert client.put(f"/francais/reponses/{ligne['id']}/retour", headers=admin, json={"commentaire": "x"}).status_code == 404
        r = client.put(f"/francais/reponses/{ligne['id']}/retour", headers=prof, json={"commentaire": "Cite la ligne exacte."})
        assert r.status_code == 200 and r.json()["statut"] == "corrigee"
        vue = client.get(f"/francais/eleve/dossiers/{CODE}", headers=h).json()["reponses"]
        assert [(x["statut"], x["commentaire"]) for x in vue] == [("corrigee", "Cite la ligne exacte.")]
        # Réécriture après le retour, puis nouvelle remise.
        assert client.put(route, headers=h, json={"texte": TEXTE + " (ligne 4)"}).json()["statut"] == "brouillon"
        assert client.post(f"{route}/remise", headers=h).json()["statut"] == "remise"
        # Aucun texte d'élève ni commentaire dans le journal.
        journal = client.get("/admin/journal?objet=reponse_redigee_francais", headers=actif["admin"]).text
        assert "REPONSE-TEMOIN" not in journal and "Cite la ligne" not in journal

    def test_export_et_purge(self, client, actif, monkeypatch, session):
        monkeypatch.setattr(settings, "redaction_active", True)
        h = actif["pilote"][1]
        client.put(f"/francais/eleve/dossiers/{CODE}/reponses/Q2", headers=h, json={"texte": TEXTE})
        client.post(f"/francais/eleve/dossiers/{CODE}/corriger", headers=h, json={"reponses": [0, 1, 0]})
        r = session.scalar(select(models.ReponseRedigeeFrancais))
        eleve = session.get(models.Eleve, r.eleve_id)
        from app.progression import export_eleve

        export = export_eleve(session, eleve).body.decode()
        assert "REPONSE-TEMOIN" in export and '"meilleur_score": 3' in export.replace(":3", ": 3")
        fin = r.conserver_jusqu_au
        assert purge.purger_redactions(session, datetime(fin.year, 8, 31, tzinfo=UTC)) == 0
        assert purge.purger_redactions(session, datetime(fin.year, 9, 1, tzinfo=UTC)) == 1
        session.commit()
        assert session.scalar(select(func.count(models.ReponseRedigeeFrancais.id))) == 0


# --- Édition par l'administrateur ---------------------------------------------------------------------------------

class TestEdition:
    def test_brouillon_soumission_puis_validation_par_un_autre(self, client, actif):
        admin = connecter_enseignant(client, email="admin@pkp.test")
        source = client.get(f"/francais/dossiers/{CODE}/source", headers=admin).json()["source"]
        assert [q["question"] for q in source["quiz"]] == [q["question"] for q in QUIZ] and source["code"] == CODE
        modifie = copy.deepcopy(source)
        modifie["quiz"][0]["explication"] = "Le narrateur raconte : ce n'est pas forcément l'auteur."
        assert client.put(f"/francais/dossiers/{CODE}/brouillon", headers=actif["prof"], json=modifie).status_code == 403
        assert client.put(f"/francais/dossiers/{CODE}/brouillon", headers=admin, json={**modifie, "code": "FR3-AUTRE"}).status_code == 422
        invalide = copy.deepcopy(modifie)
        invalide["quiz"][0]["reponse"] = 7
        assert client.put(f"/francais/dossiers/{CODE}/brouillon", headers=admin, json=invalide).status_code == 422
        assert client.put(f"/francais/dossiers/{CODE}/brouillon", headers=admin, json=source).status_code == 409  # identique
        r = client.put(f"/francais/dossiers/{CODE}/brouillon", headers=admin, json=modifie)
        assert r.status_code == 200 and (r.json()["version"], r.json()["statut"], r.json()["version_validee"]) == (3, "brouillon", 2)
        # Le brouillon ne remplace pas la version diffusée.
        lina = actif["pilote"][1]
        assert client.get(f"/francais/eleve/dossiers/{CODE}", headers=lina).json()["version"] == 2
        assert client.post(f"/francais/dossiers/{CODE}/soumettre", headers=admin).json()["statut"] == "soumis"
        assert client.post(f"/francais/dossiers/{CODE}/soumettre", headers=admin).status_code == 409
        assert client.post(f"/francais/validation/{CODE}/valider", headers=admin).status_code == 409  # son propre contenu
        assert client.post(f"/francais/validation/{CODE}/valider", headers=actif["val"]).status_code == 200
        r = client.post(f"/francais/eleve/dossiers/{CODE}/quiz/0", headers=lina, json={"reponse": 0})
        assert "forcément l'auteur" in r.json()["explication"]
        actions = [e["action"] for e in client.get("/admin/journal?objet=dossier_francais", headers=actif["admin"]).json()["elements"]]
        assert {"modifier", "soumettre"} <= set(actions)


# --- PDF ---------------------------------------------------------------------------------------------------------

def _aplatir(flux):
    for f in flux:
        yield from (_aplatir(f._content) if hasattr(f, "_content") else [f])


def test_pdf_eleve_sans_reponse_du_quiz(actif, fabrique):
    from app import francais_pdf

    with fabrique() as s:
        v = s.scalar(select(models.DossierFrancais)).validee
        eleve = " ".join(getattr(p, "text", "") for p in _aplatir(francais_pdf._partie_eleve(francais.vue_eleve(v))))
        prof = " ".join(getattr(p, "text", "") for p in _aplatir(francais_pdf._partie_professeur(francais.vue_professeur(v))))
    assert "Qui raconte" in eleve and "EXPLICATION-TEMOIN" not in eleve
    assert "EXPLICATION-TEMOIN" in prof
