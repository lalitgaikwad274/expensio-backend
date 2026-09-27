from sqlalchemy import Column, BigInteger, String, DateTime
from sqlalchemy.sql import func

from app.database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(BigInteger, primary_key=True, index=True)

    firebase_uid = Column(
        String(128),
        unique=True,
        nullable=False,
        index=True
    )

    name = Column(String(100), nullable=True)

    email = Column(
        String(255),
        unique=True,
        nullable=False
    )

    password_hash = Column(String, nullable=True)
    
    created_at = Column(
        DateTime,
        server_default=func.now()
    )

    updated_at = Column(
        DateTime,
        server_default=func.now(),
        onupdate=func.now()
    )

