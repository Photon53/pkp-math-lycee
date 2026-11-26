# Analyse du projet `Photon53/boussole-maitrise-plus`

**Version 2.1 — corrigée le 13 novembre 2026** après la contre-revue puis la revue complémentaire publiées sur l'issue #80.
**Commit analysé :** `78ecf3a` (`main`) · **branche de référence pour l'intégration :** `develop` @ `d728659`
**Nature :** analyse statique. Aucune exécution applicative complète, aucune base déployée, aucun accès GCP ou VM.

> Cette version remplace la version 1. Les corrections apportées sont listées au § 0 et explicitées dans le corps du texte. Les affirmations qui restent des **opinions** sont signalées comme telles.

---

## 0. Corrections apportées à la version 1

| # | Version 1 | Version 2 (corrigée) |
|---|---|---|
| 1 | « Licence UNLICENSE : bloquant, le produit n'est pas vendable » | L'UNLICENSE **autorise** la vente. Le sujet est la **politique de licences** (code, contenus, marque) et la protection contre la réutilisation, pas une interdiction (§ 5.1) |
| 2 | Analyse présentée comme celle du dépôt | Analyse de **`main` @ `78ecf3a`** ; `develop` est **39 commits en avance** sur des fichiers d'infrastructure/CI uniquement (§ 1.1) |
| 3 | « 0 question validée sur 1 775 » | Chiffre établi sur les **YAML versionnés**, pas sur une base déployée ; comptage reproductible fourni (§ 3.2) |
| 4 | « passer `PKP_SERVIR_QUESTIONS_NON_VALIDEES` à `false` chapitre par chapitre » | Cette variable est **globale** ; le mécanisme par compétence est `validees_en_priorite()` (§ 5.2) |
| 5 | Correctif SSRF : « ouvrir sans `HTTPRedirectHandler` » | **Faux** : `build_opener()` réinstalle les gestionnaires par défaut. Correctif reformulé (§ 5.5) |
| 6 | « 860 lignes » pour `admin.py` | **1 016 lignes physiques**, dont 860 non vides (§ 5.6) |
| 7 | « 8 tables + leçon » | **25 classes de tables** dans `models.py` ; le chiffre 8 est historique (§ 3.1) |
| 8 | Notes « sécurité 8/10 », « documentation 10/10 », « très au-dessus de la moyenne » | Supprimées : ce sont des appréciations, pas des mesures (§ 2) |
| 9 | Empreinte SHA-256 unique | Deuxempreintes distinguées et statut de vérification du commit précisé (§ 8) |
| 10 | Jeton GitHub : « risque de fuite » implicite | Vérifié : **le jeton n'est ni versionné ni présent dans le dépôt** (§ 8.3) |

Corrections de la **revue complémentaire** (version 2.1) :

| # | Version 2 | Version 2.1 |
|---|---|---|
| 11 | « Toutes des brouillons IA, aucune validation » | **« Aucune validation n'est enregistrée dans les YAML examinés »** ; le champ `auteur` ne prouve ni l'absence de relecture ailleurs, ni la qualité (§ 3.2, § 5.2) |
| 12 | Comptage décrit mais non reproductible | **Script joint en annexe A**, avec commande, périmètre et sortie attendue |
| 13 | « Sessions et limitation (#5, #7) si plusieurs instances » | #5 (révocation) traitée **indépendamment** de la topologie ; #7 dépend de la topologie (§ 7) |
| 14 | Conventions de lignes mélangées dans un même tableau | **Tous les tableaux donnent physiques et non vides** (`models.py` : 744 / 594 ; `admin.py` : 1 016 / 860) (§ 1.3, § 3.1, § 5.6) |
| 15 | Licence en tête des priorités | **Réordonné** : sécurité, sauvegardes, sessions, périmètre pédagogique d'abord ; licence en décision parallèle (§ 7) |

---

## 1. Périmètre, méthode et limites

### 1.1 Ce qui a été analysé — et ce qui ne l'a pas été

| | |
|---|---|
| Référentiel | clone de `main` au commit `78ecf3a` (10/11/2026) |
| Écart avec `develop` | `develop` @ `d728659` : **39 commits d'avance, 1 de retard** |
| Fichiers différents entre `main` et `develop` | **18**, tous dans `.github/`, `infrastructure/`, `scripts/`, `docs/` |
| Fichiers applicatifs modifiés | **aucun** (`api/`, `engine/`, `web/`, `contenu/`, `referentiels/` identiques) |

Conséquence : les constats sur le **code applicatif** restent valables pour `develop`. Les constats sur l'**exploitation, la CI/CD et l'infrastructure** doivent être lus sur `develop`, où des travaux sont en cours (#65, #72) — sans que ce code préparé vaille validation sur VM.

### 1.2 Ce qui n'a pas été vérifié

- Aucun test de l'API ni du front n'a été exécuté dans cette session (voir § 6.1).
- Aucune instance applicative démarrée, aucune base de données interrogée.
- Aucun accès GCP, VM, ni vérification de configuration de production.
- Aucun scan de sécurité (bandit, semgrep, gitleaks) relancé : les résultats cités sont ceux de `docs/audit/preuves/`, produits antérieurement.

### 1.3 Convention de comptage

Chaque tableau de volumes donne **deux colonnes** : lignes **physiques** (nombre de `\n`, ligne finale comprise) et lignes **non vides** (après suppression des lignes blanches). Les deux valeurs ne sont pas interchangeables : pour `api/app/db/models.py`, 744 physiques correspondent à 594 non vides.

La version 1 mélangeait les deux conventions dans un même tableau ; les chiffres ci-dessous ont été recalculés avec la même méthode pour chaque fichier.

---

## 2. Ce que cette analyse établit — et ce qu'elle n'établit pas

**Établi** (vérifiable par relecture du code et comptages reproductibles) :

- la séparation en trois couches et l'absence de dépendance du moteur vers le web ou la base ;
- les propriétés de sécurité du code d'authentification et de hachage (§ 4) ;
- les volumes : fichiers, routes, migrations, tests, contenu (§ 3) ;
- l'absence de certains motifs dangereux (`eval`, `exec`, `subprocess`, `console.log`) ;
- le résultat des tests du moteur, exécutés ici (§ 6.1) ;
- l'état du contenu pédagogique versionné (§ 3.2).

**Non établi** :

- la qualité pédagogique réelle des questions ;
- la conformité RGPD en exploitation ;
- la tenue en charge, la sécurité opérationnelle de l'infrastructure ;
- un jugement comparatif de maturité : cette analyse ne dispose d'aucune population de comparaison, donc **aucune note chiffrée n'est produite**.

---

## 3. Architecture et inventaire

```
web/ (React 18 + Vite)  ──HTTP/JSON──▶  api/ (FastAPI)  ──▶  PostgreSQL / SQLite
                                          │
                                          └──▶  engine/ (Python pur)
```

### 3.1 Volumes mesurés

| Élément | Fichiers | Lignes physiques | Lignes non vides | Où |
|---|--:|--:|--:|---|
| Dépôt (suivi par Git) | **615** | — | — | 15,1 Mo |
| Moteur | 18 | 1 492 | 1 174 | `engine/` |
| API (applicatif) | 53 | 12 456 | 10 064 | `api/app/` |
| API (tests) | 33 | 5 114 | 4 218 | `api/tests/` |
| Front | 78 | 14 996 | 14 064 | `web/src/` |
| Documentation | 25 | — | ~3 750 | `docs/` |
| Routes HTTP | — | — | **204** décorateurs dans **18** modules | `api/app/routes/` |
| Migrations | **31** | — | — | `api/migrations/versions/` |
| Classes de tables | — | — | **25** | `api/app/db/models.py` (`__tablename__`) |

Le chiffre « 8 tables + `lecon` » qui figure dans `docs/ARCHITECTURE.md` décrit l'état initial du projet ; le modèle en compte aujourd'hui 25, hors tables d'association.

### 3.2 Contenu pédagogique — comptage direct des fichiers

Comptage reproductible par lecture des YAML (`contenu/**/*.yaml`), indépendamment du fichier `docs/CONTENU-INVENTAIRE.md` :

| Mesure | Valeur |
|---|---|
| Fichiers / chapitres | 154 |
| Compétences | 327 |
| Questions déclarées | **1 776** |
| Questions archivées (`archivee: true`) | 1 |
| Questions actives | **1 775** |
| Questions portant un bloc `validation:` | **0** |
| Auteur déclaré | « Brouillon IA (Claude) » pour 1 775 ; 1 question sans auteur (l'archivée) |

Deux constats en découlent :

1. **Aucune validation n'est enregistrée dans les YAML examinés.** Les 1 775 questions actives portent le champ `auteur: « Brouillon IA (Claude) »`, et aucune ne comporte de bloc `validation:`. Ce constat porte sur **le contenu versionné au commit `78ecf3a`**, pas sur une base déployée.
2. Le champ `auteur` ne prouve ni qu'une relecture n'a pas eu lieu ailleurs (base, document externe, séance de classe), ni que les questions sont de mauvaise qualité. Il établit seulement qu'**aucune trace de relecture n'est versionnée avec elles**.

Le chiffre « 0 validée » doit donc être rapproché des validations saisies dans une base déployée avant toute conclusion commerciale. La commande et le script de comptage sont fournis en annexe (§ A).

---

## 4. Sécurité : propriétés vérifiées dans le code

Ces points sont des **constats de lecture**, pas un audit de sécurité.

| Propriété | Mise en œuvre | Fichier |
|---|---|---|
| Hachage des mots de passe | scrypt N=2¹⁷, r=8, p=1 ; paramètres stockés dans l'empreinte ; re-hachage si les paramètres évoluent | `api/app/security.py` |
| Borne de charge | `BoundedSemaphore(2)` : au plus 2 hachages simultanés (~256 Mo) | idem |
| Jetons | HMAC-SHA256 sur `role:id:expiration:version` ; comparaison à temps constant | idem |
| Invalidation | changer le mot de passe ou le code change la `version` → tous les jetons émis deviennent invalides | `auth.py` (`version_mot_de_passe`) |
| Second facteur | TOTP RFC 6238 (±1 pas), requis en production | `security.py`, `config.totp_requis` |
| Garde-fou de démarrage | refus si secret faible, SQLite, CORS `localhost`/`*`, ou mode de validation non choisi | `config.py::_verifier_production` |
| En-têtes HTTP | CSP `default-src 'self'`, HSTS, `X-Frame-Options: DENY`, `Referrer-Policy` | `deploy/Caddyfile` |
| Expressions élèves | parseur `ast` à liste blanche, 200 caractères, jamais d'`eval` | `engine/src/pkp_engine/expressions.py` |
| Conteneur API | utilisateur non-root (uid 10001), aucun port publié | `deploy/Dockerfile.api` |

Recherche de motifs dangereux sur tout le dépôt : `eval(`, `exec(`, `os.system`, `subprocess` → **aucun résultat** ; `console.log` → aucun ; `TODO`/`FIXME` → aucun.

**Limites de cette section** : elle ne couvre ni la configuration réellement déployée, ni les dépendances (hors `npm audit` en CI), ni les aspects réseau, ni les jetons de session côté navigateur.

---

## 5. Risques et points ouverts

### 5.1 Politique de licences — à décider (requalifié)

L'`UNLICENSE` place le code dans le **domaine public** : elle autorise explicitement la vente et la réutilisation commerciale. Elle **n'empêche donc pas** de commercialiser Boussole Maîtrise+.

Le sujet réel est différent et plus large :

| Sujet | État |
|---|---|
| Réutilisation du code par un tiers | possible, y compris pour revendre le service |
| Contributions externes | aucune clause de cession ; pas de CLA |
| Contenus (YAML, PDF de `contenu/`, `referentiels/`) | couverts par la même licence que le code, alors que les documents sources ont leurs propres conditions |
| Marque « Boussole Maîtrise+ » | aucun dépôt, aucune protection examinée |
| Nom historique « PKP » | encore présent dans le code et les variables |

Décision attendue : choisir une **politique** (rester dans le domaine public, passer à une licence propriétaire, ou double licence AGPL + commerciale) **et** clarifier séparément les droits sur les contenus et la marque. Modifier un seul fichier `LICENSE` ne suffit pas.

### 5.2 Validation pédagogique — le point le plus incertain

- 1 775 questions actives, toutes marquées `auteur: « Brouillon IA (Claude) »`, **aucune trace de validation dans les YAML examinés** (§ 3.2). Cela n'établit pas qu'aucune relecture n'a eu lieu ailleurs, ni la qualité des questions.
- Le circuit de validation existe côté anglais (soumettre → valider, un référent ne valide pas ses propres séances) ; côté maths, le statut se change dans l'interface sans soumission ni commentaire de relecture (constat du CDC V2).
- `PKP_SERVIR_QUESTIONS_NON_VALIDEES` est une **variable globale** (`api/app/config.py`). Le mécanisme par compétence est distinct : `validees_en_priorite()` (`api/app/progression.py`), qui ne sert que les questions validées d'une compétence dès qu'elle en possède au moins une.
- La configuration réellement utilisée en production n'a pas été vérifiée ici.

Conséquence pratique : la priorité n'est pas un réglage, c'est **un travail de relecture humaine** dont la trace doit être enregistrée avec les questions. Le point de départ raisonnable est un lot pilote, pas les 1 775 questions d'un coup.

### 5.3 Monétisation

Aucune inscription publique, aucun paiement, aucun courriel transactionnel. Le CDC V2 (§ 2) décrit les offres ; les décisions D1, D9 et D12 restent ouvertes. Rien n'est codé.

### 5.4 Exploitation

| Sujet | État constaté sur `main` | Où en est `develop` |
|---|---|---|
| Sauvegardes | manuelles (`pg_dump` documenté) | travaux en cours (#65, #72) |
| Supervision / alertes | aucune | idem |
| Workers | 1 seul processus : limitation en mémoire | idem |
| Domaine | provisoire (`<ip>.sslip.io`) | idem |

Les scripts présents sur `develop` **ne valent pas validation sur VM** : aucun essai réel n'a été constaté ici.

### 5.5 SSRF dans la vérification des liens — correctif à reformuler

`api/app/ressources.py::lien_repond()` (lignes 152-164) appelle `urllib.request.urlopen()` sur une URL fournie par un enseignant ou un administrateur. Le schéma `https://` et une liste de domaines interdits sont contrôlés ; ces protections restent partielles.

Corrections apportées à la version 1 du correctif :

1. **`build_opener()` sans `HTTPRedirectHandler` ne désactive pas les redirections** : ce gestionnaire est réinstallé par défaut. Il faut fournir un sous-type dont `redirect_request()` renvoie `None`.
2. Vérifier `reponse.geturl()` **après** la requête est trop tard : la destination a déjà été contactée.
3. Résoudre le nom avant la requête ne suffit pas si la bibliothèque le résout à nouveau : le rebinding DNS n'est pas couvert par ce seul contrôle.
4. L'accès aux métadonnées GCP n'est pas démontré par cet extrait : il exige l'en-tête `Metadata-Flavor: Google`, absent de la requête examinée. Le risque SSRF vers d'autres destinations internes reste réel.

Correctif attendu : contrôle **avant** chaque connexion et **avant chaque redirection autorisée**, épinglage de l'adresse effectivement contactée, restrictions réseau en défense en profondeur, et tests de contournement isolés.

### 5.6 Taille des modules

| Fichier | Lignes physiques | Lignes non vides |
|---|--:|--:|
| `api/app/routes/admin.py` | **1 016** | 860 |
| `api/app/schemas.py` | 811 | 598 |
| `api/app/contenu.py` | 771 | 657 |
| `api/app/db/models.py` | 744 | 594 |
| `api/app/schemas_admin.py` | 653 | 468 |
| `api/app/routes/admin_contenu.py` | 579 | 485 |
| `web/src/enseignant/Classes.jsx` | 650 | 614 |
| `web/src/admin/Repertoire.jsx` | 641 | 615 |
| `web/src/admin/Eleves.jsx` | 571 | 549 |
| `web/src/admin/Familles.jsx` | 555 | 525 |
| `web/src/admin/Contenu.jsx` | 480 | 458 |
| `web/src/parent/EspaceParent.jsx` | 435 | 405 |

Ce n'est pas un défaut en soi. Cela devient un coût quand plusieurs lots V2 modifient les mêmes fichiers : revue, conflits de fusion, testabilité de la logique mêlée au rendu.

### 5.7 Outillage absent

Ni linter, ni formateur, ni `pre-commit`, ni mesure de couverture, ni Dependabot (seul `npm audit --omit=dev --audit-level=high` bloque en CI). Le code est cohérent, mais ces contrôles ne sont pas **rejoués automatiquement** à chaque PR.

---

## 6. Vérifications exécutées

### 6.1 Tests du moteur — sortie brute

```
$ PYTHONPATH=engine/src python -m pytest engine/tests -q --no-header -p no:cacheprovider
........................................................................ [ 51%]
...................................................................      [100%]
139 passed in 1.44s
```

139 cas, 72 fonctions de test après paramétrage, aucune erreur.

### 6.2 Suites non exécutées

| Suite | Statut | Raison |
|---|---|---|
| API (389 fonctions) | non exécutée | le bac à sable Windows refuse l'accès aux dossiers temporaires créés par pytest (`PermissionError WinError 5`) ; diagnostic de permissions exécuté, aucune réparation applicable |
| Front (105 tests) | non exécutée | dépendances npm non installées dans cette session |

### 6.3 Preuve complémentaire indépendante

La CI GitHub du commit analysé est réussie : [run 42845732086](https://github.com/Photon53/boussole-maitrise-plus/actions/runs/42845732086) — contenu vérifié, tests moteur, tests API, `npm audit`, tests front, build.

Ce résultat démontre que la CI passe sur ce commit. Il **ne démontre pas** une recette de production, ni l'absence de vulnérabilités.

### 6.4 Comptage du contenu

Script de lecture des 154 YAML (`yaml.safe_load`), résultats au § 3.2. Reproductible en quelques secondes.

---

## 7. Recommandations

### P0 — sécurité et fiabilité de l'exploitation

1. **SSRF** : correctif conforme au § 5.5, avec tests de contournement, avant d'élargir la création de liens.
2. **Sauvegardes automatiques et restauration testée** (#8), puis supervision.
3. **Révocation des sessions** (#5) : un jeton copié reste utilisable après déconnexion **même avec un seul processus** ; ce sujet ne dépend pas du passage à plusieurs instances.
4. **Vérifier la configuration de production** (variable globale des questions non validées) et rapprocher les YAML des validations éventuellement présentes en base.

### P1 — périmètre pédagogique et décisions

5. **Construire la validation par lot pilote**, pas sur les 1 775 questions d'un coup : rapprochement YAML/base, protocole, responsables, traces liées aux versions, mesure du temps réel de relecture. Les tickets #14, #24, #37, #44, #29 et #73 couvrent déjà ce terrain ; un nouveau ticket général ferait doublon.
6. **Décider la politique de licences** (§ 5.1) : décision de porteur, à mener **en parallèle**. Elle ne bloque pas la vente du service ; elle détermine ce qu'un tiers peut réutiliser.
7. **Limitation partagée** (#7) : sujet distinct, à traiter selon la topologie retenue (un ou plusieurs processus).

### P2 — qualité et maintenabilité

8. **Outillage progressif** (#78) : mesurer la couverture avant de fixer des seuils, ne pas coupler reformatage global et montée de dépendances.
9. **Découpage ciblé** (#79) : commencer par les responsabilités que les prochains tickets modifient, sans seuil universel de lignes.

---

## 8. Traçabilité et attribution

### 8.1 Ce que la signature établit

| Élément | Valeur |
|---|---|
| Auteur et committer du commit | `DeepSeek <deepseek-agent@users.noreply.github.com>` |
| Statut GitHub du commit | `verified=false`, raison `unsigned` |
| Empreinte SHA-256 du présent fichier | publiée dans la PR d'intégration et dans l'issue #80 |

Une empreinte **n'est pas** une signature cryptographique : elle prouve l'intégrité du texte, pas l'identité de l'auteur. Le commit n'est pas signé (pas de clé GPG/SSH), et l'adresse `deepseek-agent@users.noreply.github.com` n'est liée à aucun compte vérifié.

### 8.2 Empreintes

La version 1 annonçait une empreinte qui correspondait au texte **avant** l'ajout de sa section « Signature », ce qui prêtait à confusion. Cette version ne cite pas sa propre empreinte dans son corps : la valeur SHA-256 du fichier complet est publiée dans la PR et dans l'issue #80, où elle reste vérifiable.

### 8.3 Jeton GitHub utilisé pour l'analyse

Vérifié dans cette session :

- le jeton **n'est pas versionné** : aucun fichier du dépôt ne contient sa valeur (`0` correspondance sur l'ensemble des fichiers) ;
- il est stocké **en clair** dans `.gh-config/hosts.yml`, hors du dépôt, parce que le stockage chiffré Windows et `%APPDATA%` sont inaccessibles au bac à sable.

Recommandation : le révoquer sur <https://github.com/settings/applications> lorsqu'il n'est plus nécessaire, puis supprimer la copie locale. Aucune valeur n'est reproduite dans ce document.

---

## 9. Conclusion

L'analyse établit un ensemble de propriétés vérifiables : architecture en couches respectée, authentification et hachage sérieusement implémentés, absence de motifs d'exécution dangereux, documentation dense et cohérente avec le code, contenu volumineux.

Elle n'établit pas que le produit est prêt à être exploité ou vendu : la banque de questions est un ensemble de brouillons IA sans relecture enregistrée, la politique de licences n'est pas décidée, l'exploitation (sauvegardes, supervision, multi-instance) reste à industrialiser, et un correctif SSRF est attendu.

Les freins identifiés ne sont donc **pas uniquement techniques** — mais plusieurs d'entre eux le sont, et ils sont ouverts.

---

*Rapport produit par analyse statique du dépôt, version 2, 13/11/2026. Aucune modification du code applicatif n'a été effectuée.*

---

## Annexe A — reproduire le comptage du contenu

| | |
|---|---|
| Script | [`docs/analyses/2026-11-13-compter-contenu.py`](2026-11-13-compter-contenu.py) |
| Commande (depuis la racine du dépôt) | `python docs/analyses/2026-11-13-compter-contenu.py` |
| Périmètre | `contenu/**/*.yaml` au commit `78ecf3a` — 154 fichiers |
| Environnement d'exécution | Python 3.14.6, PyYAML 6.x |

Sortie obtenue le 13/11/2026 :

```json
{
  "chapitres": 154,
  "competences": 327,
  "questions_declarees": 1776,
  "questions_archivees": 1,
  "questions_actives": 1775,
  "avec_bloc_validation": 0,
  "auteurs": [["Brouillon IA (Claude)", 1775], ["(absent)", 1]]
}
```

Le script ne lit que le contenu versionné : il ne dit rien des validations qui pourraient exister dans une base déployée.

---

## Signature

**Analyse produite par DeepSeek** (DeepSeek Harness) — 13/11/2026.

| | |
|---|---|
| Dépôt | `Photon53/boussole-maitrise-plus` |
| Commit analysé | `78ecf3a` (`main`) |
| Référentiel d'intégration | `develop` @ `d728659` |
| Empreinte du fichier | publiée dans la PR et dans l'issue #80 |
| Contre-revue intégrée | issue #80, commentaire du 13/11/2026 |
