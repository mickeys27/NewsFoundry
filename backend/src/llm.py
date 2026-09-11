import logging
import os
from typing import Callable, Sequence

from pydantic import BaseModel
from pydantic_ai import Agent
from pydantic_ai.models.mistral import MistralModel

logger = logging.getLogger(__name__)

MISTRAL_MODEL_NAME = os.getenv("MISTRAL_MODEL", "mistral-small-latest")


class LLMError(Exception):
    """Raised when the LLM provider cannot produce a reply."""


class ArticleSynthesis(BaseModel):
    """One news item/subject discussed in the chat, summarized for the revue."""

    title: str
    summary: str


class PressReviewOutput(BaseModel):
    """Structured output for a press review synthesized from a chat's own
    discussion history. Matches exactly what gets stored/displayed: a title,
    a general synthesis, and the synthesis of each distinct article/subject
    the discussion touched on."""

    title: str
    summary: str
    articles: list[ArticleSynthesis]


PRESS_REVIEW_AGENT_SYSTEM_PROMPT = (
    "Tu es un agent specialise dans la redaction de revues de presse a partir "
    "de l'historique d'une discussion de chat. On te donne l'integralite des "
    "echanges de la discussion et un sujet precis. Analyse la discussion, "
    "identifie les informations d'actualite qui s'y trouvent en rapport avec "
    "ce sujet, et produis une revue de presse structuree : un titre court, "
    "une synthese generale du sujet en quelques phrases, et la liste des "
    "articles ou sujets d'actualite distincts mentionnes dans la discussion "
    "en rapport avec le theme, chacun avec son propre titre court et son "
    "resume. Ne mentionne que ce qui est reellement present dans la "
    "discussion ; n'invente aucune information. Si la discussion ne contient "
    "aucune information pertinente pour ce sujet, dis-le clairement dans la "
    "synthese generale et laisse la liste des articles vide. "
    "Chaque champ texte (titre, synthese generale, titre et resume de chaque "
    "article) doit contenir uniquement le contenu factuel lui-meme : ne "
    "commence jamais par une phrase d'introduction ou de mise en contexte "
    "du type 'Voici la revue de presse', 'Cette synthese porte sur', "
    "'D'apres la discussion' ou equivalent, et ne fais aucun commentaire sur "
    "la tache elle-meme. Va directement au fait."
)


def _build_agent(system_prompt: str, tools: Sequence[Callable] = ()) -> Agent:
    # Built lazily (not at import time) so the app can still start without
    # MISTRAL_API_KEY configured; only sending a message requires it.
    return Agent(MistralModel(MISTRAL_MODEL_NAME), system_prompt=system_prompt, tools=tools)


async def generate_reply(
    history: list[dict], system_prompt: str, tools: Sequence[Callable] = ()
) -> str:
    """Send the full conversation so far to the LLM and return its reply.
    `tools` lets the agent call functions (e.g. a news search) mid-conversation
    when it decides it needs fresher information to answer."""
    conversation = "\n".join(f"{message['role']}: {message['content']}" for message in history)

    try:
        agent = _build_agent(system_prompt, tools=tools)
        result = await agent.run(conversation)
    except Exception as error:
        logger.exception("Mistral request failed")
        raise LLMError("The LLM provider could not be reached") from error

    return result.output


async def generate_news_synthesis(articles: list[dict], synthesis_prompt: str) -> str:
    """Condense a list of {"title", "summary"} articles into a short digest."""
    if not articles:
        return ""

    listing = "\n".join(
        f"- {article['title']}" + (f" : {article['summary']}" if article.get("summary") else "")
        for article in articles
    )

    try:
        agent = _build_agent(synthesis_prompt)
        result = await agent.run(listing)
    except Exception as error:
        logger.exception("Mistral news synthesis failed")
        raise LLMError("The LLM provider could not synthesize the news") from error

    return result.output


def _format_chat_history(history: list[dict]) -> str:
    if not history:
        return "(discussion vide, aucun message)"
    return "\n".join(f"{message['role']}: {message['content']}" for message in history)


async def generate_press_review_from_chat(history: list[dict], theme: str) -> PressReviewOutput:
    """Synthesize a press review from a chat's own message history, focused
    on a given theme. Uses a dedicated agent - separate from the chat's -
    with no tools (it only needs to read the conversation already given to
    it) and a structured output type so the result maps directly onto what
    gets stored for display, instead of parsing free-form text."""
    # A specialized, tool-less agent for this narrower task rather than
    # reusing the chat's general-purpose, tool-equipped agent.
    agent = Agent(
        MistralModel(MISTRAL_MODEL_NAME),
        system_prompt=PRESS_REVIEW_AGENT_SYSTEM_PROMPT,
        output_type=PressReviewOutput,
    )
    user_prompt = (
        f"Sujet de la revue de presse : {theme}\n\n"
        f"Historique de la discussion :\n{_format_chat_history(history)}"
    )

    try:
        result = await agent.run(user_prompt)
    except Exception as error:
        logger.exception("Press review synthesis from chat history failed")
        raise LLMError("The LLM provider could not synthesize the press review") from error

    return result.output
