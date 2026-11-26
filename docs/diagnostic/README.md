<!-- Issue #162 — Diagnostic des acquis antérieurs, note de cadrage (Claude) -->
# Diagnostic des acquis antérieurs

Suivi : issue #162. Statut : **banque importée et passation en place (lots 1 à 3), questions à relire par un
professeur**. Les fichiers sont rangés dans `contenu/<niveau>/diagnostic/`. Aucune question n'est montrée à un élève
tant qu'elle n'est pas validée et que le professeur n'a pas ouvert le diagnostic à sa classe (§ 8).

## 1. Objectif

Repérer, en début d'utilisation de Boussole, les acquis **des années précédentes** dont l'élève a besoin, sans
l'interroger sur des chapitres qu'il n'a pas encore étudiés. Un élève de 3e commence par les acquis de 4e ; en cas
de difficulté, on redescend vers la 5e puis la 6e.

| Classe de l'élève | Premier niveau interrogé | Retour possible |
|---|---|---|
| 6e | CM2 | CM1, puis cycle 2 |
| 5e | 6e | CM2 |
| 4e | 5e | 6e, puis CM2 |
| 3e | 4e | 5e, puis 6e |
| 2nde | 3e | 4e, puis plus ancien |
| 1re | 2nde | 3e, puis plus ancien |
| Terminale | socle + module de l'enseignement suivi en 1re | 2nde, puis plus ancien |

Le bilan se fait **par compétence**, jamais sous la forme « niveau de 5e ». Les observations du diagnostic restent
séparées du taux de maîtrise : une réussite isolée ne déclare pas une compétence maîtrisée.

## 2. Décisions du propriétaire (16/11/2026)

1. **Nature de chapitre « diagnostic »** (option B), distincte de `mise-a-niveau`, exemptée de la règle « cours +
   difficultés 1 à 5 » ; passation dédiée et bilan stocké à part du taux de maîtrise.
2. **Nouveau type `choix_multiples`** (plusieurs bonnes réponses), le type `qcm` étant conservé.
3. **Questions rédigées** (`redaction`) : corrigées dans l'interface par le professeur, ou sur papier après export
   PDF. L'élève répond par du texte ou **dépose une image ou un PDF**.

## 3. Quel programme interroger

Ce qui compte est le programme **que l'élève a suivi l'année précédente**, pas celui de l'année en cours. Pour
2026-2027 (`programme_prerequis` de chaque fichier) :

| Entrée en | Année précédente suivie en 2025-2026 sous | Code |
|---|---|---|
| 6e | **ancien** programme du cycle 3 (2015, consolidé en 2020) : l'arrêté du 10 avril 2025 n'applique le programme de 2025 au CM2 qu'à la rentrée 2026 | `cm2-2020` |
| 5e | programme du cycle 3 de 2025 (6e, en vigueur le 01/09/2025) | `6e-2025` |
| 4e | repères de 2020 (le programme de 5e de 2026 commence en 2026-2027) | `5e-2020` |
| 3e | repères de 2020 | `4e-2020` |
| 2nde | repères de 2020 | `3e-2020` |
| 1re | programme de 2nde de 2019 | `2nde-2019` |
| Terminale | programmes de 1re de 2019 | `1re-specialite-2019`, `1re-technologique-2019` |

En 2027-2028, l'entrée en 6e passera au programme du cycle 3 de 2025 et l'entrée en 4e, 1re et Terminale aux programmes de 2026 : il faudra une version de la
banque par programme, choisie selon l'année scolaire de passation. Les référentiels `5e-2020`, `2nde-2019` et
`1re-*-2019` ne sont pas dans `referentiels/` : les codes sont posés, les attendus ne sont pas encore rattachés.

## 4. Format des fichiers

Identique à `contenu/` (`docs/CONTENU.md`), avec :

```yaml
chapitre:
  code: 3E-DIAG-4E
  niveau: 3e
  nature: diagnostic                 # remplace `parcours` (déduit du premier public)
  programme_prerequis: 4e-2020       # programme suivi l'année précédente
  publics: [tronc-commun]            # parcours principaux des classes concernées
  ordre: 90                          # 90 et plus : pas de collision avec les chapitres d'entraînement
competences:
- code: 3E-DIAG-TRIANGLE
  prerequis: [4E-PYTHAGORE, 4E-THALES, 4E-COSINUS]   # chapitres où reprendre en cas de difficulté
  questions:
  - type: choix_multiples            # solution : lettres en ordre alphabétique, « AC »
  - type: redaction                  # solution : réponse attendue, pour le professeur
```

Chaque question rappelle en commentaire son identifiant de la banque initiale (`# 3E-08`).

## 5. Contenu de la banque

`publics` liste les **parcours de classe** (`app/referentiel.py`) qui reçoivent le questionnaire. Les classes
d'option (`mise-a-niveau`, `excellence`, `examens`) n'en reçoivent pas : l'élève passe le diagnostic dans sa classe
principale.

| Fichier | Niveau | `publics` | Questions | dont rédaction | dont choix multiples |
|---|---|---|---:|---:|---:|
| `6e/diagnostic/90-diagnostic-acquis-cm2.yaml` | 6e | `tronc-commun` | 18 | 3 | 0 |
| `5e/diagnostic/90-diagnostic-acquis-6e.yaml` | 5e | `tronc-commun` | 17 | 3 | 1 |
| `4e/diagnostic/90-diagnostic-acquis-5e.yaml` | 4e | `tronc-commun` | 20 | 1 | 1 |
| `3e/diagnostic/90-diagnostic-acquis-4e.yaml` | 3e | `tronc-commun` | 20 | 2 | 0 |
| `2nde/diagnostic/90-diagnostic-acquis-3e.yaml` | 2nde | `tronc-commun`, `professionnel` (tous viennent de 3e) | 20 | 1 | 0 |
| `1re/diagnostic/90-diagnostic-acquis-2nde.yaml` | 1re | `specialite`, `scientifique`, `technologique` (tous viennent de 2nde GT) | 20 | 1 | 0 |
| `tle/diagnostic/90-diagnostic-socle.yaml` | Tle | `specialite`, `complementaires`, `technologique` | 6 | 0 | 0 |
| `tle/diagnostic/91-diagnostic-module-specialite.yaml` | Tle | `specialite`, `complementaires` (spécialité suivie en 1re ; maths expertes : option de la classe de spécialité) | 6 | 0 | 0 |
| `tle/diagnostic/92-diagnostic-module-technologique.yaml` | Tle | `technologique` | 6 | 0 | 0 |
| **Total** | | **133** | **11** | **2** |

Toutes les questions sont vérifiées par `python -m app.contenu verifier` (solution lisible, corrigé cohérent,
prérequis existants, lettres des choix multiples, corrigé des rédactions).

## 6. Corrections apportées à la banque fusionnée (152 questions)

Vérifiées contre `referentiels/` et les calculs refaits.

**Hors du programme de l'année précédente** :

| ID | Problème | Traitement |
|---|---|---|
| 3E-14 | Réciproque de Thalès : programme de 3e (`3E-2020-GEOM-01`) | Déplacée en entrée en 2nde |
| 2N-13 | Systèmes d'équations : programme de 2nde | Retirée |
| 2N-14 | Inéquations : programme de 2nde | Remplacée par « 3 vérifie-t-il l'inégalité ? » |
| 4E-13, 4E-14, 4E-16 | Produit de relatifs, puissances, produit de fractions : 4e | Retirées (reprises à l'entrée en 3e) |
| 4E-R2 | $2/3 + 1/4$ : dénominateurs non multiples, 4e | Retirée |
| 4E-R6 | Médiane : 4e | Moyenne seulement |
| 5E-15 | Parallélogramme : 5e | Retirée (couvert par 4E-20) |
| 6E-12 | Produit de deux décimaux : 6e | Déplacée en entrée en 5e ; en 6e, « 0,4 × 10 » |

**Fausses, ambiguës ou mal posées** :

| ID | Problème | Traitement |
|---|---|---|
| 4E-15 | Deux bonnes réponses ($3/5 = 0{,}6$) | $3/5$ remplacé par $5/8$ |
| 1R-19 | Trois valeurs ne prouvent pas un zéro unique | Énoncé reformulé |
| 3E-20 | « Combien de graduations… » mal posée | Retirée |
| 6E-16, 5E-13 | Pas de lecture réelle de droite graduée | Abscisse d'un point à lire |

**Doublons** : 2N-08 / 3E-13 et 2N-09 / 3E-15 (valeurs changées en 2nde, tangente au lieu de cosinus) ; 1R-14 /
MC-02 et 1R-20 / TE-06 (valeurs changées).

**Terminale** : les élèves de maths complémentaires ont suivi la spécialité en 1re ; ils reçoivent le module
spécialité. Le module MC-01 à MC-06 ne correspond à aucun parcours de 1re : il n'est pas transcrit ; il pourrait
servir aux élèves de 1re sans spécialité (à décider).

## 7. Règles appliquées par le code (lot 2)

| Règle | Où |
|---|---|
| `choix_multiples` : ensemble exact des lettres cochées, ordre indifférent, aucun crédit partiel ; le `qcm` reste à une seule lettre | `pkp_engine/correction.py` |
| `redaction` : jamais corrigée par le moteur (`CorrectionHumaineRequise`) ; observation « en attente de correction » jusqu'à la décision du professeur de la classe | `pkp_engine/correction.py`, `api/app/diagnostic.py` |
| Les deux types sont réservés aux chapitres de diagnostic (fichiers et interface d'administration) | `api/app/contenu.py`, `routes/admin_contenu.py` |
| Exemption « cours + difficultés 1 à 5 » : chapitres de nature `diagnostic` seulement | `contenu.inventaire` |
| Non-diffusion : un chapitre de diagnostic n'est ni proposé au professeur pour ses classes, ni servi en séance, ni montré aux élèves, enfants et parents (`/pkp-math`), ni compté sur la page publique | `progression.filtre_apprentissage`, `routes/eleves.py`, `routes/pkp_math.py`, `routes/domaines.py` |
| Diffusion du diagnostic : questions **validées** seulement, quel que soit `PKP_SERVIR_QUESTIONS_NON_VALIDEES`, et seulement au niveau et aux `publics` du chapitre | `diagnostic.questions_diffusables` |
| Observations dans `observation_diagnostic`, jamais dans `reponse` : le taux de maîtrise, l'historique et le suivi n'en tiennent pas compte ; elles figurent dans l'export RGPD de l'élève | migration `0040`, `progression.export_eleve` |

Tests : `api/tests/test_diagnostic.py`, `engine/tests/test_types_diagnostic.py`.

## 8. Passation (lot 3)

| Règle | Où |
|---|---|
| Le professeur ouvre ou ferme le diagnostic de sa classe (fermé par défaut) ; fermer interrompt les passations, qui reprennent à la réouverture | `Classe.diagnostic_ouvert`, `PUT /enseignants/classes/{id}/diagnostic` |
| Une passation par inscription ; elle se reprend tant qu'elle n'est pas terminée | `PassationDiagnostic` (migration `0041`) |
| Une question à la fois, choisie et mémorisée par le serveur ; ni solution, ni difficulté, ni verdict renvoyés à l'élève | `GET /eleves/moi/diagnostic/question`, `POST /eleves/moi/diagnostic/reponses` |
| « Je ne sais pas » enregistré comme tel (statut `je-ne-sais-pas`, réponse vide) ; une réponse vide est refusée | `diagnostic.enregistrer_observation` |
| Choix de la question : difficulté 2 d'abord ; après une réussite, égale ou plus difficile ; deux réussites closent la notion ; après un échec ou « Je ne sais pas », deux relances dont une plus simple ; 4 questions au plus par notion, 45 par passation | `pkp_engine/diagnostic.py` |
| Une notion « à reprendre » (au moins deux échecs, aucune réussite) ouvre ses compétences de `retour` (diagnostic du niveau précédent) avant la notion suivante ; seules leurs questions validées sont servies | champ `retour` des fichiers, `diagnostic.plan` |
| Durée de chaque réponse mesurée côté serveur, sans limite de temps imposée | `ObservationDiagnostic.duree_s` |

**Choix par défaut à confirmer par le propriétaire** : ouverture par le professeur ; une seule passation par élève
(pas de nouvelle passation après la fin) ; descente seulement pour une notion « à reprendre » (pas pour une notion aux
résultats partagés) ; seuils ci-dessus. Les `retour` de la banque sont une proposition (même notion, niveau
précédent) à relire avec la banque.

## 9. Lots suivants

- **Lot 4, rédaction** : dépôt d'image ou de PDF, correction dans l'interface (`corriger_observation`), export PDF.
- **Lot 5, bilan** par compétence ; inclure les observations dans les archives de classe.
- Modifier une question de diagnostic se fait dans les fichiers : l'interface d'administration refuse les deux types
  nouveaux.

## 10. Limites connues

- Pas de figure : les questions « graphique » (5E-16, 2N-18…) donnent les données en texte. Les figures demandent
  une prise en charge des images dans l'énoncé.
- Une seule variante par question : les trois variantes (gabarits `gabarit:` à valeurs tirées) viendront ensuite.
- Difficultés à recalibrer après le pilote ; **aucune question n'est validée pédagogiquement**.
- Dépôt d'images ou de PDF par l'élève (lot 4) : durée de conservation et accès à décider au titre du RGPD.
