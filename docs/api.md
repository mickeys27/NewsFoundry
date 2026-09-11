# API — référence

Base URL locale : `http://localhost:8000`. Documentation interactive Swagger générée automatiquement par FastAPI sur `/docs` (également exposée dans le frontend via `Réglages > Swagger`).

Toutes les routes sauf `/` et `/login` nécessitent l'en-tête `Authorization: Bearer <token>`.

## Authentification

| Méthode | Route | Description |
|---|---|---|
| `POST` | `/login` | `{ email, password }` → `{ access_token, token_type }`. Un utilisateur de test (`test@test.com` / `test`) est créé automatiquement au démarrage du backend. |

Le token est un JWT (HS256, expiration 24h) signé avec `JWT_SECRET`, contenant l'email de l'utilisateur (`sub`). Il est stocké côté frontend dans le `localStorage` du navigateur.

## Discussions (chats)

| Méthode | Route | Description |
|---|---|---|
| `GET` | `/chats` | Liste des discussions de l'utilisateur courant, triées par date décroissante. |
| `POST` | `/chats` | Crée une nouvelle discussion vide, fige son `system_prompt`. |
| `GET` | `/chats/{chat_id}` | Historique complet d'une discussion. |
| `POST` | `/chats/{chat_id}/messages` | Ajoute un message utilisateur et retourne la réponse de l'agent LLM. |

## Revues de presse

| Méthode | Route | Description |
|---|---|---|
| `GET` | `/press-reviews` | Revues de l'utilisateur (paramètre optionnel `chat_id` pour filtrer sur une discussion). |
| `GET` | `/press-reviews/{review_id}` | Détail d'une revue (titre, synthèse, articles). |
| `POST` | `/press-reviews` | `{ theme, chat_id }` → génère une revue de presse à partir de l'historique du chat donné. |

## Réglages (settings)

| Méthode | Route | Description |
|---|---|---|
| `GET`/`PUT` | `/settings/system-prompt` | Prompt système de base utilisé par l'agent de chat. |
| `GET` | `/settings/news-digest` | Résumé des actualités du jour actuellement stocké. |
| `PUT` | `/settings/news-digest/synthesis-prompt` | Prompt utilisé pour synthétiser les actualités. |
| `POST` | `/settings/news-digest/refresh` | Recharge le top des actualités (World News API) et régénère la synthèse via le LLM. |
| `GET`/`PUT` | `/settings/display` | Préférences d'affichage (nombre de revues affichées). |

## Modèle de données (SQLModel)

| Table | Rôle |
|---|---|
| `User` | `id`, `email` (unique), `hashed_password` (bcrypt) |
| `Chat` | `id`, `user_id`, `created_at`, `messages` (JSON, historique complet), `system_prompt` (figé à la création) |
| `Settings` | Table à une ligne (`id=1`) : prompt système global par défaut |
| `NewsDigest` | Table à une ligne (`id=1`) : dernier résumé d'actualités + prompt de synthèse |
| `PressReview` | `id`, `user_id`, `chat_id`, `title`, `summary`, `prompt`, `generated_at` |
| `PressReviewArticle` | Sujets/articles distincts identifiés dans une revue (`press_review_id`, `title`, `summary`) |
| `DisplaySettings` | Table à une ligne (`id=1`) : préférences d'affichage (ex. nombre de revues visibles) |

## Gestion des erreurs

L'application utilise `HTTPException` de FastAPI de façon systématique, avec un code et un message adaptés à la situation :

| Code | Cas |
|---|---|
| `401 Unauthorized` | Identifiants invalides au login, ou token JWT absent/invalide/expiré |
| `404 Not Found` | Chat ou revue de presse inexistant(e) **ou appartenant à un autre utilisateur** |
| `422 Unprocessable Entity` | Corps de requête invalide (ex. thème vide, `press_review_list_limit` non positif) |
| `502 Bad Gateway` | Échec d'un appel externe : LLM (Mistral) indisponible, ou World News API en erreur |

**Choix de sécurité important** : accéder à un chat ou une revue d'un autre utilisateur renvoie **404**, jamais **403**. Un `403` confirmerait à un attaquant que la ressource existe mais lui est interdite ; le `404` ne révèle même pas son existence (voir `get_owned_chat` / `get_owned_press_review` dans `main.py`). Ce comportement est directement couvert par les tests automatisés (`test_get_another_users_chat_returns_404`, etc.).

Côté frontend, chaque appel API (`lib/*.ts`) intercepte les réponses en erreur et lève une exception typée (`LoginError`, `ChatError`, `PressReviewError`, `SettingsError`) avec un message français destiné à l'utilisateur final, affiché dans l'interface (bandeau d'erreur, `role="alert"`).
