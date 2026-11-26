# Protocole de relecture et d’essai en séance

Issue #24 — Produit par Codex, 14 novembre 2026.
Statut : proposition opérationnelle à relire ; aucun contenu validé par ce document.
Base documentaire consultée : develop, commit 76307a16ca999520200518d68bac8c276bc4f4cd.

## 1. Objet et limites

Vérifier séparément l’exactitude des contenus, le comportement de la correction automatique et l’utilité en séance, sur un périmètre explicitement identifié. La rédaction de ce protocole ne clôt pas #24 : les essais et leurs preuves restent nécessaires.

Le protocole commun concerne maths, français et anglais, collège et lycée, uniquement pour les contenus et fonctions effectivement disponibles. Il ne constate aucune couverture complète. #54, #55 et #56 portent les audits par matière ; #53 en consolide la couverture ; #14 porte la décision humaine sur les contenus commercialisés.

L’évaluation désigne exclusivement la correction automatique du moteur. Les explications orales et productions ouvertes donnent lieu à une observation pédagogique humaine, sans nouvelle note ni nouveau taux dans la plateforme.

## 2. Préparer un lot

Un lot regroupe un domaine pédagogique, un niveau, un parcours et un chapitre précis. Avant toute relecture, remplir :

| Champ | Valeur à renseigner |
|---|---|
| Domaine / niveau / parcours / chapitre | Codes et intitulés |
| Compétences / attendus | Liste exacte ; référence et année d’application du programme à vérifier |
| Périmètre | Codes des questions, leçons, résumés, méthodes et ressources |
| Version | SHA des fichiers ; pour le contenu modifié en base, identifiant et version ou export daté, sans données élèves |
| Environnement | Local de démonstration ou recette ; version applicative distincte de la version du contenu |
| Auteur / relecteur | Adulte identifié dans le circuit habilité ; relecteur différent de l’auteur |
| Responsable des corrections / seconde vérification | Personnes à désigner |
| Essais | Professeur, objectif de séance, dates et effectifs réellement retenus |
| Exclusions | Contenus ou fonctions indisponibles et raison |

Ne pas confondre le YAML versionné et un contenu modifié en base. Une validation doit porter sur la version réellement présentée. La propagation entre environnements relève de #29 ; ne pas présumer qu’un statut a été propagé.

La proposition historique « troisième, trois blocs de notions, quatre semaines, trois professeurs, environ quinze élèves » reste une hypothèse. Aucun effectif ni calendrier n’est engagé ici. L’affectation des relecteurs et leur rythme relèvent de V2-D8.

## 3. Relecture préalable

Relire chaque leçon, résumé, exemple et question du lot destiné à être retenu, sans extrapoler une validation depuis un échantillon. Une exploration par sondage peut orienter l’audit, mais ses éléments non relus restent non validés.

Pour chaque ligne, consigner conforme, non conforme ou non applicable avec justification et référence de l’objet.

| Contrôle | Vérification attendue | Preuve |
|---|---|---|
| Rattachement | Domaine, niveau, parcours, chapitre, compétence et prérequis cohérents | Référence du contenu et attendu officiel daté |
| Leçon et résumé | Définitions, règles, hypothèses et exemples exacts ; résumé fidèle | Points relus et anomalies éventuelles |
| Consigne | Objectif explicite, données suffisantes, vocabulaire adapté, unité et précision indiquées | Résolution sans consulter le corrigé |
| Solution | Résultat recalculé ou réponse justifiée indépendamment | Résolution du relecteur |
| Corrigé | Étapes justes, conditions explicites, résultat cohérent avec la solution, explication utile | Référence des étapes contrôlées |
| Difficulté | Valeur 1–5 cohérente avec les étapes et prérequis ; progression du lot | Justification des écarts |
| Variété | Questions réellement différentes ; distracteurs plausibles et non ambigus | Comparaison des questions |
| Correction automatique | Réponses correctes acceptées, incorrectes refusées, limites explicites | Cas et verdicts reproductibles |
| Présentation | Formules, accents, illustrations, audio et liens lisibles ; parcours clavier et mobile essayés | Environnement et problème reproduit |
| Provenance | Source, adaptation, licence ou autorisation documentées selon le registre | Référence ; doute renvoyé à #77 |
| Mineurs | Aucun contenu inadapté ni donnée personnelle réelle dans les supports de retour | Contrôle des exemples et pièces jointes |

Les vérifications de programme et de licence sont à effectuer sur leurs sources officielles avant de conclure ; ce protocole ne certifie ni programme ni licence.

### Particularités par matière

| Matière | Contrôles supplémentaires |
|---|---|
| Maths | Domaine de définition, valeurs interdites, unités, signes, arrondis, solutions extrêmes ; équivalence et forme demandée distinguées |
| Français | Texte et contexte exacts, consigne grammaticale précise, variantes recevables, justification de la réponse ; production ouverte sans promesse de correction automatique non disponible |
| Anglais | Contexte et sens, variantes acceptables, orthographe et ponctuation selon la consigne ; audio intelligible et transcription cohérente si présents |

Une réponse ouverte ne devient pas automatiquement un QCM sans relecture de l’objectif pédagogique. Les fonctions non prises en charge sont exclues du parcours automatique ou confiées à un accompagnement humain explicitement annoncé.

## 4. Essais de correction automatique

Utiliser des comptes de démonstration et noter pour chaque cas : objet et version, saisie exacte, verdict attendu, verdict observé, environnement et preuve.

| Cas | Attendu |
|---|---|
| Réponse de référence | Acceptée |
| Autre écriture correcte autorisée | Acceptée |
| Erreur fréquente ciblée | Refusée, avec retour cohérent |
| Valeur interdite ou hors domaine, si applicable | Refusée |
| Saisie vide ou invalide | Message compréhensible, sans blocage de la séance |
| Contrainte de forme ou d’arrondi | Comportement conforme à la consigne et aux capacités réelles |
| QCM | Une seule réponse correcte pour un choix unique ; distracteurs distincts |
| Gabarit variable | Examiner cas limites, zéro, signes, bornes et dénominateurs ; conserver les paramètres du cas défaillant |
| Avant / après soumission | Solution absente avant réponse ; corrigé cohérent après réponse |

La documentation décrit des vérifications automatiques et 50 tirages par gabarit : leur succès ne constitue pas une preuve universelle de justesse. Pour un petit espace de paramètres, recommander un contrôle exhaustif ; sinon analyser les conditions et couvrir les cas limites en complément.

SEC-D2 reste en attente : si la consigne exige une forme développée, factorisée ou simplifiée que le moteur ne distingue pas d’une forme équivalente, signaler le conflit. Le contenu concerné ne reçoit pas d’avis favorable tant que la consigne ou le contrôle n’est pas aligné. Ne pas trancher cette politique à la place du référent.

## 5. Classer et traiter les anomalies

Ces gravités pédagogiques ne remplacent pas les priorités P0/P1 des tickets techniques.

| Gravité | Exemple | Conséquence proposée |
|---|---|---|
| Bloquante | Solution fausse, réponse correcte rejetée, consigne insoluble ou ambiguë, ressource indispensable inaccessible, exposition de données | Retirer l’élément du lot présenté aux élèves jusqu’à correction vérifiée ; signaler immédiatement au responsable |
| Majeure | Étape trompeuse, prérequis essentiel absent, difficulté très mal annoncée | Corriger puis refaire la relecture concernée avant avis favorable |
| Mineure | Coquille sans effet sur le sens, amélioration de présentation | Action tracée avec responsable et échéance ; réserve explicite |

Un doute de provenance suspend l’usage du contenu concerné jusqu’à clarification ; il ne devient pas une simple réserve esthétique. Une exposition de données suit le circuit d’incident, sans recopier les données dans GitHub.

Le retrait s’effectue avec les mécanismes existants de non-publication ou d’archivage par une personne habilitée. Ne jamais supprimer une question. Si le retrait dégrade un parcours, réexaminer le lot entier et sa couverture.

## 6. Circuit de validation

1. Auteur : prépare le contenu et ses sources, sans s’auto-valider.
2. IA éventuelle (#50) : signale incohérences et doutes ; son avis reste une prévalidation.
3. Relecteur humain habilité pour le domaine et le niveau : refait les questions, vérifie le contenu et trace les anomalies.
4. Auteur ou responsable désigné : corrige ; le relecteur vérifie les corrections sur la nouvelle version.
5. Validateur habilité distinct de l’auteur : enregistre la validation dans le circuit existant. Le rôle admin seul ne donne pas ce droit.
6. Publication : suit les permissions et états réellement présents ; aucun nouvel état technique n’est introduit ici.
7. Professeur testeur : effectue les essais en séance ; le propriétaire décide du périmètre commercial dans #14.

Pour les questions YAML, respecter les champs existants : auteur, correction et validation avec statut, par et le. Les conclusions de séance ci-dessous sont des avis documentaires, pas des valeurs à injecter dans ces champs. Une modification substantielle impose une nouvelle relecture avant nouvelle validation ; l’invalidation technique éventuelle doit être vérifiée, pas présumée.

## 7. Fiche d’essai en séance

Ne faire essayer que le lot préalablement relu, sans anomalie bloquante ni majeure ouverte. Prévoir deux ou trois séances selon l’organisation effectivement confirmée.

| Moment | Observation à consigner |
|---|---|
| Préparation | Objectif, supports retenus, durée de préparation et aide nécessaire |
| Démarrage | Connexion et accès au bon chapitre, autonomie du professeur et des élèves, délai avant première question |
| Travail | Consignes comprises, blocages, consultation du cours et des corrigés, reprises utiles |
| Fin | Explication de la démarche et question nouvelle sur la même compétence ; difficultés à reprendre |
| Séance suivante | Court rappel sans le corrigé, avec question nouvelle ; observation des acquis et des oublis |

Noter les durées réelles, nombres de blocages et effectifs observés, sans inventer un seuil de réussite. Si aucune comparaison de temps n’a été mesurée, écrire « temps gagné non mesuré ».

La maîtrise reste le taux 0–1 du moteur, sur les dix dernières réponses avec pondération 0,9 et seuil 0,8. Une réussite isolée, une répétition mémorisée ou un taux élevé ne prouvent pas à eux seuls une rétention durable. Aucun résultat d’essai ne modifie cette formule.

Les retours partagés sont agrégés : pas de prénom, identifiant élève, code de classe réel, réponse nominative ni capture non anonymisée. Aucun export de données élèves vers une IA pour ce protocole. Les observations individuelles nécessaires restent dans les outils autorisés de l’établissement ou de la structure ; ne pas créer de fichier nominatif parallèle.

## 8. Modèles directement utilisables

### Fiche d’anomalie

- Référence : domaine / niveau / parcours / chapitre / compétence / question ou leçon.
- Version du contenu et version de l’application :
- Contexte de démonstration et étapes :
- Saisie synthétique ou paramètres :
- Attendu / observé :
- Gravité et justification :
- Preuve expurgée :
- Correction proposée :
- Responsable / échéance :
- Vérificateur / date / version corrigée / résultat du nouvel essai :
- État de suivi : ouverte, corrigée à vérifier, revérifiée (suivi documentaire uniquement).

### Bilan d’un lot

- Périmètre réellement relu / essayé / exclu :
- Relecteur et validateur, dates et versions :
- Nombre de contenus relus / total du lot ; essais automatiques réussis / exécutés :
- Séances réalisées / prévues et effectifs agrégés :
- Anomalies bloquantes / majeures / mineures encore ouvertes :
- Exemples d’utilité et de difficultés :
- Limites techniques, couverture et réserves :
- Avis : utilisable ; utilisable après correction ; à retravailler.
- Justification :
- Actions restantes, responsables et échéances :
- Décision du propriétaire dans #14 :

« Utilisable après correction » ne vaut pas autorisation de publication : il faut d’abord corriger, revérifier et enregistrer la validation. « Utilisable » ne vaut pas autorisation commerciale.

Après les essais, recueillir séparément l’envie de continuer, le nombre d’élèves envisagé et le prix acceptable. Distinguer intérêt déclaré et engagement payant. Aucune annonce commerciale dans cette phase.

## 9. Critères de clôture de #24

- [ ] Périmètre, testeurs, relecteurs, responsables et dates explicitement renseignés.
- [ ] Grille appliquée à tous les contenus du lot retenu ; éléments non relus exclus de la conclusion.
- [ ] Essais de correction reproductibles et limites documentées.
- [ ] Retours réels de deux ou trois séances disponibles, ou adaptation du protocole explicitement décidée par le propriétaire.
- [ ] Anomalies bloquantes et majeures corrigées puis revérifiées, ou éléments retirés avec réexamen du lot.
- [ ] Validation humaine tracée sur la version exacte, distincte de l’auteur.
- [ ] Bilan et avis documentés par lot ; responsables et échéances des actions restantes.
- [ ] Transmission des conclusions à #14 et #23 ; la décision commerciale reste distincte.
- [ ] Clôture décidée par une personne après vérification des preuves.

## Références internes

- [Ticket #24](https://github.com/Photon53/boussole-maitrise-plus/issues/24)
- [Guide de contenu](CONTENU.md)
- [Architecture](ARCHITECTURE.md)
- [Cahier des charges V2](CAHIER-DES-CHARGES-V2.md)
- [Décisions](DECISIONS.md) : V2-D3, V2-D8, V2-D13, SEC-D2.
- [Données personnelles](RGPD.md)
