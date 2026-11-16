"""Dossiers de français en préparation (#98) : contrat, fidélité au dossier rédigé, import idempotent, accès réservés
aux adultes habilités, protection des corrigés, absence de correction automatique et non-régression maths/anglais."""
# Issue #98 — Intégration du premier dossier Français 3e en DEV (Claude)

import copy
import json
import re
from pathlib import Path

import pytest
from sqlalchemy import func, select

from app import francais
from app.db import models
from app.db.seed import EMAIL_ANGLAIS_DEMO
from app.main import app
from tests.conftest import connecter_admin, connecter_eleve, connecter_enseignant, entete
from tests.test_anglais_validation import _connecter_eleve as connecter_eleve_anglais
from tests.test_anglais_validation import _groupe_avec_eleve
from tests.test_lot_a_habilitations import _creer
from tests.test_parents import connecter_parent

RACINE = Path(__file__).resolve().parents[2]
FICHIER = RACINE / "contenu" / "francais" / "3e" / "fr3-dnb27-01-comprendre-un-texte.json"
SOURCES = RACINE / "docs" / "francais" / "3e-brevet-2027"
CODE = "FR3-DNB27-01"
DOMAINE = "francais-college"
ROUTES = [f"/francais/dossiers/{CODE}/{v}" for v in ("eleve", "professeur", "historique")] + ["/francais/dossiers"]


def _brut() -> dict:
    return json.loads(FICHIER.read_text(encoding="utf-8"))


def _ecrire(dossier: Path, donnees: dict) -> Path:
    (dossier / "3e").mkdir(parents=True, exist_ok=True)
    chemin = dossier / "3e" / "dossier.json"
    chemin.write_text(json.dumps(donnees, ensure_ascii=False), encoding="utf-8")
    return dossier


def _importer(fabrique, dossier: Path = francais.DOSSIER_PAR_DEFAUT, simulation: bool = False):
    with fabrique() as s:
        return francais.importer(s, francais.charger(dossier), simulation=simulation)


def _compter(fabrique) -> tuple[int, int]:
    with fabrique() as s:
        return (s.scalar(select(func.count(models.DossierFrancais.id))),
                s.scalar(select(func.count(models.DossierFrancaisVersion.id))))


def _corriges() -> list[str]:
    return [p for c in _brut()["professeur"]["corriges"] for p in c["paragraphes"]]


# --- Contrat et fidélité au dossier rédigé par Codex (PR #94) -------------------------------------------------

class TestContrat:
    def test_le_dossier_du_depot_est_valide(self):
        [charge] = francais.charger()
        f = charge.dossier
        assert (f.code, f.domaine, f.niveau) == (CODE, DOMAINE, "3e")
        assert [len(t.lignes) for t in f.eleve.textes] == [20, 5]
        assert [q.code for q in f.eleve.questions] == [f"Q{i}" for i in range(1, 9)] + ["T1", "T2", "T3"]
        assert [c.question for c in f.professeur.corriges] == [q.code for q in f.eleve.questions]

    def test_attribution_d_origine_et_d_integration(self):
        a = _brut()["attribution"]
        assert (a["redaction"], a["redaction_issue"], a["redaction_pr"]) == ("Codex", 55, 94)
        assert (a["integration"], a["integration_issue"]) == ("Claude", 98)
        assert _brut()["registre"]["adaptation"] == "originale"

    def test_chaque_texte_est_repris_mot_pour_mot_des_fiches_markdown(self):
        """Fidélité : tout texte du fichier figure tel quel dans les fiches élève ou professeur de la PR #94."""
        eleve = (SOURCES / "01-comprendre-un-texte-eleve.md").read_text(encoding="utf-8")
        prof = (SOURCES / "01-comprendre-un-texte-professeur.md").read_text(encoding="utf-8")
        d = _brut()
        for partie, source in ((d["eleve"], eleve), (d["professeur"], prof)):
            for texte in francais._textes(partie):
                if texte in ("entrainement", "transfert", "retour_humain") or re.fullmatch(r"[A-Z0-9-]{2,10}", texte):
                    continue  # codes et valeurs du contrat
                assert texte in source, texte[:80]
        for t in d["eleve"]["textes"]:
            for n, ligne in enumerate(t["lignes"], 1):
                assert f"[{n:02d}] {ligne}" in eleve
        for q in d["eleve"]["questions"][:8]:
            assert f"| {q['code']} | {q['difficulte_proposee']} | {q['consigne']} |" in eleve
        for q in d["eleve"]["questions"][8:]:
            assert f"{q['code']}. {q['consigne']}" in eleve
        for c in d["professeur"]["corriges"]:
            assert f"**{c['question']}." in prof

    def test_toutes_les_reponses_relevent_d_un_retour_humain(self):
        d = _brut()
        assert {q["reponse"]["mode"] for q in d["eleve"]["questions"]} == {"retour_humain"}
        cles = json.dumps(d)
        for interdit in ('"solution"', '"bareme"', '"points"', '"note"', '"mots_cles"', '"maitrise"'):
            assert interdit not in cles

    @pytest.mark.parametrize("modifier, message", [
        (lambda d: d["eleve"]["questions"][0].update(solution="un jardin"), "Extra inputs"),
        (lambda d: d["eleve"]["questions"][0]["reponse"].update(mode="automatique"), "retour_humain"),
        (lambda d: d["eleve"]["questions"][0].update(bareme=2), "Extra inputs"),
        (lambda d: d["professeur"]["corriges"].pop(), "question sans corrigé : T3"),
        (lambda d: d["eleve"]["consignes_questions"].append(d["professeur"]["corriges"][3]["paragraphes"][0]),
         "le corrigé de Q4 figure dans la partie élève"),
        (lambda d: d.update(domaine="maths-college"), "un dossier de français relève de"),
        (lambda d: d.update(niveau="Tle"), "niveau « Tle » absent de Français collège"),
        (lambda d: d["eleve"]["questions"][1].update(code="Q1"), "code de question en double : Q1"),
        (lambda d: d["eleve"]["questions"][0].update(texte="TEXTE-9"), "texte inconnu"),
    ])
    def test_le_contrat_refuse(self, tmp_path, modifier, message):
        d = _brut()
        modifier(d)
        with pytest.raises(francais.DossierInvalide) as exc:
            francais.charger(_ecrire(tmp_path, d))
        assert message in str(exc.value)

    def test_la_mise_en_forme_ne_change_pas_l_empreinte(self, tmp_path):
        [depot] = francais.charger()
        [compact] = francais.charger(_ecrire(tmp_path, _brut()))
        assert depot.empreinte == compact.empreinte


# --- Import idempotent --------------------------------------------------------------------------------------

class TestImport:
    def test_une_seconde_execution_ne_cree_aucun_doublon(self, fabrique):
        premier = _importer(fabrique)
        assert premier.crees == [CODE] and not premier.nouvelles_versions
        second = _importer(fabrique)
        assert second.inchanges == [CODE] and not second.crees and not second.nouvelles_versions
        assert _compter(fabrique) == (1, 1)
        with fabrique() as s:
            v = s.scalar(select(models.DossierFrancaisVersion))
            assert (v.numero, v.statut, v.auteur_id, v.validateur_id) == (1, "soumis", None, None)

    def test_la_simulation_n_ecrit_rien(self, fabrique):
        assert _importer(fabrique, simulation=True).crees == [CODE]
        assert _compter(fabrique) == (0, 0)

    def test_un_fichier_modifie_cree_une_seule_nouvelle_version(self, fabrique, tmp_path):
        _importer(fabrique)
        d = _brut()
        d["eleve"]["questions"][0]["coup_de_pouce"] = "Relis la ligne 5."
        dossier = _ecrire(tmp_path, d)
        assert _importer(fabrique, dossier).nouvelles_versions == [CODE]
        assert _importer(fabrique, dossier).inchanges == [CODE]
        assert _compter(fabrique) == (1, 2)
        # Revenir au fichier d'origine ne recrée pas la version 1 : son empreinte est déjà connue.
        assert _importer(fabrique).inchanges == [CODE]
        assert _compter(fabrique) == (1, 2)

    def test_l_import_ne_touche_ni_aux_domaines_ni_aux_maths_ni_a_l_anglais(self, fabrique):
        def etat():
            with fabrique() as s:
                return (
                    [(d.code, d.actif, d.public) for d in s.scalars(select(models.DomainePedagogique).order_by("code"))],
                    s.scalar(select(func.count(models.Question.id))), s.scalar(select(func.count(models.Chapitre.id))),
                    s.scalar(select(func.count(models.SeanceAnglaisVersion.id))),
                )
        avant = etat()
        _importer(fabrique)
        assert etat() == avant
        assert (DOMAINE, False, False) in avant[0]


# --- Accès : adultes habilités seulement, jamais d'élève -------------------------------------------------

def _activer(client, admin, domaine=DOMAINE, public=False):
    r = client.post(f"/admin/domaines/{domaine}", headers=admin, json={"actif": True, "public": public})
    return r


@pytest.fixture
def prepare(client, fabrique):
    """Dossier importé, Français collège activé pour l'équipe et toujours fermé au public."""
    _importer(fabrique)
    admin = connecter_admin(client)
    assert _activer(client, admin).status_code == 200
    return admin


class TestAcces:
    def test_domaine_inactif_personne_n_y_accede(self, client, fabrique):
        _importer(fabrique)
        admin_prof = connecter_enseignant(client, email="admin@pkp.test")
        assert client.get("/francais/dossiers", headers=admin_prof).status_code == 403

    def test_professeur_habilite_en_3e_consulte_le_dossier(self, client, prepare):
        _, h = _creer(client, prepare, "fr3@pkp.test", [{"role": "professeur", "domaine": DOMAINE, "niveau": "3e"}])
        [ligne] = client.get("/francais/dossiers", headers=h).json()
        assert (ligne["code"], ligne["statut"], ligne["version_validee"], ligne["visible_eleves"]) == (CODE, "soumis", None, False)
        assert ligne["attribution"]["redaction"] == "Codex" and ligne["peut_valider"] is False
        for route in ROUTES:
            r = client.get(route, headers=h)
            assert r.status_code == 200, route
            assert r.headers["cache-control"] == "private, no-store"

    def test_administrateur_consulte_sans_habilitation_francais(self, client, prepare):
        h = connecter_enseignant(client, email="admin@pkp.test")
        assert client.get(f"/francais/dossiers/{CODE}/professeur", headers=h).status_code == 200

    @pytest.mark.parametrize("email", ["demo@pkp.test", EMAIL_ANGLAIS_DEMO])
    def test_professeurs_de_maths_ou_d_anglais_refuses(self, client, prepare, email):
        h = connecter_enseignant(client, email=email)
        for route in ROUTES:
            assert client.get(route, headers=h).status_code == 403, route

    def test_habilitation_d_un_autre_niveau_ou_domaine(self, client, prepare):
        _, h6 = _creer(client, prepare, "fr6@pkp.test", [{"role": "professeur", "domaine": DOMAINE, "niveau": "6e"}])
        assert client.get("/francais/dossiers", headers=h6).json() == []
        assert client.get(f"/francais/dossiers/{CODE}/professeur", headers=h6).status_code == 404
        assert _activer(client, prepare, "francais-lycee").status_code == 200
        _, hl = _creer(client, prepare, "frl@pkp.test", [{"role": "validateur", "domaine": "francais-lycee"}])
        assert client.get("/francais/dossiers", headers=hl).json() == []
        assert client.get(f"/francais/dossiers/{CODE}/eleve", headers=hl).status_code == 404
        assert client.post(f"/francais/dossiers/{CODE}/valider", headers=hl).status_code == 404

    def test_eleves_enfants_et_parents_refuses(self, client, prepare):
        prof_anglais = connecter_enseignant(client, email=EMAIL_ANGLAIS_DEMO)
        _, carte = _groupe_avec_eleve(client, prof_anglais, niveau="3e")
        jetons = {
            "élève de maths": connecter_eleve(client),
            "élève d'anglais": connecter_eleve_anglais(client, carte),
            "parent": connecter_parent(client),
            "sans jeton": {},
        }
        for qui, h in jetons.items():
            for route in ROUTES:
                assert client.get(route, headers=h).status_code == 401, (qui, route)
            assert client.post(f"/francais/dossiers/{CODE}/valider", headers=h).status_code == 401, qui

    def test_jeton_d_administration_refuse(self, client, prepare):
        # Le jeton « admin » (30 min, second facteur) n'est pas un jeton de l'équipe pédagogique.
        assert client.get("/francais/dossiers", headers=prepare).status_code == 401


# --- Corrigés protégés, aucune correction automatique ------------------------------------------------------

class TestCorriges:
    def test_l_apercu_eleve_ne_contient_aucun_corrige(self, client, prepare):
        _, h = _creer(client, prepare, "fr3@pkp.test", [{"role": "professeur", "domaine": DOMAINE, "niveau": "3e"}])
        r = client.get(f"/francais/dossiers/{CODE}/eleve", headers=h)
        corps = r.text
        for p in _corriges():
            assert p not in corps
        eleve = r.json()["eleve"]
        assert "professeur" not in r.json() and "corriges" not in corps
        assert len(eleve["questions"]) == 11 and {q["retour"] for q in eleve["questions"]} == {"humain"}
        assert all(set(q) == {"code", "partie", "texte", "difficulte_proposee", "consigne", "coup_de_pouce", "retour"}
                   for q in eleve["questions"])

    def test_les_supports_professeur_contiennent_tous_les_corriges(self, client, prepare):
        _, h = _creer(client, prepare, "fr3@pkp.test", [{"role": "professeur", "domaine": DOMAINE, "niveau": "3e"}])
        corps = client.get(f"/francais/dossiers/{CODE}/professeur", headers=h).text
        for p in _corriges():
            assert json.dumps(p, ensure_ascii=False)[1:-1] in corps
        prof = json.loads(corps)["professeur"]
        assert [q["code"] for q in prof["questions"]] == [q["corrige"]["question"] for q in prof["questions"]]

    def test_aucune_route_ne_recoit_de_reponse_d_eleve(self):
        chemins = {c: m for c, m in app.openapi()["paths"].items() if c.startswith("/francais")}
        assert len(chemins) == 6
        ecritures = sorted(c for c, m in chemins.items() if set(m) & {"post", "put", "patch"})
        assert ecritures == ["/francais/dossiers/{code}/refuser", "/francais/dossiers/{code}/valider"]


# --- Circuit de validation : décision humaine, sans publication aux élèves ----------------------------------

class TestValidation:
    def test_seul_un_validateur_habilite_decide(self, client, prepare):
        _, prof = _creer(client, prepare, "fr3@pkp.test", [{"role": "professeur", "domaine": DOMAINE, "niveau": "3e"}])
        assert client.post(f"/francais/dossiers/{CODE}/valider", headers=prof).status_code == 403
        admin_prof = connecter_enseignant(client, email="admin@pkp.test")
        assert client.post(f"/francais/dossiers/{CODE}/valider", headers=admin_prof).status_code == 403

        _, val = _creer(client, prepare, "val@pkp.test", [{"role": "validateur", "domaine": DOMAINE, "niveau": "3e"}])
        assert client.get("/francais/dossiers", headers=val).json()[0]["peut_valider"] is True
        assert client.post(f"/francais/dossiers/{CODE}/refuser", headers=val, json={"motif": "  "}).status_code == 422
        r = client.post(f"/francais/dossiers/{CODE}/valider", headers=val)
        assert r.status_code == 200, r.text
        assert (r.json()["statut"], r.json()["version_validee"], r.json()["visible_eleves"]) == ("valide", 1, False)
        assert client.post(f"/francais/dossiers/{CODE}/valider", headers=val).status_code == 409
        journal = client.get("/admin/journal?objet=dossier_francais", headers=prepare).json()
        assert journal["total"] == 1 and journal["elements"][0]["action"] == "valider"

    def test_le_domaine_reste_impossible_a_ouvrir_au_public(self, client, prepare, fabrique):
        _, val = _creer(client, prepare, "val@pkp.test", [{"role": "validateur", "domaine": DOMAINE}])
        assert client.post(f"/francais/dossiers/{CODE}/valider", headers=val).status_code == 200
        # Un dossier validé ne compte pas comme contenu ouvert aux élèves : pas de module élève (V2-D12).
        assert _activer(client, prepare, public=True).status_code == 409
        etats = {d["code"]: d["etat"] for d in client.get("/domaines/publics").json()}
        assert etats[DOMAINE] == "en_preparation"

    def test_refus_motive_puis_nouvelle_version_a_relire(self, client, prepare, fabrique, tmp_path):
        _, val = _creer(client, prepare, "val@pkp.test", [{"role": "validateur", "domaine": DOMAINE}])
        r = client.post(f"/francais/dossiers/{CODE}/refuser", headers=val, json={"motif": "Vérifier la ligne 12."})
        assert (r.json()["statut"], r.json()["motif_refus"]) == ("refuse", "Vérifier la ligne 12.")
        d = copy.deepcopy(_brut())
        d["eleve"]["questions"][3]["coup_de_pouce"] = "Compare les lignes 2 et 12."
        assert _importer(fabrique, _ecrire(tmp_path, d)).nouvelles_versions == [CODE]
        histo = client.get(f"/francais/dossiers/{CODE}/historique", headers=val).json()
        assert [(v["numero"], v["statut"]) for v in histo] == [(2, "soumis"), (1, "refuse")]


# --- Non-régression maths et anglais ------------------------------------------------------------------------

def test_maths_et_anglais_inchanges_par_le_francais(client, fabrique):
    chiffres = client.get("/domaines/chiffres").json()
    admin = connecter_admin(client)
    domaines = client.get("/admin/domaines", headers=admin).json()
    _importer(fabrique)
    assert _activer(client, admin).status_code == 200
    assert client.get("/domaines/chiffres").json() == chiffres
    apres = {d["code"]: d for d in client.get("/admin/domaines", headers=admin).json()}
    for d in domaines:
        if d["code"] != DOMAINE:
            assert apres[d["code"]] == d
    assert apres[DOMAINE]["nb_contenus"] == 0 and apres[DOMAINE]["public"] is False
    # Les espaces existants fonctionnent toujours.
    assert client.get("/enseignants/classes", headers=connecter_enseignant(client)).status_code == 200
    assert client.get("/anglais/seances", headers=connecter_enseignant(client, email=EMAIL_ANGLAIS_DEMO)).status_code == 200
    h = connecter_eleve(client)
    assert client.get("/eleves/moi/chapitres", headers=h).status_code == 200
