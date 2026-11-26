# Registre des décisions — Boussole Maîtrise+

Ce registre **recense** les décisions structurantes du projet, sans les déplacer : chaque entrée renvoie au
document où la décision est argumentée. Il sert à répondre vite à « qu'a-t-on décidé, quand, et pourquoi ? » et à
voir ce qui reste à trancher.

## Comment lire les identifiants

Trois séries de décisions numérotées « D » ont été créées indépendamment, avec des numéros qui se chevauchent.
Pour lever l'ambiguïté, ce registre les **préfixe** ; les documents sources gardent leur numérotation.

| Préfixe | Source | Numéros utilisés |
|---|---|---|
| `SEC-D` | Audit de sécurité, `docs/audit/lot-a-securite.md`, `docs/audit/README.md` | D1 à D3 |
| `V2-D` | Cahier des charges V2, `docs/CAHIER-DES-CHARGES-V2.md` § 15 | D1 à D14 |
| `DEV-D` | Ticket #65 (pipeline DEV GitHub → GCP) et ses commentaires | D1 à D5 |
| `ARCH` | `docs/ARCHITECTURE.md` « Décisions validées » (non numérotées à la source) | — |
| `RGPD` | Décisions du propriétaire sur les données personnelles, consignées dans ce registre et `docs/RGPD.md` | 1 à 3 |

Exemple : « D1 » seul est ambigu ; `SEC-D1` désigne le code personnel des élèves, `V2-D1` le premier client visé,
`DEV-D1` la fusion de la PR #64.

Statuts : **Prise** (arbitrée et appliquée ou en cours d'application), **En attente** (à trancher),
**Suspendue** (décision reportée, avec la raison), **Écartée** (option refusée).

Attention : le tableau « Décisions à prendre » du cahier des charges V2 (§ 15) donne une **recommandation** pour
chacune de ses 14 décisions. Seules celles qui sont appliquées dans le code ou arbitrées par écrit sont
comptées ici comme prises (V2-D3, V2-D11 et arbitrages de présentation de V2-D12) ; les autres restent en attente, recommandation comprise.

## Décisions prises

### Architecture et produit

| Id | Date | Décision | Conséquence | Source |
|---|---|---|---|---|
| ARCH-1 | 2026 (phase 1) | Moteur pédagogique pur, sans dépendance web ni base | `engine/` n'importe ni FastAPI ni SQLAlchemy ; `api/app/db/conversions.py` traduit | `docs/ARCHITECTURE.md` |
| ARCH-2 | phase 3 | Schéma normalisé (8 tables + `lecon`, puis extensions par migrations) | Toute modification de modèle exige une migration Alembic relue à la main | `docs/ARCHITECTURE.md` |
| ARCH-3 | phase 3 | Une question n'est jamais supprimée, elle est archivée | Colonne `archivee`, garde ORM `SuppressionInterdite`, clé étrangère `RESTRICT` | `docs/ARCHITECTURE.md` |
| ARCH-4 | phase 4 ; précisée le 2026-11-14 (#17, #110) | La bonne réponse n'est révélée qu'après soumission. **Précision du propriétaire** : les corrigés sont réservés aux adultes (professeur, administrateur, parent) ; un élève ou un enfant ne voit le corrigé d'une question qu'après y avoir répondu, réponse enregistrée. Vaut pour les maths, l'anglais et le français. **Mode de correction des quiz** (décisions du propriétaire du 2026-11-14, #110) : (1) le professeur ou l'administrateur le choisit pour un groupe ou pour une séance, le réglage de la séance l'emporte ; par défaut, correction **après chaque question**, sinon **à la fin du quiz** ; (2) anglais dès maintenant, français quand son espace élève existera, maths inchangées (déjà corrigées après chaque question) ; (3) « Try again » ouvre un nouvel essai d'entraînement : le professeur voit le **score du premier essai**, figé, et le meilleur score à côté | `QuestionPublique` sans solution ; `ResultatReponse` la renvoie ; fiches PKP Math (`/pkp-math/chapitres`) : `corrige_visible` faux et solution vide côté élève tant qu'aucune réponse n'est enregistrée. Anglais : vue élève sans corrigé ; corrigé du quiz seulement après une réponse à chaque question (#107, corrigé). Mode de correction : `groupe_anglais.mode_correction` et `mode_correction_seance_anglais` (migration `0038`), réponses par question et par essai (`reponse_anglais`), premier score figé (`api/tests/test_mode_correction.py`, #112) ; français : réglage de la classe et du dossier branché depuis #217 (`classe.mode_correction`, `mode_correction_dossier_francais`, migration `0049`) | `docs/ARCHITECTURE.md` |
| ARCH-5 | phase 2 | Maîtrise = taux 0–1 calculé sur les 10 dernières réponses, pondération 0,9, a priori 1, seuil 0,8 | `engine/src/pkp_engine/maitrise.py` ; pas de table dérivée | `docs/ARCHITECTURE.md` |
| ARCH-6 | 2026 | Code, documentation et vocabulaire en **français** | Tables, classes, routes, tests, commentaires en français ; pas de traduction anglaise des concepts | `docs/CONSIGNES-DEVELOPPEUR.md` (constat du dépôt) |
| V2-D3 | 2026-10-30 | Ne servir que les questions validées en production, chapitre par chapitre | **Appliquée dans le code** : réglage `PKP_SERVIR_QUESTIONS_NON_VALIDEES`, choix explicite obligatoire en production (E0.4) | CDC V2 § 15, § 5 |
| V2-D11 | 2026-11-03 | **Pas** de compte unique pour tous les utilisateurs | **Appliquée dans le code** : trois familles de comptes conservées ; rôles avec périmètre via `habilitation` (EX.6 à EX.9-bis, migration 0023) | CDC V2 § 3.2, § 15 |

### Présentation du Français — arbitrages partiels de V2-D12

| Id | Date | Décision confirmée | Conséquence | Source |
|---|---|---|---|---|
| V2-D12 — présentation | 2026-11-14 | Parcours guidé par défaut ; le professeur choisit aussi Bibliothèque ou Objectif brevet, pour un groupe ou une séance. Priorité : séance explicite → groupe → guidé ; option « Hériter du groupe » | À implémenter. Préparation réservée aux adultes, sans ouverture aux élèves. Le reste de V2-D12 demeure en attente | #111 ; [cadrage proposé](francais/CADRAGE-PARCOURS-GUIDE.md) |
| V2-D12 — validation et ouverture pilote | 2026-11-21 | **Circuit du français aligné sur celui de l'anglais** : file de validation dédiée, interdiction d'auto-validation, décisions journalisées, refus motivé ; seule la **version validée** d'un dossier est diffusée et une révision soumise ou refusée ne la remplace pas ; le professeur **ouvre à sa classe** un dossier validé ; seuls les élèves des classes qui ont accès au domaine (classes pilotes, SEC-D6) le lisent, sans corrigé (ARCH-4) | `/francais/validation`, `/francais/dossiers/{code}/classes`, `/francais/eleve/dossiers` ; table `ouverture_dossier_francais` (migration `0048`). Les autres points de V2-D12 (contrat des activités, saisie des réponses, retour humain dans l'application) restent en attente | #212 (décision du propriétaire du 21/11) |
| V2-D12 — activité des élèves | 2026-11-23 | **Parcours du français au niveau de l'anglais** : (1) chaque dossier peut porter un **quiz corrigé par la plateforme** (QCM, corrigé après réponse, ARCH-4), avec meilleur score, score du premier essai et nombre d'essais ; (2) les questions rédigées restent au **retour du professeur**, mais l'élève peut y **répondre en ligne** ; (3) auto-évaluation « Je sais » à quatre niveaux ; (4) progression de la classe par dossier ; (5) mode de correction de la classe ou du dossier (#110, branché pour le français) ; (6) l'administrateur **modifie un dossier dans l'application** (brouillon, soumission, validation par un autre) | Contrat `boussole-francais-dossier/1` étendu (`quiz`, `je_sais`), garde-fou #98 « aucune correction automatique » limité aux questions rédigées ; migration `0049` ; `/francais/eleve/dossiers/{code}/quiz|corriger|auto-evaluation|reponses`, `/francais/classes/*`, `/francais/reponses/{id}/retour`, `/francais/dossiers/{code}/source|brouillon|soumettre`. Réponses rédigées sous RGPD-2 (fermées tant que `PKP_REDACTION_ACTIVE` est faux) | #217 (décision du propriétaire du 23/11 : « quiz + réponses rédigées », G2 à G5) |
| V2-D12 — Mon cours | 2026-11-19 | Rubrique « Mon cours » du français : fiches et liens de la professeure, rattachés aux chapitres et visibles de ses seules classes, au fil de l'ouverture des chapitres. **Pendant le pilote, liens seulement** ; les PDF ne sont pas abandonnés et s'ouvriront après #4 | `GET /cours/mon-cours`, onglet « Mon cours » des classes de français ; PDF refusés côté API pour un chapitre ou une classe de français tant que `PKP_PDF_FRANCAIS_OUVERT` est faux | #180 (décision du propriétaire) |

### Validation des contenus par l'administrateur

| Id | Date | Décision confirmée | Conséquence | Source |
|---|---|---|---|---|
| V2-D15 | 2026-11-23 | **L'administrateur valide les contenus dans toutes les matières** (maths, anglais, français et toute matière ajoutée), sans habilitation de validateur. La **séparation auteur / validateur** reste absolue : personne, administrateur compris, ne valide un contenu dont il est l'auteur. Les décisions restent journalisées. Remplace EX.9-bis pour l'administrateur ; pour les autres comptes, une habilitation de validateur par domaine (et niveau) reste nécessaire. L'administrateur ouvre l'espace Français avec sa session d'administration | `permissions.peut_valider`, `domaines_valides` et `permissions_de` (`contenu.valider`) ; page « Validation » des maths, files de l'anglais et du français, validation des questions dans l'administration ; `auth.adulte_authentifie` | #217 (décision du propriétaire du 23/11, option « toutes les matières ») |

### Sécurité et données personnelles

| Id | Date | Décision | Conséquence | Source |
|---|---|---|---|---|
| SEC-D1 | 2026-10-29 | Chaque élève a un **code personnel** généré par l'enseignant, stocké haché (correction de A-07) | Connexion = prénom + code classe + code personnel ; 5 essais / 15 min par compte ; comptes créés par l'enseignant | `docs/audit/lot-a-securite.md` § « Correction de A-07 (d) » |
| RGPD-1 | 2026-11-13 | **Enfant** : identifié par son **prénom suivi d'un numéro, sans séparateur** (`Lina1`, `Lina2`…), unique sur toute la plateforme, comparé sans casse ni accents (`Léa1` = `lea1`), numéro **jamais réattribué** ; **aucun nom de famille**. Base de l'identifiant : le prénom **sans accents**, lettres d'origine conservées (`à` → `a`, `é` → `e`), identifiant de **40 caractères au plus** (prénom raccourci). Les **identifiants déjà émis sont conservés** ; le nouveau format ne s'applique qu'aux nouveaux comptes. **Parent** : nom et prénom conservés. **Précisions du 2026-11-15 (#87)** : un classeur d'import dont la colonne « Nom » est remplie est **refusé** (rien n'est importé) ; deux homonymes d'une même classe ou d'un même groupe se distinguent par l'**identifiant affiché à la place du prénom** (« Lina2 »), ce qui garde la connexion prénom + code classe (SEC-D1) ; les numéros sont tenus par un **compteur par prénom normalisé**, sans lien vers aucun compte | **Appliquée** (#87) : migration `0039` (colonne `enfant.nom` supprimée, noms affichés et journal nettoyés, table `compteur_identifiant`, index uniques sur `lower(identifiant)`), `enfants.identifiant_libre` (compteur atomique, essais bornés), prénom sans lettre refusé ; limitation des tentatives revérifiée : `docs/audit/rgpd-1-limitation-connexion.md` (limite des échecs par adresse : SEC-D5, appliquée) | #83 (décision du propriétaire), #87 |
| RGPD-2 | 2026-11-19 | **Rédactions des élèves** (cadre du propriétaire pour le pilote) : usage limité à la correction et au suivi ; accès de l'élève et du professeur de sa classe (versions remises), aucun autre ; parents : bilan pédagogique, pas les textes ; conservation jusqu'au 31 août de l'année scolaire, 30 jours après le départ ; export et effacement sur demande (réponse sous un mois) ; sauvegardes : rotation de 30 jours si possible ; sujets fictifs recommandés. **Restent ouverts** : responsable de traitement, base légale, information des élèves et des parents (#183), vérification effective des protections | `models.Redaction` (migration `0044`), `app/routes/redactions.py`, purge et export ; fermé tant que `PKP_REDACTION_ACTIVE` est faux ; détail dans `docs/RGPD.md` § 8 | #179 (décision du propriétaire), #183 |
| SEC-D3 | 2026-10 | Banque de questions commune : tout enseignant peut archiver toute question | Comportement actuel assumé (contrôle A-08) | `docs/audit/README.md`, `lot-a-securite.md` |
| SEC-D4 | 2026-11-15 | **Sauvegardes de production** (GCP et Oracle) : une archive par nuit et avant chaque déploiement, chiffrée avec `age` pour des **clés publiques** (clé principale + clé de secours, privées hors VM), copiée dans un **bucket GCS dédié** par un compte de service qui ne peut que créer des objets ; **rétention 60 jours** ; restauration de contrôle isolée chaque trimestre | `deploy/sauvegarde-prod.sh`, timer systemd, `docs/exploitation/technique.md` T-04/T-05 ; durée de 60 jours à confirmer avec le DPO (`docs/RGPD.md`) | #8 (décision du propriétaire) |
| SEC-D5 | 2026-11-15 | **Échecs de connexion élève limités par adresse** : 60 échecs par adresse et par 15 minutes, toutes routes de connexion élève confondues (carte d'enfant, identifiant, prénom + code classe, anglais), en plus des 300 tentatives par adresse et des 5 échecs par compte. Seuls les échecs comptent : une classe derrière une même adresse n'est pas gênée | `limitation.echecs_eleve_par_ip`, réglage `PKP_CONNEXION_ELEVE_MAX_ECHECS_PAR_IP` ; surveillance globale des échecs et code à 7 caractères non retenus à ce stade (`docs/audit/rgpd-1-limitation-connexion.md`) | #87 (décision du propriétaire) |
| SEC-D6 | 2026-11-19 | **Classes pilotes** (exception à EX.4) : un domaine actif mais fermé au public n'est accessible qu'aux élèves des classes inscrites par un administrateur dans la liste des classes pilotes. Le contrôle est fait **côté API, route par route** (cours, leçons, ressources, documents de chapitre, séances, réponses), y compris par URL directe. **Règle uniforme** (option a du 19/11) : une classe dont le domaine est fermé et qui n'est pas pilote perd aussi la lecture du contenu, en maths comme en français ; sa propre progression et son historique restent consultables. Accès par niveau (enfant de famille, parent) : domaines publics seulement, d'où **aucun accès des parents** au contenu pilote. **Révocation** : accès coupé immédiatement, séance en cours comprise, rien n'est supprimé. Un professeur ne crée toujours pas de classe dans un domaine fermé. **Précisions du 2026-11-19** : quand l'accès de la classe est refusé, l'historique vu par le **parent** ne contient plus ni énoncé, ni solution, ni correction (la réponse de l'enfant et son résultat restent ; option b), et la **progression** vue par l'élève et son parent se limite aux compétences déjà travaillées ; la vue du professeur n'est pas limitée | Table `classe_pilote` (migration `0042`), `permissions.refus_acces_classe`, `progression.ids_ouverts_eleve`, `/admin/classes-pilotes` (journalisé), écran « Classes pilotes » sous « Domaines » ; avant déploiement, vérifier en lecture qu'aucune classe active n'est rangée dans un domaine fermé | #176 (décisions du propriétaire du 19/11) |
| DEV-D5 | 2026-11-13 | **Exception D5 (DEV)** : `boussole-dev-tf-plan` peut lister les objets du bucket de déploiement et leurs métadonnées, mais ne doit jamais lire leur contenu | Contrôle `scripts/controle-acces-sauvegardes.sh` affiche « exception D5 acceptée » ; aucun identifiant personnel dans les noms ni métadonnées des sauvegardes ; réduction des droits suivie dans #74 | #65 (commentaires du 13/11) |

### Pipeline DEV (GitHub → GCP), ticket #65

| Id | Date | Décision | Conséquence | Source |
|---|---|---|---|---|
| DEV-A1 à A8 | 2026-11-11 | Huit arbitrages d'architecture du pipeline : isolation DEV par surcharge Compose, rollback conditionné aux révisions Alembic réelles et aux données, manifestes immuables et pointeur conditionnel dans GCS, rétention Artifact Registry en simulation, fenêtre sans écriture pour sauvegarde et migration, contrôle de version par `docker inspect`, comptes WIF séparés par workflow, réutilisation CI seulement sur le SHA exact | Structure des PR 1 à 4 du ticket | #65, « Arbitrage après revue du 11/11 » |
| DEV-D1 | 2026-11-12 | Intégrer la PR #64 (déploiement manuel durci) avant la PR 3 | Fait : #64 fusionnée | #65 |
| DEV-D2 | 2026-11-12 | Retirer les liaisons IAM historiques du bucket via Terraform, en PR séparée (3a), **option A** : conserver uniquement `projectOwner` → `legacyBucketOwner` | Fait : #71 appliquée, politique vérifiée, PLAN `No changes` | #65, #71 |
| DEV-D3 | 2026-11-12 | En V1, l'état « version déployée » n'est connu que sur la VM (`active.json`, `--etat`, journaux) | Pas de remontée vers GCS pour l'instant | #65 |
| DEV-D5 | 2026-11-13 | Voir « Sécurité » ci-dessus | | |

## Décisions en attente

| Id | Décision à prendre | Recommandation documentée | Qui | Bloque |
|---|---|---|---|---|
| V2-D8 | Qui relit le contenu, à quel rythme, pour chaque domaine | **À prendre en premier** : fixe la date de vente | Propriétaire + référent pédagogique | La vente |
| V2-D5 | Statut juridique et TVA du vendeur | Avec un comptable, avant la première facture | Propriétaire | La vente |
| V2-D1 | Premier client : enseignant indépendant ou centre | Enseignant indépendant ; centre en lot 1-bis | Propriétaire | Lot 1 |
| V2-D7 | Domaines vendus au lancement | Maths lycée seul, ou Maths lycée + Anglais collège | Propriétaire | Lot 1, V2-D13 |
| V2-D9 | Contenu de l'offre Découverte | Tous les chapitres ; corrigés détaillés, devoirs et vue de classe réservés au payant | Propriétaire | Lot 1 |
| V2-D2 | Essai gratuit | 30 jours sans carte, puis Découverte | Propriétaire | Lot 1 |
| V2-D4 | Prestataire d'e-mails | Hébergé dans l'UE, choisi sur délivrabilité et prix | Propriétaire | Lot 1 (inscription) |
| V2-D6 | Hébergeur de production | Une VM dans l'UE ; région à confirmer | Propriétaire | Mise en production |
| V2-D13 | Seuil d'ouverture publique d'un domaine | Par exemple 80 % des compétences d'un niveau couvertes par du contenu publié | Propriétaire + référent | Ouverture de chaque domaine |
| V2-D10 | Avancer la vue de classe au lot 1 | Oui (recommandation du CDC, non actée) | Propriétaire | Périmètre du lot 1 |
| V2-D12 | Reste du cadrage français : contrat des activités hors dossiers (chapitres #177) | Présentation, héritage, validation, ouverture pilote et activité des élèves confirmés ci-dessus ; autres propositions dans la fiche dédiée à relire. EX.4 reste applicable | Propriétaire + référent | Lots suivants du français ; création de groupes non publics avant arbitrage EX.4 |
| RGPD-3 | **Accueil et demandes** (#172, #171) : durée de conservation de chaque file (familles et préinscriptions, informations et questions, candidatures, partenariats), comptée depuis le dernier traitement, CV compris ; responsable de traitement et base légale ; validation des formats et de la taille du CV proposés (PDF seulement, 5 Mo) | Durées courtes, alignées sur chaque finalité (étudier la demande et y répondre) ; la CNIL publie des repères pour le recrutement et la prospection, à confirmer avec un avis spécialisé. Rien n'est collecté dans une file sans durée (`PKP_ACCUEIL_CONSERVATION_JOURS`) | Propriétaire, avis spécialisé (#18) | Ouverture des formulaires (#170, #171) |
| V2-D14 | Abonnement par domaine ou tous domaines inclus | Par domaine au lancement, bouquet plus tard | Propriétaire | Lot 1 (offres) |
| SEC-D2 | Politique de correction : forme exigée (développée, factorisée, simplifiée, libre) par question | Le moteur ne vérifie que l'équivalence ; le lot B de l'audit ne peut pas définir « correct » sans cette règle | Référent pédagogique | Audit lot B |
| DEV-D4 | Retirer `roles/editor` du compte Compute par défaut | Accord de principe ; **suspendu** tant que l'absence d'usage n'est pas démontrée (plusieurs contrôles incomplets) ; prévoir des droits de remplacement | Propriétaire | Rien (sécurité en profondeur) |
| DEV-#74 | Réduire les droits de `boussole-dev-tf-plan` après inventaire des besoins Terraform (option B de D5) | Rôle plus étroit sans permission de liste, bascule sans couper le PLAN | Propriétaire | Rien : l'exception D5 couvre la mise en service DEV |
| DEV-TS | Critère d'acceptation des accès aux sauvegardes : code 0 (confirmé par Policy Troubleshooter) exigé, ou dérogation au code 3 (analyse des politiques seule) | Code 0 exigé ; le diagnostic réel du 13/11 a renvoyé une **évaluation incomplète** (`NOT_GRANTED` avec erreurs), à analyser avant toute conclusion | Propriétaire | Première sauvegarde (PR 3b) |
| CONV-1 | Ajouter un linter et un formateur (ruff, ESLint) en CI | Oui, en PR dédiée après le ticket #65, formatage initial séparé | Propriétaire | Rien |
| CONV-2 | Licence du dépôt (UNLICENSE héritée de la migration) | À examiner avant commercialisation | Propriétaire | La vente |

Ordre conseillé par le cahier des charges : **V2-D8** et **V2-D5** (elles bloquent la vente), puis **V2-D1**,
**V2-D7** et **V2-D9** ensemble, puis les autres.

## Décisions écartées

| Id | Option écartée | Raison | Source |
|---|---|---|---|
| V2-D11 | Compte unique pour tous les utilisateurs (proposition V2.0) | Obligerait à migrer la connexion des élèves, la fonction la plus utilisée et la plus sensible, sans bénéfice | CDC V2 § 3.2 |
| DEV-D5 option B immédiate | Remplacer tout de suite `iam.securityReviewer` de `tf-plan` par un rôle personnalisé | Touche les droits du PLAN qui fonctionne ; demande un inventaire préalable ; ne bloque pas la mise en service | #65, #74 |
| DEV (PR 3a) | Autoriser la liste GCS par préfixe avec `objectListPrefix` dans une liaison conditionnelle | Attribut pris en charge seulement dans les Credential Access Boundaries | #65, commit annulé `f4e119a` |
| Consignes | Code en anglais (`Competency`, `MasteryLevel`…) | Le dépôt est intégralement en français ; deux vocabulaires dans le même code | `docs/CONSIGNES-DEVELOPPEUR.md` |

## Ajouter une décision

Une entrée tient sur une ligne : identifiant préfixé, date, décision, conséquence dans le code ou
l'exploitation, source. La discussion et les options comparées restent dans le document ou le ticket source ;
ce registre ne les duplique pas. Quand une décision en attente est prise, la déplacer dans « Décisions prises »
en gardant son identifiant.
