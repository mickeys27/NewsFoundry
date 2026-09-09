import os

from pydantic_ai import Agent
from pydantic_ai.models.mistral import MistralModel

MISTRAL_MODEL_NAME = os.getenv("MISTRAL_MODEL", "mistral-small-latest")


class LLMError(Exception):
    """Raised when the LLM provider cannot produce a reply."""


def _build_agent(system_prompt: str) -> Agent:
    # Built lazily (not at import time) so the app can still start without
    # MISTRAL_API_KEY configured; only sending a message requires it.
    return Agent(MistralModel(MISTRAL_MODEL_NAME), system_prompt=system_prompt)


async def generate_reply(history: list[dict], system_prompt: str) -> str:
    """Send the full conversation so far to the LLM and return its reply."""
    conversation = "\n".join(f"{message['role']}: {message['content']}" for message in history)

    try:
        agent = _build_agent(system_prompt)
        result = await agent.run(conversation)
    except Exception as error:
        raise LLMError("The LLM provider could not be reached") from error

    return result.output
