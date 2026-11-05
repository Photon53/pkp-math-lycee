"""Mesure de l'import en masse (V3, Lot 0) : 500 élèves fictifs, avec le vrai coût de hachage des mots de passe.

Crée une base SQLite temporaire migrée (jamais la production), génère un classeur de N lignes
(familles de deux enfants, un second responsable une fois sur deux), puis chronomètre la vérification
et l'import. Usage, depuis `api/` :

    python ../scripts/mesure_import.py --lignes 500
"""

import argparse
import shutil
import tempfile
import time
from io import BytesIO
from pathlib import Path

from alembic import command
from alembic.config import Config
from openpyxl import load_workbook
from sqlalchemy.orm import sessionmaker

RACINE_API = Path(__file__).resolve().parent.parent / "api"
NIVEAUX = ["6e", "5e", "4e", "3e", "2nde", "1re", "Tle"]
LETTRES = "abcdefghijklmnopqrstuvwxyz"


def nom(i: int) -> str:
    """Prénoms et noms uniquement en lettres : Aa, Ab, … (règle de validation)."""
    return LETTRES[i // 26 % 26].upper() + LETTRES[i % 26] + LETTRES[i // 676 % 26]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--lignes", type=int, default=500)
    args = parser.parse_args()

    from app import import_familles
    from app.db.session import creer_moteur

    dossier = Path(tempfile.mkdtemp(prefix="pkp-mesure-"))
    try:
        url = f"sqlite:///{dossier / 'mesure.db'}"
        config = Config(str(RACINE_API / "alembic.ini"))
        config.set_main_option("sqlalchemy.url", url)
        config.attributes["configure_logger"] = False
        command.upgrade(config, "head")
        moteur = creer_moteur(url)
        Session = sessionmaker(bind=moteur, expire_on_commit=False)

        with Session() as session:
            classeur = load_workbook(BytesIO(import_familles.modele(session)))
        feuille = classeur[import_familles.FEUILLE]
        for i in range(args.lignes):
            famille = i // 2
            feuille.append([
                f"Eleve{nom(i)}", f"Famille{nom(famille)}", NIVEAUX[i % len(NIVEAUX)],
                f"parent{famille}@mesure.test", f"second{famille}@mesure.test" if famille % 2 else None, None, None,
            ])
        flux = BytesIO()
        classeur.save(flux)
        contenu = flux.getvalue()
        familles = (args.lignes + 1) // 2
        print(f"{args.lignes} lignes, {familles} familles, {familles + familles // 2} comptes responsables à créer")

        with Session() as session:
            t0 = time.perf_counter()
            rapport = import_familles.importer(session, contenu, simulation=True)
            t1 = time.perf_counter()
        print(f"Vérification : {t1 - t0:.1f} s")
        with Session() as session:
            t2 = time.perf_counter()
            rapport = import_familles.importer(session, contenu, simulation=False)
            t3 = time.perf_counter()
        resume = {k: v for k, v in rapport.model_dump().items() if not isinstance(v, list)}
        print(f"Import : {t3 - t2:.1f} s — {resume}")
        print(f"Total : {t3 - t0:.1f} s (objectif < 120 s)")
        moteur.dispose()
    finally:
        shutil.rmtree(dossier, ignore_errors=True)


if __name__ == "__main__":
    main()
