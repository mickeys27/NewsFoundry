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


DEFAULT_SYSTEM_PROMPT = (
    "Tu es l'assistant de revue de presse de NewsFoundry. Reponds toujours en "
    "francais, de maniere claire, concise et factuelle, dans un style de synthese "
    "de presse professionnelle. Structure les reponses longues avec des puces. "
    "Reste neutre sur les sujets d'actualite et precise quand une information "
    "meriterait d'etre verifiee aupres d'une source recente."
)


class Settings(SQLModel, table=True):
    # Single-row table: the app has one global system prompt, id is always 1.
    id: Optional[int] = Field(default=1, primary_key=True)
    system_prompt: str = Field(default=DEFAULT_SYSTEM_PROMPT)
