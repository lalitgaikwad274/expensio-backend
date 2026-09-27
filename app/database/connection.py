import os

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise ValueError("DATABASE_URL is not configured")


engine = create_engine(
    DATABASE_URL,
    echo=True,
)


SessionLocal = sessionmaker(
    bind=engine,
    autocommit=False,
    autoflush=False,
)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()

    try:
        yield db
    finally:
        db.close()


def create_tables():
    import app.models  # noqa: F401
    Base.metadata.create_all(bind=engine)

    try:
        from app.models import Category, User, BankAccount
        with SessionLocal() as db:
            if db.query(Category).count() == 0:
                categories = [
                    Category(id=1, name="Food & Dining"),
                    Category(id=2, name="Transport"),
                    Category(id=3, name="Shopping"),
                    Category(id=4, name="Bills & Utilities"),
                    Category(id=5, name="Entertainment"),
                    Category(id=6, name="Health"),
                    Category(id=7, name="General"),
                ]
                db.add_all(categories)
                db.commit()

            if db.query(BankAccount).count() == 0:
                user = db.query(User).first()
                if not user:
                    user = User(
                        firebase_uid="default_user",
                        name="Default User",
                        email="user@expensio.app",
                        password_hash="",
                    )
                    db.add(user)
                    db.commit()
                    db.refresh(user)

                bank_account = BankAccount(
                    id=1,
                    user_id=user.id,
                    bank_name="Primary Bank",
                    account_name="Main Account",
                    account_type="savings",
                    current_balance=0.00,
                )
                db.add(bank_account)
                db.commit()
    except Exception as e:
        print(f"Initial seed notice: {e}")