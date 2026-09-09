import os
from datetime import datetime

import uvicorn
from auth import create_access_token, get_current_user, verify_password
from database import get_session, init_db
from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from llm import LLMError, generate_reply
from models import Chat, Settings, User
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


@app.get("/chats", response_model=list[ChatSummary])
async def list_chats(
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    chats = session.exec(
        select(Chat).where(Chat.user_id == current_user.id).order_by(Chat.created_at.desc())
    ).all()
    return [ChatSummary(id=chat.id, created_at=chat.created_at) for chat in chats]


@app.post("/chats", response_model=ChatCreateResponse)
async def create_chat(
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    chat = Chat(user_id=current_user.id, messages=[])
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
    system_prompt = get_settings(session).system_prompt

    try:
        reply = await generate_reply(history, system_prompt)
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
