# Architecture

## Vue d'ensemble

NewsFoundry est une application de chat IA spécialisée dans l'actualité : l'utilisateur discute avec un agent qui s'appuie sur des actualités récentes (World News API) et peut générer, à partir d'une discussion, une **revue de presse** structurée sur un thème donné.

Le projet est un **monorepo** avec deux codebases indépendantes, chacune déployée séparément :

```
NewsFoundry/
├── backend/          # API FastAPI (Python)
│   ├── src/
│   │   ├── main.py       # Routes HTTP, orchestration
│   │   ├── models.py     # Modèles SQLModel (tables + schémas par défaut)
│   │   ├── auth.py       # JWT, hashage bcrypt, dépendance get_current_user
│   │   ├── database.py   # Connexion PostgreSQL, init/seed de la DB
│   │   ├── llm.py        # Agents PydanticAI (chat + revue de presse)
│   │   └── news.py       # Client World News API + outil agent search_news
│   ├── tests/            # pytest (auth, chats, revues, news)
│   ├── Dockerfile
│   └── pyproject.toml
├── frontend/         # Application Next.js (TypeScript)
│   ├── app/
│   │   ├── page.tsx          # Page de connexion
│   │   ├── home/page.tsx     # Chat + liste des discussions + revues
│   │   └── settings/page.tsx # Réglages (prompt système, digest, affichage)
│   └── lib/               # Clients API typés (auth, chats, pressReviews, settings)
└── docs/             # Cette documentation
```

**Pourquoi un monorepo avec deux dossiers racines ?** Cela garde l'historique Git unifié et facilite la coordination des évolutions front/back, tout en gardant des cycles de déploiement indépendants — Railway et Vercel sont chacun configurés avec leur propre "Root Directory" (`backend/` et `frontend/`).

## Les trois environnements

Un même changement traverse toujours les mêmes trois environnements, ce qui garantit qu'aucun code non testé n'atteint la production.

```
┌─────────────────┐      git push       ┌──────────────────────┐
│   Environnement  │ ──────────────────▶ │   GitHub (CI)          │
│   local           │                     │   GitHub Actions       │
│                    │                     │   → pytest             │
│ - Docker Postgres  │                     │   (isolation, auth,    │
│ - uv run src/main  │                     │    LLM via TestModel)  │
│ - npm run dev       │                    └──────────┬─────────────┘
└─────────────────┘                                   │ tests OK
                                                        ▼
                                          ┌──────────────────────────┐
                                          │      Production            │
                                          │  Railway (backend + DB)    │
                                          │  Vercel   (frontend)       │
                                          │  déploiement auto sur      │
                                          │  chaque push sur `main`    │
                                          └──────────────────────────┘
```

- **Local** : Docker fait tourner uniquement PostgreSQL (port 5433 côté hôte pour éviter les conflits avec une instance locale existante) ; le backend et le frontend tournent directement sur la machine du développeur pour un rechargement à chaud rapide.
- **GitHub / CI** : chaque push déclenche une GitHub Action qui exécute la suite `pytest`. Les tests utilisent une base SQLite en mémoire et remplacent le modèle Mistral par `TestModel` de PydanticAI : aucune dépendance externe (DB réelle, clé API) n'est nécessaire pour valider la logique métier et l'isolation des autorisations.
- **Production** : Railway héberge à la fois le service backend (conteneurisé via le `Dockerfile`) et une instance PostgreSQL managée dans le même projet. Vercel héberge le frontend Next.js. Les deux plateformes redéploient automatiquement à chaque commit sur `main`.

## Flux de données principal (chat)

```
Utilisateur ──POST /chats/{id}/messages──▶ FastAPI
                                              │
                               get_owned_chat │ (vérifie chat.user_id == current_user.id)
                                              ▼
                                   Agent PydanticAI (Mistral)
                                   system_prompt = prompt de base
                                                 + digest du jour
                                   tools = [search_news_tool]
                                              │
                     si nécessaire ───────────┼──── appelle World News API (/search-news)
                                              ▼
                                   Réponse texte, ajoutée à
                                   l'historique JSON du Chat
                                              │
                                              ▼
                                   Réponse renvoyée au frontend
```

Points clés :
- L'historique complet de la discussion est stocké dans une seule colonne JSON (`Chat.messages`), conformément aux recommandations du cahier des charges.
- Le `system_prompt` d'un chat est **figé à sa création** (prompt de base + résumé d'actualités du jour) et réutilisé pour tous les messages suivants de cette discussion, afin qu'une modification ultérieure des réglages globaux ne casse pas la continuité d'une conversation déjà commencée (voir `docs/ai.md`).
