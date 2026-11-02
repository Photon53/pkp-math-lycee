# PKP Anglais — Cahier des charges fonctionnel V1.8

**Statut :** cadrage consolidé — à valider pédagogiquement et techniquement  
**Périmètre MVP :** 4e et 3e  
**Durée de référence :** 90 minutes  
**Dépôt :** `Photon53/pkp-math-lycee`  
**Branche de base :** `retours-classes`  
**Public prioritaire :** bénévoles et enseignants intervenant auprès de groupes de 8 à 10 collégiens.

---

## 1. Historique et décisions V1.8

La V1.8 consolide le document de synthèse V1 / CDC V1.7 et les décisions prises pour l'intégration au dépôt PKP Math Lycée.

| Sujet | Décision V1.8 |
|---|---|
| Classes | MVP limité à la 4e et à la 3e |
| Extension | 6e et 5e après retour d'expérience du MVP |
| Durée | 90 minutes de référence ; durée configurable ultérieurement si le besoin est confirmé |
| Groupe | 8 à 10 élèves, niveaux hétérogènes |
| Public utilisateur principal | Bénévoles ; enseignants référents et coordinateurs |
| Mode d'animation | Pack papier autosuffisant, préparé et imprimé avant la séance |
| Saisie des évaluations | Après la séance |
| Différenciation | Trois parcours A / B / C |
| Contenus | Séquences, séances, fiches, grilles et remédiations |
| IA générative | Hors MVP |
| Architecture | Intégration progressive dans le dépôt existant, domaine anglais isolé |
| Référence technique | Branche `retours-classes` au commit de cadrage du 02/11/2026 ; vérifier le SHA avant toute intégration ultérieure |

**Changement important par rapport à V1.7 :** les séances modèles initialement prévues sur 2 heures doivent être adaptées à 90 minutes. Il ne faut pas simplement raccourcir les durées sur le papier : les activités, rotations, temps de parole et modalités d'évaluation doivent être revus et testés.

## 2. Vision et promesse

PKP Anglais est un outil de préparation, d'animation et de suivi pédagogique de séances collectives d'anglais au collège.

**Promesse MVP :** un bénévole non spécialiste peut préparer une séance de 90 minutes, l'animer avec un groupe hétérogène de 8 à 10 élèves à l'aide d'un pack papier autosuffisant, puis saisir les observations essentielles en moins de 15 minutes.

L'application soutient le bénévole ; elle ne remplace ni son jugement ni l'interaction pédagogique en salle.

Principes :
- primauté de la pédagogie et des objectifs observables ;
- consignes compréhensibles par un animateur non spécialiste ;
- priorité à l'oral et à la communication, sans négliger lecture et écriture ;
- différenciation sans étiquetage permanent des élèves ;
- traçabilité des sources, versions et validations ;
- collecte minimale de données sur les mineurs ;
- séparation du domaine anglais et du domaine mathématique.

## 3. Objectifs et exclusions

### 3.1 Objectifs du MVP
1. Mettre à disposition un référentiel anglais versionné pour les classes de 4e et 3e.
2. Fournir une bibliothèque de séances prêtes à animer.
3. Permettre à un bénévole de créer un groupe et d'y inscrire des élèves.
4. Permettre de composer une progression en choisissant et ordonnant des séances.
5. Fournir un pack animateur et un pack élève en PDF.
6. Proposer trois parcours différenciés A/B/C.
7. Permettre la création d'une séance personnelle, le fork d'une séance existante et sa soumission à validation.
8. Permettre la saisie différée d'une évaluation individuelle.
9. Donner au coordinateur une vue de suivi limitée à ses groupes.
10. Garantir que les contenus non validés ne sont pas partagés comme contenus de référence.

### 3.2 Hors périmètre
- classes de 6e et 5e ;
- génération autonome de contenus par IA et chatbot ;
- application mobile native ;
- fonctionnement applicatif hors connexion ;
- intégration ENT et notifications push ;
- suivi longitudinal multi-années ;
- marketplace ou facturation commerciale ;
- remplacement de l'enseignant ou certification automatique d'un niveau CECRL.

Le pack papier doit rester utilisable sans réseau une fois imprimé ; cela ne signifie pas que l'application web fonctionne hors connexion.

## 4. Utilisateurs et rôles

| Rôle | Création du compte | Permissions principales |
|---|---|---|
| Bénévole | Demande, validation par administrateur | Gérer ses groupes, préparer les progressions, créer/forker des séances, générer les packs, saisir les évaluations |
| Enseignant référent | Compte autorisé par l'administration | Relire et valider/refuser les contenus par élément |
| Coordinateur | Compte autorisé par l'administration | Consulter les groupes qui lui sont affectés, progression et observations nécessaires au suivi |
| Administrateur | Créé par un administrateur existant | Gérer comptes, rôles, demandes, référentiels et paramètres |
| Parent | Auto-création, puis rattachement vérifié | Voir uniquement les enfants rattachés, réinitialiser les accès selon les règles, demander une suppression |
| Élève | Créé par le bénévole | Accès de consultation limité si l'espace élève est activé dans le MVP |

**Règle d'autorisation :** aucun contenu non validé ne doit être visible par un autre bénévole que son auteur. Le coordinateur n'obtient pas automatiquement les droits de validation. Les permissions doivent être contrôlées côté API, pas seulement masquées dans l'interface.

Le périmètre parent/élève est conservé comme exigence fonctionnelle issue de V1.7, mais il est secondaire par rapport au pilote animateur : il ne doit pas retarder la validation du parcours central préparer → imprimer → animer → évaluer. Sa livraison doit être explicitement planifiée et testée avant ouverture publique.

## 5. Périmètre fonctionnel détaillé

### 5.1 Référentiel pédagogique
- niveaux : 4e et 3e ;
- version de programme et date d'effet ;
- domaines/activités langagières, compétences, sous-compétences et objectifs observables ;
- prérequis, critères de réussite et exemples de preuves ;
- vocabulaire, fonctions de communication, grammaire en contexte et phonologie ;
- médiation et repères culturels ;
- sources officielles et références des ressources ;
- statut de validation et historique des versions.

Les cinq activités langagières doivent être prises en compte : compréhension de l'oral, compréhension de l'écrit, expression orale en continu, interaction orale et expression écrite. La médiation est également intégrée. Les niveaux CECRL associés aux objectifs sont des repères à justifier par les programmes et ressources officiels applicables ; ils ne doivent pas être présentés comme une certification.

### 5.2 Bibliothèque et création de séances
Une séance comprend au minimum :
- niveau, titre, thème et durée cible (90 min) ;
- objectifs mesurables et compétences ciblées ;
- prérequis et matériel ;
- déroulement séquencé et minuté ;
- consignes animateur (français et/ou anglais selon l'activité) ;
- activités de compréhension, production et interaction ;
- fiches A/B/C et corrigés ;
- erreurs fréquentes et remédiations ;
- grille d'observation/évaluation ;
- sources, auteur, version et statut de validation.

Le bénévole peut :
- utiliser une séance validée ;
- créer un brouillon personnel ;
- forker une séance existante ;
- modifier son fork sans altérer l'original ;
- soumettre le fork à validation.

Une modification d'un élément validé crée une nouvelle version soumise ; elle ne modifie pas silencieusement la version déjà publiée.

### 5.3 Différenciation A/B/C
- **A — Consolidation :** banque de mots, modèles, phrases à compléter, consignes fortement guidées.
- **B — Maîtrise :** production semi-guidée, choix de formulations, questions-réponses et réemploi autonome.
- **C — Approfondissement :** production plus autonome, justification, relance, enrichissement lexical et interaction spontanée.

A/B/C décrivent le niveau d'étayage d'une activité, pas une identité fixe de l'élève. Le bénévole peut faire évoluer un élève d'un parcours à l'autre selon l'objectif et les observations.

### 5.4 Groupes et progression
- création d'un groupe 4e ou 3e par un bénévole autorisé ;
- ajout/retrait d'élèves et identifiants de connexion si l'espace élève est activé ;
- choix nominatif ou pseudonymisé selon le cadre de l'association ;
- sélection et ordonnancement des séances ;
- association d'une séance réalisée à un groupe et une date ;
- suivi des séances prévues/réalisées.

### 5.5 Packs PDF
**Pack animateur :**
- fiche de préparation ;
- déroulement minuté ;
- consignes et réponses attendues ;
- fiches A/B/C ;
- corrigés ;
- erreurs fréquentes et remédiations ;
- grille papier ;
- matériel et préparation en amont.

**Pack élève :**
- fiches de travail A/B/C ;
- documents nécessaires à l'activité ;
- aucun corrigé ni note réservée à l'animateur.

Chaque page porte titre, niveau, identifiant/version, date de génération et statut de validation. Un contenu non validé porte un avertissement explicite « NON VALIDÉ — usage personnel uniquement ». La génération et le téléchargement sont journalisés selon une politique de conservation définie.

Le pack est autosuffisant : l'animateur ne doit pas avoir besoin de réseau, d'un compte ou d'un écran pendant l'animation.

### 5.6 Évaluation et suivi
- grille papier et grille numérique avec libellés identiques ;
- évaluation saisie après la séance ;
- observations factuelles, courtes et limitées aux besoins pédagogiques ;
- critères adaptés à l'objectif de la séance ;
- niveau d'acquisition et prochaine action proposée ;
- export pseudonymisé par défaut ;
- accès nominatif limité aux personnes autorisées.

Ne pas transformer une observation ponctuelle en diagnostic définitif du niveau d'un élève.

### 5.7 Parents et demandes
Si le module est activé dans le MVP :
- parent peut créer un compte ;
- rattachement par code à usage unique ou demande à valider ;
- demande non validée = aucun accès aux données de l'enfant ;
- parent ne voit que les enfants effectivement rattachés ;
- parent peut demander la suppression du compte élève ;
- toute réinitialisation/révocation est tracée ;
- parent ne peut pas modifier les observations pédagogiques.

## 6. Workflow de validation des contenus

| Statut | Visibilité | Utilisation |
|---|---|---|
| Brouillon personnel | Auteur seul | Oui, avec avertissement |
| Soumis | Auteur et référent assigné | Non pour les autres bénévoles |
| Validé partiellement | Bénévoles autorisés du niveau | Oui, avertissement sur les éléments non validés |
| Validé complètement | Bénévoles autorisés | Oui |
| Refusé | Auteur et référent | Non ; motif obligatoire |
| Archivé | Consultation selon droits | Non comme version active |

Validation indépendante par élément :
- référentiel/objectif ;
- déroulé de séance ;
- fiches A/B/C ;
- corrigés ;
- grille d'évaluation ;
- ressources et licences.

Un contenu publié doit avoir un auteur, une version, une date, une source si nécessaire et un validateur distinct de l'auteur. Un fork validé peut devenir la nouvelle version de référence ; l'ancienne version est conservée en archive, sans écrasement.

## 7. Règles de gestion essentielles

1. La durée standard d'une séance MVP est de 90 minutes.
2. Le groupe cible comprend 8 à 10 élèves ; l'application peut signaler un effectif hors cible sans bloquer systématiquement.
3. Chaque séance complète possède des supports A/B/C, un corrigé animateur et une grille adaptée.
4. Chaque objectif est relié à une source et à une version de référentiel.
5. Les programmes applicables peuvent différer selon la classe et l'année scolaire : versionner séparément.
6. Toute modification d'un élément validé crée une nouvelle version à soumettre.
7. Les contenus non validés sont privés à leur auteur, sauf accès de revue du référent.
8. Les packs distinguent clairement les informations animateur et élève.
9. La grille papier et sa saisie en ligne utilisent les mêmes critères.
10. Le bénévole ne voit que ses groupes, sauf délégation explicite.
11. Le coordinateur ne voit que les groupes affectés.
12. Le parent ne voit que les enfants dont le rattachement est validé.
13. Les codes secrets ne sont affichés qu'à leur création/réinitialisation ; seules leurs empreintes sont conservées.
14. Les demandes de suppression sont traitées et tracées selon la politique RGPD validée.
15. Les exports sont pseudonymisés par défaut.
16. Toute action sensible (validation, reset, rattachement, suppression, export) est journalisée.
17. Les droits sont vérifiés côté serveur pour chaque ressource.
18. Une observation pédagogique doit être factuelle, pertinente, non sensible et limitée au besoin.

## 8. Sécurité, données personnelles et RGPD

Les mécanismes existants de PKP Math doivent être réutilisés seulement après vérification de leur adéquation au modèle multi-rôles et aux comptes parents.

Exigences :
- mots de passe adultes hachés avec le mécanisme déjà adopté par le dépôt ; ne pas réimplémenter une seconde solution ;
- jetons et durée de session conformes à la configuration actuelle ;
- limitation des tentatives de connexion et journalisation ;
- codes élèves et codes de rattachement générés avec un alphabet non ambigu, à usage et durée limités ;
- secrets jamais stockés en clair ;
- autorisations testées par rôle et par relation au groupe/enfant ;
- collecte minimale, aucune donnée sensible ;
- conservation et purge documentées ;
- procédure de demande d'accès, rectification et suppression ;
- exports pseudonymisés par défaut ;
- séparation des environnements dev, pilote et production ;
- secrets de production hors dépôt Git.

Le choix nominatif/pseudonymisé par groupe doit être confirmé avec le responsable de traitement/DPO. Le coordinateur n'accède aux observations nominatives que si cette mission et cette habilitation sont formellement définies.

## 9. Critères d'acceptation du MVP

Le parcours pilote est accepté lorsque :
1. un bénévole demande un compte et un administrateur l'active ;
2. un bénévole crée un groupe 4e ou 3e en moins de 5 minutes ;
3. il compose une progression avec des séances publiées et ses brouillons ;
4. il peut créer ou forker une séance, puis la soumettre ;
5. il génère le pack animateur et le pack élève en moins de 10 minutes après sélection du contenu ;
6. le pack est complet et utilisable sans réseau pendant 90 minutes ;
7. les trois parcours A/B/C sont présents et correctement différenciés ;
8. le bénévole peut animer sans assistance technique et déclare pouvoir refaire la séance ;
9. il saisit la grille après séance en moins de 15 minutes ;
10. les contenus non validés ne sont jamais proposés à un autre bénévole comme contenus partagés ;
11. les permissions de bénévole, référent et coordinateur sont testées côté API ;
12. les actions sensibles sont journalisées ;
13. les tests de sécurité parent non rattaché et code expiré passent si le module parent est livré ;
14. les contenus pilotes ont été relus et validés par un enseignant d'anglais.

Le test de séance doit vérifier la durée réelle de 90 minutes, pas seulement le minutage théorique.

## 10. Livrables pédagogiques initiaux

Le document V1/V1.7 indique comme produits :
- référentiel 4e : 10 objectifs (4E-01 à 4E-10) ;
- référentiel 3e : 10 objectifs (3E-01 à 3E-10) ;
- séance modèle 4e « My daily life and my preferences » ;
- séance modèle 3e « Presenting a project » ;
- fiches A/B/C, corrigés et grilles ;
- protocole de test pilote.

**État à confirmer :** ces contenus sont déclarés produits dans le document source, mais leur présence physique, leur exactitude, leur conformité aux programmes en vigueur et leur adaptation à 90 minutes doivent être vérifiées avant import dans le dépôt. Ils ne sont pas considérés automatiquement comme validés.

## 11. Conditions de lancement du pilote

Avant animation :
- référent anglais relit le référentiel et les deux séances ;
- activités, corrigés, consignes et niveau de langue sont vérifiés ;
- les deux séances sont adaptées et testées à 90 minutes ;
- un ou deux bénévoles réalisent un test à blanc ;
- les packs animateur/élève sont imprimés ;
- les retours sont recueillis sans données personnelles excessives ;
- une décision de correction est consignée par élément.

## 12. Décisions ouvertes à ne pas inventer

Les points suivants nécessitent une décision du responsable du projet ou du DPO :
- durée exacte de conservation des observations ;
- périmètre fonctionnel parent/élève livré avant ou après le pilote ;
- règles de délégation coordinateur/bénévole ;
- fournisseur d'email transactionnel et politique de reset ;
- statut exact des contenus pédagogiques existants et licences de chaque ressource ;
- programme officiel de référence et date d'effet par classe ;
- seuils et libellés de la grille d'évaluation.

---
