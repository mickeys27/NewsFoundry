from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import JSON, Column
from sqlmodel import Field, SQLModel


class User(SQLModel, table=True):
    id: Optional[int] = Field(primary_key=True)
    email: str = Field(unique=True, index=True)
    hashed_password: str = Field()


class Chat(SQLModel, table=True):
    id: Optional[int] = Field(primary_key=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    # Full message history, e.g. [{"role": "user", "content": "..."}, ...]
    messages: list[dict] = Field(default_factory=list, sa_column=Column(JSON))
    # The system prompt (base instructions + that day's news digest) used for
    # this discussion, captured once when the chat is created and reused for
    # every message in it. Without this, the system prompt would drift day to
    # day (e.g. after a digest refresh) and break continuity of an already
    # ongoing discussion.
    system_prompt: str = Field(default="")


DEFAULT_SYSTEM_PROMPT = (
    "Tu es l'assistant de revue de presse de NewsFoundry. Reponds toujours en "
    "francais, de maniere claire, concise et factuelle, dans un style de synthese "
    "de presse professionnelle. Structure les reponses longues avec des puces. "
    "Reste neutre sur les sujets d'actualite et precise quand une information "
    "meriterait d'etre verifiee aupres d'une source recente. Si l'utilisateur "
    "demande plus de details ou des informations plus recentes sur un sujet, "
    "utilise l'outil de recherche d'actualites pour charger de nouveaux articles "
    "avant de repondre."
)


class Settings(SQLModel, table=True):
    # Single-row table: the app has one global system prompt, id is always 1.
    id: Optional[int] = Field(default=1, primary_key=True)
    system_prompt: str = Field(default=DEFAULT_SYSTEM_PROMPT)


DEFAULT_NEWS_SYNTHESIS_PROMPT = (
    "Tu vas recevoir une liste de titres et resumes d'articles d'actualite du jour. "
    "Redige une synthese courte en francais, sous forme de liste a puces : une puce "
    "par sujet distinct, une phrase courte par puce, pas de titres ni de sous-titres, "
    "15 puces maximum. Regroupe les informations qui parlent du meme sujet et evite "
    "les repetitions. Va a l'essentiel."
)


class NewsDigest(SQLModel, table=True):
    # Single-row table (id always 1): the latest LLM-synthesized top-news digest.
    # It is refreshed on demand (not on every chat message) and persisted so the
    # chat system prompt stays stable across a day instead of drifting between
    # messages of the same ongoing discussion.
    id: Optional[int] = Field(default=1, primary_key=True)
    synthesis_prompt: str = Field(default=DEFAULT_NEWS_SYNTHESIS_PROMPT)
    content: str = Field(default="")
    updated_at: Optional[datetime] = Field(default=None)


class PressReview(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    # The discussion this revue was synthesized from. Every revue now comes
    # directly from a chat's own history, so this is required (not
    # optional). Lets a discussion show only the press reviews generated
    # within it via the "Revue de presse" tab.
    chat_id: int = Field(foreign_key="chat.id", index=True)
    title: str
    # The general synthesis of the theme, as produced by the press review
    # agent's structured output.
    summary: str
    # The exact prompt sent to the LLM to generate this revue, shown back to
    # the user for transparency.
    prompt: str = Field(default="")
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class PressReviewArticle(SQLModel, table=True):
    # The raw source articles a PressReview's synthesis was built from, shown
    # alongside the AI text as individual source cards. Only title/summary
    # are kept, matching the "title and summary only" rule used everywhere
    # article data from World News API is persisted.
    id: Optional[int] = Field(default=None, primary_key=True)
    press_review_id: int = Field(foreign_key="pressreview.id", index=True)
    title: str
    summary: str = Field(default="")


DEFAULT_PRESS_REVIEW_LIST_LIMIT = 5


class DisplaySettings(SQLModel, table=True):
    # Single-row table (id always 1): UI display preferences.
    id: Optional[int] = Field(default=1, primary_key=True)
    press_review_list_limit: int = Field(default=DEFAULT_PRESS_REVIEW_LIST_LIMIT)
