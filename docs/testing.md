# Tests

## Lancer les tests

```bash
cd backend
uv run pytest
```

Aucune base PostgreSQL ni clé API n'est requise pour exécuter la suite :

- La base de données est remplacée par une **base SQLite en mémoire**, recréée à neuf pour chaque test (`tests/conftest.py`, fixture `session`), et injectée dans FastAPI via `app.dependency_overrides[get_session]`.
- Le modèle Mistral est remplacé par **`TestModel`** de PydanticAI (`pydantic_ai.models.test`), qui simule un modèle de langage déterministe sans appel réseau réel. `call_tools=[]` ou `call_tools="all"` permet de choisir si l'on veut aussi vérifier que l'agent appelle bien ses outils (ex. `search_news_tool`).

## Ce qui est couvert

| Fichier | Contenu |
|---|---|
| `tests/test_chats.py` | Création/consultation de chats, envoi de messages, accumulation de l'historique, gestion des erreurs LLM (502), utilisation de l'outil `search_news`, **stabilité du `system_prompt` figé à la création d'un chat** |
| `tests/test_news.py` | Construction du prompt système, synthèse et rafraîchissement du digest d'actualités, construction des requêtes de recherche (`_build_search_query`), génération/consultation/liste des revues de presse, réglages d'affichage |

## Tests d'autorisation (isolation entre utilisateurs)

C'est le point de vigilance le plus important du projet (cf. auto-évaluation) : un utilisateur ne doit jamais pouvoir accéder aux données d'un autre. Chaque ressource protégée (chat, revue de presse) est couverte par le même schéma de test :

- **Cas nominal** : un utilisateur créé une ressource, peut la relire.
  - ex. `test_create_chat_returns_a_new_empty_chat`
- **Cas d'intrusion** : un second utilisateur (« intruder ») tente d'accéder à une ressource créée par le premier (« owner ») → **`404 Not Found`**, jamais `403`, pour ne même pas révéler l'existence de la ressource.
  - `test_get_another_users_chat_returns_404`
  - `test_post_message_to_another_users_chat_returns_404`
  - `test_get_another_users_press_review_returns_404`
  - `test_generate_press_review_rejects_another_users_chat_id`
- **Listing** : les routes de liste ne renvoient jamais les ressources d'un autre utilisateur.
  - `test_list_chats_only_returns_own_chats`
  - `test_list_press_reviews_only_returns_own_reviews`
- **Authentification requise** : chaque route protégée refuse une requête sans token (`401`).
  - `test_create_chat_requires_authentication`, `test_get_chat_requires_authentication`, etc.

## Intégration continue (GitHub Actions)

Un workflow GitHub Actions exécute automatiquement `uv run pytest` à chaque push et pull request. Le déploiement sur Railway/Vercel n'est déclenché (redéploiement automatique de la branche `main`) qu'après le succès de cette étape, ce qui garantit qu'aucune régression sur la logique métier — en particulier l'isolation des chats entre utilisateurs — n'atteint la production.
