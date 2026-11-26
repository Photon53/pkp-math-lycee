# Checklist RGPD — PKP Math Lycée

Les utilisateurs sont des **mineurs**. Cette checklist recense ce que le logiciel fait et
ce qui reste à la charge de l'établissement. Elle ne remplace pas l'avis du **délégué à la
protection des données (DPO)** de l'établissement ou de l'académie, à qui elle doit être
soumise avant la mise en service.

Légende : ✅ assuré par le logiciel (et testé) · ☐ à faire par l'établissement / l'hébergeur

## 1. Minimisation des données

| | Point | Où |
|---|-------|----|
| ✅ | Élève : prénom + classe uniquement (ni nom, ni email, ni date de naissance) ; un code personnel de 6 caractères, généré par l'enseignant et stocké haché, protège son compte | `models.Eleve`, `ConnexionEleve` |
| ✅ | Enfant (famille) : **aucun nom de famille** ; identifiant = prénom + numéro sans séparateur (`Lina1`), unique sur la plateforme, comparé sans casse ni accents, numéro jamais réattribué (décision RGPD-1, appliquée par #87). Migration `0039` : colonne `enfant.nom` supprimée, noms effacés aussi des noms affichés en classe (« Lina D. » → identifiant) et du journal d'administration ; un nom saisi est refusé par l'API et par l'import. Compteur des numéros (`compteur_identifiant`) : base de prénom normalisée et dernier numéro, sans lien vers aucun compte. Les identifiants déjà émis (`lina-k7m4`) restent valables | `models.Enfant`, `app/enfants.py`, `app/import_familles.py`, migration `0039` |
| ✅ | Prénom limité aux lettres, espaces, tirets, apostrophes (50 car.) | `schemas.py` |
| ✅ | Enseignant : nom, email, empreinte du mot de passe | `models.Enseignant` |
| ✅ | Parent : email, **nom et prénom** (facultatifs, vides pour les comptes antérieurs), empreinte du mot de passe, date de dernière connexion, enfants suivis (ni téléphone ni adresse) ; compte créé par le professeur ou l'administrateur, sans envoi de courriel | `models.Parent`, `app/parents.py` |
| ✅ | Justification du nom et du prénom du parent (décision RGPD-1) : le parent est un adulte, responsable légal ; son nom permet à l'administrateur et au professeur d'identifier sans ambiguïté le titulaire du compte qui suit l'enfant, de rapprocher les lignes d'un import de familles et de traiter une demande d'exercice des droits. Ces données ne sont visibles que des adultes habilités et sont effacées avec le compte parent | `models.Parent`, `app/import_familles.py` |
| ✅ | Diagnostic des acquis (#162) : passation (début, fin, question en cours) et réponses de l'élève aux questions de diagnostic (texte saisi, statut juste / faux / « je ne sais pas » / en attente de correction, date, durée de réponse, professeur correcteur), dans des tables séparées de la progression ; supprimées avec l'élève, incluses dans son export. Le **dépôt de copies** (image, PDF) n'existe pas encore : durée de conservation et accès à décider avant le lot 4 | `models.ObservationDiagnostic`, `app/diagnostic.py`, migration `0040` |
| ✅ | Aucun traceur, aucune police ni script tiers (CSP `default-src 'self'`) | `deploy/Caddyfile` |
| ✅ | Session navigateur en `sessionStorage` : fermer l'onglet déconnecte (postes partagés) | `web/src/stockage.js` |
| ✅ | Consigne aux familles : **uniquement le prénom** de l'enfant. Le formulaire n'a plus de champ nom ; le modèle d'import n'a plus de colonne « Nom », et un ancien classeur qui la remplit est refusé sans rien enregistrer (#87) | `EnfantsFamille.jsx`, `app/import_familles.py` |

## 2. Durée de conservation

| | Point | Où |
|---|-------|----|
| ✅ | Purge automatique des élèves inactifs depuis `PKP_RETENTION_JOURS` (365 par défaut), quotidienne | `app/purge.py`, service `purge` |
| ✅ | Compte parent supprimé dès qu'il ne suit plus aucun enfant (retrait par le professeur, suppression ou purge de l'élève) | `parents.supprimer_orphelins` |
| ✅ | Simulation avant purge : `python -m app.purge --simulation` | `app/purge.py` |
| ✅ | Suppression d'une classe entière (fin d'année) | `DELETE /enseignants/classes/{id}` |
| ✅ | Journaux serveur (contiennent des IP) bornés à 3 × 10 Mo par service | `docker-compose.yml` |
| ☐ | Fixer la durée de conservation avec le DPO et l'inscrire au registre | `.env` |
| ☐ | Durée de conservation des **sauvegardes** alignée (une sauvegarde contient des données purgées) : **60 jours** décidés par le propriétaire (15/11/2026, #8), à confirmer avec le DPO et à inscrire au registre | cycle de vie du bucket, `docs/exploitation/technique.md` T-04 |

## 3. Droits des personnes

| | Droit | Mise en œuvre |
|---|-------|---------------|
| ✅ | Accès et portabilité | Bouton « Exporter » (JSON complet : séances, réponses, progression, réponses au diagnostic) |
| ✅ | Effacement | Bouton « Supprimer » : élève, séances et réponses ; son jeton cesse de fonctionner |
| ⚠️ | Rectification | Pas d'édition du prénom : supprimer puis l'élève se reconnecte (l'historique est perdu) |
| ☐ | Procédure de traitement des demandes (qui reçoit, délai d'un mois) | — |

## 4. Sécurité

| | Point | Où |
|---|-------|----|
| ✅ | HTTPS obligatoire, certificat automatique, HSTS | `deploy/Caddyfile` |
| ✅ | Mots de passe enseignant hachés (scrypt N = 2¹⁷, r = 8, p = 1 selon OWASP, sel aléatoire), re-hachés à la connexion si plus faibles ; 12 caractères minimum | `app/security.py`, `app/admin.py` |
| ✅ | Jetons signés (HMAC-SHA256), durée limitée (12 h élève, 8 h enseignant) ; jetons enseignant invalidés par un changement de mot de passe | `app/security.py`, `app/auth.py` |
| ✅ | Démarrage refusé en production sans clé secrète forte, avec SQLite ou avec CORS ouvert | `app/config.py` |
| ✅ | Limitation des tentatives : 5 échecs / 15 min par compte enseignant ; 30 codes classe faux / 15 min par IP | `app/limitation.py` |
| ✅ | Cloisonnement : un enseignant ne voit que ses classes (404 sinon) ; un parent ne voit que ses enfants, et plus rien si le professeur est désactivé | `routes/enseignants.py`, `routes/parents.py` |
| ✅ | Parent : mot de passe provisoire à changer à la première connexion (12 caractères minimum), 5 échecs / 15 min par compte, jeton invalidé par un changement ou une réinitialisation ; réinitialisation par un administrateur journalisée ; par un professeur, seulement si le parent ne suit que ses élèves (#114). La carte d'un enfant de famille n'est renouvelée que par l'administrateur ou le parent (#115) | `routes/parents.py`, `routes/admin.py` |
| ✅ | Code choisi par le parent pour l'enfant : 8 à 16 lettres et chiffres, au moins une lettre et un chiffre, 4 caractères différents, sans le prénom ni l'identifiant ; stocké haché ; l'ancien code et les sessions de l'enfant cessent de fonctionner | `security.probleme_code_choisi` |
| ✅ | Messages de connexion identiques que le compte existe ou non | `routes/enseignants.py` |
| ✅ | API et base non exposées sur Internet (réseau Docker interne) | `docker-compose.yml` |
| ✅ | Documentation OpenAPI désactivée en production | `app/main.py` |
| ☐ | Hébergement dans l'Union européenne, contrat de sous-traitance avec l'hébergeur | — |
| ☐ | Sauvegardes chiffrées et testées (restauration) : chiffrement `age` à clés publiques (la VM ne peut pas relire), copie hors VM, restauration isolée scriptée ; à cocher après la première restauration de contrôle en production (#8) | `deploy/sauvegarde-prod.sh`, `docs/exploitation/technique.md` T-04/T-05 |
| ☐ | Mises à jour de sécurité du serveur et des images Docker | — |

## 5. Information et formalités

| | Point |
|---|-------|
| ✅ | Mention à la connexion élève : « Seuls ton prénom et ta classe sont enregistrés. » |
| ☐ | Page de mentions d'information complète (responsable, finalité, base légale, durée, droits, contact DPO) — **à rédiger avec le DPO**, puis à lier depuis l'écran de connexion |
| ☐ | Inscription du traitement au registre des activités de traitement de l'établissement |
| ☐ | Information des familles (ENT, carnet de liaison…) |
| ☐ | Base légale à confirmer par le DPO (vraisemblablement mission d'intérêt public de l'établissement) |

## 6. Espace parents (lot 3) — à valider avant ouverture

L'espace parents ajoute une donnée personnelle nouvelle (l'**adresse e-mail d'un adulte**) et un
nouveau destinataire des données de l'élève (ses progrès, son historique, son temps de travail).
Le cahier des charges (E8.2) prévoit pour ce lot une analyse spécifique. Avant de créer les premiers
comptes parents en production :

| | Point |
|---|-------|
| ☐ | Avis du DPO sur l'espace parents ; analyse d'impact (AIPD) si le DPO l'estime nécessaire (mineurs, suivi de l'activité) |
| ☐ | Mise à jour du registre : nouvelle catégorie de personnes (responsables légaux), nouvelle donnée (e-mail), nouveaux destinataires |
| ☐ | Mentions d'information complétées pour les parents (finalité : suivre le travail et gérer le code de connexion de l'enfant ; durée ; droits) |
| ☐ | Procédure du professeur : vérifier que l'adresse est bien celle d'un **responsable légal** de l'élève (fiche de l'établissement), remettre le mot de passe provisoire par un canal sûr (ENT, carnet, en main propre) |
| ☐ | Cas des parents séparés ou d'un retrait d'autorité parentale : le professeur retire le compte concerné (« Retirer » dans la fiche de l'élève) |
| ☐ | Élèves majeurs (Terminale) : décider avec le DPO si le suivi parental reste ouvert sans leur accord |
| ⚠️ | Le code choisi par un parent est plus facile à deviner qu'un code tiré au hasard : les règles ci-dessus et le blocage après 5 essais limitent ce risque |

## 7. Remarques et suggestions (ticket #30) — à valider avec le délégué à la protection des données

- Élèves, parents et professeurs connectés envoient une remarque **avec leur nom** ou **anonyme** ; le choix est
  obligatoire avant l'envoi.
- **Anonyme** : aucune identité n'est enregistrée avec la remarque (ni nom, ni rôle, ni identifiant de compte ;
  une contrainte de la base l'interdit). Rien ne peut donc apparaître dans l'administration, l'export CSV ou le
  journal. Le compte connecté ne sert qu'à limiter le spam, en mémoire (10 remarques par heure et par compte,
  30 par adresse IP), sans trace durable. L'interface rappelle les limites : l'utilisateur est connecté et le texte
  qu'il écrit peut permettre de le reconnaître.
- **Avec son nom** : rôle, identifiant et nom affiché (prénom et classe pour un élève) sont visibles des seuls
  administrateurs, dans l'écran et l'export.
- Suivi : référence aléatoire (`R-` + 8 caractères) et code de suivi confidentiel de 12 caractères, montré une
  seule fois ; seule son empreinte (HMAC-SHA-256 avec la clé du serveur) est conservée. Essais de suivi limités
  par adresse IP.
- Journal d'administration : seulement le traitement (statut, priorité, assignation, présence d'une réponse),
  jamais l'identité de l'auteur ni le texte.
- Conservation : même durée que les données des élèves (`PKP_RETENTION_JOURS`), comptée depuis le dernier
  traitement ; supprimées par `python -m app.purge`.
- Pas encore de pièce jointe (V1) : à ajouter avec contrôle du type, de la taille et suppression des métadonnées.

## 8. Rédactions des élèves (#179, décision RGPD-2) — cadre du propriétaire, à confirmer

Cadre retenu par le propriétaire le 19/11/2026 pour le pilote. Les durées sont des **choix de Boussole**, justifiés
par le besoin pédagogique, et non des durées imposées par la CNIL.

| État | Règle | Où |
|---|---|---|
| ✅ | **Usage** : corriger les rédactions et suivre les progrès ; aucune publication, aucun usage marketing, aucune alimentation d'une IA | — |
| ✅ | **Données** : texte, sujet, commentaire du professeur, dates, élève (identifiant pédagogique) ; rappel à l'élève de ne pas écrire d'adresse, de coordonnées ni d'informations intimes, et de préférer des sujets fictifs | `models.Redaction`, écran « Rédaction » |
| ✅ | **Accès** : l'élève à ses textes ; le professeur de sa classe aux versions **remises** (jamais aux brouillons) ; aucun autre élève ni professeur ; aucune route d'administration vers les textes ; les parents ne voient pas les textes | `app/routes/redactions.py`, `tests/test_redactions.py` |
| ✅ | **Conservation** : jusqu'au 31 août de l'année scolaire, puis suppression automatique (texte et commentaire) | `conserver_jusqu_au`, `purge.purger_redactions` |
| ✅ | **Départ** : suppression 30 jours après l'archivage de la classe ; suppression immédiate avec l'élève | idem, clé étrangère en cascade |
| ✅ | **Export** : inclus dans l'export RGPD de l'élève | `progression.export_eleve` |
| ✅ | **Journaux** : aucun texte de rédaction ni commentaire | — |
| ✅ | **Fermé par défaut** : `PKP_REDACTION_ACTIVE=false` ; toutes les routes répondent 403 | `app/config.py` |
| ☐ | **Responsable de traitement** et **base légale** à documenter (entreprise, association partenaire ou répartition des rôles) ; une case « j'accepte » ne suffit pas | propriétaire, avis spécialisé |
| ☐ | **Information** des élèves et des parents avant l'ouverture (charte d'utilisation, #183) | #183 |
| ☐ | **Parents** : bilan pédagogique dans l'espace parent (non fait) ; demandes d'accès aux textes traitées après vérification du lien parental | à faire |
| ☐ | **Demandes d'effacement** : réponse sous un mois ; aujourd'hui par l'administration (suppression de l'élève), sans formulaire dédié | à faire |
| ☐ | **Intervention d'un administrateur** sur un texte, justifiée et tracée : non prévue (aucun accès) ; à créer si le besoin est confirmé | — |
| ☐ | **Sauvegardes** : rotation de 30 jours au plus si possible (aujourd'hui 60 jours, SEC-D4) ; réappliquer les suppressions après une restauration | `docs/exploitation/technique.md` T-04/T-05 |
| ☐ | **Vérification effective** des accès, de l'export, de l'effacement et de la purge en DEV avant l'ouverture | recette |
| ✅ | **Réponses rédigées aux dossiers de français** (#217) : mêmes règles (usage, accès du seul professeur de la classe aux réponses remises, aucun accès administrateur ni parent, conservation au 31 août, suppression 30 jours après l'archivage de la classe et avec l'élève, export, journaux sans texte, fermées par `PKP_REDACTION_ACTIVE`) | `models.ReponseRedigeeFrancais`, `app/routes/francais_eleves.py`, `purge.purger_redactions`, `tests/test_francais_activite.py` |
| ✅ | **Quiz et auto-évaluation de français** (#217) : réponses au quiz par essai, scores et niveaux d'auto-évaluation, comme en anglais ; supprimés avec l'élève, inclus dans l'export | `models.ProgressionFrancais`, `models.ReponseQuizFrancais` |


## 9. Accueil et demandes (#172) : contacts adultes, candidatures et partenariats (#171) — à valider avant toute collecte réelle

« Accueil et demandes » regroupe les demandes des **adultes qui ne sont pas encore inscrits**, une file par finalité :
familles et préinscriptions, informations et questions, candidatures de professeurs, partenariats de structures. Les
retours des utilisateurs déjà inscrits restent dans « Remarques » (§ 7), sans seconde boîte de réception.
Entrées aujourd'hui : formulaire public « Enseigner ou collaborer avec nous » (`/collaborer`, #171, fermé par défaut)
et saisie par un administrateur d'une demande reçue hors formulaire (familles et informations). Le formulaire des
familles relève de #170.

| État | Règle | Où |
|---|---|---|
| ✅ | **Contact adulte** : prénom, nom, e-mail, téléphone facultatif. **Ni compte, ni parent, ni inscrit** : aucun enfant, aucun accès, aucun résultat pédagogique relié. Chaque demande garde les coordonnées saisies avec elle | `models.ContactAdulte`, `models.DemandeAccueil` |
| ✅ | **Données par file** : famille et information : besoin exprimé (texte), sans donnée d'enfant ; candidature : matières, niveaux, disponibilités, message, CV, facultatifs sauf matières et niveaux ; partenariat : structure, type, fonction facultative, partenariat envisagé | `app/routes/accueil.py`, `app/routes/collaboration.py` |
| ✅ | **Rattachement prudent** : une demande rejoint un contact seulement si l'e-mail normalisé est identique (minuscules, espaces retirés, aucune ressemblance approchée) ; les coordonnées du contact ne sont jamais écrasées ; aucun accès, aucun enfant, aucun compte n'en découle ; un administrateur peut détacher une demande rattachée à tort | `accueil.contact_pour`, `accueil.detacher` |
| ✅ | **Usage** : étudier la demande et y répondre ; aucun envoi automatique, aucune prospection, aucun export vers un outil externe ; une demande ne crée ni compte, ni inscription, ni habilitation, ni contrat ; l'issue est notée explicitement (suite demandée, inscription effective pour une famille, refus, clôture) | — |
| ✅ | **Information** avant l'envoi du formulaire public (usage, accès, conservation, droits) ; case « J'ai lu » exigée par l'API | `web/src/Collaborer.jsx` |
| ✅ | **CV** : PDF seulement, 5 Mo au plus (`PKP_CV_TAILLE_MAX_MO`), type réel vérifié (en-tête puis analyse complète du contrôle renforcé #4), refusé s'il est chiffré ou porte un contenu actif ; nom de fichier aléatoire, droits `0600`, dossier privé `PKP_DOSSIER_CANDIDATURES` distinct des ressources pédagogiques ; aucune URL publique, téléchargement par un administrateur seulement, journalisé | `app/collaboration.py` |
| ✅ | **Accès** : administrateurs seulement (jeton admin, rôle revérifié en base) ; ni professeur, ni validateur, ni parent, ni élève. Journal : traitement seulement (catégorie, statut, issue, responsable, présence de notes, téléchargement, export, suppression), jamais les coordonnées, le message, les notes ni le CV | `tests/test_accueil.py`, `tests/test_collaboration.py` |
| ✅ | **Droits** : export JSON du contact et de toutes ses demandes (accès) ; suppression d'une demande, ou du contact avec toutes ses demandes **et ses CV** (effacement) ; un contact sans demande est supprimé | `/admin/accueil/contacts/{id}/export`, `DELETE` |
| ✅ | **Anti-abus** du formulaire public : 5 envois par heure et par adresse (refusés compris), 60 par heure au total, piège à robots, corps borné | `limitation.collaboration_*` |
| ✅ | **Durées par finalité** : `PKP_ACCUEIL_CONSERVATION_JOURS` donne une durée par file, comptée depuis le dernier traitement ; la purge quotidienne supprime les demandes échues, leurs CV et les contacts restés sans demande. **Sans durée, une file ne collecte rien** (formulaire fermé, saisie refusée, démarrage refusé en production si le formulaire est activé) et n'est jamais purgée | `accueil.purger`, `app/purge.py` |
| ☐ | **Durées de conservation** de chaque file, responsable de traitement et base légale : décision **RGPD-3**, en attente | propriétaire, avis spécialisé (#18) |
| ☐ | **Exploitation** : volume persistant et sauvegarde du dossier des CV, réapplication des suppressions après une restauration (`docs/DEPLOIEMENT.md`) | PR d'exploitation |
| ☐ | **Procédure** des demandes d'accès et d'effacement (qui reçoit, délai d'un mois) ; recette en DEV avec des données fictives | — |
