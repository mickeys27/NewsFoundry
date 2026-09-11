import os
import re
from datetime import datetime, timezone

import uvicorn
from auth import create_access_token, get_current_user, verify_password
from database import get_session, init_db
from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from llm import (
    LLMError,
    PRESS_REVIEW_AGENT_SYSTEM_PROMPT,
    generate_press_review_from_chat,
    generate_reply,
)
from models import Chat, DisplaySettings, NewsDigest, PressReview, PressReviewArticle, Settings, User
from news import NewsError, build_news_digest, search_news_tool
from pydantic import BaseModel
from sqlmodel import Session, select

app = FastAPI()

allowed_origins = os.getenv("FRONTEND_URL", "http://localhost:3000").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)


class LoginRequest(BaseModel):
    email: str
    password: str


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class ChatCreateResponse(BaseModel):
    id: int


class ChatSummary(BaseModel):
    id: int
    created_at: datetime
    last_message: str | None = None


class ChatDetailResponse(BaseModel):
    id: int
    messages: list[dict]


class MessageRequest(BaseModel):
    content: str


class MessageResponse(BaseModel):
    role: str
    content: str


class SystemPromptResponse(BaseModel):
    system_prompt: str


class SystemPromptUpdateRequest(BaseModel):
    system_prompt: str


class NewsDigestResponse(BaseModel):
    synthesis_prompt: str
    content: str
    updated_at: datetime | None


class NewsSynthesisPromptUpdateRequest(BaseModel):
    synthesis_prompt: str


class PressReviewRequest(BaseModel):
    theme: str
    chat_id: int


class PressReviewSummary(BaseModel):
    id: int
    title: str
    excerpt: str
    generated_at: datetime


class PressReviewArticleResponse(BaseModel):
    title: str
    summary: str


class PressReviewDetailResponse(BaseModel):
    id: int
    title: str
    summary: str
    prompt: str
    generated_at: datetime
    articles: list[PressReviewArticleResponse]


class DisplaySettingsResponse(BaseModel):
    press_review_list_limit: int


class DisplaySettingsUpdateRequest(BaseModel):
    press_review_list_limit: int


@app.get("/")
async def hello():
    return {"message": "👋"}


@app.post("/login", response_model=LoginResponse)
async def login(credentials: LoginRequest, session: Session = Depends(get_session)):
    user = session.exec(select(User).where(User.email == credentials.email)).first()

    if not user or not verify_password(credentials.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    token = create_access_token(subject=user.email)
    return LoginResponse(access_token=token)


def get_owned_chat(chat_id: int, current_user: User, session: Session) -> Chat:
    chat = session.get(Chat, chat_id)

    # 404 (not 403) even when the chat exists but belongs to someone else,
    # so we never reveal that another user's chat id is valid.
    if not chat or chat.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chat not found")

    return chat


def get_settings(session: Session) -> Settings:
    settings = session.get(Settings, 1)

    if not settings:
        settings = Settings(id=1)
        session.add(settings)
        session.commit()
        session.refresh(settings)

    return settings


@app.get("/settings/system-prompt", response_model=SystemPromptResponse)
async def get_system_prompt(
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    settings = get_settings(session)
    return SystemPromptResponse(system_prompt=settings.system_prompt)


@app.put("/settings/system-prompt", response_model=SystemPromptResponse)
async def update_system_prompt(
    body: SystemPromptUpdateRequest,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    settings = get_settings(session)
    settings.system_prompt = body.system_prompt
    session.add(settings)
    session.commit()
    session.refresh(settings)
    return SystemPromptResponse(system_prompt=settings.system_prompt)


def get_news_digest(session: Session) -> NewsDigest:
    digest = session.get(NewsDigest, 1)

    if not digest:
        digest = NewsDigest(id=1)
        session.add(digest)
        session.commit()
        session.refresh(digest)

    return digest


def build_system_prompt(settings: Settings, digest: NewsDigest) -> str:
    if not digest.content:
        return settings.system_prompt
    return f"{settings.system_prompt}\n\nActualites du jour :\n{digest.content}"


@app.get("/settings/news-digest", response_model=NewsDigestResponse)
async def get_news_digest_endpoint(
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    digest = get_news_digest(session)
    return NewsDigestResponse(
        synthesis_prompt=digest.synthesis_prompt,
        content=digest.content,
        updated_at=digest.updated_at,
    )


@app.put("/settings/news-digest/synthesis-prompt", response_model=NewsDigestResponse)
async def update_news_synthesis_prompt(
    body: NewsSynthesisPromptUpdateRequest,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    digest = get_news_digest(session)
    digest.synthesis_prompt = body.synthesis_prompt
    session.add(digest)
    session.commit()
    session.refresh(digest)
    return NewsDigestResponse(
        synthesis_prompt=digest.synthesis_prompt,
        content=digest.content,
        updated_at=digest.updated_at,
    )


@app.post("/settings/news-digest/refresh", response_model=NewsDigestResponse)
async def refresh_news_digest(
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    digest = get_news_digest(session)

    try:
        content = await build_news_digest(digest.synthesis_prompt)
    except NewsError:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Impossible de recuperer ou de synthetiser les actualites du jour.",
        )

    digest.content = content
    digest.updated_at = datetime.now(timezone.utc)
    session.add(digest)
    session.commit()
    session.refresh(digest)
    return NewsDigestResponse(
        synthesis_prompt=digest.synthesis_prompt,
        content=digest.content,
        updated_at=digest.updated_at,
    )


def get_owned_press_review(review_id: int, current_user: User, session: Session) -> PressReview:
    review = session.get(PressReview, review_id)

    # 404 (not 403) even when the review exists but belongs to someone else,
    # so we never reveal that another user's review id is valid.
    if not review or review.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Press review not found")

    return review


def get_display_settings(session: Session) -> DisplaySettings:
    settings = session.get(DisplaySettings, 1)

    if not settings:
        settings = DisplaySettings(id=1)
        session.add(settings)
        session.commit()
        session.refresh(settings)

    return settings


_MARKDOWN_MARKERS = re.compile(r"^[#>*\-•\s]+|\*\*", flags=re.MULTILINE)


def press_review_excerpt(summary: str, max_length: int = 220) -> str:
    """A short, markdown-stripped intro for the card preview (not the full text)."""
    plain = _MARKDOWN_MARKERS.sub("", summary).strip()
    plain = " ".join(plain.split())
    if len(plain) <= max_length:
        return plain
    return plain[:max_length].rsplit(" ", 1)[0] + "…"


@app.get("/settings/display", response_model=DisplaySettingsResponse)
async def get_display_settings_endpoint(
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    settings = get_display_settings(session)
    return DisplaySettingsResponse(press_review_list_limit=settings.press_review_list_limit)


@app.put("/settings/display", response_model=DisplaySettingsResponse)
async def update_display_settings(
    body: DisplaySettingsUpdateRequest,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    if body.press_review_list_limit < 1:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="press_review_list_limit must be at least 1",
        )

    settings = get_display_settings(session)
    settings.press_review_list_limit = body.press_review_list_limit
    session.add(settings)
    session.commit()
    session.refresh(settings)
    return DisplaySettingsResponse(press_review_list_limit=settings.press_review_list_limit)


@app.get("/press-reviews", response_model=list[PressReviewSummary])
async def list_press_reviews(
    chat_id: int | None = None,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    query = select(PressReview).where(PressReview.user_id == current_user.id)

    if chat_id is not None:
        # Scoped to one discussion: show every revue generated in it, not
        # capped by the global "recent reviews" display limit.
        query = query.where(PressReview.chat_id == chat_id)
    else:
        limit = get_display_settings(session).press_review_list_limit
        query = query.limit(limit)

    reviews = session.exec(query.order_by(PressReview.generated_at.desc())).all()
    return [
        PressReviewSummary(
            id=review.id,
            title=review.title,
            excerpt=press_review_excerpt(review.summary),
            generated_at=review.generated_at,
        )
        for review in reviews
    ]


def get_press_review_articles(review_id: int, session: Session) -> list[PressReviewArticleResponse]:
    articles = session.exec(
        select(PressReviewArticle).where(PressReviewArticle.press_review_id == review_id)
    ).all()
    return [
        PressReviewArticleResponse(title=article.title, summary=article.summary)
        for article in articles
    ]


@app.get("/press-reviews/{review_id}", response_model=PressReviewDetailResponse)
async def get_press_review(
    review_id: int,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    review = get_owned_press_review(review_id, current_user, session)
    return PressReviewDetailResponse(
        id=review.id,
        title=review.title,
        summary=review.summary,
        prompt=review.prompt,
        generated_at=review.generated_at,
        articles=get_press_review_articles(review.id, session),
    )


@app.post("/press-reviews", response_model=PressReviewDetailResponse)
async def generate_press_review(
    body: PressReviewRequest,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    theme = body.theme.strip()
    if not theme:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Theme required")

    # The revue is synthesized directly from this discussion's own history.
    chat = get_owned_chat(body.chat_id, current_user, session)

    try:
        output = await generate_press_review_from_chat(chat.messages, theme)
    except LLMError:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Impossible de generer la revue de presse pour ce theme.",
        )

    review = PressReview(
        user_id=current_user.id,
        chat_id=chat.id,
        title=output.title,
        summary=output.summary,
        prompt=f"{PRESS_REVIEW_AGENT_SYSTEM_PROMPT}\n\nSujet demande : {theme}",
        generated_at=datetime.now(timezone.utc),
    )
    session.add(review)
    session.commit()
    session.refresh(review)

    for article in output.articles:
        session.add(
            PressReviewArticle(
                press_review_id=review.id,
                title=article.title,
                summary=article.summary,
            )
        )
    session.commit()

    return PressReviewDetailResponse(
        id=review.id,
        title=review.title,
        summary=review.summary,
        prompt=review.prompt,
        generated_at=review.generated_at,
        articles=get_press_review_articles(review.id, session),
    )


@app.get("/chats", response_model=list[ChatSummary])
async def list_chats(
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    chats = session.exec(
        select(Chat).where(Chat.user_id == current_user.id).order_by(Chat.created_at.desc())
    ).all()
    return [
        ChatSummary(
            id=chat.id,
            created_at=chat.created_at,
            last_message=chat.messages[-1]["content"] if chat.messages else None,
        )
        for chat in chats
    ]


@app.post("/chats", response_model=ChatCreateResponse)
async def create_chat(
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    # Captured once here (base prompt + that day's digest) and reused for
    # every message in this chat, so the discussion stays consistent even if
    # the global system prompt or digest changes later.
    system_prompt = build_system_prompt(get_settings(session), get_news_digest(session))
    chat = Chat(user_id=current_user.id, messages=[], system_prompt=system_prompt)
    session.add(chat)
    session.commit()
    session.refresh(chat)
    return ChatCreateResponse(id=chat.id)


@app.get("/chats/{chat_id}", response_model=ChatDetailResponse)
async def get_chat(
    chat_id: int,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    chat = get_owned_chat(chat_id, current_user, session)
    return ChatDetailResponse(id=chat.id, messages=chat.messages)


@app.post("/chats/{chat_id}/messages", response_model=MessageResponse)
async def post_message(
    chat_id: int,
    body: MessageRequest,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    chat = get_owned_chat(chat_id, current_user, session)
    history = [*chat.messages, {"role": "user", "content": body.content}]
    # Reuse the prompt captured when this chat was created rather than
    # recomputing it, so an ongoing discussion doesn't shift prompt mid-way
    # if the global settings or the news digest change later. Older chats
    # created before this field existed get it backfilled here.
    if not chat.system_prompt:
        chat.system_prompt = build_system_prompt(get_settings(session), get_news_digest(session))
    system_prompt = chat.system_prompt

    try:
        reply = await generate_reply(history, system_prompt, tools=[search_news_tool])
    except LLMError:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="L'assistant est momentanément indisponible, veuillez réessayer.",
        )

    chat.messages = [*history, {"role": "assistant", "content": reply}]
    session.add(chat)
    session.commit()

    return MessageResponse(role="assistant", content=reply)


if __name__ == "__main__":
    init_db()

    uvicorn.run(
        app,
        host="0.0.0.0",
        port=int(os.getenv("PORT", 8000)),
    )
