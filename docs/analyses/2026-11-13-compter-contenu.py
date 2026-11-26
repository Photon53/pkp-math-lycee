"""Annexe A — comptage du contenu pédagogique versionné (rapport d'analyse du 13/11/2026).

Périmètre : tous les fichiers `contenu/**/*.yaml` du dépôt.
Usage (depuis la racine du dépôt, PyYAML installé) :

    python docs/analyses/2026-11-13-compter-contenu.py

Sortie attendue au commit `78ecf3a` : 154 chapitres, 327 compétences,
1 776 questions déclarées dont 1 archivée (1 775 actives), 0 bloc `validation:`,
1 775 questions au champ `auteur: « Brouillon IA (Claude) »`.
"""

import collections
import glob
import json

import yaml

RACINE = "contenu"

chapitres = 0
competences = 0
questions = 0
archivees = 0
avec_validation = 0
auteurs = collections.Counter()

for chemin in sorted(glob.glob(f"{RACINE}/**/*.yaml", recursive=True)):
    with open(chemin, encoding="utf-8") as fichier:
        data = yaml.safe_load(fichier) or {}
    if "chapitre" in data:
        chapitres += 1
    for competence in data.get("competences") or []:
        competences += 1
        for question in competence.get("questions") or []:
            questions += 1
            if question.get("archivee"):
                archivees += 1
            auteurs[question.get("auteur", "(absent)")] += 1
            if "validation" in question:
                avec_validation += 1

print(json.dumps({
    "chapitres": chapitres,
    "competences": competences,
    "questions_declarees": questions,
    "questions_archivees": archivees,
    "questions_actives": questions - archivees,
    "avec_bloc_validation": avec_validation,
    "auteurs": auteurs.most_common(),
}, ensure_ascii=False, indent=2))
