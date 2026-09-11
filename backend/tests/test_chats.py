import llm
import main
import news
from pydantic_ai.models.test import TestModel


def use_test_model(monkeypatch, reply: str = "Réponse factice de test") -> None:
    """Replace the real Mistral model with PydanticAI's TestModel so tests
    never call the real LLM provider and get a deterministic reply.
    call_tools=[] so TestModel doesn't auto-probe the search_news tool
    (which would otherwise hit the real World News API)."""
    monkeypatch.setattr(
        llm,
        "MistralModel",
        lambda *_args, **_kwargs: TestModel(custom_output_text=reply, call_tools=[]),
    )


# --- POST /chats -----------------------------------------------------------


def test_create_chat_requires_authentication(client):
    response = client.post("/chats")
    assert response.status_code == 401


def test_create_chat_returns_a_new_empty_chat(client, auth_headers):
    headers = auth_headers()
    response = client.post("/chats", headers=headers)
    assert response.status_code == 200
    chat_id = response.json()["id"]

    detail = client.get(f"/chats/{chat_id}", headers=headers)
    assert detail.status_code == 200
    assert detail.json() == {"id": chat_id, "messages": []}


# --- GET /chats -------------------------------------------------------------


def test_list_chats_requires_authentication(client):
    response = client.get("/chats")
    assert response.status_code == 401


def test_list_chats_only_returns_own_chats(client, auth_headers):
    owner_headers = auth_headers("owner@test.com", "secret")
    owned_chat_id = client.post("/chats", headers=owner_headers).json()["id"]

    other_headers = auth_headers("other@test.com", "secret")
    client.post("/chats", headers=other_headers)

    response = client.get("/chats", headers=owner_headers)
    assert response.status_code == 200
    assert [chat["id"] for chat in response.json()] == [owned_chat_id]


# --- GET /chats/{id} ---------------------------------------------------------


def test_get_chat_requires_authentication(client, auth_headers):
    chat_id = client.post("/chats", headers=auth_headers()).json()["id"]

    response = client.get(f"/chats/{chat_id}")
    assert response.status_code == 401


def test_get_nonexistent_chat_returns_404(client, auth_headers):
    response = client.get("/chats/999", headers=auth_headers())
    assert response.status_code == 404


def test_get_another_users_chat_returns_404(client, auth_headers):
    owner_headers = auth_headers("owner@test.com", "secret")
    chat_id = client.post("/chats", headers=owner_headers).json()["id"]

    intruder_headers = auth_headers("intruder@test.com", "secret")
    response = client.get(f"/chats/{chat_id}", headers=intruder_headers)

    # 404, not 403: an intruder must not be able to tell the chat exists.
    assert response.status_code == 404


# --- POST /chats/{id}/messages ----------------------------------------------


def test_post_message_requires_authentication(client, auth_headers):
    chat_id = client.post("/chats", headers=auth_headers()).json()["id"]

    response = client.post(f"/chats/{chat_id}/messages", json={"content": "Bonjour"})
    assert response.status_code == 401


def test_post_message_to_another_users_chat_returns_404(client, auth_headers):
    owner_headers = auth_headers("owner@test.com", "secret")
    chat_id = client.post("/chats", headers=owner_headers).json()["id"]

    intruder_headers = auth_headers("intruder@test.com", "secret")
    response = client.post(
        f"/chats/{chat_id}/messages",
        json={"content": "Bonjour"},
        headers=intruder_headers,
    )

    assert response.status_code == 404


def test_post_message_returns_llm_reply_and_persists_history(client, auth_headers, monkeypatch):
    use_test_model(monkeypatch, reply="Voici votre revue de presse.")
    headers = auth_headers()
    chat_id = client.post("/chats", headers=headers).json()["id"]

    response = client.post(
        f"/chats/{chat_id}/messages",
        json={"content": "Bonjour"},
        headers=headers,
    )

    assert response.status_code == 200
    assert response.json() == {"role": "assistant", "content": "Voici votre revue de presse."}

    detail = client.get(f"/chats/{chat_id}", headers=headers).json()
    assert detail["messages"] == [
        {"role": "user", "content": "Bonjour"},
        {"role": "assistant", "content": "Voici votre revue de presse."},
    ]


def test_post_message_accumulates_conversation_history(client, auth_headers, monkeypatch):
    use_test_model(monkeypatch, reply="Réponse")
    headers = auth_headers()
    chat_id = client.post("/chats", headers=headers).json()["id"]

    client.post(f"/chats/{chat_id}/messages", json={"content": "Premier message"}, headers=headers)
    client.post(f"/chats/{chat_id}/messages", json={"content": "Deuxième message"}, headers=headers)

    messages = client.get(f"/chats/{chat_id}", headers=headers).json()["messages"]
    assert [m["content"] for m in messages] == [
        "Premier message",
        "Réponse",
        "Deuxième message",
        "Réponse",
    ]


def test_post_message_with_llm_failure_returns_502_without_persisting(
    client, auth_headers, monkeypatch
):
    def broken_model(*_args, **_kwargs):
        raise RuntimeError("LLM provider misconfigured")

    monkeypatch.setattr(llm, "MistralModel", broken_model)

    headers = auth_headers()
    chat_id = client.post("/chats", headers=headers).json()["id"]

    response = client.post(
        f"/chats/{chat_id}/messages",
        json={"content": "Bonjour"},
        headers=headers,
    )

    assert response.status_code == 502

    detail = client.get(f"/chats/{chat_id}", headers=headers).json()
    assert detail["messages"] == []


def test_post_message_gives_agent_a_search_news_tool(client, auth_headers, monkeypatch):
    """The chat agent has a search_news tool available (backed by World News
    API's /search-news) that it can call mid-conversation for fresh articles."""
    captured_queries = []

    def fake_search_news(query, *_args, **_kwargs):
        captured_queries.append(query)
        return [
            {
                "title": "Titre article",
                "summary": "Resume article",
                "text": "Texte complet",
                "image": None,
                "url": "https://example.com/article",
                "publish_date": "2026-09-10 09:00:00",
            }
        ]

    monkeypatch.setattr(news, "search_news", fake_search_news)
    # call_tools="all" (TestModel's default) makes it probe every registered
    # tool once, so this proves the tool is actually wired into the agent.
    monkeypatch.setattr(
        llm, "MistralModel", lambda *_a, **_kw: TestModel(custom_output_text="Reponse")
    )

    headers = auth_headers()
    chat_id = client.post("/chats", headers=headers).json()["id"]

    response = client.post(
        f"/chats/{chat_id}/messages",
        json={"content": "Donne-moi plus de details sur ce sujet"},
        headers=headers,
    )

    assert response.status_code == 200
    assert captured_queries, "the search_news tool should have been called"


# --- System prompt continuity -------------------------------------------------


def test_chat_captures_system_prompt_at_creation(client, auth_headers, monkeypatch):
    """The system prompt (base instructions + that day's digest) is captured
    once when the chat is created, not recomputed on the fly, so it survives
    later changes to the global settings."""
    headers = auth_headers()
    client.put(
        "/settings/system-prompt",
        json={"system_prompt": "Instructions initiales"},
        headers=headers,
    )

    chat_id = client.post("/chats", headers=headers).json()["id"]

    # Changing the global prompt after the chat exists must not affect it.
    client.put(
        "/settings/system-prompt",
        json={"system_prompt": "Instructions modifiees"},
        headers=headers,
    )

    captured = []

    async def fake_generate_reply(history, system_prompt, tools=()):
        captured.append(system_prompt)
        return "Reponse"

    monkeypatch.setattr(main, "generate_reply", fake_generate_reply)
    client.post(f"/chats/{chat_id}/messages", json={"content": "Bonjour"}, headers=headers)

    assert captured == ["Instructions initiales"]


def test_post_message_reuses_the_same_system_prompt_across_the_whole_discussion(
    client, auth_headers, monkeypatch
):
    """Every message of an ongoing discussion must be answered with the exact
    same system prompt, even if the global settings or the news digest change
    in between - continuity within an already-started discussion must not be
    broken by a later refresh."""
    captured_prompts = []

    async def fake_generate_reply(history, system_prompt, tools=()):
        captured_prompts.append(system_prompt)
        return "Reponse"

    monkeypatch.setattr(main, "generate_reply", fake_generate_reply)
    headers = auth_headers()

    chat_id = client.post("/chats", headers=headers).json()["id"]
    client.post(f"/chats/{chat_id}/messages", json={"content": "Premier message"}, headers=headers)

    client.put(
        "/settings/system-prompt",
        json={"system_prompt": "Nouvelles instructions apres coup"},
        headers=headers,
    )

    client.post(f"/chats/{chat_id}/messages", json={"content": "Deuxieme message"}, headers=headers)

    assert len(captured_prompts) == 2
    assert captured_prompts[0] == captured_prompts[1]
    assert "Nouvelles instructions apres coup" not in captured_prompts[1]
