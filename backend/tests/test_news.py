import llm
import main
import news
from main import build_system_prompt, press_review_excerpt
from models import DEFAULT_NEWS_SYNTHESIS_PROMPT, DEFAULT_PRESS_REVIEW_LIST_LIMIT, NewsDigest, Settings
from pydantic_ai.models.test import TestModel


def use_test_model(monkeypatch, reply: str = "Synthese factice de test", call_tools="all") -> None:
    """Replace the real Mistral model with PydanticAI's TestModel so tests
    never call the real LLM provider and get a deterministic reply.
    call_tools=[] avoids auto-probing the chat's search_news tool (which
    would otherwise hit the real World News API) when posting a message."""
    monkeypatch.setattr(
        llm,
        "MistralModel",
        lambda *_args, **_kwargs: TestModel(custom_output_text=reply, call_tools=call_tools),
    )


def fake_press_review(
    monkeypatch,
    title: str = "Titre genere",
    summary: str = "Synthese generee",
    articles: list[dict] | None = None,
):
    """Replace the press review agent call with a stub returning a fixed
    PressReviewOutput, and capture the (history, theme) it was called with."""
    if articles is None:
        articles = [{"title": "Un titre", "summary": "Un resume"}]

    captured = {}

    async def fake(history, theme):
        captured["history"] = history
        captured["theme"] = theme
        return llm.PressReviewOutput(
            title=title,
            summary=summary,
            articles=[llm.ArticleSynthesis(**article) for article in articles],
        )

    monkeypatch.setattr(main, "generate_press_review_from_chat", fake)
    return captured


FAKE_ARTICLES = [
    {"title": "Un titre", "summary": "Un resume"},
    {"title": "Un autre titre", "summary": ""},
]


# --- build_system_prompt (pure function) ------------------------------------


def test_build_system_prompt_returns_plain_prompt_when_digest_is_empty():
    settings = Settings(id=1, system_prompt="Instructions de base")
    digest = NewsDigest(id=1, content="")

    assert build_system_prompt(settings, digest) == "Instructions de base"


def test_build_system_prompt_appends_digest_when_present():
    settings = Settings(id=1, system_prompt="Instructions de base")
    digest = NewsDigest(id=1, content="- Sujet du jour")

    result = build_system_prompt(settings, digest)

    assert "Instructions de base" in result
    assert "- Sujet du jour" in result


# --- GET /settings/news-digest ------------------------------------------------


def test_get_news_digest_requires_authentication(client):
    response = client.get("/settings/news-digest")
    assert response.status_code == 401


def test_get_news_digest_returns_defaults_on_first_call(client, auth_headers):
    response = client.get("/settings/news-digest", headers=auth_headers())
    assert response.status_code == 200
    body = response.json()
    assert body["synthesis_prompt"] == DEFAULT_NEWS_SYNTHESIS_PROMPT
    assert body["content"] == ""
    assert body["updated_at"] is None


# --- PUT /settings/news-digest/synthesis-prompt -------------------------------


def test_update_news_synthesis_prompt_requires_authentication(client):
    response = client.put("/settings/news-digest/synthesis-prompt", json={"synthesis_prompt": "x"})
    assert response.status_code == 401


def test_update_news_synthesis_prompt_persists(client, auth_headers):
    headers = auth_headers()
    response = client.put(
        "/settings/news-digest/synthesis-prompt",
        json={"synthesis_prompt": "Sois tres bref"},
        headers=headers,
    )
    assert response.status_code == 200
    assert response.json()["synthesis_prompt"] == "Sois tres bref"

    refetched = client.get("/settings/news-digest", headers=headers)
    assert refetched.json()["synthesis_prompt"] == "Sois tres bref"


# --- POST /settings/news-digest/refresh ---------------------------------------


def test_refresh_news_digest_requires_authentication(client):
    response = client.post("/settings/news-digest/refresh")
    assert response.status_code == 401


def test_refresh_news_digest_fetches_and_saves(client, auth_headers, monkeypatch):
    monkeypatch.setattr(news, "fetch_top_news", lambda *_args, **_kwargs: FAKE_ARTICLES)
    use_test_model(monkeypatch, reply="- Synthese generee")
    headers = auth_headers()

    response = client.post("/settings/news-digest/refresh", headers=headers)

    assert response.status_code == 200
    body = response.json()
    assert body["content"] == "- Synthese generee"
    assert body["updated_at"] is not None

    persisted = client.get("/settings/news-digest", headers=headers)
    assert persisted.json()["content"] == "- Synthese generee"


def test_refresh_news_digest_returns_502_when_fetch_fails(client, auth_headers, monkeypatch):
    def broken_fetch(*_args, **_kwargs):
        raise news.NewsError("World News API request failed")

    monkeypatch.setattr(news, "fetch_top_news", broken_fetch)
    headers = auth_headers()

    response = client.post("/settings/news-digest/refresh", headers=headers)

    assert response.status_code == 502

    # A failed refresh must not overwrite the previously saved digest.
    persisted = client.get("/settings/news-digest", headers=headers)
    assert persisted.json()["content"] == ""


# --- _build_search_query (pure function) ----------------------------------------


def test_build_search_query_keeps_short_single_word_theme_as_is():
    assert news._build_search_query("technologie") == "technologie"


def test_build_search_query_ors_significant_words_of_a_real_topic():
    assert news._build_search_query("intelligence artificielle") == "intelligence OR artificielle"


def test_build_search_query_strips_filler_words_from_example_prompt():
    # Mirrors the example prompts shown in the chat UI, which users may type
    # verbatim as a revue theme; the API requires ALL words to match by
    # default, so an unfiltered natural-language sentence matches nothing.
    query = news._build_search_query("Résume l'actualité économique de la semaine")
    assert query == "économique"


def test_build_search_query_ors_multiple_significant_words_from_a_question():
    query = news._build_search_query("Quelles sont les dernières nouvelles en politique ?")
    assert query == "dernières OR politique"


# --- search_news_tool (chat agent tool) -----------------------------------------


def test_search_news_tool_returns_only_title_and_summary(monkeypatch):
    """The tool's output must stay simple for the agent: just title/summary,
    not the full raw World News API fields (image, url, publish_date...)."""
    monkeypatch.setattr(
        news,
        "search_news",
        lambda *_args, **_kwargs: [
            {
                "title": "Un titre",
                "summary": "Un resume",
                "text": "Texte complet tres long",
                "image": "https://example.com/image.jpg",
                "url": "https://example.com/article",
                "publish_date": "2026-09-10 09:00:00",
            }
        ],
    )

    result = news.search_news_tool("elections")

    assert result == [{"title": "Un titre", "summary": "Un resume"}]


def test_search_news_tool_falls_back_to_text_when_summary_empty(monkeypatch):
    monkeypatch.setattr(
        news,
        "search_news",
        lambda *_args, **_kwargs: [
            {
                "title": "Un titre",
                "summary": "",
                "text": "Le texte complet de l'article.",
                "image": None,
                "url": "https://example.com/article",
                "publish_date": None,
            }
        ],
    )

    result = news.search_news_tool("elections")

    assert result == [{"title": "Un titre", "summary": "Le texte complet de l'article."}]


# --- POST /press-reviews -------------------------------------------------------


def test_generate_press_review_requires_authentication(client):
    response = client.post("/press-reviews", json={"theme": "technologie", "chat_id": 1})
    assert response.status_code == 401


def test_generate_press_review_synthesizes_from_chat_history(client, auth_headers, monkeypatch):
    captured = fake_press_review(
        monkeypatch,
        title="Actualites politiques",
        summary="Synthese basee sur la discussion",
        articles=[{"title": "Sujet aborde", "summary": "Resume du sujet"}],
    )
    headers = auth_headers()
    chat_id = client.post("/chats", headers=headers).json()["id"]

    use_test_model(monkeypatch, reply="Voici les dernieres actualites en politique.", call_tools=[])
    client.post(
        f"/chats/{chat_id}/messages",
        json={"content": "Quelles sont les dernieres nouvelles en politique ?"},
        headers=headers,
    )

    response = client.post(
        "/press-reviews", json={"theme": "politique", "chat_id": chat_id}, headers=headers
    )

    assert response.status_code == 200
    body = response.json()
    assert body["title"] == "Actualites politiques"
    assert body["summary"] == "Synthese basee sur la discussion"
    assert body["articles"] == [{"title": "Sujet aborde", "summary": "Resume du sujet"}]
    assert body["generated_at"] is not None

    # The agent must receive the chat's own history and the chosen theme.
    assert captured["theme"] == "politique"
    assert captured["history"] == [
        {"role": "user", "content": "Quelles sont les dernieres nouvelles en politique ?"},
        {"role": "assistant", "content": "Voici les dernieres actualites en politique."},
    ]


def test_generate_press_review_works_with_empty_chat_history(client, auth_headers, monkeypatch):
    """The agent still runs (and may say there's nothing relevant) even when
    the discussion has no messages yet."""
    captured = fake_press_review(monkeypatch, summary="Aucune information pertinente.", articles=[])
    headers = auth_headers()
    chat_id = client.post("/chats", headers=headers).json()["id"]

    response = client.post(
        "/press-reviews", json={"theme": "technologie", "chat_id": chat_id}, headers=headers
    )

    assert response.status_code == 200
    assert captured["history"] == []
    assert response.json()["articles"] == []


def test_generate_press_review_rejects_empty_theme(client, auth_headers):
    headers = auth_headers()
    chat_id = client.post("/chats", headers=headers).json()["id"]
    response = client.post(
        "/press-reviews", json={"theme": "   ", "chat_id": chat_id}, headers=headers
    )
    assert response.status_code == 422


def test_generate_press_review_requires_a_chat_id(client, auth_headers):
    response = client.post("/press-reviews", json={"theme": "technologie"}, headers=auth_headers())
    assert response.status_code == 422


def test_generate_press_review_returns_502_on_llm_failure(client, auth_headers, monkeypatch):
    async def broken(history, theme):
        raise llm.LLMError("boom")

    monkeypatch.setattr(main, "generate_press_review_from_chat", broken)
    headers = auth_headers()
    chat_id = client.post("/chats", headers=headers).json()["id"]

    response = client.post(
        "/press-reviews", json={"theme": "technologie", "chat_id": chat_id}, headers=headers
    )

    assert response.status_code == 502


def test_generate_press_review_persists_it(client, auth_headers, monkeypatch):
    fake_press_review(monkeypatch, title="Revue generee", summary="- Revue generee")
    headers = auth_headers()
    chat_id = client.post("/chats", headers=headers).json()["id"]

    created = client.post(
        "/press-reviews", json={"theme": "technologie", "chat_id": chat_id}, headers=headers
    )
    review_id = created.json()["id"]

    detail = client.get(f"/press-reviews/{review_id}", headers=headers)
    assert detail.status_code == 200
    body = detail.json()
    assert body["id"] == review_id
    assert body["title"] == "Revue generee"
    assert body["summary"] == "- Revue generee"
    assert body["generated_at"] == created.json()["generated_at"]
    assert body["articles"] == [{"title": "Un titre", "summary": "Un resume"}]
    assert "technologie" in body["prompt"]


# --- GET /press-reviews --------------------------------------------------------


def test_list_press_reviews_requires_authentication(client):
    response = client.get("/press-reviews")
    assert response.status_code == 401


def test_list_press_reviews_only_returns_own_reviews(client, auth_headers, monkeypatch):
    fake_press_review(monkeypatch)

    owner_headers = auth_headers("owner@test.com", "secret")
    owner_chat_id = client.post("/chats", headers=owner_headers).json()["id"]
    created = client.post(
        "/press-reviews", json={"theme": "technologie", "chat_id": owner_chat_id}, headers=owner_headers
    )
    owned_review_id = created.json()["id"]

    other_headers = auth_headers("other@test.com", "secret")
    other_chat_id = client.post("/chats", headers=other_headers).json()["id"]
    client.post("/press-reviews", json={"theme": "sport", "chat_id": other_chat_id}, headers=other_headers)

    response = client.get("/press-reviews", headers=owner_headers)
    assert response.status_code == 200
    assert [review["id"] for review in response.json()] == [owned_review_id]


def test_generate_press_review_links_it_to_a_chat(client, auth_headers, monkeypatch):
    fake_press_review(monkeypatch)
    headers = auth_headers()
    chat_id = client.post("/chats", headers=headers).json()["id"]

    created = client.post(
        "/press-reviews", json={"theme": "technologie", "chat_id": chat_id}, headers=headers
    )
    assert created.status_code == 200

    other_chat_id = client.post("/chats", headers=headers).json()["id"]
    client.post("/press-reviews", json={"theme": "sport", "chat_id": other_chat_id}, headers=headers)

    scoped = client.get(f"/press-reviews?chat_id={chat_id}", headers=headers)
    assert scoped.status_code == 200
    assert [review["id"] for review in scoped.json()] == [created.json()["id"]]


def test_generate_press_review_rejects_another_users_chat_id(client, auth_headers, monkeypatch):
    fake_press_review(monkeypatch)

    owner_headers = auth_headers("owner@test.com", "secret")
    chat_id = client.post("/chats", headers=owner_headers).json()["id"]

    intruder_headers = auth_headers("intruder@test.com", "secret")
    response = client.post(
        "/press-reviews",
        json={"theme": "technologie", "chat_id": chat_id},
        headers=intruder_headers,
    )

    assert response.status_code == 404


# --- GET /press-reviews/{id} ----------------------------------------------------


def test_get_press_review_requires_authentication(client, auth_headers, monkeypatch):
    fake_press_review(monkeypatch)
    headers = auth_headers()
    chat_id = client.post("/chats", headers=headers).json()["id"]
    review_id = client.post(
        "/press-reviews", json={"theme": "technologie", "chat_id": chat_id}, headers=headers
    ).json()["id"]

    response = client.get(f"/press-reviews/{review_id}")
    assert response.status_code == 401


def test_get_nonexistent_press_review_returns_404(client, auth_headers):
    response = client.get("/press-reviews/999", headers=auth_headers())
    assert response.status_code == 404


def test_get_another_users_press_review_returns_404(client, auth_headers, monkeypatch):
    fake_press_review(monkeypatch)

    owner_headers = auth_headers("owner@test.com", "secret")
    chat_id = client.post("/chats", headers=owner_headers).json()["id"]
    review_id = client.post(
        "/press-reviews", json={"theme": "technologie", "chat_id": chat_id}, headers=owner_headers
    ).json()["id"]

    intruder_headers = auth_headers("intruder@test.com", "secret")
    response = client.get(f"/press-reviews/{review_id}", headers=intruder_headers)

    # 404, not 403: an intruder must not be able to tell the review exists.
    assert response.status_code == 404


# --- press_review_excerpt (pure function) ---------------------------------------


def test_press_review_excerpt_strips_markdown_markers():
    content = "# Titre\n\n**Intro** en gras.\n- Premier point\n- Deuxieme point"
    assert press_review_excerpt(content) == "Titre Intro en gras. Premier point Deuxieme point"


def test_press_review_excerpt_truncates_long_text_at_word_boundary():
    content = "mot " * 100
    excerpt = press_review_excerpt(content, max_length=20)
    assert excerpt.endswith("…")
    assert len(excerpt) <= 21


# --- GET/PUT /settings/display ---------------------------------------------------


def test_get_display_settings_requires_authentication(client):
    response = client.get("/settings/display")
    assert response.status_code == 401


def test_get_display_settings_returns_default(client, auth_headers):
    response = client.get("/settings/display", headers=auth_headers())
    assert response.status_code == 200
    assert response.json() == {"press_review_list_limit": DEFAULT_PRESS_REVIEW_LIST_LIMIT}


def test_update_display_settings_persists(client, auth_headers):
    headers = auth_headers()
    response = client.put(
        "/settings/display",
        json={"press_review_list_limit": 3},
        headers=headers,
    )
    assert response.status_code == 200
    assert response.json() == {"press_review_list_limit": 3}

    refetched = client.get("/settings/display", headers=headers)
    assert refetched.json() == {"press_review_list_limit": 3}


def test_update_display_settings_rejects_non_positive_limit(client, auth_headers):
    response = client.put(
        "/settings/display", json={"press_review_list_limit": 0}, headers=auth_headers()
    )
    assert response.status_code == 422


def test_list_press_reviews_respects_configured_limit(client, auth_headers, monkeypatch):
    fake_press_review(monkeypatch)
    headers = auth_headers()
    chat_id = client.post("/chats", headers=headers).json()["id"]

    client.put("/settings/display", json={"press_review_list_limit": 2}, headers=headers)

    ids = []
    for theme in ["un", "deux", "trois"]:
        created = client.post(
            "/press-reviews", json={"theme": theme, "chat_id": chat_id}, headers=headers
        )
        ids.append(created.json()["id"])

    response = client.get("/press-reviews", headers=headers)
    assert response.status_code == 200
    # Most recent first, capped to the configured limit.
    assert [review["id"] for review in response.json()] == list(reversed(ids))[:2]
