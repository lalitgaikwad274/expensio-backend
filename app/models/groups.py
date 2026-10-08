from datetime import datetime
from typing import Optional
from sqlalchemy import Column, BigInteger, String, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base


class Group(Base):
    __tablename__ = "groups"

    id = Column(BigInteger, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    icon = Column(String(50), nullable=True, default="🌴")
    description = Column(Text, nullable=True)
    created_by = Column(BigInteger, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    created_at = Column(
        DateTime,
        default=datetime.utcnow,
        server_default=func.now()
    )
    updated_at = Column(
        DateTime,
        default=datetime.utcnow,
        server_default=func.now(),
        onupdate=func.now()
    )

    members = relationship(
        "GroupMember",
        back_populates="group",
        cascade="all, delete-orphan"
    )

    expenses = relationship(
        "GroupExpense",
        back_populates="group",
        cascade="all, delete-orphan"
    )

    creator = relationship(
        "User",
        foreign_keys=[created_by]
    )

    @property
    def avatarIcon(self) -> str:
        return self.icon or "🌴"

    @property
    def currency(self) -> str:
        return "INR"

    @property
    def simplifyDebts(self) -> bool:
        return True

    @property
    def defaultSplit(self) -> str:
        return "equal"

    @property
    def createdBy(self) -> Optional[str]:
        if self.creator and self.creator.name:
            return self.creator.name
        return str(self.created_by) if self.created_by else None

    @property
    def createdAt(self) -> datetime:
        return self.created_at
