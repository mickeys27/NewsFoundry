import os
from models import Chat, PressReview, PressReviewArticle, User
from sqlmodel import SQLModel, Session, create_engine, delete, select
import bcrypt

DATABASE_URL = os.getenv("DATABASE_URL")
engine = create_engine(DATABASE_URL, echo=True)


def get_session():
    with Session(engine) as session:
        yield session


def init_db():
    SQLModel.metadata.create_all(engine)
    print("Database initialized successfully")

    with Session(engine) as session:
        # Reset conversation data on every startup so discussions always
        # start from zero; config/settings and users are left untouched.
        session.exec(delete(PressReviewArticle))
        session.exec(delete(PressReview))
        session.exec(delete(Chat))
        session.commit()

    # Creating a default user
    default_email = "test@test.com"
    default_password = "test"

    with Session(engine) as session:
        statement = select(User).where(User.email == default_email)
        user = session.exec(statement).first()

        if not user:
            session.add(
                User(
                    email=default_email,
                    hashed_password=bcrypt.hashpw(
                        default_password.encode("utf-8"), bcrypt.gensalt()
                    ).decode("utf-8"),
                )
            )
            session.commit()
