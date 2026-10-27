import ast
from pathlib import Path

import pkp_engine
from pkp_engine import Question, TypeQuestion

INTERDITS = {"fastapi", "sqlalchemy", "requests", "httpx", "sqlite3"}


def test_api_publique_exposee():
    assert callable(pkp_engine.corriger)
    assert callable(pkp_engine.calculer_maitrise)
    assert callable(pkp_engine.choisir_prochaine_question)


def test_question_immuable():
    q = Question(1, 1, "2 + 2 ?", TypeQuestion.NUMERIQUE, "4", 1)
    assert q.archivee is False


def test_moteur_reste_pur():
    """Garde-fou d'architecture : aucune dépendance web ou BDD dans le moteur."""
    src = Path(pkp_engine.__file__).parent
    for fichier in src.glob("*.py"):
        for noeud in ast.walk(ast.parse(fichier.read_text(encoding="utf-8"))):
            if isinstance(noeud, ast.Import):
                modules = [a.name for a in noeud.names]
            elif isinstance(noeud, ast.ImportFrom):
                modules = [noeud.module or ""]
            else:
                continue
            for m in modules:
                assert m.split(".")[0] not in INTERDITS, f"{fichier.name} importe {m}"
