"""Fiabilité des tableaux de bord (#16) : sur des scénarios connus, les chiffres affichés au professeur, à l'élève
et au parent sont exactement ceux des réponses enregistrées, et l'absence de données se distingue d'un zéro.

Scénario : une nouvelle classe de 2nde et trois élèves sur une même compétence.
- Ana ne travaille pas ;
- Bilal répond juste 5 fois de suite (compétence maîtrisée), puis faux une fois ;
- Chloé répond faux une fois et abandonne sa séance sans la terminer.
"""
# Issue #16 — Vérifier la fiabilité des tableaux de bord professeur (Claude)

import pytest
from pkp_engine.maitrise import DECROISSANCE, POIDS_A_PRIORI, SEUIL_MAITRISE

from app import exemplaires
from app.db import models
from tests.conftest import connecter_enseignant, entete

NOUVEAU_MDP = "un-mot-de-passe-solide"


def maitrise_attendue(sequence: list[bool]) -> float:
    """Recalcul indépendant de la maîtrise (ARCH-5), de la plus ancienne à la plus récente réponse."""
    recentes = list(reversed(sequence[-10:]))
    poids = [DECROISSANCE**rang for rang in range(len(recentes))]
    return sum(p for p, ok in zip(poids, recentes, strict=True) if ok) / (sum(poids) + POIDS_A_PRIORI)


class Classe:
    """Classe de test pilotée par l'API, avec des réponses justes ou fausses choisies à l'avance."""

    def __init__(self, client, fabrique):
        self.client, self.fabrique = client, fabrique
        self.prof = connecter_enseignant(client)
        r = client.post("/enseignants/classes", headers=self.prof, json={"niveau": "2nde", "parcours": "tronc-commun"})
        assert r.status_code == 201, r.text
        self.id, self.code = r.json()["id"], r.json()["code"]
        r = client.post(f"/enseignants/classes/{self.id}/eleves", headers=self.prof, json={"prenoms": ["Ana", "Bilal", "Chloé"]})
        assert r.status_code == 201, r.text
        self.codes = {e["prenom"]: e["code"] for e in r.json()["crees"]}
        self.ids = {e["prenom"]: e["id"] for e in self.resumes()}
        self.jetons = {p: self._connecter(p) for p in self.codes}
        self.competence = self._competence_numerique()

    def _connecter(self, prenom: str) -> dict[str, str]:
        r = self.client.post("/eleves/connexion", json={"prenom": prenom, "code_classe": self.code, "code_personnel": self.codes[prenom]})
        assert r.status_code == 200, r.text
        return entete(r.json()["jeton"])

    def _competence_numerique(self) -> int:
        """Première compétence ouverte dont toutes les questions servables sont numériques (réponse fausse sûre)."""
        with self.fabrique() as s:
            ouverts = sorted(s.get(models.Classe, self.id).chapitres_proposes, key=lambda ch: ch.ordre)
            for chapitre in ouverts:
                for c in sorted(chapitre.competences, key=lambda c: c.ordre):
                    questions = [q for q in c.questions if not q.archivee]
                    if not c.masque and len(questions) >= 3 and all(q.type.value == "numerique" for q in questions):
                        return c.id
        pytest.skip("Aucune compétence entièrement numérique ouverte en 2nde.")

    def resumes(self) -> list[dict]:
        r = self.client.get(f"/enseignants/classes/{self.id}/eleves", headers=self.prof)
        assert r.status_code == 200, r.text
        return r.json()

    def resume(self, prenom: str) -> dict:
        return next(e for e in self.resumes() if e["prenom"] == prenom)

    def progression(self, prenom: str) -> dict[int, dict]:
        r = self.client.get(f"/enseignants/eleves/{self.ids[prenom]}/progression", headers=self.prof)
        return {p["competence_id"]: p for p in r.json()}

    def seance(self, prenom: str) -> int:
        r = self.client.post("/seances", headers=self.jetons[prenom], json={"competence_ids": [self.competence]})
        assert r.status_code == 201, r.text
        return r.json()["id"]

    def repondre(self, prenom: str, seance: int, juste: bool) -> None:
        h = self.jetons[prenom]
        question = self.client.get(f"/seances/{seance}/question", headers=h).json()
        with self.fabrique() as s:
            q = s.get(models.Question, question["id"])
            bonne = exemplaires.solution(q, s.get(models.Seance, seance).tirage_courant)
        r = self.client.post(f"/seances/{seance}/reponses", headers=h,
                             json={"question_id": question["id"], "reponse_donnee": bonne if juste else f"{bonne}1"})
        assert r.status_code == 200, r.text
        assert r.json()["correcte"] is juste, (bonne, r.json())


@pytest.fixture
def classe(client, fabrique) -> Classe:
    c = Classe(client, fabrique)
    s = c.seance("Bilal")
    for juste in [True] * 5 + [False]:
        c.repondre("Bilal", s, juste)
    c.client.post(f"/seances/{s}/fin", headers=c.jetons["Bilal"])
    c.repondre("Chloé", c.seance("Chloé"), False)  # séance laissée ouverte
    return c


SEQUENCE_BILAL = [True] * 5 + [False]


def test_liste_de_classe_fidele_aux_reponses(classe):
    ana, bilal, chloe = (classe.resume(p) for p in ("Ana", "Bilal", "Chloé"))
    total = ana["competences_total"]
    assert total > 0 and bilal["competences_total"] == chloe["competences_total"] == total
    # Aucune réponse : taux absent (affiché « — »), jamais 0 %.
    assert (ana["nb_reponses"], ana["taux_reussite"], ana["competences_maitrisees"]) == (0, None, 0)
    assert (bilal["nb_reponses"], bilal["taux_reussite"]) == (6, pytest.approx(5 / 6))
    # Une seule réponse fausse, séance non terminée : comptée, et 0 % (pas « — »).
    assert (chloe["nb_reponses"], chloe["taux_reussite"], chloe["competences_maitrisees"]) == (1, 0.0, 0)


def test_la_maitrise_suit_l_ordre_des_reponses(classe):
    """5 justes puis 1 faute : la maîtrise retombe sous le seuil ; elle était atteinte juste avant."""
    assert maitrise_attendue([True] * 5) >= SEUIL_MAITRISE > maitrise_attendue(SEQUENCE_BILAL)
    p = classe.progression("Bilal")[classe.competence]
    assert p["nb_reponses"] == 6
    assert p["maitrise"] == pytest.approx(maitrise_attendue(SEQUENCE_BILAL))
    assert p["maitrisee"] is False and classe.resume("Bilal")["competences_maitrisees"] == 0
    # Une bonne réponse de plus : la maîtrise repasse le seuil, et la liste de classe le compte.
    s = classe.seance("Bilal")
    classe.repondre("Bilal", s, True)
    p = classe.progression("Bilal")[classe.competence]
    assert p["maitrise"] == pytest.approx(maitrise_attendue([*SEQUENCE_BILAL, True]))
    assert p["maitrisee"] is (maitrise_attendue([*SEQUENCE_BILAL, True]) >= SEUIL_MAITRISE)
    assert classe.resume("Bilal")["competences_maitrisees"] == int(p["maitrisee"])


def test_competences_non_travaillees_sans_ambiguite(classe):
    for prenom in ("Ana", "Bilal", "Chloé"):
        for cid, p in classe.progression(prenom).items():
            if p["nb_reponses"] == 0:
                assert (p["maitrise"], p["maitrisee"]) == (0.0, False), (prenom, cid)
    assert all(p["nb_reponses"] == 0 for p in classe.progression("Ana").values())


def test_historique_du_professeur(classe):
    h = classe.prof
    page = classe.client.get(f"/enseignants/eleves/{classe.ids['Bilal']}/historique", headers=h).json()
    assert (page["total"], page["erreurs"]) == (6, 1)
    # Du plus récent au plus ancien : la faute est en tête.
    assert [e["correcte"] for e in page["elements"]] == list(reversed(SEQUENCE_BILAL))
    assert all(e["competence_id"] == classe.competence for e in page["elements"])
    erreurs = classe.client.get(f"/enseignants/eleves/{classe.ids['Bilal']}/historique", headers=h, params={"erreurs": True}).json()
    assert [e["correcte"] for e in erreurs["elements"]] == [False] and erreurs["total"] == 6
    vide = classe.client.get(f"/enseignants/eleves/{classe.ids['Ana']}/historique", headers=h).json()
    assert (vide["total"], vide["erreurs"], vide["elements"]) == (0, 0, [])


def test_professeur_eleve_et_parent_voient_les_memes_chiffres(classe):
    c, prenom = classe.client, "Bilal"
    eleve = c.get("/eleves/moi/progression", headers=classe.jetons[prenom]).json()
    assert {p["competence_id"]: p for p in eleve} == classe.progression(prenom)
    r = c.post(f"/enseignants/eleves/{classe.ids[prenom]}/parents", headers=classe.prof, json={"email": "parent.bilal@exemple.fr"})
    provisoire = r.json()["mot_de_passe_provisoire"]
    jeton = c.post("/parents/connexion", json={"email": "parent.bilal@exemple.fr", "mot_de_passe": provisoire}).json()["jeton"]
    parent = entete(c.post("/parents/mot-de-passe", headers=entete(jeton), json={"actuel": provisoire, "nouveau": NOUVEAU_MDP}).json()["jeton"])
    tableau = c.get(f"/parents/enfants/{classe.ids[prenom]}", headers=parent).json()
    prof = classe.resume(prenom)
    for champ in ("nb_reponses", "taux_reussite", "competences_maitrisees", "competences_total"):
        assert tableau["enfant"][champ] == prof[champ], champ
    assert {p["competence_id"]: p for p in tableau["progression"]} == classe.progression(prenom)
    assert sum(j["nb_reponses"] for j in tableau["activite"]) == 6 and tableau["seances_30_jours"] == 1
    assert sum(ch["competences_total"] for ch in tableau["chapitres"]) == prof["competences_total"]


def test_fermer_un_chapitre_retire_ses_competences_sans_effacer_l_historique(classe):
    c = classe.client
    chapitres = c.get(f"/enseignants/classes/{classe.id}/chapitres", headers=classe.prof).json()
    with classe.fabrique() as s:
        chapitre_travaille = s.get(models.Competence, classe.competence).chapitre_id
    garder = [ch["id"] for ch in chapitres if ch["propose"] and ch["id"] != chapitre_travaille]
    r = c.put(f"/enseignants/classes/{classe.id}/chapitres", headers=classe.prof, json={"chapitre_ids": garder})
    assert r.status_code == 200, r.text
    bilal = classe.resume("Bilal")
    assert classe.competence not in classe.progression("Bilal")
    # Les réponses déjà données restent comptées et consultables dans l'historique.
    assert bilal["nb_reponses"] == 6 and bilal["taux_reussite"] == pytest.approx(5 / 6)
    page = c.get(f"/enseignants/eleves/{classe.ids['Bilal']}/historique", headers=classe.prof).json()
    assert page["total"] == 6
