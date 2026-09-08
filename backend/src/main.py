import os

import uvicorn
from auth import create_access_token, verify_password
from database import get_session, init_db
from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from models import User
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


if __name__ == "__main__":
    init_db()

    uvicorn.run(
        app,
        host="0.0.0.0",
        port=int(os.getenv("PORT", 8000)),
    )
