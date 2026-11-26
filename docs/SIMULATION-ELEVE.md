<!-- Issue #184 — Vue élève simulée (Claude) -->
# Vue élève simulée (« Voir comme un élève »)

Issue #184. Un professeur ou un administrateur ouvre, depuis son espace, l'espace élève d'une classe avec un
**élève fictif** qui lui est propre. Il parcourt les mêmes écrans qu'un élève de cette classe (accueil, cours,
« Mon cours », entraînement, diagnostic s'il est ouvert, réponses, correction, historique, progression, fiches PDF,
rédaction en français) sans emprunter les identifiants d'un mineur ni toucher aux données réelles.

## Premier lot : périmètre et limites

| Inclus | Pas encore inclus |
|---|---|
| Classes de maths et de français (table `classe`) | Groupes de Boussole Anglais (`groupe_anglais`, autre espace élève) |
| Entrée depuis le menu professeur (« Voir comme un élève ») et le menu administrateur (Pilotage) | Raccourci depuis la fiche d'une classe |
| Professeur : ses classes actives. Administrateur : toutes les classes actives | Choix d'une séance : les classes de maths et de français n'ont pas de séance planifiée |
| Reprise de la dernière simulation, bouton « Réinitialiser la simulation » | Vue de l'état d'un **élève réel** : besoin distinct, à cadrer (finalité, lecture seule, traçabilité) |
| Bandeau permanent, retour à l'espace d'origine | Espace parent simulé |

Une classe dont le domaine est fermé aux élèves (ni public, ni classe pilote, #176) reste simulable : la simulation
montre alors exactement ce que voient ses élèves, c'est-à-dire le refus. La liste des classes l'indique.

## Fonctionnement

1. `GET /enseignants/simulation/classes` ou `GET /admin/simulation/classes` : classes autorisées pour l'acteur, avec
   l'état d'accès des élèves et l'existence d'une simulation à reprendre.
2. `POST /enseignants/simulation` ou `POST /admin/simulation` `{classe_id}` : crée (ou reprend) l'élève fictif de
   l'acteur dans cette classe et renvoie un **jeton élève ordinaire** de 2 heures. Classe inexistante ou hors du
   périmètre : 404, sans rien révéler.
3. Le front range ce jeton dans la session de l'onglet (`sessionStorage`, jamais `localStorage`), vide toute séance
   élève en cours sur ce poste et ouvre `/eleve`. L'espace élève existant s'affiche, avec le bandeau.
4. `POST /eleves/moi/simulation/reinitialiser` : supprime l'élève fictif (séances, réponses, diagnostic, demandes
   d'aide, rédactions partent en cascade) et en recrée un vierge ; nouveau jeton.
5. `POST /eleves/moi/simulation/fermer` (« Revenir à mon espace… ») : révoque le jeton ; le travail fictif est
   conservé pour la prochaine reprise.

## Isolement et sécurité

- **Même code que l'élève** : l'élève fictif est une ligne `eleve` de la classe choisie (`simulation_par_id`,
  `simulation_role`, migration `0045`). Toutes les règles serveur de l'espace élève s'appliquent sans copie :
  chapitres ouverts, publication, classes pilotes, mode de correction, ARCH-4 (aucune solution avant la réponse,
  aucun PDF professeur).
- **Aucun pouvoir d'adulte** : le jeton est un jeton `eleve` ; toute route professeur ou administrateur le refuse.
  L'identité de l'acteur ne figure que dans la ligne `eleve` et le journal.
- **Connexion impossible autrement** : pas d'identifiant, et `code_hash` n'est pas une empreinte de code ; la
  connexion par prénom ne le trouve pas (filtre ci-dessous).
- **Revérification à chaque requête** (`auth.eleve_courant` → `simulation.refus_acteur`) : acteur actif, mot de
  passe inchangé depuis l'ouverture, classe toujours à lui (professeur) ou rôle administrateur toujours détenu,
  classe non archivée. Sinon 401 et retour à l'espace d'origine.
- **Un seul onglet actif** : rouvrir la simulation (autre onglet, autre appareil) régénère le secret et révoque le
  jeton précédent. Les sessions professeur ou administrateur ne sont jamais modifiées.
- **Masquage global** (`api/app/db/simulation.py`) : un filtre ORM `with_loader_criteria` est ajouté à **toute**
  lecture. Il retire les élèves fictifs, ainsi que leurs séances, réponses, passations et observations de
  diagnostic, demandes d'aide et rédactions : listes de classe, séance en direct, rédactions et diagnostics à
  corriger, statistiques, recherche, répertoire, bilans parents et purge ordinaire ne les voient pas. Seule la
  requête faite avec le jeton d'un élève fictif voit **ses** données fictives (et aucune autre). Le code de gestion
  des simulations lève le filtre explicitement (`execution_options(inclure_simulations=True)`).
- **Compteurs** : l'ouverture d'une ressource par un élève fictif n'est pas comptée (`ressource_consultation`).
- **Aucun envoi** : le projet n'envoie ni courriel ni notification ; l'élève fictif n'a ni parent ni enfant de
  famille rattaché.

## Journal, conservation, quotas

- Journal (`journal_admin`) : `simulation.ouverture`, `simulation.reinitialisation`, `simulation.fermeture`, avec
  l'acteur, la classe et le rôle d'origine ; ni réponse, ni texte, ni secret.
- Quota : un élève fictif par acteur, rôle d'origine et classe (contrainte `uq_eleve_simulation`).
- Purge (`python -m app.purge`) : élève fictif sans séance depuis 30 jours (`simulation.JOURS_CONSERVATION`), ou
  dont la classe est archivée, supprimé avec tout son travail.
- Dépôts de fichiers : aucun ouvert par ce lot.

## Points à confirmer par le propriétaire

- Point d'entrée : menu (fait) ; raccourci depuis la fiche classe à ajouter ?
- Reprise de la dernière simulation avec bouton de réinitialisation (fait), plutôt qu'une remise à zéro à chaque
  ouverture ?
- Durée du jeton (2 h) et de conservation (30 jours).
- Les entrées de journal d'un professeur apparaissent dans le journal de l'administration : à garder ?
- Deuxième lot : Boussole Anglais, puis, si le besoin est confirmé, la vue en lecture seule d'un élève réel.

## Tests

- API : `api/tests/test_simulation_eleve.py` (parcours professeur et administrateur, isolement des listes et
  statistiques, refus d'un autre professeur et d'une URL modifiée, aucun pouvoir d'adulte, reprise et nouvel onglet,
  réinitialisation, fermeture, révocations, domaine fermé, filtre global, purge).
- Front : `web/src/tests/simulation.test.jsx` (choix de la classe, bandeau, retour, réinitialisation).
- Recette humaine (critère de l'issue) : professeur, administrateur et compte élève de référence sur la même classe,
  comparaison des écrans, sur mobile et au clavier. **Non faite** par l'agent.
