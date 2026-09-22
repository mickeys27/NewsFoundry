# Bilan critique : qualité des réponses et fluidité des interactions

Ce document complète `docs/ai.md` (qui traite déjà de la robustesse des appels
réseau, du retry et d'un premier jet d'évaluation de fidélité). Il se
concentre sur deux angles distincts, demandés explicitement en fin de
formation : **la qualité perçue des résultats côté utilisateur** et **la
fluidité de l'interaction**, en s'appuyant sur une observation directe du
code actuel (`backend/src/llm.py`, `backend/src/main.py`,
`frontend/app/home/page.tsx`).

## Regard critique global

Sur la **qualité des résultats** : le modèle utilisé (`mistral-small-latest`)
produit des réponses de chat et des revues de presse globalement cohérentes
sur les cas testés manuellement, et les deux prompts systèmes intègrent des
garde-fous explicites (consigne anti-hallucination pour la revue de presse,
neutralité pour le chat). Mais **rien n'est mesuré ni surveillé dans le
temps** : aucune trace, aucun log structuré des entrées/sorties du LLM,
aucune métrique de qualité au-delà des tests unitaires en CI qui utilisent
`TestModel` (donc jamais le vrai modèle). Concrètement, si une régression de
qualité apparaît après un changement de prompt ou de version de modèle,
l'équipe ne le saurait qu'en la découvrant a posteriori dans les retours
utilisateurs.

Sur la **fluidité des interactions** : l'utilisateur envoie un message et
attend un texte fixe (« … » / génération en cours) jusqu'à ce que **la
réponse complète** arrive d'un coup — que ce soit pour un message de chat
(`POST /chats/{id}/messages`) ou pour une revue de presse
(`POST /press-reviews`). Il n'y a aucun affichage progressif, ce qui est
aujourd'hui l'attente standard sur toute application de chat IA. Sur un
message qui nécessite un appel à `search_news_tool` (donc deux allers-retours
LLM + un appel World News API en série), l'attente peut dépasser plusieurs
secondes sans aucun retour visuel intermédiaire — au-delà du seuil de 10
secondes identifié par Nielsen Norman Group comme la limite au-delà de
laquelle l'utilisateur perd le fil de la tâche.

Les pistes ci-dessous répondent aux trois questions posées : l'observabilité
(MLflow), le streaming, et le temps de génération des revues de presse.

---

## Piste 1 — Absence totale d'observabilité sur l'agent (MLflow tracing)

**Constat.** Aucune des trois fonctions qui appellent le LLM
(`generate_reply`, `generate_news_synthesis`, `generate_press_review_from_chat`
dans `llm.py`) n'enregistre de trace, de durée d'exécution ou de contenu
échangé au-delà d'un `logger.exception` en cas d'erreur. Il est donc
aujourd'hui **impossible de répondre factuellement** à des questions pourtant
basiques : combien de temps met une réponse en moyenne ? Le modèle appelle-t-il
`search_news_tool` souvent, et cela ralentit-il la conversation ? Y a-t-il des
conversations où le modèle « boucle » ou répond de travers ? Ce manque de
visibilité est aussi ce qui empêche de vérifier la piste n°3 de `docs/ai.md`
(fidélité anti-hallucination) autrement qu'à la main.

**Implémentation proposée.**
1. Ajouter `mlflow` aux dépendances backend et pointer `MLFLOW_TRACKING_URI`
   vers un serveur MLflow (auto-hébergé sur Railway dans un service séparé, ou
   une instance locale en développement).
2. Au démarrage de l'application (dans `main.py`, avant la création de
   `app = FastAPI()`), activer l'auto-instrumentation officielle de
   PydanticAI :
   ```python
   import mlflow
   mlflow.pydantic_ai.autolog()
   mlflow.set_experiment("newsfoundry-agents")
   ```
   Cette seule ligne trace automatiquement chaque `agent.run(...)` (les trois
   fonctions de `llm.py` sont donc couvertes sans aucune modification de leur
   code) : prompt système, message envoyé, appels d'outils (`search_news_tool`),
   sortie du modèle, et durée de chaque étape.
3. Enrichir les traces avec des attributs métier utiles à l'analyse, via
   `mlflow.update_current_trace(tags={...})` juste avant `agent.run(...)` dans
   `generate_reply` et `generate_press_review_from_chat` : `chat_id`,
   `history_length` (nombre de messages), `used_tool` (booléen). Cela permet
   ensuite de filtrer/agréger les traces par ces critères dans l'UI MLflow ou
   via `mlflow.search_traces(...)`.

**Objectif mesurable.** Disposer, après une semaine d'usage réel, d'un
tableau de bord (ou d'une requête `search_traces`) donnant la latence P50/P95
par type d'agent (chat / revue / synthèse), et pouvoir répondre avec des
chiffres réels à la question « la génération d'une revue de presse est-elle
satisfaisante ? » — ce qui n'est pas possible aujourd'hui faute de données.

---

## Piste 2 — Réponses affichées d'un bloc plutôt qu'en flux (streaming)

**Constat.** Le flux actuel est entièrement synchrone bout en bout :
- Backend : `await generate_reply(...)` dans `post_message` (main.py, ligne
  ~493) attend que `agent.run(...)` renvoie `result.output` en entier avant
  de retourner la réponse HTTP.
- Frontend : `sendMessage()` (`lib/chats.ts`) fait un `fetch` classique et
  attend `response.json()` ; pendant ce temps, `page.tsx` affiche seulement
  un indicateur de saisie figé (`isSending`, ligne ~407), sans aucun texte
  qui apparaît progressivement.

Le même problème existe pour `handleGenerateRevue`, avec le texte fixe
« Génération de la revue de presse… » (page.tsx, ligne ~456) affiché pendant
toute la durée de l'appel, potentiellement plusieurs secondes.

**Implémentation proposée.**
1. **Backend** — PydanticAI (`>=2.42`, déjà utilisé) expose `agent.run_stream()`
   qui permet d'itérer sur les deltas de texte au fur et à mesure de leur
   génération par le modèle. Transformer `POST /chats/{chat_id}/messages` en
   endpoint `StreamingResponse` (`media_type="text/event-stream"`) :
   ```python
   async def event_stream():
       async with agent.run_stream(conversation) as result:
           async for delta in result.stream_text(delta=True):
               yield f"data: {json.dumps({'delta': delta})}\n\n"
           yield f"data: {json.dumps({'done': True, 'full_text': result.output})}\n\n"
       # message complet persisté en base une fois le stream terminé
   ```
2. **Frontend** — remplacer le `fetch` + `.json()` de `sendMessage` par une
   lecture du corps en flux (`response.body.getReader()`), en parsant les
   lignes `data: ...` au fur et à mesure et en les concaténant dans le
   dernier message assistant du state React (append token par token plutôt
   que remplacement d'un coup). Le JWT restant nécessaire en en-tête
   `Authorization`, on garde `fetch` plutôt que `EventSource` (qui ne permet
   pas d'en-têtes personnalisés).
3. La revue de presse utilise une sortie structurée (`PressReviewOutput`) :
   PydanticAI permet aussi de streamer un objet structuré en cours de
   validation (objets partiels). À défaut de streamer chaque champ, une
   première itération plus simple consiste à streamer uniquement le texte
   brut du modèle et à ne parser en JSON qu'à la réception du flux complet,
   tout en affichant un indicateur de progression réel (nombre de caractères
   déjà reçus) plutôt qu'un texte figé.

**Objectif mesurable.** Faire tomber le *temps avant premier retour visuel*
(actuellement égal au temps de génération complet, soit plusieurs secondes)
sous la barre du **1 seconde**, conformément aux repères NN/g sur les temps
de réponse perçus. Ce chiffre est directement vérifiable dans les traces
MLflow de la Piste 1 en comparant l'horodatage du premier delta reçu par le
frontend à celui de la fin de la génération.

---

## Piste 3 — Temps de génération des revues de presse et effet de la longueur de la discussion

**Constat.** À ce jour, cette durée **n'est pas mesurée** (voir Piste 1), ce
qui est en soi la première conclusion à tirer : impossible de dire
aujourd'hui si elle est satisfaisante. Le code fait cependant apparaître un
risque de dégradation prévisible avec la longueur de la discussion :
`_format_chat_history` (`llm.py`, ligne ~102) concatène **l'intégralité** des
messages de la discussion, sans troncature ni résumé, et cette chaîne
complète est envoyée telle quelle au modèle à chaque génération de revue.
Le nombre de tokens envoyés — et donc la latence et le coût — croît ainsi
linéairement avec le nombre de messages de la discussion, sans plafond : une
discussion longue (plusieurs dizaines d'échanges) produira un prompt
nettement plus volumineux qu'une discussion de 3 messages, et finira par
approcher la limite de contexte du modèle.

**Implémentation proposée.**
1. Une fois la Piste 1 en place, taguer chaque trace de
   `generate_press_review_from_chat` avec `history_length` et
   `history_char_count`, puis constituer après quelques jours d'usage un
   graphique latence vs. longueur (`mlflow.search_traces` → dataframe →
   nuage de points). Cela transforme la question qualitative de l'énoncé en
   mesure factuelle.
2. Si la corrélation se confirme (attendue vu le point ci-dessus), introduire
   une étape de **résumé progressif** : au lieu de renvoyer l'historique brut
   complet, ne garder in extenso que les N derniers messages et remplacer le
   reste par un résumé condensé (déjà généré et mis en cache dès qu'une
   discussion dépasse un seuil, ex. 20 messages), à la manière de ce qui est
   déjà fait pour le digest d'actualités du jour (`generate_news_synthesis`).
   Cela plafonne la taille du prompt indépendamment de la longueur réelle de
   la discussion.
3. Alternative plus légère à court terme : ne transmettre que les messages
   effectivement pertinents pour le thème demandé (filtrage lexical simple,
   sur le même principe que `_build_search_query` dans `news.py`) plutôt que
   la discussion entière.

**Objectif mesurable.** Passer d'un prompt dont la taille croît sans limite
avec la discussion à un prompt de taille bornée (ex. plafond fixé à
l'équivalent de ~20 messages), avec pour cible une latence P95 de génération
de revue de presse stable (variation < 20 %) quelle que soit la longueur de
la discussion, mesurée via les mêmes traces MLflow avant/après le
plafonnement.

---

## Piste 4 — Une revue de presse ne peut porter que sur ce qui a déjà été discuté

**Constat.** Contrairement à l'agent de chat (`generate_reply`, qui dispose
de `search_news_tool`), l'agent de revue de presse
(`generate_press_review_from_chat`, `llm.py` ligne ~116) est construit
**sans aucun outil** et ne travaille que sur `chat.messages`. Le prompt
système lui demande explicitement de dire qu'il n'a rien trouvé plutôt que
d'inventer si le thème demandé n'a pas été abordé dans la conversation — ce
qui est le bon réflexe anti-hallucination, mais dégrade l'utilité perçue :
un utilisateur qui ouvre la fenêtre de génération de revue et tape un thème
non discuté obtient une revue vide, sans qu'on lui explique qu'il devrait
d'abord en parler dans le chat.

**Implémentation proposée.** Deux options complémentaires, à trancher selon
l'usage réel observé :
- **Coté produit (rapide)** : quand `output.articles` est vide, l'afficher
  clairement dans l'UI comme « Ce thème n'a pas été abordé dans cette
  discussion » avec une suggestion d'en discuter d'abord, plutôt qu'une carte
  vide silencieuse.
- **Côté agent (plus ambitieux)** : donner à cet agent le même
  `search_news_tool` que l'agent de chat, avec un prompt qui l'autorise à
  l'utiliser *uniquement* pour compléter des articles déjà mentionnés dans la
  discussion (jamais pour introduire un sujet entièrement nouveau), afin de
  garder la garantie anti-hallucination tout en évitant les revues vides sur
  des thèmes pourtant liés à ce qui a été dit.

**Objectif mesurable.** Suivre la proportion de revues générées avec
`articles` vide (mesurable simplement en base, `PressReview` sans ligne
associée dans `PressReviewArticle`) et viser une réduction d'au moins 50 %
de ce taux après mise en place de l'option retenue.

---

## Synthèse

| Piste | Levier | Effort | Impact attendu |
|---|---|---|---|
| 1. Traçage MLflow | Qualité + fluidité (mesure) | Faible (1 ligne d'autolog + tags) | Rend les 3 autres pistes vérifiables |
| 2. Streaming | Fluidité perçue | Moyen (backend SSE + frontend) | Temps avant 1ère réponse visible < 1s |
| 3. Historique borné | Fluidité + coût | Moyen | Latence stable quelle que soit la longueur du chat |
| 4. Revue sans outil de recherche | Qualité perçue | Faible à moyen | Moins de revues vides sans sacrifier l'anti-hallucination |

La piste 1 est volontairement présentée en premier : sans elle, les
affirmations sur les pistes 2 et 3 restent des hypothèses de lecture de code,
pas des mesures — c'est elle qui transforme ce document en un vrai suivi de
performance dans le temps plutôt qu'un audit ponctuel.
