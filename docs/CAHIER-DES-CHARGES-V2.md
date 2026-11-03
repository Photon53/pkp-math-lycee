# Cahier des charges — PKP Éducation V2

**Statut :** version 2.4 de cadrage, à valider · **Date :** 3 novembre 2026 (historique en § 17)
**Objet :** préparer PKP à devenir un service payant, multi-matières et multi-rôles, en s'appuyant sur ce qui
existe déjà. Ce document fusionne le cahier des charges commercial du 30 octobre (v1.1) et la proposition
d'architecture « PKP Éducation V2.0 » du 3 novembre, confrontés au code. Il fixe le périmètre, l'ordre des lots,
les exigences, les critères de recette et les décisions encore ouvertes.

Logique retenue : **Fiabiliser → Administrer → Valider → Mesurer → Commercialiser → Élargir.**

Deux règles s'appliquent à tous les lots :
- **étendre plutôt que réécrire** : on ajoute des champs, des tables et des écrans sans casser les routes ni les
  connexions existantes ; on ne retire un ancien composant qu'après recette du nouveau ;
- **préparer la vente sans l'annoncer** : tant que le lot 1 n'est pas recetté, rien de commercial n'apparaît sur le
  site public (inscription fermée par réglage, pas de page tarifs en ligne).

---

## 1. État des lieux vérifié (dépôt au 03/11/2026, `origin/main` commit `75adc1a`)

Les affirmations ci-dessous ont été vérifiées dans le code, pas supposées. Toutes les branches distantes
(`PKP-Anglais`, `comptes-parents`, `retours-classes`, `fiabilite-fluidite`, `fiches-exploitation`,
`couverture-programmes-2026`, `feature/pkp-anglais-v1.8-cadrage`…) sont **déjà fusionnées** dans `origin/main` :
il n'y a pas de lot d'intégration de branches à prévoir. La branche locale `main` est en retard et doit être
mise à jour (`git pull`) avant tout développement.

| Domaine | Ce qui existe | Où | Écart pour la V2 |
|---|---|---|---|
| Comptes adultes | Table `enseignant` : nom, e-mail, mot de passe scrypt, `role` (`enseignant` ou `admin`), cases `enseigne_maths`, `enseigne_anglais`, `referent_anglais`, désactivation, mot de passe provisoire, second facteur TOTP pour l'admin. Création par l'admin dans l'interface | `models.Enseignant`, `referentiel.Role`, `routes/admin.py` | **Pas de rôle validateur** : la relecture anglais passe par une case `referent_anglais`, la relecture maths n'a pas de rôle. Pas de périmètre par matière et par niveau. Ni inscription, ni vérification d'e-mail, ni mot de passe oublié en libre-service |
| Parents | Table `parent` (e-mail, mot de passe), lien n-n avec les élèves, créés par le professeur de l'enfant, espace parent, suppression des comptes sans enfant | `models.Parent`, `parents.py`, `routes/parents.py`, `parent/EspaceParent.jsx`, migration 0022 | **Dans l'admin : liste et réinitialisation du mot de passe seulement.** L'admin ne peut ni créer un parent, ni rattacher ou détacher un enfant, ni voir l'historique des rattachements |
| Élèves et classes | Connexion par prénom, code classe et code personnel ; inscriptions multiples ; cartes à QR code ; groupes d'anglais séparés des classes de maths | `models.Classe`, `models.Eleve`, `models.GroupeAnglais`, `models.EleveAnglais` | Aucun plafond de classes ou d'élèves |
| Matières et niveaux | Maths : niveaux `2nde`, `1re`, `Tle` et 9 parcours (spécialité, complémentaires, expertes, technologique, examens…). Anglais : séances, groupes et progression propres, niveaux `4e` et `3e` | `engine/domain.Niveau`, `referentiel.Parcours`, tables `*_anglais` | **Aucune notion commune de matière ni de cycle.** Ni maths collège, ni anglais lycée, ni français |
| Contenu maths | Chapitres, compétences, leçons (cours et résumé) **versionnées avec restauration**, questions avec `auteur`, `correction` structurée, valeurs variables (`gabarit`), source et licence. Édition dans l'admin, la base devient la référence après modification (`modifiee_admin_le`) | `routes/admin_contenu.py`, `models.LeconVersion`, `models.Question`, `admin/Contenu.jsx`, `admin/Exercices.jsx` | Les questions ne sont pas versionnées. Le statut (`a-valider`, `validee`, `a-corriger`) se change d'un clic, sans soumission ni commentaire de relecture |
| Contenu anglais | Séances versionnées (fichier de séance, cahier, QCM), circuit soumettre → valider / refuser par un référent qui ne valide jamais les siennes, PDF | `models.SeanceAnglaisVersion`, `routes/admin.py` (`/anglais/seances/...`), `anglais_pdf.py` | Circuit propre à l'anglais, distinct de celui des maths |
| Écriture du contenu par les enseignants | Plus de route d'écriture de la banque côté enseignant (lecture seule des questions et des cours) | `routes/enseignants.py`, `routes/enseignants_contenu.py` | Faille E1.0 de la v1.1 **corrigée** ; reste à vérifier la limitation de la lecture aux chapitres ouverts |
| Questions non validées | Réglage `PKP_SERVIR_QUESTIONS_NON_VALIDEES`, **choix explicite obligatoire en production** | `config.py` | Valeur par défaut `true` en développement ; à passer à `false` chapitre par chapitre (E0.4) |
| Tableau de bord admin | Professeurs et élèves actifs, séances, réponses, taux de réussite, courbes par jour, réussite par chapitre, questions difficiles, couverture, ressources, export CSV | `statistiques.py`, `admin/TableauDeBord.jsx` | **Maths seulement : l'anglais n'est compté nulle part.** Pas de vue par professeur, ni de suivi de la validation, ni de distinction « pas de données » / « zéro » |
| Journal | Actions de l'admin tracées (qui, quoi, quand, sur quoi) | `models.JournalAdmin`, `admin/Journal.jsx` | Ne couvre pas les décisions de relecture des maths |
| Paiement, e-mail | Aucun | — | Tout est à faire |
| RGPD | Minimisation (prénom seul), purge des inactifs, aucun traceur, CSP stricte | `docs/RGPD.md`, `purge.py` | À adapter au rôle de sous-traitant (§ 12.1) et aux comptes parents (mineurs) |
| Qualité | Environ 375 tests Python (API et moteur) et 77 tests du front, vérification du contenu en CI | `api/tests`, `engine/tests`, `web/src/tests` | Suite à exécuter et à garder verte comme référence avant chaque lot |
| Exploitation | Docker Compose (PostgreSQL, API, purge, Caddy), script d'installation Oracle Linux, fiches d'exploitation | `deploy/`, `docs/` | Sauvegardes **manuelles** ; ni supervision ni alertes ; domaine provisoire |

**Conclusion de l'audit :** PKP est plus avancé que ne le supposait la proposition V2.0 : parents, versions des
leçons, validation de l'anglais et tableau de bord existent. Ce qui manque est de trois ordres :
1. **une structure commune** (matière × cycle, rôles avec périmètre, circuit de validation unique) ;
2. **une administration utilisable au quotidien** (parents, comptes, tableau de bord multi-matières) ;
3. **ce qui permet d'encaisser** (contenu validé et corrigé, inscription, paiement, documents juridiques).

---

## 2. Cible et offres

### 2.1 Premier client

**Hypothèse retenue : l'enseignant indépendant ou le professeur particulier qui paie lui-même son abonnement.**
Il décide seul, paie par carte et utilise le produit tel qu'il est. Le centre de soutien vient ensuite, avec la même
base technique plus une notion d'organisation (lot 1-bis). C'est la décision **D1**, à confirmer (§ 15).

### 2.2 Offres (prix à tester, non définitifs)

| Offre | Pour qui | Prix de départ à tester | Lot |
|---|---|---|---|
| **Découverte** (gratuite) | Enseignant qui évalue | 1 classe, 10 élèves, fonctions limitées (décision **D9**) | 1 |
| **PKP Enseignant** | Enseignant indépendant | 49 €/an (ou 6 €/mois) : 5 classes, 150 élèves, par matière souscrite | 1 |
| **PKP Centre** | Centre de soutien | 2 à 4 € par élève et par an, plusieurs enseignants | 1-bis |
| **PKP Famille** | Parents | 49 €/an, Pass examen | après la V2 |

**Exigence :** les plafonds, les fonctions et les **domaines inclus** dans chaque offre sont des **données** (table
`offre`), modifiables sans redéploiement. Les prix vivent dans Stripe.

**Point d'attention :** un professeur particulier suit souvent moins de 10 élèves. L'offre gratuite doit se distinguer
par les fonctions (corrigés détaillés limités, pas de vue de classe ni de devoirs) ou par une durée, pas seulement par
le volume (décision **D9**).

---

## 3. Architecture cible

### 3.1 Les six domaines pédagogiques

Un **domaine** est le couple matière × cycle. Les six domaines existent dans la configuration dès la V2 ; chacun a deux
interrupteurs indépendants : **actif** (visible par les admins, professeurs et validateurs, pour produire du contenu)
et **public** (ouvert aux élèves et à la vente).

| Domaine | Niveaux | État du code | Ouverture publique proposée |
|---|---|---|---|
| Maths lycée | 2nde, 1re, Tle | Complet | Vague 1 |
| Anglais collège | 4e, 3e (6e, 5e à ajouter) | Complet pour 4e et 3e | Vague 1 |
| Maths collège | 6e à 3e | Rien (le moteur sert tel quel) | Vague 2, selon le contenu produit |
| Anglais lycée | 2nde, 1re, Tle | Rien (le modèle anglais sert tel quel) | Vague 2 |
| Français collège | 6e à 3e | Rien | Vague 3 |
| Français lycée | 2nde, 1re (épreuve anticipée) | Rien | Vague 3 |

- **EX.1** Nouvelle table `domaine` (`code`, `matiere`, `cycle`, `niveaux`, `actif`, `public`, `ordre`), remplie par la
  migration avec les six domaines ; seuls Maths lycée et Anglais collège sont `public`.
- **EX.2** Les tables racines du contenu et des groupes reçoivent une colonne `domaine_id` : `chapitre`,
  `seance_anglais`, `classe`, `groupe_anglais`. La migration la remplit d'après l'existant (maths → Maths lycée,
  anglais → Anglais collège). Les contraintes `niveau IN ('4e', '3e')` de l'anglais sont remplacées par un contrôle sur
  les niveaux du domaine. *(Fait : migration 0024, colonne `domaine_code` ; la colonne `niveau` de l'anglais passe à
  4 caractères pour accueillir « 2nde » ; les nouvelles classes et les nouveaux groupes reçoivent le domaine de leur
  espace, Maths lycée ou Anglais collège.)*
- **EX.3** On **ne fusionne pas** les tables des maths et de l'anglais : leurs contenus sont de nature différente
  (question à valeurs variables d'un côté, séance chronométrée avec supports audio de l'autre). La bibliothèque
  unifiée est une **vue commune** (§ 3.3), pas une table unique.
- **EX.4** Un domaine non `public` refuse côté API toute nouvelle séance élève et toute création de classe ou de
  groupe pour un professeur ; il ne supprime ni contenu ni historique.
- **EX.5** Le français aura son module propre (types d'exercices : compréhension de texte, grammaire, orthographe,
  rédaction guidée), cadré par une fiche dédiée avant tout développement (décision **D12**).

### 3.2 Comptes, rôles et permissions

On garde **trois familles de comptes**, parce que leurs modes de connexion sont différents et doivent le rester :

| Famille | Connexion | Table | Évolution |
|---|---|---|---|
| Adultes de l'équipe : admin, professeur, validateur | E-mail, mot de passe, TOTP pour l'admin | `enseignant` (renommage hors périmètre) | Rôles cumulables avec périmètre |
| Parents | E-mail, mot de passe | `parent` | Gestion complète dans l'admin (lot A) |
| Élèves | Prénom, code classe, code personnel | `eleve` | **Inchangée** |

La proposition V2.0 d'un compte unique pour tous les utilisateurs est **écartée** : elle obligerait à migrer la
connexion des élèves, qui est la fonction la plus utilisée et la plus sensible, sans bénéfice pour l'utilisateur.

- **EX.6** Nouvelle table `habilitation` (`enseignant_id`, `role`, `domaine_id` facultatif, `niveau` facultatif,
  `accordee_par`, `accordee_le`). Rôles : `professeur`, `validateur` ; le rôle `admin` reste porté par
  `enseignant.role`, sans périmètre, et ne donne pas le droit de valider. Un même compte peut être professeur de
  Maths lycée et validateur d'Anglais collège. *(Fait : table `habilitation`, migration 0023.)*
- **EX.7** Les permissions sont une **table de correspondance dans le code** (`app/permissions.py`), pas un moteur
  configurable en base : `contenu.lire`, `contenu.modifier`, `contenu.soumettre`, `contenu.valider`,
  `contenu.publier`, `comptes.gerer`, `parents.gerer`, `pilotage.global`, `pilotage.domaine`, `configuration`.
  Une seule fonction `exiger(permission, domaine=None)` est appelée par chaque route.
- **EX.8** Migration sans rupture : `role = admin` → habilitation `admin` ; `enseigne_maths` → `professeur` de Maths
  lycée ; `enseigne_anglais` → `professeur` d'Anglais collège ; `referent_anglais` → `validateur` d'Anglais collège. Aujourd'hui, ce sont les admins qui valident les questions
  de maths : pour ne pas bloquer la relecture, chaque admin actif reçoit à la migration une habilitation `validateur`
  de Maths lycée, que l'admin principal confirme ou retire ensuite compte par compte (EX.9-bis).
  Les anciennes colonnes restent lues pendant une version, puis sont retirées. Les jetons en cours restent valables.
- **EX.9** Règle invariante : **personne ne valide un contenu dont il est l'auteur**, quel que soit son rôle, admin compris.
- **EX.9-bis** **La validation est une qualification par matière, pas un droit global.** Le circuit de validation est
  commun à toutes les matières (§ 3.3), mais les validateurs ne le sont pas :
  - un validateur reçoit une habilitation `validateur` **par domaine** pour lequel il est qualifié : une seule matière,
    deux, ou plus. Un validateur de maths n'est pas validateur d'anglais, et inversement ;
  - à l'attribution, l'admin coche les **matières** (Maths, Anglais, Français) et, pour chacune, le ou les **cycles**
    (collège, lycée) ; cocher « toute la matière » donne les deux cycles. Un niveau précis peut restreindre davantage
    (par exemple : validateur Maths lycée, Terminale seulement) ;
  - **le rôle admin ne donne pas le droit de valider** : un admin ne valide que dans les domaines où il a aussi une
    habilitation `validateur`. Sa permission `contenu.publier` ne s'applique qu'à des versions déjà validées ;
  - un contenu soumis dans un domaine sans validateur habilité reste `soumis` : il n'est jamais validé par défaut ni
    par un validateur d'une autre matière. Le tableau de bord de la validation signale ce domaine à l'admin ;
  - retirer une habilitation de validateur prend effet immédiatement ; les décisions déjà prises restent attribuées
    à leur auteur dans l'historique.

### 3.3 Bibliothèque, versions et validation unifiées

Types de contenu : chapitre, compétence, cours, résumé, exercice (question), séance d'anglais, ressource ; plus tard
sujet d'examen (lot 2) et contenus de français.

- **EX.10** **Source de vérité :** le YAML de Git sert à l'import initial ; après import, **la base est la référence**
  pour tout contenu modifié dans l'admin (règle déjà en place, `modifiee_admin_le`). Une commande
  `python -m app.contenu exporter` réécrit le YAML depuis la base, et l'import refuse d'écraser un contenu modifié en
  base depuis le dernier import (conflit signalé, jamais résolu en silence). Cette règle remplace « contenu
  uniquement en YAML » de la v1.1.
- **EX.11** Les questions sont versionnées comme les leçons et les séances d'anglais : table `question_version`.
  Chaque réponse d'élève garde la version qu'il a vue, pour que les statistiques restent justes après correction.
- **EX.12** Un seul cycle de vie pour tous les types :

  | Statut | Qui le donne | Effet |
  |---|---|---|
  | `brouillon` | Auteur | Modifiable, invisible des élèves |
  | `soumis` | Auteur | Version figée, entre dans la file de relecture |
  | `a-corriger` | Validateur | Commentaires obligatoires, retour à l'auteur |
  | `validee` | Validateur ≠ auteur | Décision horodatée et attribuée |
  | `publiee` | Validateur ou admin | Servie aux élèves (si le domaine est `public`) |
  | `retiree` | Validateur ou admin | Plus servie, historique conservé |

  Les statuts actuels se convertissent ainsi : `a-valider` → `soumis`, `validee` → `publiee`, `a-corriger` →
  `a-corriger`. Restaurer une ancienne version crée une nouvelle version `brouillon`.
- **EX.13** **L'API refuse** de publier une version non validée et de modifier une version publiée, même appelée
  directement. Modifier un contenu publié crée une nouvelle version de travail ; l'ancienne reste servie jusqu'à la
  publication de la nouvelle.
- **EX.14** Table `relecture` (version, validateur, décision, commentaire, date) : elle alimente le journal et le
  tableau de bord de la validation.

### 3.4 Données d'activité

- **EX.15** Les statistiques sont calculées dans **un seul module** (`statistiques.py` étendu) à partir de définitions
  écrites une fois (§ 8.2), jamais recalculées différemment dans chaque écran.
- **EX.16** On réutilise d'abord ce qui est déjà enregistré : `seance`, `reponse`, `progression_anglais`,
  `ressource_consultation`, `journal_admin`, `relecture`. Une table `evenement` (type, date, domaine, acteur
  pseudonymisé, objet, version) n'est ajoutée que pour ce qui n'est capté nulle part : cours consulté, correction
  consultée, espace parent consulté, connexion.
- **EX.17** Aucune donnée personnelle superflue : pas d'adresse IP, pas de contenu de réponse dans `evenement` ;
  agrégats anonymes dans les tableaux de bord globaux. Dates stockées en UTC, affichées en heure de Paris.

---

## 4. Périmètre et ordre des lots

| Lot | Contenu | Livrable | Dépend de |
|---|---|---|---|
| **0 — Fiabilisation pédagogique** | Corrections détaillées, relecture des questions, outil IA de brouillon | Banque fiable et vendable | — (en continu) |
| **A — Administration et rôles** | Domaines, habilitations, refonte de la navigation admin, comptes de tous les rôles, gestion des parents | Une admin pratique au quotidien | — |
| **B — Validation unifiée** | Cycle de vie commun, versions des questions, file de relecture, publication sécurisée | Un seul circuit pour maths et anglais | A |
| **C — Pilotage** | Tableaux de bord global, par domaine, anglais, professeurs, validation | Piloter le site avec des chiffres fiables | A, B |
| **1 — Commercialisation enseignant** | Inscription, e-mails, offres, Stripe, droits, plafonds, juridique, exploitation | Un enseignant s'inscrit, paie et utilise PKP sans intervention | 0 (chapitres vendus), A |
| **2 — Préparation aux examens** | Épreuve anticipée de 1re, Bac, devoirs, simulations | Offre différenciante | 1 en recette |
| **D — Nouveaux domaines** | Ouverture de Maths collège, Anglais lycée, puis Français | Élargissement | B, contenu validé |

Règles d'ordre :
- **aucune mise en vente avant la fin du lot 0 sur les chapitres proposés à la vente** ;
- le lot 0 est surtout du travail d'enseignant : il avance en parallèle des lots A et B ;
- un domaine ne passe `public` que s'il atteint le seuil de couverture fixé par la décision **D13**.

---

## 5. Lot 0 — Fiabilisation pédagogique

### 5.1 Correction détaillée

Le modèle a déjà les champs `auteur` et `correction` (JSON). Le lot 0 fixe leur contenu et leurs contrôles :

```yaml
- code: 1RE-DER-CALC-03
  difficulte: 3
  type: numerique
  enonce: '...'
  solution: 6
  auteur: R. Martin
  correction:
    methode: Dériver un produit avec $(uv)' = u'v + uv'$.
    etapes:
      - On pose $u(x) = ...$ et $v(x) = ...$.
      - ...
    resultat: 6
    erreurs_frequentes:
      - Écrire $(uv)' = u'v'$.
  validation:
    statut: validee
    par: M. Dupont
    le: 2026-11-15
```

- **E0.1** `correction.methode` (une phrase), `correction.etapes` (au moins une), `correction.resultat` (obligatoire pour
  `numerique` et `expression`) et `correction.erreurs_frequentes` (facultatif) sont validés par le schéma, en YAML
  comme dans l'admin, et rendus avec KaTeX. À vérifier : ce que le schéma actuel impose déjà.
- **E0.2** Le vérificateur (`python -m app.contenu verifier`) et l'API refusent : une question validée sans correction ;
  une question validée par son auteur (EX.9) ; une formule refusée par KaTeX (script Node
  `web/scripts/verifier-katex.mjs`) ; un `correction.resultat` que le moteur ne juge pas équivalent à `solution`.
- **E0.3** L'élève voit la correction **après** sa réponse, juste ou fausse. La route vérifie côté serveur qu'il a déjà
  répondu dans la séance (sinon 403). Chaque consultation est enregistrée (indicateur du § 14).
- **E0.4** `PKP_SERVIR_QUESTIONS_NON_VALIDEES=false` en production dès que les chapitres vendus sont validés. Un
  chapitre sans question publiée n'est pas proposable par l'enseignant.

### 5.2 Relecture

- **E0.5** Relecture par un professeur identifié qui n'est pas l'auteur. Jusqu'au lot B, elle se fait par le YAML ou par
  l'admin ; à partir du lot B, par la file de relecture (EB.3).
- **E0.6** L'inventaire (`python -m app.contenu inventaire`) donne par chapitre et par domaine : publiées, soumises, à
  corriger, sans correction.
- **E0.7** Objectif : **100 % des questions servies en production sont validées et corrigées.** Une banque plus petite
  et sûre vaut mieux qu'une banque large et douteuse.

### 5.3 Outil IA de brouillon (supervisé)

- **E0.8** Un script hors ligne `python -m app.ia_corrections --chapitre <CODE>` propose une correction pour chaque
  question qui n'en a pas. Il écrit avec le statut `brouillon` et `auteur: brouillon-ia` : **rien n'est publié sans
  relecture humaine.** Il conserve la mise en forme du YAML (ruamel.yaml) ou écrit une nouvelle version en base.
- **E0.9** Il fait vérifier `correction.resultat` par le moteur avant d'écrire, journalise le coût de chaque appel et
  s'arrête au plafond `--budget`.
- **E0.10** Aucune donnée d'élève n'est envoyée au modèle : seuls l'énoncé, la solution et le cours de la compétence.

### 5.4 Recette du lot 0

1. Le vérificateur refuse une question validée sans correction, une correction incohérente, une formule refusée par
   KaTeX et une question validée par son auteur.
2. Avec `PKP_SERVIR_QUESTIONS_NON_VALIDEES=false`, une question non publiée n'est jamais servie (test automatisé).
3. L'élève voit la correction après une réponse fausse ; la consultation est enregistrée.
4. Demander la correction d'une question pas encore répondue renvoie 403 (test automatisé).
5. L'inventaire montre que les chapitres mis en vente sont validés et corrigés à 100 %.

---

## 6. Lot A — Administration et rôles

### 6.1 Navigation de l'admin

L'admin actuelle empile des onglets par fonction et par matière. Elle est réorganisée en **quatre espaces**, avec un
**sélecteur de domaine** permanent en haut de page (« Tous », Maths collège, Maths lycée, Anglais collège, Anglais
lycée, Français collège, Français lycée) qui filtre tout ce qui s'affiche :

| Espace | Contenu | Écrans existants repris |
|---|---|---|
| **Comptes** | Équipe (admins, professeurs, validateurs), parents, élèves, classes et groupes | `Professeurs.jsx`, `Eleves.jsx`, `AnglaisAdmin.jsx` |
| **Pédagogie** | Programme (chapitres, compétences), cours et résumés, exercices, séances d'anglais, ressources, file de relecture | `Contenu.jsx`, `Exercices.jsx`, `SeancesAnglaisAdmin.jsx`, `RessourcesAdmin.jsx` |
| **Pilotage** | Tableaux de bord (lot C), journal | `TableauDeBord.jsx`, `Journal.jsx` |
| **Configuration** | Domaines (actif, public), niveaux, rôles et habilitations, réglages, domaines interdits des ressources ; offres (lot 1) | nouveau |

- **EA.1** Recherche globale (compte, élève, classe, contenu par code ou titre) depuis toutes les pages.
- **EA.2** Listes paginées avec filtres (domaine, niveau, statut, actif) et export CSV, sur le modèle de la liste des élèves.
- **EA.3** Chaque espace n'apparaît qu'aux comptes qui ont la permission correspondante (EX.7) ; l'API refuse de toute
  façon les appels non autorisés.
- **EA.4** La refonte est activée par un réglage (`PKP_ADMIN_V2`) : l'ancienne navigation reste disponible jusqu'à la
  recette. *(Sans objet : la nouvelle navigation a été recettée puis fusionnée le 3 novembre 2026, pull request n° 12 ;
  l'ancienne a été retirée, il n'y a plus rien à basculer.)*

### 6.2 Comptes de l'équipe

- **EA.5** Créer un compte : nom, e-mail, une ou plusieurs habilitations (rôle × domaine × niveau facultatif). Pour
  le rôle validateur, l'écran présente une grille matières × cycles à cocher (avec « toute la matière ») et affiche
  sur la fiche du compte la liste de ses qualifications (EX.9-bis). Mot de
  passe provisoire affiché une fois (mécanisme existant), puis invitation par e-mail dès que le lot 1 l'apporte.
- **EA.6** Modifier les habilitations, désactiver, réinitialiser le mot de passe, transférer les classes (existant).
  Chaque changement d'habilitation est tracé dans `journal_admin`.
- **EA.7** Un admin ne peut ni retirer son propre rôle admin ni désactiver le dernier admin actif.

### 6.3 Parents

- **EA.8** Recherche des familles : parent, enfants rattachés, dernière connexion, compte provisoire ou non. Pas de
  liste complète (minimisation RGPD, choix déjà en place) : on cherche par e-mail (3 caractères au moins) ou par classe
  d'un enfant.
- **EA.9** Créer un parent depuis l'admin, rattacher ou détacher un enfant (recherche par prénom et classe). La
  révocation prend effet **immédiatement** : les jetons du parent ne donnent plus accès à cet enfant.
- **EA.10** Plusieurs responsables par enfant (déjà permis par le lien n-n) ; un parent peut avoir plusieurs enfants
  dans plusieurs classes et plusieurs domaines.
- **EA.11** Historique des rattachements (qui, quand, par qui, ajout ou retrait) dans une table `rattachement_parent`.
- **EA.12** Suppression d'un compte parent à sa demande, et export de ses données.

### 6.4 Recette du lot A

1. Les comptes existants (admin, professeurs maths et anglais, référents) se connectent après migration avec les mêmes
   droits qu'avant (test automatisé sur des données de référence).
2. Un validateur d'Anglais collège ne voit ni ne modifie le contenu de Maths lycée, même en appelant l'API.
3. Un parent détaché d'un enfant reçoit 403 sur cet enfant à la requête suivante.
4. Désactiver le domaine Anglais collège bloque les nouvelles séances élèves sans rien supprimer.
5. Le sélecteur de domaine filtre toutes les listes de l'admin.
6. Connexion élève, cartes QR, séances adaptatives et PDF anglais fonctionnent comme avant (suite de non-régression).

### 6.5 Avancement (au 03/11/2026)

| Exigence | État |
|---|---|
| EX.1, EX.4, EX.6 à EX.9-bis | Fait : domaines, habilitations, validateurs qualifiés par matière et par niveau, domaine fermé au public bloquant séances, classes et groupes |
| EX.8 | Fait : migration 0023 des cases historiques, admins actuels validateurs de Maths lycée |
| EB.0 (avancé du lot B) | Fait : la validation des questions de maths et des séances d'anglais exige la qualification |
| EA.5 à EA.7 | Fait : grille de qualifications, journal des habilitations, dernier admin protégé |
| EA.8 à EA.12 | Fait, y compris l'export JSON des données d'un parent, journalisé (EA.12) |
| Navigation en quatre espaces | Fait (Pilotage, Comptes, Pédagogie, Configuration) |
| EX.2 | Fait : migration 0024, domaine enregistré sur classes, chapitres, groupes et séances d'anglais ; contrôle des niveaux par domaine |
| EA.1 | Fait : recherche globale dans le bandeau de l'admin (équipe, familles dès 3 caractères, élèves, classes, chapitres, exercices, groupes, élèves et séances d'anglais) ; chaque résultat ouvre sa page déjà filtrée |
| EA.2, recette 5 | Fait : sélecteur de domaine permanent, mémorisé pour la session ; il filtre l'équipe, les élèves, les classes, les familles, les cours, les exercices, les ressources et PKP Anglais. Le journal n'est pas filtré (il le dit) ; le tableau de bord couvre Maths lycée jusqu'au lot C (il le dit) |
| EX.7, EA.3 | Fait : table des permissions dans `app/permissions.py` (`permissions_de`, `exiger`) ; `/admin/moi` les expose et l'admin n'affiche que les espaces permis |
| EA.4 | Sans objet (voir l'exigence) |
| Validateur non enseignant | Fait : un validateur d'anglais qui n'enseigne pas l'anglais accède à la seule page Validation de PKP Anglais |

Recette : cas 1 à 6 couverts par `api/tests/test_lot_a_habilitations.py`, `api/tests/test_lot_a_domaines.py`,
`web/src/tests/lot-a-domaines.test.jsx` et la suite existante. **Le lot A est terminé.**

Restent pour les lots suivants : appeler `exiger(permission, domaine)` route par route à mesure que des comptes non
administrateurs entrent dans l'admin (validateurs de maths, lot B) ; tableaux de bord par domaine (lot C).

---

## 7. Lot B — Validation unifiée

« Unifiée » désigne **le circuit** (mêmes statuts, mêmes écrans, mêmes contrôles de l'API pour toutes les matières),
**pas les validateurs** : chaque validateur ne relit que les matières pour lesquelles il est qualifié (EX.9-bis).

- **EB.0** Toute décision de relecture (`validee`, `a-corriger`) vérifie côté serveur que l'utilisateur a une
  habilitation `validateur` sur le domaine **et** le niveau du contenu, et qu'il n'en est pas l'auteur ; sinon 403.
- **EB.1** Migration des statuts et création de `question_version` (EX.11, EX.12), sans changer ce que voient les
  élèves le jour de la bascule.
- **EB.2** Les séances d'anglais adoptent le même cycle ; leurs routes `soumettre`, `valider`, `refuser` restent
  disponibles et appellent le service commun.
- **EB.3** **File de relecture** : un même écran pour toutes les matières, qui ne montre à chacun que les contenus
  `soumis` des domaines où il est validateur (un validateur de deux matières voit les deux, filtrables),
  triés par ancienneté, avec la comparaison entre la version soumise et la version publiée (différences surlignées)
  et le test de la question (route existante `questions/tester`).
- **EB.4** Demande de correction : commentaire obligatoire, notifié à l'auteur dans son espace (et par e-mail au lot 1).
- **EB.5** Publication, retrait et restauration depuis la fiche du contenu, avec historique complet des versions.

### Recette du lot B

1. L'API refuse la publication d'une version non validée et la modification d'une version publiée (tests automatisés).
2. Un auteur ne peut pas valider son propre contenu, admin compris.
2-bis. Un validateur de Maths lycée reçoit 403 en validant une séance d'Anglais collège, même en appelant l'API ;
   un validateur habilité en maths et en anglais peut valider les deux ; un admin sans habilitation validateur ne
   valide rien (tests automatisés).
3. Corriger une question publiée laisse servir l'ancienne version jusqu'à la publication de la nouvelle.
4. Les réponses passées restent rattachées à la version vue par l'élève.
5. Une séance d'anglais suit le même circuit et produit le même PDF qu'avant.

---

## 8. Lot C — Pilotage

### 8.1 Tableaux de bord

| Tableau | Pour qui | Contenu principal |
|---|---|---|
| **Global** | Admin | Par domaine : élèves et professeurs actifs, séances, réponses, réussite, tendance sur la période ; parents actifs ; comparaison entre domaines ; clic vers le détail |
| **Par domaine** | Admin, validateur du domaine | Réussite par niveau, chapitre et compétence ; questions difficiles ; couverture du programme ; contenus à produire |
| **Anglais** | Admin, référents | Groupes et élèves actifs, séances faites, progression « I can », réussite aux QCM de grammaire, **taux de préparation des séances** |
| **Professeurs** | Admin | Activité de chaque professeur : classes, élèves actifs, séances de ses élèves, dernière connexion ; professeurs inactifs à relancer |
| **Validation** | Admin, validateurs | Contenus soumis, à corriger, publiés par semaine ; délai de relecture ; charge par validateur ; couverture par domaine |
| **Commercial** (lot 1) | Admin | Inscriptions, essais, conversions, abonnés actifs, revenu récurrent, résiliations |

- **EC.1** Chaque tableau a une période (7, 30, 90 jours, année scolaire), un filtre de niveau et un export CSV.
- **EC.2** « Pas de données » est affiché différemment de « 0 » ; une période sans activité ne casse pas les courbes.
- **EC.3** Les calculs lourds sont mis en cache (mécanisme existant `vider_cache`) ; p95 < 1 s à l'ouverture d'un tableau.

### 8.2 Définitions des indicateurs (écrites une fois, dans le code et ici)

| Indicateur | Définition |
|---|---|
| Élève actif | Au moins une réponse évaluée (maths) ou une séance suivie (anglais) sur la période |
| Professeur actif | Au moins une connexion, ou au moins un élève actif dans ses classes, sur la période |
| Taux de réussite | Réponses justes / réponses évaluées ; les questions abandonnées et les séances non terminées sont exclues |
| Couverture | Compétences du référentiel ayant au moins une question publiée et un cours publié / compétences du référentiel |
| Délai de relecture | Temps entre la soumission d'une version et la décision du validateur (médiane et 90ᵉ centile) |
| Préparation des séances d'anglais | Séances prévues dont fichier, cahier et QCM sont publiés / séances prévues |

### 8.3 Recette du lot C

1. Le tableau global additionne correctement maths et anglais sur des données de référence (test automatisé).
2. Un domaine sans activité affiche « pas de données », pas « 0 % ».
3. Un validateur ne voit que les tableaux de ses domaines.
4. L'export CSV redonne les mêmes chiffres que l'écran.

---

## 9. Lot 1 — Commercialisation enseignant

### 9.0 Prérequis

- **E1.0** *(fait)* Aucun compte enseignant ne peut modifier la banque commune. Reste : limiter la lecture de la
  banque (`GET /enseignants/questions`, avec solutions) aux chapitres ouverts dans ses classes.
- **E1.0-bis** L'inscription est fermée par le réglage `PKP_INSCRIPTION_OUVERTE=false` tant que la recette n'est pas
  passée ; les pages commerciales ne sont pas publiées avant.

### 9.1 Inscription et compte

- **E1.1** Inscription en libre-service : nom, e-mail, mot de passe (12 caractères minimum), domaine(s) enseigné(s),
  acceptation des CGU/CGV et de la politique de confidentialité (horodatée, avec la version du document). Le compte
  reçoit l'habilitation `professeur` des domaines choisis, s'ils sont `public`.
- **E1.2** Vérification de l'e-mail par lien à usage unique, valable 24 h ; avant vérification, pas d'inscription d'élèves.
- **E1.3** Mot de passe oublié : lien à usage unique valable 1 h, jetons stockés hachés ; changer le mot de passe ferme
  les sessions ouvertes (mécanisme existant). S'applique aussi aux parents.
- **E1.4** Pas d'énumération des comptes : même réponse que l'e-mail existe ou non.
- **E1.5** Limitation des tentatives par IP et par adresse (mécanisme de `limitation.py`).
- **E1.6** L'enseignant modifie son nom et son e-mail (nouvelle vérification), exporte les données de ses classes et
  peut supprimer son compte. Ne subsiste que ce qu'impose l'obligation comptable (factures chez Stripe ; identifiant
  client, nom et e-mail de facturation isolés, sans accès au service).
- **E1.7** La création par l'admin (lot A) reste disponible pour le support.

### 9.2 Envoi d'e-mails

- **E1.8** Prestataire d'e-mails transactionnels hébergé dans l'UE (décision **D4**), domaine authentifié (SPF, DKIM,
  DMARC), modèles en français, sans traceur.
- **E1.9** Messages : vérification, mot de passe oublié, invitation (équipe et parents), bienvenue, demande de correction
  (lot B), confirmation d'abonnement, échec de paiement, fin d'essai à J-7, rappel avant reconduction, résiliation.
  Les messages à date partent par une tâche planifiée quotidienne (modèle du conteneur `purge`), jamais deux fois ;
  les adresses en échec permanent ne reçoivent plus rien.

### 9.3 Offres, abonnements et droits

| Table | Rôle | Champs principaux |
|---|---|---|
| `offre` | Catalogue | `code`, `max_classes`, `max_eleves`, `domaines`, `fonctions`, `stripe_price_id`, `active` |
| `abonnement` | État commercial d'un enseignant | `enseignant_id`, `offre_id`, `statut`, `stripe_customer_id`, `stripe_subscription_id`, `fin_periode`, `essai_jusqu_au` |
| `evenement_stripe` | Idempotence et audit | `id` de l'événement Stripe (clé primaire), `type`, `recu_le`, `traite` |

Statuts : ceux de Stripe (`trialing`, `active`, `past_due`, `canceled`, `unpaid`), plus `essai` (sans carte, géré dans
PKP) et `decouverte`.

- **E1.10** **Un seul point de calcul des droits** (`droits_de(enseignant)`) : offre effective, plafonds, domaines.
  `past_due` conserve l'offre 7 jours ; au-delà, retour en Découverte. Relances Stripe alignées sur ces 7 jours.
- **E1.11** Plafonds vérifiés **côté serveur**. Passer sous un plafond ne supprime **jamais** de données : les classes
  en trop passent en lecture seule (l'enseignant choisit lesquelles), les élèves déjà inscrits continuent de travailler.
- **E1.12** Essai de 30 jours sans carte (décision **D2**), commençant à la vérification de l'e-mail ; le client Stripe
  n'est créé qu'au premier passage par Checkout.

### 9.4 Paiement (Stripe)

- **E1.13** Souscription par **Stripe Checkout**, gestion par **Customer Portal** ; aucune donnée bancaire chez PKP ;
  `client_reference_id` et réutilisation du client existant ; redirections, donc pas de script Stripe dans la CSP.
- **E1.14** État de l'abonnement mis à jour **uniquement par webhook** (`checkout.session.completed`,
  `customer.subscription.*`, `invoice.paid`, `invoice.payment_failed`), signature vérifiée, traitement idempotent,
  relecture de l'abonnement chez Stripe en cas de désordre.
- **E1.15** Factures émises par Stripe avec les mentions légales du vendeur (régime de TVA selon **D5**).
- **E1.16** Clés uniquement dans `.env`, clés de test hors production ; route de webhook exclue de la limitation globale.

### 9.5 Interface

- **E1.17** Pages publiques, mises en ligne à l'ouverture seulement : accueil commercial, tarifs, inscription, mentions
  légales, CGU/CGV, politique de confidentialité, contrat de sous-traitance.
- **E1.18** Espace enseignant, onglet « Mon compte » : offre, utilisation (« 3/5 classes, 87/150 élèves »),
  renouvellement, « S'abonner », « Gérer mon abonnement ».
- **E1.19** Bandeaux : essai (jours restants), échec de paiement, retour en Découverte.
- **E1.20** Administration commerciale : liste des comptes avec offre et statut dans l'espace Comptes, tableau de bord
  commercial (lot C), suspension d'un compte, journal. Le tableau de bord Stripe reste la référence pour la facturation.
  *(Remplace « pas d'interface d'administration web en V2 » de la v1.1 : elle existe déjà.)*

### 9.6 Prérequis d'exploitation avant la première vente

- **E1.21** Vrai nom de domaine et e-mail d'envoi sur ce domaine.
- **E1.22** **Sauvegarde automatique** quotidienne de PostgreSQL, chiffrée, hors de la VM (stockage objet UE), 30 jours.
  **Restauration testée**, documentée et chronométrée. Obligatoire aussi **avant chaque migration de données** des lots A et B.
- **E1.23** Supervision : sonde externe sur `/api/health` toutes les 5 min, alerte disque à 80 %, erreurs de l'API consultables.
- **E1.24** Environnement de **recette** distinct (base séparée, clés Stripe de test).
- **E1.25** Hébergement dans l'UE (décision **D6**).

### 9.7 Lot 1-bis — Centres de soutien

Table `organisation`, enseignants rattachés, responsable qui invite par e-mail, facturation au nombre d'élèves
(virement possible), tableau de bord du responsable agrégé par classe et par enseignant.

### 9.8 Recette du lot 1

0. Un compte enseignant ne lit les solutions que des chapitres ouverts dans ses classes.
1. Un enseignant s'inscrit, vérifie son e-mail, crée une classe et inscrit des élèves, sans intervention.
2. Mot de passe oublié : lien à usage unique qui expire ; anciennes sessions fermées.
3. Paiement en mode test : l'offre ne s'active qu'au webhook ; rejouer l'événement ne change rien.
4. Échec de paiement : bandeau, accès maintenu 7 jours, retour en Découverte **sans perte de données**.
5. Plafonds refusés côté API, même en appel direct.
6. Un enseignant ne voit jamais les classes, élèves ni abonnement d'un autre.
7. Sauvegarde restaurée sur une VM vierge, procédure chronométrée.
8. Pages juridiques en ligne, version acceptée enregistrée à l'inscription.

---

## 10. Lot 2 — Préparation aux examens

### 10.1 Cadre réglementaire

Les modalités de l'épreuve anticipée de mathématiques de Première (voie générale avec et sans spécialité, voie
technologique) doivent être **vérifiées au Bulletin officiel en vigueur** avant toute rédaction : partie
« automatismes » et partie « exercices » pour la session 2027, et annonce de questions à réponse courte à partir de la
session 2028.

**E2.0** Une fiche `docs/EXAMENS.md` cite les textes officiels (références, dates) et la structure de chaque épreuve.
Aucun parcours d'examen n'est publié sans elle. Même règle pour l'épreuve anticipée de français quand le domaine
Français lycée sera ouvert.

### 10.2 Modèle et fonctions

- **E2.1** Les parcours `scientifique`, `technologique` et `examens` existent déjà : le lot 2 y ajoute le contenu.
- **E2.2** Questions à réponse courte : contrôle d'équivalence pour les intervalles et ensembles de solutions si besoin.
- **E2.3** Entité **exercice d'examen** : énoncé commun et sous-questions ordonnées, chacune avec type, solution,
  correction et barème ; même cycle de validation (§ 3.3).
- **E2.4** **Devoir assigné** à une classe : chapitres ou exercices, date limite, suivi par l'enseignant.
- **E2.5** **Simulation chronométrée** : temps calculé par le serveur, clôture à la requête suivante après expiration,
  note sur 20 présentée comme une **estimation**, correction détaillée et compétences à retravailler.
- **E2.6** **Vue de classe** : réussite par compétence, compétences les plus échouées, élèves à accompagner (peut être
  avancée au lot 1, décision **D10**).
- **E2.7** Parcours fournis : automatismes de 1re (trois variantes), un sujet complet par variante, au moins 3 sujets
  types de Bac de spécialité rédigés pour PKP.

### 10.3 Recette du lot 2

1. `docs/EXAMENS.md` cite les références officielles à jour.
2. Une simulation se termine à l'heure même si l'élève ferme la page.
3. La note est la somme du barème des réponses justes (test automatisé).
4. Un devoir n'est visible que des élèves de la classe ; la vue de classe que des élèves de l'enseignant.

---

## 11. Lot D — Ouverture des nouveaux domaines

Pour chaque domaine, dans l'ordre des vagues du § 3.1 :
1. référentiel du programme officiel importé (compétences, niveaux) ;
2. contenu produit et validé jusqu'au seuil **D13** ;
3. au moins un validateur habilité qui n'est pas l'auteur principal ;
4. recette des parcours élève et professeur sur ce domaine ;
5. passage à `public`, puis ajout du domaine aux offres.

Le français exige en plus son module d'exercices (EX.5) ; il n'est pas chiffré dans ce document.

---

## 12. RGPD, juridique et propriété intellectuelle

### 12.1 Rôles RGPD

- **Enseignant indépendant ou centre :** responsable de traitement pour ses élèves ; PKP est **sous-traitant** (art. 28),
  avec un **contrat de sous-traitance** accepté à l'inscription.
- **Comptes de l'enseignant, des parents et de l'équipe :** PKP est responsable de traitement.
- **E8.1** Mettre à jour `docs/RGPD.md` : registre des traitements (dont les comptes parents et la table `evenement`),
  durées de conservation, procédure de violation de données (72 h).
- **E8.2** Les élèves restent pseudonymes. Les comptes parents concernent des mineurs : **analyse spécifique avant
  toute offre Famille**, et probablement une analyse d'impact.
- **E8.3** Les noms d'auteurs et de validateurs sont des données personnelles ; s'ils sont publiés dans un dépôt public,
  accord écrit ou pseudonyme stable.

### 12.2 Documents à produire (relecture par un juriste recommandée)

Mentions légales, CGU, CGV, politique de confidentialité, contrat de sous-traitance. L'acheteur est souvent un
**consommateur** (enseignant qui paie de sa poche) :
- **E8.4** Droit de rétractation de 14 jours, ou renonciation expresse recueillie à Checkout (case dédiée, horodatée).
- **E8.5** Médiateur de la consommation désigné, prix affichés TTC.
- **E8.6** Rappel avant chaque reconduction annuelle, résiliation en ligne en quelques clics.

### 12.3 Propriété intellectuelle

Le registre des sources s'applique aux corrigés, aux séances d'anglais, aux sujets d'examen et aux futurs textes de
français : contenus originaux, une source sans licence claire ne sert que d'inspiration, pas de reproduction de
manuels ni de sujets protégés. Les textes littéraires du français devront être libres de droits ou cités dans les
limites légales (décision **D12**).

---

## 13. Exigences transverses

| Domaine | Exigence |
|---|---|
| Architecture | Pile actuelle conservée (React/Vite, FastAPI, SQLAlchemy/Alembic, PostgreSQL, moteur Python, Docker). Nouveaux modules : `app/permissions.py`, `app/domaines.py`, `app/validation.py`, `app/facturation.py`, `app/emails.py`. Migrations numérotées à partir de **0023** |
| Migration | Démarche **étendre → migrer → basculer → retirer** : ajout sans suppression, script de migration reproductible avec contrôles d'intégrité, bascule par réglage, retrait après recette. Sauvegarde vérifiée avant chaque migration de données |
| API | Routes existantes conservées. Un préfixe `/api/v2` seulement pour un contrat incompatible, pas par principe |
| Autorisations | Contrôle côté serveur sur chaque route par `exiger(permission, domaine)` (EX.7) ; cloisonnement par élève, famille, classe et domaine |
| Tests | Suite actuelle exécutée et verte avant chaque lot (référence de non-régression) ; tout nouveau comportement testé ; cas de recette automatisés quand c'est possible |
| Sécurité | Protections existantes maintenues (CSP, HSTS, limitation, TOTP admin) ; secrets dans `.env` ; `npm audit` et **`pip-audit`** en CI |
| Traçabilité | Auteur, action, date, objet et résultat pour les actions sensibles (comptes, habilitations, rattachements, publication) |
| Montée en charge | Un seul processus API suffit pour la V2 ; Redis pour la limitation au-delà |
| Accessibilité | Formulaires étiquetés, clavier, contrastes (cible RGAA AA sur les parcours principaux) |
| Performance | p95 < 500 ms sur les routes élève ; < 1 s à l'ouverture d'un tableau de bord |
| Disponibilité | Objectif 99,5 % mensuel sur la connexion et les séances élèves, mesuré par la sonde externe |

---

## 14. Indicateurs de succès

| Indicateur | Question | Dès le lot |
|---|---|---|
| Couverture validée par domaine | Peut-on vendre ce domaine ? | 0 |
| Délai de relecture | La production suit-elle ? | B |
| Classes et élèves actifs par domaine | Le produit est-il utilisé ? | C |
| Réponses par élève actif et par semaine | Engagement | C |
| Consultation des corrections | Les corrigés servent-ils ? | 0 |
| Parents actifs | L'espace famille a-t-il une valeur ? | C |
| Inscriptions, passage de l'essai au paiement | Les enseignants paient-ils ? | 1 |
| Résiliations et renouvellements | Satisfaction durable | 1 |

S'y ajoutent des entretiens avec les 10 premiers enseignants : temps gagné, fonctions manquantes, prix acceptable.

---

## 15. Décisions à prendre

| # | Décision | Recommandation |
|---|---|---|
| D1 | Premier client : enseignant indépendant ou centre | Enseignant indépendant ; centre en lot 1-bis |
| D2 | Essai gratuit | 30 jours sans carte, puis Découverte |
| D3 | Ne servir que les questions validées en production | Oui, chapitre par chapitre (E0.4) |
| D4 | Prestataire d'e-mails | Hébergé dans l'UE, choisi sur la délivrabilité et le prix |
| D5 | Statut juridique et TVA du vendeur | Avec un comptable, avant la première facture |
| D6 | Hébergeur de production | Une VM dans l'UE ; région à confirmer |
| D7 | Domaines vendus au lancement | Maths lycée seul, ou Maths lycée + Anglais collège |
| D8 | Qui relit, à quel rythme, pour chaque domaine | **À prendre en premier** : elle fixe la date de vente |
| D9 | Ce que donne l'offre Découverte | Tous les chapitres, mais corrigés détaillés, devoirs et vue de classe réservés à l'offre payante |
| D10 | Avancer la vue de classe au lot 1 | Oui |
| D11 | Compte unique pour tous les utilisateurs (proposition V2.0) | **Non** : trois familles de comptes, rôles avec périmètre pour l'équipe (§ 3.2) |
| D12 | Cadrage du français (types d'exercices, textes, auteurs) | Fiche dédiée avant tout développement ; pas avant l'ouverture des vagues 1 et 2 |
| D13 | Seuil d'ouverture publique d'un domaine | Par exemple 80 % des compétences d'au moins un niveau couvertes par du contenu publié |
| D14 | Abonnement par domaine ou tous domaines inclus | Par domaine au lancement, bouquet plus tard |

Ordre conseillé : **D8** et **D5** (elles bloquent la vente), puis **D1**, **D7** et **D9** ensemble, puis les autres.

---

## 16. Risques et effort

### 16.1 Risques

| Risque | Effet | Parade |
|---|---|---|
| Relecture plus longue que prévu (chemin critique) | Retard de la vente | D8 en premier ; vendre d'abord un sous-ensemble 100 % validé |
| Périmètre trop large pour l'équipe | Rien n'est fini | Ordre strict des lots ; un domaine n'ouvre qu'au seuil D13 |
| Régression de la connexion élève ou des séances pendant la migration | Classes bloquées en cours | Comptes élèves inchangés (D11), bascule par réglage, suite de non-régression |
| Migration des rôles incorrecte | Accès perdu ou trop large | Tests sur données de référence, anciennes colonnes conservées une version |
| Offre gratuite suffisante | Personne ne paie | D9 |
| Erreur dans une correction publiée | Perte de confiance | Moteur + relecteur humain, signalement par l'enseignant, versions |
| Incident de paiement non synchronisé | Accès faux | Webhook idempotent, relecture chez Stripe, période de grâce |
| Perte de données | Fatal pour un service payant | Sauvegarde automatique et restauration testée avant la première migration des lots A et B |
| VM unique | Indisponibilité | Supervision et reconstruction scriptée (`deploy/installer-oracle.sh`) |

### 16.2 Ordre de grandeur de l'effort (indicatif, développement seul)

| Lot | Développement | Contenu |
|---|---|---|
| 0 | ~1 semaine | Le plus long : corrigés et relecture de la banque de maths, environ **80 à 120 h** d'enseignant |
| A | ~3 semaines (domaines, habilitations, navigation, parents) | — |
| B | ~2 semaines (versions des questions, cycle commun, file de relecture) | — |
| C | ~2 semaines (statistiques multi-domaines, cinq tableaux) | — |
| 1 | ~3 à 4 semaines | Documents juridiques |
| 1-bis | ~1 à 2 semaines | — |
| 2 | ~3 semaines | Sujets et parcours d'examen |
| D | Par domaine, surtout du contenu | Référentiel et banque complète par domaine |

---

## 17. Historique

| Version | Date | Changements |
|---|---|---|
| 1.0 | 30/10/2026 | Version de cadrage initiale |
| 1.1 | 30/10/2026 | Relecture confrontée au code (faille E1.0, réglage des questions non validées, YAML aligné sur le schéma, Stripe, droit de la consommation, décisions D9 et D10, effort de relecture) |
| 2.1 | 03/11/2026 | Fusion avec la proposition « PKP Éducation V2.0 » du 3 novembre. État des lieux refait sur `origin/main` `75adc1a` (branches déjà fusionnées, parents, versions des leçons, validation anglais, TOTP, E1.0 corrigée). Ajout de l'architecture cible (six domaines, habilitations avec périmètre, bibliothèque et validation unifiées, données d'activité) et des lots A (administration et rôles), B (validation unifiée), C (pilotage) et D (nouveaux domaines). La base devient la référence après import (remplace « contenu uniquement en YAML »). L'admin web est dans le périmètre (remplace E1.20). Migrations à partir de 0023. Compte unique écarté (D11). Décisions D7, D11 à D14. Règle « préparer la vente sans l'annoncer » |
| 2.2 | 03/11/2026 | Validateurs qualifiés par matière (EX.9-bis) : une, deux matières ou plus, par cycle et éventuellement par niveau ; le rôle admin ne donne plus le droit de valider ; contenu sans validateur habilité laissé `soumis` ; migration des admins actuels en validateurs de Maths lycée (EX.8) ; grille de qualifications dans l'écran des comptes (EA.5) ; contrôle serveur EB.0, file de relecture filtrée (EB.3), recette 2-bis |
| 2.3 | 03/11/2026 | Premier incrément du lot A réalisé (§ 6.5). Le rôle admin reste sur `enseignant.role` (EX.6) ; EX.2 reporté ; familles cherchées par e-mail ou par classe, sans liste complète (EA.8) |
| 2.4 | 03/11/2026 | Lot A terminé (§ 6.5) : domaine enregistré (EX.2, migration 0024), sélecteur de domaine et recherche globale (EA.1, EA.2, recette 5), table des permissions (EX.7, EA.3), export des données d'un parent (EA.12), accès des validateurs non enseignants à la validation d'anglais ; EA.4 sans objet |
