import os

# Must be set before importing any app module: auth.py and database.py
# read these at import time.
os.environ.setdefault("DATABASE_URL", "sqlite://")
os.environ.setdefault("JWT_SECRET", "test-secret-key-only-used-in-the-test-suite")

import bcrypt
import pytest
from database import get_session
from fastapi.testclient import TestClient
from main import app
from models import User
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine


@pytest.fixture(name="session")
def session_fixture():
    # Fresh in-memory SQLite database per test, isolated from the real app engine.
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)

    with Session(engine) as session:
        yield session


@pytest.fixture(name="client")
def client_fixture(session):
    def override_get_session():
        yield session

    app.dependency_overrides[get_session] = override_get_session
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.fixture
def create_user(session):
    def _create_user(email: str = "alice@test.com", password: str = "secret") -> User:
        user = User(
            email=email,
            hashed_password=bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode(
                "utf-8"
            ),
        )
        session.add(user)
        session.commit()
        session.refresh(user)
        return user

    return _create_user


@pytest.fixture
def auth_headers(client, create_user):
    def _auth_headers(email: str = "alice@test.com", password: str = "secret") -> dict:
        create_user(email, password)
        response = client.post("/login", json={"email": email, "password": password})
        token = response.json()["access_token"]
        return {"Authorization": f"Bearer {token}"}

    return _auth_headers
