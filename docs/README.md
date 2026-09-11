# Documentation NewsFoundry

Cette documentation a pour but de permettre à toute nouvelle personne rejoignant le projet de comprendre rapidement son fonctionnement, ses choix techniques et la manière de le faire évoluer.

| Fichier | Contenu |
|---|---|
| [`architecture.md`](./architecture.md) | Vue d'ensemble du projet, structure des dossiers, schéma des 3 environnements (local / CI / production) |
| [`api.md`](./api.md) | Référence des routes de l'API backend, modèle de données, codes d'erreur |
| [`ai.md`](./ai.md) | Choix liés à l'IA (agents PydanticAI, prompts, outils), et pistes d'amélioration qualité/performance |
| [`testing.md`](./testing.md) | Stratégie de tests, commande pour les lancer, fonctionnement de la CI GitHub Actions |
| [`deployment.md`](./deployment.md) | Déploiement Railway / Vercel, variables d'environnement, URLs de production |

## Application déployée

- **Frontend (Vercel)** : https://news-foundry-git-main-generate-ia.vercel.app/
- **Backend (Railway)** : https://newsfoundry-production-ac98.up.railway.app/

## Démarrage rapide

```bash
git clone <repo>
cd NewsFoundry/backend && cp .env.example .env && uv sync
docker run --name newsfoundry_db -e POSTGRES_USER=user -e POSTGRES_PASSWORD=password -e POSTGRES_DB=newsfoundry -p 5432:5432 postgres:17
uv run --env-file .env src/main.py
```

```bash
cd NewsFoundry/frontend && npm install && npm run dev
```

Utilisateur de test : `test@test.com` / `test` (créé automatiquement au démarrage du backend).
