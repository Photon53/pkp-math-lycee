#!/usr/bin/env python3
# Issue #80 — Reprise du code de Boussole dans PKP : remise de la marque PKP Éducation (Claude)
"""Remplace les textes visibles « Boussole » par ceux de PKP Éducation, après une copie du code de Boussole.

Usage, depuis la racine du dépôt : `python3 scripts/marque-pkp.py` (ajouter `--verifier` pour seulement lister
ce qui reste à remplacer, code de sortie 1 s'il reste quelque chose).

Le script est idempotent : on le relance après chaque synchronisation depuis Boussole. Il ne touche pas :
- aux identifiants techniques (`pkp`, `PKP_*`, format `boussole-francais-dossier/1` des dossiers de français) ;
- au sélecteur de variante `web/src/marque.js` et à ses tests : la variante PKP est choisie à la construction du
  front (`VITE_MARQUE=pkp`, voir `deploy/Dockerfile.web`) ;
- aux commentaires qui décrivent l'histoire du code.
"""
import argparse
import re
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent

DOSSIERS = ("api/app", "api/tests", "web/src")
EXTENSIONS = {".py", ".js", ".jsx"}

# Fichiers laissés tels quels : le sélecteur de variante et les tests qui vérifient les deux variantes.
EXCLUS = {
    "web/src/marque.js",
    "web/src/ui/Icone.jsx",
    # L'accueil public lit son préfixe dans marque.js (« Boussole Maths » ou « PKP Maths ») ; ses tests
    # vérifient la variante par défaut.
    "web/src/Accueil.jsx",
    "web/src/tests/accueil.test.jsx",
    "web/src/tests/accueils.test.jsx",
}

# Remplacements exacts, dans l'ordre (les plus précis d'abord).
REMPLACEMENTS = [
    ("Boussole Maths", "PKP Maths"),
    ("Boussole Anglais", "PKP Anglais"),
    ("Boussole Français", "PKP Français"),
    ("BOUSSOLE ANGLAIS", "PKP ANGLAIS"),
    ("BOUSSOLE · CARTE D'ACCÈS", "PKP ÉDUCATION · CARTE D'ACCÈS"),
    ("boussole-cartes-acces.pdf", "pkp-cartes-acces.pdf"),
    ("boussole-modele-professeurs.xlsx", "pkp-modele-professeurs.xlsx"),
    ("boussole-comptes-professeurs.csv", "pkp-comptes-professeurs.csv"),
    ("otpauth://totp/Boussole:{email}?secret={secret}&issuer=Boussole",
     "otpauth://totp/PKP%20%C3%89ducation:{email}?secret={secret}&issuer=PKP%20%C3%89ducation"),
    ('title="Boussole"', 'title="PKP Éducation"'),
    ('author="Boussole"', 'author="PKP Éducation"'),
    ('setAuthor("Boussole")', 'setAuthor("PKP Éducation")'),
    ('?? "Boussole"', '?? "PKP Éducation"'),
    ("Boussole <em>", "PKP <em>"),
    ("Dans Boussole,", "Dans PKP Éducation,"),
    ("dans Boussole.", "dans PKP Éducation."),
    ("l'équipe Boussole", "l'équipe PKP Éducation"),
    ("administrateurs de Boussole", "administrateurs de PKP Éducation"),
    ("bientôt sur Boussole", "bientôt sur PKP Éducation"),
    ("Ta carte Boussole", "Ta carte PKP Éducation"),
    ("Boussole vérifie chaque ligne", "PKP Éducation vérifie chaque ligne"),
    ("Boussole n'envoie aucun courriel", "PKP Éducation n'envoie aucun courriel"),
]

# Page HTML servie avant le chargement du front.
INDEX = "web/index.html"
INDEX_REMPLACEMENTS = [
    (re.compile(r"<title>[^<]*</title>"), "<title>PKP Éducation</title>"),
    (re.compile(r'content="Boussole( Maîtrise\+)? :'), 'content="PKP Éducation :'),
]

# Une mention restante n'est signalée que hors commentaire et hors identifiant technique.
RESTE = re.compile(r"Boussole|BOUSSOLE")
IGNORES = re.compile(r"boussole-francais-dossier|boussole\.test|Boussole Maîtrise\+")


def fichiers():
    for dossier in DOSSIERS:
        for chemin in sorted((RACINE / dossier).rglob("*")):
            relatif = chemin.relative_to(RACINE).as_posix()
            if chemin.suffix in EXTENSIONS and relatif not in EXCLUS and "node_modules" not in chemin.parts:
                yield chemin, relatif


def est_commentaire(ligne: str) -> bool:
    nette = ligne.strip()
    return nette.startswith(("#", "//", "*", "/*", '"""')) or nette.endswith('"""')


def appliquer() -> int:
    total = 0
    for chemin, relatif in fichiers():
        texte = chemin.read_text(encoding="utf-8")
        nouveau = texte
        for ancien, remplacant in REMPLACEMENTS:
            nouveau = nouveau.replace(ancien, remplacant)
        if nouveau != texte:
            chemin.write_text(nouveau, encoding="utf-8")
            total += 1
            print(f"modifié : {relatif}")
    index = RACINE / INDEX
    texte = index.read_text(encoding="utf-8")
    nouveau = texte
    for motif, remplacant in INDEX_REMPLACEMENTS:
        nouveau = motif.sub(remplacant, nouveau)
    if nouveau != texte:
        index.write_text(nouveau, encoding="utf-8")
        total += 1
        print(f"modifié : {INDEX}")
    return total


def restes() -> list[str]:
    trouves = []
    for chemin, relatif in fichiers():
        for numero, ligne in enumerate(chemin.read_text(encoding="utf-8").splitlines(), 1):
            code = re.split(r"\s#\s|\s//\s", ligne, maxsplit=1)[0]  # sans commentaire de fin de ligne
            if RESTE.search(code) and not est_commentaire(ligne) and not IGNORES.search(code):
                trouves.append(f"{relatif}:{numero}: {ligne.strip()}")
    return trouves


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--verifier", action="store_true", help="lister les mentions restantes sans rien modifier")
    args = parser.parse_args()
    if not args.verifier:
        print(f"{appliquer()} fichier(s) modifié(s).")
    reste = restes()
    for ligne in reste:
        print(f"reste : {ligne}")
    return 1 if args.verifier and reste else 0


if __name__ == "__main__":
    sys.exit(main())
