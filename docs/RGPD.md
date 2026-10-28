# Checklist RGPD — PKP Math Lycée

Les utilisateurs sont des **mineurs**. Cette checklist recense ce que le logiciel fait et
ce qui reste à la charge de l'établissement. Elle ne remplace pas l'avis du **délégué à la
protection des données (DPO)** de l'établissement ou de l'académie, à qui elle doit être
soumise avant la mise en service.

Légende : ✅ assuré par le logiciel (et testé) · ☐ à faire par l'établissement / l'hébergeur

## 1. Minimisation des données

| | Point | Où |
|---|-------|----|
| ✅ | Élève : prénom + classe uniquement (ni nom, ni email, ni date de naissance, ni mot de passe) | `models.Eleve`, `ConnexionEleve` |
| ✅ | Prénom limité aux lettres, espaces, tirets, apostrophes (50 car.) | `schemas.py` |
| ✅ | Enseignant : nom, email, empreinte du mot de passe | `models.Enseignant` |
| ✅ | Aucun traceur, aucune police ni script tiers (CSP `default-src 'self'`) | `deploy/Caddyfile` |
| ✅ | Session navigateur en `sessionStorage` : fermer l'onglet déconnecte (postes partagés) | `web/src/stockage.js` |
| ☐ | Consigne aux élèves : saisir **uniquement leur prénom** (pas de nom de famille) | — |

## 2. Durée de conservation

| | Point | Où |
|---|-------|----|
| ✅ | Purge automatique des élèves inactifs depuis `PKP_RETENTION_JOURS` (365 par défaut), quotidienne | `app/purge.py`, service `purge` |
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
| ✅ | Cloisonnement : un enseignant ne voit que ses classes (404 sinon) | `routes/enseignants.py` |
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
