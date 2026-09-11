# Déploiement

## URLs de production

| Composant | URL |
|---|---|
| Frontend | https://news-foundry-git-main-generate-ia.vercel.app/ |
| Backend | https://newsfoundry-production-ac98.up.railway.app/ |

Déploiement continu : chaque push sur `main` redéploie automatiquement le frontend (Vercel) et le backend (Railway).

## Backend — Railway

Le backend est un conteneur construit à partir du `Dockerfile` du dossier `backend/` :

```dockerfile
FROM ghcr.io/astral-sh/uv:python3.13-bookworm
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen
COPY src/ ./src/
EXPOSE 8000
CMD ["uv", "run", "python", "src/main.py"]
```

Étapes de configuration Railway :

1. Connecter le repository GitHub, puis définir **`backend/` comme Root Directory** (le projet étant un monorepo, Railway chercherait sinon la configuration à la racine du repo et ne trouverait rien).
2. Ajouter un plugin **PostgreSQL** dans le même projet Railway.
3. Variables d'environnement du service backend :

   | Variable | Rôle |
   |---|---|
   | `DATABASE_URL` | `${{Postgres.DATABASE_URL}}` — référence Railway vers la base managée du même projet |
   | `JWT_SECRET` | Secret de signature des tokens JWT |
   | `MISTRAL_API_KEY` | Clé API du fournisseur LLM (Mistral) |
   | `MISTRAL_MODEL` | (optionnel) nom du modèle, défaut `mistral-small-latest` |
   | `WORLD_NEWS_API_KEY` | Clé World News API |
   | `FRONTEND_URL` | Origine autorisée en CORS (URL Vercel du frontend) |
   | `PORT` | Fourni automatiquement par Railway |

4. Activer un **domaine public** (Public Networking) pour que le frontend Vercel puisse joindre l'API.

## Frontend — Vercel

1. Connecter le repository, définir **`frontend/` comme Root Directory**.
2. Variable d'environnement :

   | Variable | Rôle |
   |---|---|
   | `NEXT_PUBLIC_API_URL` | URL publique du backend Railway |

3. Build/Start commands par défaut de Next.js (`next build` / `next start`), aucune configuration additionnelle nécessaire.

## Environnement local

```bash
# Base de données (PostgreSQL en conteneur, port hôte 5433 pour éviter
# tout conflit avec une instance Postgres déjà installée sur la machine)
docker run --name newsfoundry_db \
  -e POSTGRES_USER=user -e POSTGRES_PASSWORD=password -e POSTGRES_DB=newsfoundry \
  -p 5433:5432 postgres:17

# Backend
cd backend && cp .env.example .env   # renseigner DATABASE_URL (port 5433), JWT_SECRET, MISTRAL_API_KEY, WORLD_NEWS_API_KEY
uv sync
uv run --env-file .env src/main.py   # http://localhost:8000

# Frontend
cd frontend && npm install
npm run dev                           # http://localhost:3000
```

Au démarrage, le backend (`init_db()`) crée les tables, réinitialise les discussions/revues (pour repartir d'un état propre à chaque redémarrage local) et crée l'utilisateur de test `test@test.com` / `test` s'il n'existe pas déjà.
