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
| ✅ | Prénom limité aux lettres, espaces, tirets, apostrophes (50 car.) | `schemas.py` |
| ✅ | Enseignant : nom, email, empreinte du mot de passe | `models.Enseignant` |
| ✅ | Parent : email, empreinte du mot de passe, date de dernière connexion, enfants suivis (ni nom ni téléphone) ; compte créé par le professeur, sans envoi de courriel | `models.Parent`, `app/parents.py` |
| ✅ | Aucun traceur, aucune police ni script tiers (CSP `default-src 'self'`) | `deploy/Caddyfile` |
| ✅ | Session navigateur en `sessionStorage` : fermer l'onglet déconnecte (postes partagés) | `web/src/stockage.js` |
| ☐ | Consigne aux élèves : saisir **uniquement leur prénom** (pas de nom de famille) | — |

## 2. Durée de conservation

| | Point | Où |
|---|-------|----|
| ✅ | Purge automatique des élèves inactifs depuis `PKP_RETENTION_JOURS` (365 par défaut), quotidienne | `app/purge.py`, service `purge` |
| ✅ | Compte parent supprimé dès qu'il ne suit plus aucun enfant (retrait par le professeur, suppression ou purge de l'élève) | `parents.supprimer_orphelins` |
| ✅ | Simulation avant purge : `python -m app.purge --simulation` | `app/purge.py` |
| ✅ | Suppression d'une classe entière (fin d'année) | `DELETE /enseignants/classes/{id}` |
| ✅ | Journaux serveur (contiennent des IP) bornés à 3 × 10 Mo par service | `docker-compose.yml` |
| ☐ | Fixer la durée de conservation avec le DPO et l'inscrire au registre | `.env` |
| ☐ | Durée de conservation des **sauvegardes** alignée (une sauvegarde contient des données purgées) | — |

## 3. Droits des personnes

| | Droit | Mise en œuvre |
|---|-------|---------------|
| ✅ | Accès et portabilité | Bouton « Exporter » (JSON complet : séances, réponses, progression) |
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
| ✅ | Parent : mot de passe provisoire à changer à la première connexion (12 caractères minimum), 5 échecs / 15 min par compte, jeton invalidé par un changement ou une réinitialisation ; réinitialisation par un administrateur journalisée | `routes/parents.py`, `routes/admin.py` |
| ✅ | Code choisi par le parent pour l'enfant : 8 à 16 lettres et chiffres, au moins une lettre et un chiffre, 4 caractères différents, sans le prénom ni l'identifiant ; stocké haché ; l'ancien code et les sessions de l'enfant cessent de fonctionner | `security.probleme_code_choisi` |
| ✅ | Messages de connexion identiques que le compte existe ou non | `routes/enseignants.py` |
| ✅ | API et base non exposées sur Internet (réseau Docker interne) | `docker-compose.yml` |
| ✅ | Documentation OpenAPI désactivée en production | `app/main.py` |
| ☐ | Hébergement dans l'Union européenne, contrat de sous-traitance avec l'hébergeur | — |
| ☐ | Sauvegardes chiffrées et testées (restauration) | `docs/DEPLOIEMENT.md` |
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
