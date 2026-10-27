# Déploiement — PKP Math Lycée

```
Internet ──443──▶ Caddy (web) ──▶ /api/* ──▶ API FastAPI ──▶ PostgreSQL
                     │                         ▲
                     └── fichiers du front     └── purge RGPD (quotidienne)
```

Seul Caddy est exposé. Il obtient seul le certificat HTTPS (Let's Encrypt).

## Prérequis

- Un serveur Linux (2 Go de RAM suffisent) hébergé dans l'UE, avec Docker et Docker Compose.
- Un nom de domaine dont l'enregistrement DNS pointe vers ce serveur.
- Ports 80 et 443 ouverts (le 80 sert à la validation du certificat).

## Première installation

```bash
cd deploy
cp .env.example .env
python3 -c "import secrets; print(secrets.token_urlsafe(48))"   # → PKP_SECRET_KEY
python3 -c "import secrets; print(secrets.token_urlsafe(24))"   # → PKP_DB_MOT_DE_PASSE
nano .env                                                        # domaine + les deux secrets
docker compose up -d --build
docker compose exec api python -m app.admin creer --email prof@lycee.fr --nom "Mme Martin"
```

Vérifier : `https://<domaine>/api/health` répond `{"status":"ok"}`, puis se connecter sur
`https://<domaine>/enseignant`.

Les migrations de base de données sont appliquées automatiquement à chaque démarrage de l'API.
Les données de démo ne sont **jamais** chargées en production.

## Exploitation courante

| Besoin | Commande (depuis `deploy/`) |
|--------|-----------------------------|
| Mettre à jour | `git pull && docker compose up -d --build` |
| Journaux | `docker compose logs -f api web` |
| Purge : voir ce qui serait supprimé | `docker compose exec api python -m app.purge --simulation` |
| Nouveau compte enseignant | `docker compose exec api python -m app.admin creer --email … --nom …` |
| Mot de passe oublié | `docker compose exec api python -m app.admin mot-de-passe --email …` |
| Sauvegarde | `docker compose exec -T db pg_dump -U pkp pkp \| gzip > pkp-$(date +%F).sql.gz` |
| Restauration | `gunzip -c sauvegarde.sql.gz \| docker compose exec -T db psql -U pkp pkp` |

Sauvegardes : les chiffrer, les stocker hors du serveur, les conserver au plus la durée de
conservation RGPD, et **tester une restauration** au moins une fois par an.

## Limites connues

- **Un seul processus API** : la limitation des tentatives de connexion est en mémoire. Pour
  plusieurs serveurs ou workers, il faudrait un stockage partagé (Redis). Un redémarrage remet
  les compteurs à zéro.
- **Blocage d'un compte enseignant** : 5 mots de passe faux en 15 min bloquent ce compte
  15 min, même pour son propriétaire. C'est voulu, mais un tiers peut le provoquer.
- **Lycée derrière une seule IP** : les plafonds par IP (300 connexions, 30 codes classe faux
  par 15 min) sont réglés pour une classe entière ; voir `PKP_CONNEXION_*` dans `app/config.py`.
