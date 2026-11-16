# Français 3e — cadrage du parcours guidé et des trois présentations

Issue #111 — Codex — 14/11/2026.
**Statut : spécification proposée pour relecture.** Les décisions du propriétaire sont identifiées ci-dessous ;
les choix techniques et le découpage sont des propositions. Ce document ne prouve aucune implémentation,
validation pédagogique, recette ou ouverture aux élèves.

## 1. Objectif et périmètre

Donner au français une navigation cohérente avec l’anglais et une lecture adaptée aux adolescents :
objectif visible, activité clairement annoncée, rappel de cours accessible et travail découpé.
Cible initiale : **3e, année scolaire 2026-2027, brevet général de juin 2027**.
L’interface ne doit pas annoncer une couverture complète lorsque seules quelques ressources existent.

### Décisions confirmées par le propriétaire

| Sujet | Décision |
|---|---|
| Présentation par défaut | **Parcours guidé** |
| Autres présentations | **Bibliothèque** et **Objectif brevet** |
| Qui choisit | Le professeur |
| Périmètre du réglage | Un groupe ou une séance ; pas de surcharge individuelle par élève |
| Priorité | Séance explicite, sinon groupe, sinon parcours guidé |
| Retour à l’héritage | Option **Hériter du groupe** sur la séance |
| Activités attendues | Rappels, quiz, questions à réponse rédigée, dictées, conjugaison, grammaire et lexique |
| Déploiement actuel | Français actif pour l’équipe, fermé aux élèves ; préparation en DEV |

Le choix d’affichage ne règle ni le moment de correction (#110), ni la validation ou la publication des contenus.
L’élève ne reçoit pas de sélecteur des trois modes dans ce périmètre.

## 2. État vérifié du dépôt

Base examinée : `develop` à `faf854dec90c816eab9c0d7cf8620a22357522bb`.

| Élément | Existant | Conséquence |
|---|---|---|
| Contenu | `api/app/francais.py`, contrat `boussole-francais-dossier/1` | Garder la compatibilité et l’import idempotent |
| Stockage | `DossierFrancais`, `DossierFrancaisVersion`, migration 0037 | Référencer une version ; ne pas recopier les dossiers par présentation |
| Réponses | Mode `retour_humain` seulement ; aucune réponse française stockée | Ne pas annoncer de quiz corrigé, d’envoi au professeur ou de sauvegarde d’élève déjà disponible |
| API | `api/app/routes/francais.py` : adultes habilités, aperçu séparé des supports professeur | Préserver les refus existants et les corrigés séparés |
| Interface | `web/src/francais/EspaceFrancais.jsx` : liste, aperçu, supports, historique/validation | Étendre l’espace existant, sans remplacer les écrans de validation |
| Groupes/séances français | Pas de module opérationnel identifié dans les fichiers examinés | Un sélecteur visuel seul ne constitue pas un réglage persistant de groupe/séance |
| #110 | Réglage distinct du mode de correction, PR #112 préparée par Claude | Relire son état courant avant toute extension ; ne pas recréer un système concurrent |

Les sorties VM et retours d’interface antérieurs sont suivis dans #98 et #102. Cet examen est statique ;
aucune base réelle ni configuration GCP n’a été consultée.

## 3. Organisation pédagogique commune

Une banque de ressources, plusieurs entrées de navigation. Proposition :
**grammaire**, **conjugaison**, **orthographe et dictées**, **lexique**, **lecture et interprétation**,
**écriture**, **culture littéraire et oral**. Une ressource peut être reliée à plusieurs entrées sans duplication.

Les codes documentaires locaux de la matrice ne sont pas des identifiants officiels du programme.
Une fiche indique son niveau, ses objectifs, ses prérequis et son statut de relecture.
Une durée reste « proposée » tant qu’elle n’a pas été éprouvée en séance.

Références institutionnelles à conserver dans le suivi de couverture :
- [Attendus Éduscol de fin de troisième](https://eduscol.education.gouv.fr/sites/default/files/document/17-francais-3e-attendus-eduscolpdf-74685.pdf).
- [Entrée en vigueur des nouveaux programmes, article 3](https://www.education.gouv.fr/bo/2026/Hebdo10/MENE2602912A) :
  nouveau programme de français de troisième à la rentrée 2028-2029, pas en 2026-2027.
- [Définition des épreuves du DNB à compter de 2027](https://www.education.gouv.fr/bo/2026/Hebdo4/MENE2623228N).

Nomad Éducation a servi de référence d’organisation (mini-cours, quiz, dictées), pas de source à reproduire.
Les cours, textes et questions Boussole gardent leur propre registre des sources.

## 4. Écrans et comportements

### Écran professeur : préparer

Navigation proposée : **Dossiers**, **Aperçu du parcours**, puis **Groupes et séances** lorsqu’ils seront implémentés.
Conserver l’accès aux supports professeur et au circuit de validation.

Sur le futur groupe :
- choix entre Parcours guidé, Bibliothèque et Objectif brevet ;
- libellé « Présentation du groupe » et aide sur les séances qui héritent ;
- sauvegarde explicite, confirmation du serveur, message d’erreur sans changement local trompeur.

Sur la future préparation de séance :
- sélecteur **Hériter du groupe / Parcours guidé / Bibliothèque / Objectif brevet** ;
- afficher le mode effectif et son origine, par exemple « Bibliothèque — choix du groupe » ;
- afficher séparément le mode de correction de #110 ;
- aperçu accessible avant utilisation, avec mention « Aperçu réservé aux adultes ».

### Parcours guidé

| Étape | Présentation attendue |
|---|---|
| Je comprends | Objectif, rappel court, exemple expliqué ; texte numéroté s’il y en a un |
| Je mémorise | Règles essentielles et questions de rappel ; pas d’obligation de relire tout le cours |
| Je m’entraîne | Une activité à la fois, consigne, type de réponse et accès au rappel |
| Je me dépasse | Réinvestissement sur un autre texte ou une transformation nouvelle |
| Je vérifie | Liste de relecture et bilan des activités ; retour aux notions à reprendre |

Indiquer « étape 3 sur 5 » ou « activité consultée », jamais transformer ces états en taux de maîtrise.
Le rappel reste accessible sans effacer le travail en cours. Une réponse rédigée n’est pas présentée comme
automatiquement juste ou fausse.

### Bibliothèque

Entrée par notion ; fiche avec objectifs, rappel, activités disponibles et corrigés dans l’espace adulte.
Filtres utiles : catégorie, niveau et type d’activité, seulement quand le volume le justifie.
Les ressources absentes ont un état explicite « à préparer », sans bouton d’exercice factice.
Changer la navigation ne doit ni créer une nouvelle copie du contenu ni réinitialiser une réponse.

### Objectif brevet

Ateliers : **texte et langue**, **dictée**, **rédaction** ; rappels de grammaire, conjugaison et lexique associés.
Une activité isolée est appelée « atelier », pas « sujet blanc complet ».
Les sujets complets n’apparaissent comme tels que lorsque textes, questions, consignes, audio requis et
corrigés ont été préparés et relus. Le découpage éditorial d’un site tiers ne devient pas un barème officiel.
Pas de note estimée ni de chronomètre d’examen dans le premier lot d’aperçus.

### Ergonomie et accessibilité

Reprendre les composants et la charte de l’anglais, sans copier ses règles de score.
Texte avec largeur de lecture raisonnable, interlignage confortable, numéros de ligne lisibles.
Sur ordinateur, texte et question peuvent être rapprochés ; sur téléphone, basculer entre eux sans perdre la saisie.
Aucune information essentielle dépendant uniquement d’une couleur.
Libellés de formulaire, ordre de tabulation, focus visible, état de chargement, erreur et état vide explicites.
Tester à 360 px et sur écran large ; aucun défilement horizontal pour les consignes et contrôles.

## 5. Réglages : contrat fonctionnel

Noms techniques proposés, **non existants à ce jour** :

| Champ | Valeurs |
|---|---|
| `mode_affichage` d’un groupe français | `guide`, `bibliotheque`, `brevet` |
| Surcharge de séance | Même ensemble ou absence de surcharge |
| Mode effectif | Surcharge séance, sinon groupe, sinon `guide` |
| Origine | `seance`, `groupe`, `defaut` |

L’absence de surcharge est une information distincte d’un choix explicite `guide`.
Si un groupe change de mode, une séance explicitement réglée conserve son choix.
Si la séance hérite, son aperçu utilise le nouveau mode du groupe.
La remise à « Hériter du groupe » ne touche ni aux contenus ni aux réponses.

**Proposition pour les futurs essais d’élèves :** figer le mode effectif au démarrage d’un essai afin de ne pas
modifier son affichage en cours de travail ; appliquer les changements aux nouveaux essais.
Ce comportement n’a pas encore été arbitré : le premier lot adulte ne crée aucun essai réel.

## 6. Activités, saisie et correction : limites à respecter

| Activité cible | Comportement proposé | Premier lot adulte |
|---|---|---|
| Rappel de cours | Règle, exemple et erreur fréquente ; résumé disponible pendant l’activité | Réutiliser les sections existantes |
| Quiz QCM | Réponse enregistrée côté serveur, puis corrigé selon #110 | Ne pas transformer les questions rédigées actuelles en QCM ; si aucun quiz original n’existe, ne pas en inventer un dans l’interface |
| Réponse rédigée | Zone de texte, consigne de justification, retour du professeur | Présenter un aperçu de la consigne ; pas d’envoi ni de sauvegarde d’élève |
| Réécriture/conjugaison | Consigne précise et justification ; correction automatique uniquement si contrat et moteur adéquats définis | Retour humain conformément au contrat actuel |
| Dictée | Lecture intégrale, groupes de mots, relecture ; texte/corrigé protégés | Pas de lecteur actif sans vrai audio ; afficher les ressources disponibles |
| Lexique | Sens en contexte, familles, nuances et réemploi | Classer les ressources existantes, signaler ce qui reste à produire |
| Rédaction/oral | Préparation, production et retour humain | Supports professeur et consignes ; aucun enregistrement audio d’un mineur |

ARCH-4 : un futur élève ne reçoit aucun corrigé avant l’enregistrement de sa réponse.
Ne pas envoyer le texte de dictée ou ses corrigés cachés dans le DOM/JSON avant le moment autorisé.
Le moment de correction (#110) ne donne pas le droit d’annoncer une correction automatique de texte libre.
L’accès parent au français n’est pas ajouté par ce cadrage.

**Contrat d’import :** la version 1 refuse les champs de solution automatique et n’accepte que `retour_humain`.
L’ajout de QCM ou d’audio exige un contrat versionné documenté, un import rétrocompatible et ses tests.
Ne pas retirer la validation stricte pour faire entrer les nouveaux types.

## 7. Habilitations et données

Reprendre les familles de comptes existantes ; ne pas donner au jeton admin le rôle d’un jeton professeur.
Consultation des dossiers : comportement existant conservé, avec contrôle du domaine et du niveau.
La préparation de séances d’un groupe exigera le rôle de professeur habilité et la propriété du groupe ;
le rôle de validateur seul n’autorise pas à administrer les groupes.
Un administrateur ne valide pas un contenu sans habilitation de validateur ; auteur et validateur restent distincts.

Sur les futurs réglages persistants, prévoir refus côté serveur et 404 sur un objet hors périmètre.
Toute route nouvelle applique les contrôles de permission du projet et les règles de domaine.
Journaliser auteur, objet, ancien/nouveau mode et date sans enregistrer le texte des réponses dans les journaux.

Pas de nom de famille ni d’e-mail d’enfant, pas de nouvel identifiant individuel, pas de service IA externe.
Le premier lot ne conserve aucune saisie d’élève, même dans localStorage.
Toute future conservation de texte libre ou de réponse par question nécessite les règles de rétention,
effacement/export/purge et la documentation RGPD de l’implémentation. Le réglage de présentation n’est pas un score.

## 8. Point à arbitrer : groupes dans un domaine fermé

Le CDC V2 **EX.4** refuse la création de groupes professeur pour un domaine non public.
Le propriétaire demande de préparer le français en DEV sans ouvrir le domaine aux élèves.

Il ne faut ni rendre le domaine public pour contourner cette règle, ni créer silencieusement une exception.
Pour le **lot A**, les aperçus restent réservés aux adultes, avec scénarios groupe/séance de démonstration
sans création de groupe opérationnel ni inscription d’élèves.

Avant la persistance de nouveaux groupes français (**lot B**), le propriétaire doit choisir :
1. autoriser explicitement des **groupes de préparation sans élèves**, sur un domaine actif/non public,
   avec exception EX.4 documentée et tests spécifiques — recommandation ;
2. réserver la création de groupes opérationnels au futur lot d’ouverture du domaine ; conserver seulement
   les aperçus jusque-là.

Cette question ne remet pas en cause les trois présentations choisies. Elle empêche seulement d’implémenter
un CRUD de groupes dans le domaine fermé sans décision tracée.

## 9. Découpage proposé pour Claude Code

| Lot | Livraison | Hors périmètre / dépendance |
|---|---|---|
| A — Aperçus adultes | Trois présentations des dossiers disponibles, parcours guidé par défaut, simulation explicite de l’héritage groupe/séance, charte commune, supports/historique conservés | Pas de persistance des réglages de groupe, pas de groupe réel ni réponse élève |
| B — Réglages persistants | Modèle et migration de préparation groupe/séance, mode effectif calculé côté serveur, contrôles et journal ; reprendre #110 pour le réglage distinct de correction | Choix EX.4 du § 8 nécessaire avant cette partie ; architecture des entités à proposer avant code |
| C — Activités enrichies | Contrat rétrocompatible pour quiz/audio, contenus originaux, vrais supports et parcours de retour humain | Pas de récupération des contenus Nomad ; pas de correction IA implicite |
| D — Futur espace élève | Authentification, réponses/essais, reprise, accès aux corrections, export/purge et tests d’isolement | Décision et recette distinctes ; aucune ouverture par les lots A–C |

Le lot A doit annoncer ses limites : « Simulation de présentation — réglages non enregistrés ».
Ne pas stocker une configuration prétendument persistante dans le navigateur.
Les modes Objectif brevet et Bibliothèque n’inventent aucun exercice : ils réorganisent les ressources réellement disponibles.

## 10. Critères de recette

| Code | Scénario | Attendu |
|---|---|---|
| FR-01 | Aucun réglage explicite | Parcours guidé, origine « Par défaut » |
| FR-02 | Groupe Bibliothèque, séance héritée | Bibliothèque, origine « Groupe » |
| FR-03 | Groupe Bibliothèque, séance Objectif brevet | Objectif brevet, origine « Séance » |
| FR-04 | Retirer la surcharge de séance | Mode du groupe retrouvé |
| FR-05 | Changer le groupe avec séance explicitement réglée | Surcharge conservée |
| FR-06 | Changer de présentation sur le même dossier | Même code/version, aucun contenu dupliqué, aucun travail effacé |
| FR-07 | Parcours guidé | Cinq étapes accessibles, rappel consultable, type d’activité visible |
| FR-08 | Dossier partiel en mode brevet | « Atelier » ; pas d’annonce de sujet complet ni note fictive |
| FR-09 | Aperçu adulte vs supports professeur | Aperçu sans corrigés ; supports et historique toujours accessibles aux adultes autorisés |
| FR-10 | Jeton élève/enfant/parent/anonyme sur les routes de préparation | Refus ; domaine reste non public |
| FR-11 | Professeur hors domaine/niveau ; identifiant d’autrui | Refus serveur, sans divulgation d’objet hors périmètre |
| FR-12 | Mobile, clavier et retour au texte | Pas de débordement, focus utilisable, saisie préservée lorsqu’elle existera |
| FR-13 | Contrat d’import v1 existant | Import et répétition inchangés ; pas de nouvelle version par simple changement de présentation |
| FR-14 | Nouveaux lots quiz/audio | Aucune solution avant réponse enregistrée ; couverture #110 et absence de fuite audio/texte |
| FR-15 | Lot A | Simulation clairement étiquetée ; aucun groupe/élève/réponse créé ; aucun réglage persisté |
| FR-16 | Non-régression | Maths/anglais/admin/parents et validation français inchangés |

FR-01 à FR-05 sont d’abord testés sur les scénarios explicites du lot A, puis repris en API dans le lot B.
FR-06 ne constitue pas une preuve de conservation de réponses réelles avant le lot D.
FR-14 reste un critère de lots futurs, pas une case à cocher dans le lot A.

## 11. Passage de relais à Claude Code

1. Lire AGENTS.md et les références ; comparer ce cadrage au code courant et aux PR de #110.
2. Commencer par le **lot A seulement** : une branche depuis develop, PR en brouillon, Refs #111.
3. Réutiliser les dossiers, leurs versions et leurs vues séparées ; étendre la page française existante.
4. Présenter les trois modes et l’héritage dans une simulation adulte clairement identifiée.
5. Garder les supports professeur et la validation accessibles, avec leurs autorisations existantes.
6. Ne créer ni groupes réels ni réponses d’élèves ; ne pas modifier `actif`/`public`, la production ou les droits IAM.
7. Ajouter les tests de navigation, calcul de priorité, séparation des corrigés et non-régression pertinents.
8. Exécuter la CI complète requise et documenter les tests impossibles sans les annoncer réussis.
9. Documenter ce qui est préparé, fusionné, publié, déployé, importé et vérifié ; ne pas fusionner la PR.
10. Signaler dans #111 les écarts, résultats et blocages ; le lot B attend l’arbitrage EX.4.

Cette consigne prépare un travail relisible ; elle n’envoie aucun message à Claude et ne lance aucune session.

## 12. État et éléments encore ouverts

| Élément | État |
|---|---|
| Présentations et priorité groupe/séance | Confirmées par le propriétaire, à implémenter |
| Fiche détaillée | Présent document proposé à la relecture |
| Contrat QCM/audio | À spécifier dans le lot C ; v1 inchangée |
| Groupes de préparation non publics | Arbitrage EX.4 à prendre avant lot B |
| Changement pendant un essai réel | Gel au démarrage recommandé ; décision avant lot D |
| Cadre de stockage des réponses libres | À spécifier avant lot D |
| Relecture des contenus, audio et couverture | À suivre dans #55/#24, pas attestée ici |
| Ouverture aux élèves | Non autorisée par ce cadrage |

Liens : [contrat actuel](FORMAT-IMPORT.md), [matrice initiale](3e-brevet-2027/MATRICE-INITIALE.md).

---
Spécification rédigée par **Codex** pour #111. Les contributions de contenu et d’intégration précédentes
restent attribuées à leurs auteurs ; aucun code, migration, contenu pédagogique ou configuration déployée modifié.
