# Choix liés à l'intelligence artificielle

## Fournisseur et modèle

Le projet utilise **Mistral** (`mistral-small-latest` par défaut, configurable via `MISTRAL_MODEL`) au travers de **PydanticAI**, plutôt qu'un appel direct à une API HTTP. PydanticAI fournit une abstraction commune (`Agent`) qui gère de façon homogène : le prompt système, les outils (`tools=[...]`), et le typage strict de la sortie (`output_type=...`), ce qui a permis de garder `llm.py` compact malgré deux usages très différents (chat conversationnel et génération structurée).

## Deux agents distincts, pour deux tâches distinctes

| Agent | Rôle | Outils | Sortie |
|---|---|---|---|
| Agent de chat (`generate_reply`) | Discuter avec l'utilisateur, style « synthèse de presse professionnelle » | `search_news_tool` (World News API `/search-news`) | Texte libre (Markdown) |
| Agent de revue de presse (`generate_press_review_from_chat`) | Synthétiser l'historique d'une discussion sur un thème donné | Aucun | `PressReviewOutput` structuré (`title`, `summary`, `articles[]`) |

**Pourquoi deux agents séparés plutôt qu'un seul agent généraliste ?** Un agent spécialisé, sans outils inutiles et avec un prompt entièrement dédié à sa tâche, produit des sorties plus fiables et plus faciles à contraindre qu'un agent généraliste à qui l'on demanderait en plus de respecter un format de sortie strict. La sortie structurée (`output_type=PressReviewOutput`) élimine tout parsing de texte libre côté backend : le modèle Pydantic est directement persisté en base.

## Prompts

- **Prompt système du chat** (`DEFAULT_SYSTEM_PROMPT`) : fixe la langue (français), le style (clair, concis, factuel, structuré en puces), la neutralité sur l'actualité, et instruit explicitement le modèle d'utiliser l'outil de recherche quand l'utilisateur demande plus de détails ou des informations récentes.
- **Prompt de l'agent de revue de presse** (`PRESS_REVIEW_AGENT_SYSTEM_PROMPT`) : contraint le modèle à ne synthétiser que ce qui est réellement présent dans la discussion (anti-hallucination explicite : « n'invente aucune information »), et à produire un contenu direct sans phrase d'introduction (« Voici la revue de presse... ») pour que chaque champ soit directement affichable tel quel dans l'interface.
- **Prompt de synthèse des actualités** (`DEFAULT_NEWS_SYNTHESIS_PROMPT`) : condense les articles du jour en une liste à puces courte (15 puces maximum), un sujet par puce, afin de garder le prompt système du chat court une fois le digest injecté.

Les trois prompts sont **stockés en base de données** (`Settings`, `NewsDigest`) et modifiables via `/settings/*`, plutôt qu'en constantes figées dans le code : cela permet d'itérer sur leur formulation sans redéployer, et surtout de **figer le prompt utilisé par un chat au moment de sa création** (voir `docs/architecture.md`) pour ne jamais casser la continuité d'une conversation en cours.

## Contexte d'actualité à jour (cutoff date)

Les LLM ont une date de coupure d'entraînement. Le prompt système est enrichi avec un résumé des actualités du jour (World News API `/top-news`, synthétisé par un appel LLM dédié) pour que le chat puisse répondre correctement aux questions sur l'actualité récente. Pour aller plus loin sur un sujet précis, l'agent dispose en plus de l'outil `search_news_tool` (World News API `/search-news`), dont l'input (une simple chaîne `query`) et l'output (liste de `{title, summary}`) ont été volontairement simplifiés par rapport au format brut de l'API, plus complexe et plus verbeux, pour rester facile à utiliser par l'agent.

## Pistes d'amélioration qualité / performance de la partie IA

### 1. Appels réseau bloquants dans un serveur asynchrone

- **Constat** : `news.py` effectue les appels à World News API avec `httpx.get(...)` (client **synchrone**) alors que ces fonctions sont invoquées depuis des routes et un outil d'agent **asynchrones** (`async def refresh_news_digest`, `search_news_tool` appelé par l'agent PydanticAI dans un event loop asyncio). Un appel HTTP synchrone bloque tout l'event loop de FastAPI pendant sa durée : le timeout est fixé à 20 secondes, donc **toutes les requêtes concurrentes du serveur sont mises en pause jusqu'à 20s** dans le pire cas.
- **Implémentation proposée** : remplacer `httpx.get` par `httpx.AsyncClient().get` (`await client.get(...)`) dans `_get`, et adapter `fetch_top_news`/`search_news` en fonctions `async`.
- **Objectif mesurable** : ramener le temps de traitement des requêtes concurrentes (mesuré en local avec `wrk`/`k6`, 20 requêtes simultanées sur `/chats/{id}/messages` pendant qu'un appel World News API est en cours) d'un comportement quasi séquentiel à un débit proche du nominal (temps de réponse P95 divisé par un facteur proportionnel au nombre de requêtes concurrentes, ex. de ~20s à <1s pour la requête la plus rapide du lot).

### 2. Pas de mécanisme de reprise (retry) sur les échecs LLM/API transitoires

- **Constat** : un échec ponctuel (timeout réseau, erreur 5xx temporaire de Mistral ou de World News API) provoque immédiatement un `502` renvoyé à l'utilisateur (`except Exception` dans `llm.py`, `except httpx.HTTPError` dans `news.py`), sans nouvelle tentative. Sur des API tierces, une part significative des erreurs sont transitoires et disparaissent en re-essayant une fois.
- **Implémentation proposée** : ajouter une politique de retry avec backoff exponentiel (ex. librairie `tenacity`, 2 tentatives, backoff 0.5s/1.5s) autour des appels `agent.run(...)` et `httpx` avant de lever `LLMError`/`NewsError`.
- **Objectif mesurable** : suivre le taux de réponses `502` renvoyées aux utilisateurs (via les logs déjà en place, `logger.exception`) et viser une réduction d'au moins 50% des `502` liés à des erreurs transitoires sur une semaine d'utilisation.

### 3. Absence d'évaluation systématique de la qualité des réponses

- **Constat** : rien ne garantit dans le temps que les revues de presse générées respectent bien la consigne « ne mentionne que ce qui est réellement présent dans la discussion » (anti-hallucination) — seule la structure de sortie est testée (`TestModel` en CI), pas la fidélité du contenu généré par le vrai modèle.
- **Implémentation proposée** : mettre en place un petit jeu d'évaluation (10-20 discussions type + thème attendu), exécuté périodiquement avec le vrai modèle Mistral, et un second appel LLM « juge » qui vérifie que chaque article de la revue générée est bien attribuable à un passage de la discussion (score de fidélité 0-1).
- **Objectif mesurable** : obtenir un score moyen de fidélité ≥ 0.9 sur le jeu d'évaluation, suivi à chaque changement de prompt ou de modèle pour détecter une régression avant mise en production.

Chaque recommandation ci-dessus est réalisable sans changement d'architecture : elles portent sur `news.py` et `llm.py` uniquement.
