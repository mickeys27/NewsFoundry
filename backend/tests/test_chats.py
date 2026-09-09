import llm
from pydantic_ai.models.test import TestModel


def use_test_model(monkeypatch, reply: str = "Réponse factice de test") -> None:
    """Replace the real Mistral model with PydanticAI's TestModel so tests
    never call the real LLM provider and get a deterministic reply."""
    monkeypatch.setattr(llm, "MistralModel", lambda *_args, **_kwargs: TestModel(custom_output_text=reply))


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
