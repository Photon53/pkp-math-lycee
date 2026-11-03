"""Test de charge : une classe entière qui travaille en même temps.

Chaque élève virtuel se connecte, démarre une séance, puis enchaîne question -> réponse,
avec une courte pause de « réflexion ». Le script affiche les temps de réponse de l'API
(médiane, 95e centile, maximum) et les erreurs.

Les élèves sont créés dans une classe du professeur indiqué (prénoms « Charge … ») :
ne pas lancer sur la production. Usage, depuis `api/` avec l'API démarrée :

    python ../scripts/charge_classe.py --url http://localhost:8000 --eleves 35 --questions 15
"""

import argparse
import random
import statistics
import string
import threading
import time
from collections import defaultdict

import httpx


def prenoms(n: int) -> list[str]:
    """Prénoms uniquement en lettres (règle de validation des prénoms) : « Charge Aa », « Charge Ab »…"""
    return [f"Charge {string.ascii_uppercase[i // 26]}{string.ascii_lowercase[i % 26]}" for i in range(n)]


def preparer(url: str, email: str, mot_de_passe: str, classe_code: str, n: int) -> dict[str, str]:
    """Inscrit les élèves virtuels ; renvoie {prénom: code personnel}. Relancer régénère leurs codes."""
    with httpx.Client(base_url=url, timeout=30) as c:
        r = c.post("/enseignants/connexion", json={"email": email, "mot_de_passe": mot_de_passe})
        r.raise_for_status()
        h = {"Authorization": f"Bearer {r.json()['jeton']}"}
        classe = next(k for k in c.get("/enseignants/classes", headers=h).json() if k["code"] == classe_code.upper())
        r = c.post(f"/enseignants/classes/{classe['id']}/eleves", headers=h, json={"prenoms": prenoms(n)})
        r.raise_for_status()
        codes = {e["prenom"]: e["code"] for e in r.json()["crees"]}
        # Déjà inscrits lors d'un essai précédent : on leur donne un nouveau code.
        for e in c.get(f"/enseignants/classes/{classe['id']}/eleves", headers=h).json():
            if e["prenom"] in prenoms(n) and e["prenom"] not in codes:
                r = c.post(f"/enseignants/eleves/{e['id']}/code", headers=h)
                r.raise_for_status()
                codes[e["prenom"]] = r.json()["code"]
        return codes


class Mesures:
    def __init__(self):
        self.durees: dict[str, list[float]] = defaultdict(list)
        self.erreurs: list[str] = []
        self.verrou = threading.Lock()

    def noter(self, etape: str, debut: float, reponse: httpx.Response | None, erreur: str | None = None):
        with self.verrou:
            self.durees[etape].append((time.perf_counter() - debut) * 1000)
            if erreur or (reponse is not None and reponse.status_code >= 400):
                self.erreurs.append(f"{etape} : {erreur or reponse.status_code}")


def eleve(url: str, prenom: str, code: str, classe: str, nb_questions: int, pause: float, m: Mesures, depart: threading.Barrier):
    depart.wait()  # toute la classe se connecte au même moment, comme en début de cours
    t = time.perf_counter()
    try:
        _travailler(url, prenom, code, classe, nb_questions, pause, m)
    except httpx.HTTPError as exc:
        # Connexion coupée, délai dépassé… : comptée comme une erreur, pas un fil qui meurt en silence.
        m.noter("reseau", t, None, f"{type(exc).__name__} : {exc}")


def _travailler(url: str, prenom: str, code: str, classe: str, nb_questions: int, pause: float, m: Mesures):
    with httpx.Client(base_url=url, timeout=30) as c:
        t = time.perf_counter()
        r = c.post("/eleves/connexion", json={"prenom": prenom, "code_classe": classe, "code_personnel": code})
        m.noter("connexion", t, r)
        if r.status_code != 200:
            return
        h = {"Authorization": f"Bearer {r.json()['jeton']}"}
        t = time.perf_counter()
        r = c.post("/seances", headers=h)
        m.noter("seance", t, r)
        if r.status_code != 201:
            return
        seance = r.json()["id"]
        for _ in range(nb_questions):
            t = time.perf_counter()
            r = c.get(f"/seances/{seance}/question", headers=h)
            m.noter("question", t, r)
            if r.status_code != 200:
                return
            time.sleep(random.uniform(0, pause))
            t = time.perf_counter()
            r = c.post(f"/seances/{seance}/reponses", headers=h, json={"question_id": r.json()["id"], "reponse_donnee": "1"})
            m.noter("reponse", t, r)


def main():
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument("--url", default="http://localhost:8000")
    p.add_argument("--email", default="demo@pkp.test")
    p.add_argument("--mot-de-passe", default="demo-pkp-2026")
    p.add_argument("--classe", default="2NDE-A-DEMO")
    p.add_argument("--eleves", type=int, default=35)
    p.add_argument("--questions", type=int, default=15)
    p.add_argument("--pause", type=float, default=2.0, help="réflexion maximale entre question et réponse (s)")
    a = p.parse_args()

    codes = preparer(a.url, a.email, a.mot_de_passe, a.classe, a.eleves)
    m, depart = Mesures(), threading.Barrier(len(codes))
    fils = [
        threading.Thread(target=eleve, args=(a.url, prenom, code, a.classe, a.questions, a.pause, m, depart))
        for prenom, code in codes.items()
    ]
    debut = time.perf_counter()
    for f in fils:
        f.start()
    for f in fils:
        f.join()
    total = time.perf_counter() - debut

    print(f"{len(codes)} élèves, {a.questions} questions chacun, en {total:.1f} s")
    for etape, d in m.durees.items():
        d = sorted(d)
        p95 = d[min(len(d) - 1, int(len(d) * 0.95))]
        print(f"  {etape:<10} {len(d):>5} appels · médiane {statistics.median(d):6.0f} ms · p95 {p95:6.0f} ms · max {d[-1]:6.0f} ms")
    print(f"Erreurs : {len(m.erreurs)}" + (f" (ex. {m.erreurs[:3]})" if m.erreurs else ""))
    raise SystemExit(1 if m.erreurs else 0)


if __name__ == "__main__":
    main()
