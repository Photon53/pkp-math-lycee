"""« Mon cours » (issue #180) : les fiches et liens de la professeure suivent l'avancée du cours ; pendant le pilote,
le français n'accepte que des liens (décision du 19/11/2026), les PDF rouvrant par réglage après #4."""
# Issue #180 — Mon cours : fiches de la professeure au fil du cours (Claude)

from sqlalchemy import event, select

from app import config

from app.config import settings
from app.db import models
from tests import pdf_exemples
from tests.conftest import connecter_admin, connecter_eleve, connecter_enseignant
from tests.test_classes_pilotes import pilote  # noqa: F401  (fixture : classe pilote de Lina, classe révoquée de Noé)

PDF = pdf_exemples.ordinaire()


def _lien(client, pilote, **autres) -> dict:
    corps = {"type": "lien", "titre": "Tableau de conjugaison", "url": "https://fr.wikipedia.org/wiki/Conjugaison",
             "chapitre_id": pilote["chapitre"], "classe_ids": [pilote["classe"]], **autres}
    r = client.post("/enseignants/ressources", headers=connecter_enseignant(client), json=corps)
    assert r.status_code == 201, r.text
    return r.json()


def test_mon_cours_suit_l_avancee_du_cours(client, pilote):  # noqa: F811
    lien = _lien(client, pilote)
    cours = client.get("/cours/mon-cours", headers=pilote["lina"])
    assert cours.status_code == 200, cours.text
    assert [(c["id"], [r["id"] for r in c["ressources"]]) for c in cours.json()] == [(pilote["chapitre"], [lien["id"]])]
    assert cours.json()[0]["ressources"][0]["url"] == "https://fr.wikipedia.org/wiki/Conjugaison"
    # Une autre classe de français (révoquée) ne voit rien, même par cette route.
    assert client.get("/cours/mon-cours", headers=pilote["noe"]).json() == []
    # La professeure ferme le chapitre : il disparaît de « Mon cours » ; elle le rouvre : il revient.
    prof = connecter_enseignant(client)
    chemin = f"/enseignants/classes/{pilote['classe']}/chapitres"
    assert client.put(chemin, headers=prof, json={"chapitre_ids": []}).status_code == 200
    assert client.get("/cours/mon-cours", headers=pilote["lina"]).json() == []
    assert client.put(chemin, headers=prof, json={"chapitre_ids": [pilote["chapitre"]]}).status_code == 200
    assert len(client.get("/cours/mon-cours", headers=pilote["lina"]).json()) == 1


def test_un_eleve_d_une_autre_matiere_ne_voit_pas_le_lien(client, pilote):  # noqa: F811
    """Classe de maths de démonstration : ni « Mon cours » ni le cours ne servent le lien de la classe de français."""
    lien = _lien(client, pilote)
    maths = connecter_eleve(client)
    cours = client.get("/cours/mon-cours", headers=maths)
    assert cours.status_code == 200, cours.text
    assert pilote["chapitre"] not in {c["id"] for c in cours.json()}
    assert lien["id"] not in {r["id"] for c in cours.json() for r in c["ressources"]}
    assert client.get(f"/cours/{pilote['competence']}", headers=maths).status_code == 404


def test_un_lien_masque_ou_reserve_aux_enseignants_n_apparait_pas(client, pilote):  # noqa: F811
    _lien(client, pilote, public="enseignants")
    assert client.get("/cours/mon-cours", headers=pilote["lina"]).json()[0]["ressources"] == []


def test_pdf_refuse_en_francais_pendant_le_pilote(client, session, pilote, monkeypatch):  # noqa: F811
    prof = connecter_enseignant(client)
    pdf_fr = {"type": "pdf", "titre": "Fiche", "chapitre_id": pilote["chapitre"], "classe_ids": [pilote["classe"]],
              "droits_declares": True, "source": "Professeure de la classe", "licence": "CC BY 4.0"}
    refus = client.post("/enseignants/ressources", headers=prof, json=pdf_fr)
    assert refus.status_code == 403 and "liens" in refus.json()["detail"]
    # Destiné à une classe de français, même rattaché à un chapitre de maths : refusé aussi.
    maths = session.scalar(select(models.Chapitre).where(models.Chapitre.domaine_code == "maths-lycee"))
    assert client.post("/enseignants/ressources", headers=prof, json={**pdf_fr, "chapitre_id": maths.id}).status_code == 403
    # Les maths ne changent pas.
    classe_maths = session.scalar(select(models.Classe).where(models.Classe.code == "2NDE-A-DEMO"))
    cree = client.post("/enseignants/ressources", headers=prof, json={**pdf_fr, "chapitre_id": maths.id, "classe_ids": [classe_maths.id]})
    assert cree.status_code == 201, cree.text
    # Ressource commune de l'administrateur rattachée au français : refusée aussi.
    admin = connecter_admin(client)
    assert client.post("/admin/ressources", headers=admin, json={**pdf_fr, "classe_ids": []}).status_code == 403
    # Verrou technique : le réglage seul ne rouvre rien sans le contrôle renforcé des PDF (#4).
    monkeypatch.setattr(config, "CONTROLE_PDF_RENFORCE", False)
    monkeypatch.setattr(settings, "pdf_francais_ouvert", True)
    assert client.post("/enseignants/ressources", headers=prof, json=pdf_fr).status_code == 403
    # Avec #4 (verrou levé, valeur livrée), le réglage rouvre les PDF ; refermé, l'envoi du fichier est de nouveau refusé.
    monkeypatch.setattr(config, "CONTROLE_PDF_RENFORCE", True)
    cree = client.post("/enseignants/ressources", headers=prof, json=pdf_fr)
    assert cree.status_code == 201, cree.text
    monkeypatch.setattr(settings, "pdf_francais_ouvert", False)
    envoi = client.put(f"/enseignants/ressources/{cree.json()['id']}/fichier", headers={**prof, "Content-Type": "application/pdf"}, content=PDF)
    assert envoi.status_code == 403


def test_mon_cours_reserve_aux_eleves(client):
    assert client.get("/cours/mon-cours").status_code == 401
    assert client.get("/cours/mon-cours", headers=connecter_enseignant(client)).status_code in (401, 403)


def test_mon_cours_en_nombre_de_requetes_fixe(client, session, pilote):  # noqa: F811
    """Relecture de la PR #186 : le nombre de requêtes SQL ne dépend pas du nombre de ressources."""
    moteur = session.get_bind()

    def requetes() -> int:
        compte = []
        ecouteur = lambda *args: compte.append(1)  # noqa: E731
        event.listen(moteur, "before_cursor_execute", ecouteur)
        try:
            assert client.get("/cours/mon-cours", headers=pilote["lina"]).status_code == 200
        finally:
            event.remove(moteur, "before_cursor_execute", ecouteur)
        return len(compte)

    _lien(client, pilote)
    avec_une = requetes()
    for i in range(5):
        _lien(client, pilote, titre=f"Fiche {i}", url=f"https://fr.wikipedia.org/wiki/Conjugaison_{i}")
    assert len(client.get("/cours/mon-cours", headers=pilote["lina"]).json()[0]["ressources"]) == 6
    assert requetes() == avec_une
