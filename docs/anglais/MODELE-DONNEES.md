# PKP Anglais — Modèle de données conceptuel

**Version :** V1.8 — proposition à confronter au schéma réel de la branche  
**Statut :** conceptuel, aucune migration SQL autorisée sur cette seule base.

## 1. Principes

1. Le modèle anglais est isolé du modèle de travail individuel Math.
2. Une séance modèle n'est pas une occurrence de séance collective.
3. Un groupe d'atelier n'est pas automatiquement une classe scolaire.
4. Une observation concerne un élève dans un atelier donné et un objectif identifié.
5. Les contenus sont versionnés ; un fork ne modifie jamais sa source.
6. Les autorisations sont évaluées côté API en tenant compte du rôle et du lien avec le groupe.
7. Réutiliser les tables communes existantes uniquement si leur sémantique et leurs contraintes correspondent exactement.

## 2. Entités

| Entité | Responsabilité | Relations principales |
|---|---|---|
| CurriculumVersion | Version du programme/référentiel par classe et date d'effet | possède domaines et objectifs |
| LanguageDomain | Domaine/activité langagière | possède skills |
| LanguageSkill | Compétence/sous-compétence | possède objectifs |
| LearningObjective | Objectif observable, prérequis, critères et source | lié aux séances et observations |
| Sequence | Progression thématique | regroupe des templates |
| SessionTemplate | Modèle pédagogique d'une séance de 90 min | possède étapes, fiches, grille ; peut être forké |
| SessionTemplateVersion | Version immuable d'un template | statut de validation, auteur, validateur |
| SessionStep | Étape minutée, consigne, activité et modalité | appartient à une version |
| ActivitySheet | Fiche A/B/C, document et corrigé associé | appartient à une version |
| AssessmentGrid | Critères et échelle d'observation | appartient à une version |
| TeachingGroup | Groupe animé et possédé par un bénévole | possède inscriptions et progression |
| GroupStudent | Inscription d'un élève dans un groupe | lie groupe et élève/pseudonyme |
| GroupPlanItem | Position d'une séance dans la progression | lie groupe et template version |
| Workshop | Réalisation réelle d'un template avec un groupe à une date | possède observations |
| Observation | Résultat/observation d'un élève pour un objectif dans un workshop | lie élève, objectif, critère |
| ValidationEvent | Décision de revue par élément | acteur, version, statut, motif, date |

## 3. Relations cardinalités

- Une CurriculumVersion contient plusieurs LanguageDomain.
- Un LanguageDomain contient plusieurs LanguageSkill.
- Un LanguageSkill contient plusieurs LearningObjective.
- Une Sequence regroupe plusieurs SessionTemplateVersion.
- Un SessionTemplate possède plusieurs versions immuables.
- Une version contient plusieurs SessionStep, ActivitySheet et AssessmentGrid.
- Un TeachingGroup est géré par un bénévole propriétaire et peut avoir un coordinateur délégué.
- Un TeachingGroup possède plusieurs GroupStudent.
- Un TeachingGroup possède une progression ordonnée de GroupPlanItem.
- Un Workshop matérialise une séance planifiée/réalisée avec un groupe.
- Un Workshop peut contenir plusieurs Observation.
- Une Observation se rapporte à un seul élève, un objectif et un atelier.
- Une version peut recevoir plusieurs ValidationEvent.

## 4. Attributs minimaux recommandés

### LearningObjective
- id stable et code (ex. 4E-01) ;
- curriculum_version_id ;
- domaine/skill ;
- formulation observable ;
- prérequis ;
- critères de réussite ;
- activités/preuves attendues ;
- repère CECRL si justifié ;
- source, URL, licence et date de consultation ;
- statut et version.

### SessionTemplateVersion
- id, template_id, version ;
- classe, titre, thème ;
- durée cible en minutes (90 par défaut) ;
- objectifs ciblés ;
- prérequis et matériel ;
- auteur, dates ;
- parent_version_id pour le fork ;
- statut de validation ;
- statut actif/archivé.

### SessionStep
- ordre ;
- durée en minutes ;
- objectif associé ;
- type d'activité et compétence langagière ;
- consigne animateur ;
- consigne élève ;
- organisation (individuel, binôme, groupe, classe) ;
- matériel ;
- modalités de différenciation.

### ActivitySheet
- parcours A/B/C ;
- contenu élève ;
- corrigé animateur séparé ;
- consignes et réponses attendues ;
- version et statut de validation ;
- source/licence des documents intégrés.

### TeachingGroup
- niveau 4e/3e ;
- nom non nominatif ;
- propriétaire ;
- coordinateur(s) affecté(s) ;
- mode d'identification des élèves ;
- dates de création/archivage.

### Observation
- workshop_id ;
- group_student_id ;
- learning_objective_id ;
- critère ;
- valeur/niveau ;
- commentaire factuel court facultatif ;
- auteur et horodatage ;
- visibilité et base d'habilitation.

## 5. Contraintes

- La somme des durées des SessionStep d'une séance standard doit être égale à 90 minutes ou afficher explicitement l'écart.
- Une fiche élève ne peut référencer aucun corrigé réservé à l'animateur dans son rendu.
- Une version validée est immuable ; toute modification produit une nouvelle version.
- Un validateur ne peut pas être l'auteur de l'élément qu'il valide, si cette règle est retenue pour le workflow.
- Les inscriptions à un groupe sont uniques selon la règle d'identité retenue.
- Les suppressions et anonymisations doivent respecter les obligations de conservation et les dépendances.
- Les clés étrangères et cascades sont définies explicitement ; aucune cascade de suppression non maîtrisée sur les référentiels.
- Les accès aux observations sont limités par groupe et rôle.

## 6. Questions à résoudre avant DDL

1. L'élève est-il une entité partagée avec le domaine Math ou une identité pédagogique indépendante ?
2. Le groupe d'anglais doit-il réutiliser la table `classe` existante ou être une entité distincte ?
3. Le rôle bénévole est-il un rôle existant étendu ou une nouvelle permission attribuée à un utilisateur ?
4. Les ressources/validations génériques couvrent-elles les versions de séances et les fiches A/B/C ?
5. Quel fournisseur d'email et quel processus de reset sont disponibles ?
6. Quelle durée de conservation est retenue pour les observations et journaux ?
7. Le module parent/élève est-il livré dans le MVP initial ou dans un lot post-pilote ?

Ces questions doivent être tranchées après inspection des modèles, routes, migrations et permissions réels. Ce document ne constitue pas une autorisation de créer directement ces tables.
