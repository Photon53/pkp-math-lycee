"""Droits d'accès et isolement des données (#17) : chaque espace refuse les autres jetons, et un compte
n'atteint jamais les identifiants d'un autre compte du même rôle.

Deux familles de contrôles :
- matrice des rôles : chaque route protégée de l'API (lue dans le schéma OpenAPI, donc toute nouvelle route
  est couverte d'office) refuse l'appel sans jeton et avec le jeton de tout rôle qui n'est pas le sien ;
- isolement horizontal : professeur contre professeur, élève contre élève, famille contre famille, en
  substituant les identifiants de l'autre compte dans les routes.

Les appels attendus en refus n'ont pas d'effet : une seule base suffit pour toute la matrice.
"""
# Issue #17 — Tester les droits d'accès et l'isolement des données (Claude)

import base64
import re

import pytest
from sqlalchemy import select

from app.db import models
from app.db.seed import EMAIL_ANGLAIS_DEMO
from app.main import app
from tests.conftest import connecter_admin, connecter_eleve, connecter_enseignant, entete
from tests.test_parents import connecter_parent

REFUS = {401, 403}
REFUS_OU_INTROUVABLE = {401, 403, 404}
# Le compte de service IA est bloqué (429) après des échecs d'authentification répétés : c'est aussi un refus.
REFUS_MATRICE = REFUS | {429}
MDP = "mot-de-passe-de-test-2026"

# Rôles dont le jeton est fabriqué par `acteurs`. « prof_francais » n'en fait pas partie : aucune des routes
# /francais n'est ouverte aux comptes de démo, ce qui est vérifié ici.
ROLES = ("eleve", "eleve_anglais", "enfant", "parent", "prof_maths", "prof_anglais", "admin")

# Espace de chaque route : la première expression qui correspond au chemin s'applique. Une route qui ne
# correspond à aucune ligne fait échouer `test_chaque_route_protegee_a_un_espace_declare` : il faut la classer.
ESPACES: list[tuple[str, set[str]]] = [
    (r"^/eleves/", {"eleve"}),
    (r"^/seances", {"eleve"}),
    (r"^/cours", {"eleve"}),
    (r"^/anglais/eleve/", {"eleve_anglais"}),
    (r"^/enfants/moi", {"enfant"}),
    (r"^/parents/", {"parent"}),
    (r"^/enseignants/mot-de-passe$", {"prof_maths", "prof_anglais"}),
    (r"^/enseignants/", {"prof_maths"}),
    (r"^/anglais/", {"prof_anglais"}),
    (r"^/francais/", {"prof_francais"}),
    (r"^/admin/", {"admin"}),
    # Même fichier ouvert depuis trois espaces ; la visibilité fine est testée plus bas.
    (r"^/ressources/", {"eleve", "prof_maths", "admin"}),
    # Fiches de cours et corrigés : lecture multi-rôles, filtrée par chapitre ou niveau (routes/pkp_math.py).
    (r"^/pkp-math/", {"eleve", "enfant", "parent", "prof_maths", "admin"}),
    # Remarques et signalements (routes/remarques.py) : tout compte connecté, quel que soit son espace.
    (r"^/remarques", set(ROLES)),
    # Prévalidation IA (routes/prevalidation_ia.py) : jeton du compte de service, aucun compte de démo.
    (r"^/service-ia/", {"service_ia"}),
]

VALEURS_FICTIVES = {"code": "x", "public": "eleve", "niveau": "2nde", "parcours": "tronc-commun"}


def routes_protegees() -> list[tuple[str, str]]:
    return [
        (methode.upper(), chemin)
        for chemin, operations in app.openapi()["paths"].items()
        for methode, op in operations.items()
        if op.get("security")
    ]


def espace(chemin: str) -> set[str] | None:
    return next((roles for motif, roles in ESPACES if re.search(motif, chemin)), None)


def remplir(chemin: str, valeurs: dict[str, object]) -> str:
    return re.sub(r"\{(\w+)\}", lambda m: str(valeurs.get(m.group(1), 1)), chemin)


# Corps valides des routes testées en isolement horizontal. Indispensable : la validation du corps (422) passe
# avant le contrôle de propriétaire, si bien qu'un corps vide ne prouverait rien.
CORPS: dict[tuple[str, str], dict] = {
    ("POST", "/enseignants/classes/{classe_id}/eleves"): {"prenoms": ["Intrus"]},
    ("PUT", "/enseignants/classes/{classe_id}/chapitres"): {"chapitre_ids": []},
    ("PATCH", "/enseignants/eleves/{eleve_id}"): {"prenom": "Renomme"},
    ("POST", "/enseignants/eleves/{eleve_id}/parents"): {"email": "intrus@exemple.fr"},
    ("POST", "/enseignants/classes/{classe_id}/enfants"): {"enfant_ids": [1]},
    ("PATCH", "/anglais/groupes/{groupe_id}"): {"nom": "Renomme"},
    ("PATCH", "/anglais/groupes/{groupe_id}/eleves/{eleve_id}"): {"prenom": "Renomme"},
    ("POST", "/anglais/groupes/{groupe_id}/eleves"): {"prenoms": ["Intrus"]},
    ("POST", "/anglais/groupes/{groupe_id}/enfants"): {"enfant_ids": [1]},
    ("PUT", "/anglais/groupes/{groupe_id}/correction"): {"mode": "fin_du_quiz"},
    ("PUT", "/anglais/groupes/{groupe_id}/seances/{code}/correction"): {"mode": "fin_du_quiz"},
    ("POST", "/enseignants/demandes/{demande_id}"): {"statut": "resolue"},
    ("POST", "/remarques"): {"categorie": "bug", "description": "Remarque de test", "anonyme": False},
}


def appeler(client, methode: str, url: str, h: dict | None = None, corps: dict | None = None):
    if corps is None and methode in ("POST", "PUT", "PATCH"):
        corps = {}
    return client.request(methode, url, headers=h or {}, json=corps)


def tenter(client, methode: str, chemin: str, valeurs: dict, h: dict):
    """Appel d'un intrus avec un corps valide ; les fichiers sont envoyés en multipart."""
    url = remplir(chemin, valeurs)
    if chemin.endswith("/fichier") and methode == "PUT":
        return client.put(url, headers=h, files={"fichier": ("a.pdf", b"%PDF-1.4 intrus", "application/pdf")})
    corps = CORPS.get((methode, chemin))
    if corps is None and (methode, chemin) in {("POST", "/enseignants/eleves/{eleve_id}/liens")}:
        corps = {"eleve_id": valeurs.get("autre_eleve_id", 1)}
    if corps is None and (methode, chemin) == ("POST", "/enseignants/ressources/{ressource_id}"):
        corps = valeurs.get("corps_ressource")
    return appeler(client, methode, url, h, corps)


def creer_enseignant(client, admin, email: str, habilitations: list[dict]) -> dict[str, str]:
    r = client.post("/admin/enseignants", headers=admin, json={
        "nom": email.split("@")[0], "email": email, "role": "enseignant", "habilitations": habilitations,
    })
    assert r.status_code == 201, r.text
    provisoire = r.json()["mot_de_passe_provisoire"]
    jeton = client.post("/enseignants/connexion", json={"email": email, "mot_de_passe": provisoire}).json()["jeton"]
    r = client.post("/enseignants/mot-de-passe", headers=entete(jeton), json={"actuel": provisoire, "nouveau": MDP})
    assert r.status_code == 200, r.text
    return entete(r.json()["jeton"])


def creer_famille(client, admin, email: str, prenom: str, niveau: str = "2nde") -> dict:
    r = client.post("/admin/familles", headers=admin, json={"email": email, "enfants": [{"prenom": prenom, "niveau": niveau}]})
    assert r.status_code == 201, r.text
    return r.json()


def connecter_carte(client, carte: dict, route: str = "/enfants/connexion") -> dict[str, str]:
    r = client.post(route, json={"identifiant": carte["identifiant"], "code_personnel": carte["code"]})
    assert r.status_code == 200, r.text
    return entete(r.json()["jeton"])


def connecter_famille(client, famille: dict, email: str) -> dict[str, str]:
    provisoire = famille["mot_de_passe_provisoire"]
    jeton = client.post("/parents/connexion", json={"email": email, "mot_de_passe": provisoire}).json()["jeton"]
    r = client.post("/parents/mot-de-passe", headers=entete(jeton), json={"actuel": provisoire, "nouveau": MDP})
    assert r.status_code == 200, r.text
    return entete(r.json()["jeton"])


@pytest.fixture
def acteurs(client) -> dict[str, dict[str, str]]:
    """Un jeton valide de chaque rôle."""
    admin = connecter_admin(client)
    anglais = connecter_enseignant(client, email=EMAIL_ANGLAIS_DEMO)
    gid = client.post("/anglais/groupes", headers=anglais, json={"nom": "Groupe test", "niveau": "4e"}).json()["id"]
    carte_anglais = client.post(f"/anglais/groupes/{gid}/eleves", headers=anglais, json={"prenoms": ["Zoé"]}).json()["crees"][0]
    famille = creer_famille(client, admin, "famille.a@exemple.fr", "Noé", "4e")
    return {
        "eleve": connecter_eleve(client),
        "eleve_anglais": connecter_carte(client, carte_anglais, "/anglais/eleve/connexion"),
        "enfant": connecter_carte(client, famille["cartes"][0]),
        "parent": connecter_parent(client),
        "prof_maths": connecter_enseignant(client),
        "prof_anglais": anglais,
        "admin": admin,
    }


# --- Matrice des rôles ------------------------------------------------------------------------------------


def test_chaque_route_protegee_a_un_espace_declare():
    sans_espace = [f"{m} {c}" for m, c in routes_protegees() if espace(c) is None]
    assert not sans_espace, f"Routes à classer dans ESPACES : {sans_espace}"


def test_la_matrice_couvre_l_api():
    # Garde-fou : si le schéma OpenAPI cessait de déclarer la sécurité, la matrice ne testerait plus rien.
    assert len(routes_protegees()) > 150


def test_sans_jeton_toute_route_protegee_refuse(client):
    fuites = []
    for methode, chemin in routes_protegees():
        # Corps valide quand il est connu : sinon la validation (422) masquerait l'absence de contrôle du jeton.
        r = appeler(client, methode, remplir(chemin, VALEURS_FICTIVES), corps=CORPS.get((methode, chemin)))
        if r.status_code != 401:
            fuites.append(f"{methode} {chemin} → {r.status_code}")
    assert not fuites, fuites


def test_jeton_falsifie_refuse_partout(client, acteurs):
    """Un jeton dont on a changé le rôle (signature conservée) est refusé : la signature couvre le rôle."""
    charge, signature = acteurs["prof_maths"]["Authorization"].removeprefix("Bearer ").split(".")
    brut = base64.urlsafe_b64decode(charge + "=" * (-len(charge) % 4)).decode()
    falsifie = base64.urlsafe_b64encode(brut.replace("enseignant:", "admin:", 1).encode()).decode().rstrip("=")
    h = entete(f"{falsifie}.{signature}")
    fuites = [
        f"{m} {c} → {r.status_code}"
        for m, c in routes_protegees() if c.startswith("/admin/")
        if (r := appeler(client, m, remplir(c, VALEURS_FICTIVES), h)).status_code not in REFUS
    ]
    assert not fuites, fuites


def test_un_jeton_n_ouvre_que_son_espace(client, acteurs):
    fuites = []
    for methode, chemin in routes_protegees():
        autorises = espace(chemin) or set()
        url = remplir(chemin, VALEURS_FICTIVES)
        for role in ROLES:
            if role in autorises:
                continue
            r = appeler(client, methode, url, acteurs[role])
            if r.status_code not in REFUS_MATRICE:
                fuites.append(f"{role} : {methode} {chemin} → {r.status_code}")
    assert not fuites, "\n".join(fuites)


def test_les_comptes_d_un_espace_l_ouvrent_bien(client, acteurs):
    """Contre-épreuve : sans elle, une matrice où tout serait refusé passerait aussi."""
    for role, url in [
        ("eleve", "/eleves/moi"), ("eleve_anglais", "/anglais/eleve/moi"), ("enfant", "/enfants/moi"),
        ("parent", "/parents/enfants"), ("prof_maths", "/enseignants/classes"), ("prof_anglais", "/anglais/groupes"),
        ("admin", "/admin/moi"),
    ]:
        assert client.get(url, headers=acteurs[role]).status_code == 200, (role, url)


# --- Isolement horizontal : professeurs -----------------------------------------------------------------


@pytest.fixture
def prof_b(client) -> dict[str, str]:
    """Second professeur de maths du lycée, sans aucune classe."""
    return creer_enseignant(client, connecter_admin(client), "prof.b@pkp.test", [{"role": "professeur", "domaine": "maths-lycee"}])


@pytest.fixture
def donnees_prof_a(client, session) -> dict[str, object]:
    """Identifiants appartenant au professeur de démo (A) : classe, élève, parent, ressource."""
    h = connecter_enseignant(client)
    classe_id = next(c["id"] for c in client.get("/enseignants/classes", headers=h).json() if c["code"] == "2NDE-A-DEMO")
    lina = session.scalar(select(models.Eleve.id).where(models.Eleve.prenom == "Lina"))
    r = client.post(f"/enseignants/eleves/{lina}/parents", headers=h, json={"email": "parent.a@exemple.fr"})
    assert r.status_code == 201, r.text
    chapitre = client.get("/cours", headers=connecter_eleve(client)).json()[0]["id"]
    corps_ressource = {
        "type": "lien", "titre": "Lien de A", "url": "https://www.example.org/a", "chapitre_id": chapitre,
        "classe_ids": [classe_id],
    }
    r2 = client.post("/enseignants/ressources", headers=h, json=corps_ressource)
    assert r2.status_code == 201, r2.text
    yanis = session.scalar(select(models.Eleve.id).where(models.Eleve.prenom == "Yanis"))
    return {
        "classe_id": classe_id, "eleve_id": lina, "autre_eleve_id": yanis, "parent_id": r.json()["parent"]["id"],
        "ressource_id": r2.json()["id"], "corps_ressource": {**corps_ressource, "titre": "Modifié par B", "classe_ids": []},
    }


def test_un_professeur_n_atteint_aucune_donnee_d_un_autre(client, prof_b, donnees_prof_a):
    fuites = []
    for methode, chemin in routes_protegees():
        if not chemin.startswith("/enseignants/") or "{" not in chemin or "/cours/" in chemin:
            continue  # sans identifiant, ou contenu commun du programme (cours)
        r = tenter(client, methode, chemin, donnees_prof_a, prof_b)
        if r.status_code not in REFUS_OU_INTROUVABLE:
            fuites.append(f"{methode} {chemin} → {r.status_code}")
    assert not fuites, fuites
    # Les listes du professeur B ne contiennent rien de A.
    assert client.get("/enseignants/classes", headers=prof_b).json() == []
    assert "Lien de A" not in {x["titre"] for x in client.get("/enseignants/ressources", headers=prof_b).json()}


def test_les_donnees_de_a_restent_intactes_apres_les_tentatives(client, prof_b, donnees_prof_a):
    for methode, chemin in routes_protegees():
        if chemin.startswith("/enseignants/") and "{" in chemin and methode in ("DELETE", "PATCH", "PUT", "POST"):
            tenter(client, methode, chemin, donnees_prof_a, prof_b)
    h = connecter_enseignant(client)
    eleves = client.get(f"/enseignants/classes/{donnees_prof_a['classe_id']}/eleves", headers=h).json()
    assert "Lina" in {e["prenom"] for e in eleves}
    assert client.get(f"/enseignants/eleves/{donnees_prof_a['eleve_id']}/parents", headers=h).json()
    # Lina se connecte toujours avec son code : aucune régénération par B.
    connecter_eleve(client)


def test_un_professeur_d_anglais_n_atteint_pas_les_groupes_d_un_autre(client):
    admin = connecter_admin(client)
    a = connecter_enseignant(client, email=EMAIL_ANGLAIS_DEMO)
    b = creer_enseignant(client, admin, "anglais.b@pkp.test", [{"role": "professeur", "domaine": "anglais-college"}])
    gid = client.post("/anglais/groupes", headers=a, json={"nom": "Groupe de A", "niveau": "4e"}).json()["id"]
    eleve_id = client.post(f"/anglais/groupes/{gid}/eleves", headers=a, json={"prenoms": ["Zoé"]}).json()["groupe"]["eleves"][0]["id"]
    valeurs = {"groupe_id": gid, "eleve_id": eleve_id, "code": "4E-01"}
    fuites = [
        f"{m} {c} → {r.status_code}"
        for m, c in routes_protegees() if c.startswith("/anglais/groupes/{groupe_id}")
        if (r := tenter(client, m, c, valeurs, b)).status_code not in REFUS_OU_INTROUVABLE
    ]
    assert not fuites, fuites
    assert "Groupe de A" not in {g["nom"] for g in client.get("/anglais/groupes", headers=b).json()}
    assert [g["nom"] for g in client.get("/anglais/groupes", headers=a).json()] == ["Groupe de A"]


def test_une_ressource_limitee_a_une_classe_reste_invisible_aux_autres_classes(client, donnees_prof_a):
    rid = donnees_prof_a["ressource_id"]
    hugo = connecter_eleve(client, "Hugo", "1RE-B-DEMO")  # même professeur, autre classe
    assert client.get(f"/ressources/{rid}/fichier", headers=hugo).status_code == 404
    assert client.post(f"/ressources/{rid}/ouverture", headers=hugo).status_code == 404


# --- Isolement horizontal : élèves, enfants, familles ---------------------------------------------------


def test_un_eleve_n_utilise_pas_la_seance_d_un_camarade(client):
    yanis = connecter_eleve(client, "Yanis")
    r = client.post("/seances", headers=yanis)
    assert r.status_code == 201, r.text
    seance = r.json()["id"]
    question = client.get(f"/seances/{seance}/question", headers=yanis).json()["id"]
    lina = connecter_eleve(client)
    for methode, url, corps in [
        ("GET", f"/seances/{seance}/question", None),
        ("POST", f"/seances/{seance}/variante", {"question_id": question}),
        ("POST", f"/seances/{seance}/reponses", {"question_id": question, "reponse_donnee": "1"}),
        ("POST", f"/seances/{seance}/fin", None),
    ]:
        assert appeler(client, methode, url, lina, corps).status_code in REFUS_OU_INTROUVABLE, url
    # La séance de Yanis reste ouverte et sa question n'a pas reçu de réponse de Lina.
    assert client.get(f"/seances/{seance}/question", headers=yanis).json()["id"] == question
    assert client.get("/eleves/moi/historique", headers=yanis).json() == client.get(
        "/eleves/moi/historique", headers=connecter_eleve(client, "Yanis")
    ).json()


def test_un_eleve_ne_bascule_pas_sur_l_inscription_d_un_autre(client, session):
    yanis = session.scalar(select(models.Eleve.id).where(models.Eleve.prenom == "Yanis"))
    assert client.post(f"/eleves/moi/parcours/{yanis}", headers=connecter_eleve(client)).status_code in REFUS_OU_INTROUVABLE


def test_un_enfant_n_ouvre_pas_l_inscription_d_un_autre(client, session):
    admin = connecter_admin(client)
    enfant_a = connecter_carte(client, creer_famille(client, admin, "a@exemple.fr", "Inès")["cartes"][0])
    lina = session.scalar(select(models.Eleve.id).where(models.Eleve.prenom == "Lina"))
    assert client.post(f"/enfants/moi/maths/{lina}", headers=enfant_a).status_code in REFUS_OU_INTROUVABLE
    assert client.post(f"/enfants/moi/anglais/{lina}", headers=enfant_a).status_code in REFUS_OU_INTROUVABLE


def test_une_famille_n_atteint_pas_les_enfants_d_une_autre(client):
    admin = connecter_admin(client)
    fa = creer_famille(client, admin, "famille.a@exemple.fr", "Inès")
    fb = creer_famille(client, admin, "famille.b@exemple.fr", "Noé")
    parent_a = connecter_famille(client, fa, "famille.a@exemple.fr")
    enfant_b = fb["cartes"][0]["id"]
    assert client.get(f"/parents/famille/{enfant_b}", headers=parent_a).status_code in REFUS_OU_INTROUVABLE
    r = client.post(f"/parents/famille/{enfant_b}/acces", headers=parent_a, json={"code": "MATHS2026X"})
    assert r.status_code in REFUS_OU_INTROUVABLE, r.text
    assert [s["enfant"]["prenom"] for s in client.get("/parents/famille", headers=parent_a).json()] == ["Inès"]
    # La carte de B fonctionne toujours : A n'a pas pu renouveler son accès.
    connecter_carte(client, fb["cartes"][0])


# --- Corrigés PKP Math (ARCH-4, décision du propriétaire du 14/11/2026) ---------------------------------


def _fiche(client, h) -> dict[int, dict]:
    """Toutes les questions des fiches PKP Math visibles par ce jeton, par identifiant."""
    return {
        q["id"]: q
        for ch in client.get("/pkp-math/catalogue", headers=h).json()
        for c in client.get(f"/pkp-math/chapitres/{ch['id']}", headers=h).json()["competences"]
        for q in c["questions"]
    }


def test_l_eleve_ne_lit_le_corrige_qu_apres_sa_reponse(client):
    h = connecter_eleve(client, "Inès")  # aucune réponse dans les données de démo
    seance = client.post("/seances", headers=h).json()["id"]
    question = client.get(f"/seances/{seance}/question", headers=h).json()["id"]
    avant = _fiche(client, h)
    assert avant[question]["solution"] == "" and avant[question]["correction"] is None
    assert avant[question]["corrige_visible"] is False
    assert not any(q["solution"] or q["correction"] for q in avant.values())

    r = client.post(f"/seances/{seance}/reponses", headers=h, json={"question_id": question, "reponse_donnee": "0"})
    assert r.status_code == 200, r.text
    apres = _fiche(client, h)[question]
    assert apres["corrige_visible"] is True and apres["solution"]
    # Seule la question répondue est dévoilée.
    assert sum(q["corrige_visible"] for q in _fiche(client, h).values()) == 1


def test_les_adultes_lisent_tous_les_corriges(client):
    for h in (connecter_parent(client), connecter_enseignant(client)):
        fiche = _fiche(client, h)
        assert fiche and all(q["corrige_visible"] and q["solution"] for q in fiche.values())
