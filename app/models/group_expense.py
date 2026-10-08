from sqlalchemy import Integer
from sqlalchemy import BigInteger
from app.database import Base
from sqlalchemy import (
    Column,
    String,
    Numeric,
    DateTime,
    ForeignKey,
    Text,
)
from sqlalchemy.orm import relationship
from datetime import datetime
from typing import Optional


class GroupExpense(Base):
    __tablename__ = "group_expenses"

    id = Column(
        BigInteger,
        primary_key=True,
    )

    group_id = Column(
        BigInteger,
        ForeignKey("groups.id", ondelete="CASCADE"),
        nullable=False
    )

    description = Column(
        String(255),
        nullable=False
    )

    amount = Column(
        Numeric(12, 2),
        nullable=False
    )

    category_id = Column(
        Integer,
        ForeignKey("categories.id"),
        nullable=True
    )

    paid_by = Column(
        BigInteger,
        ForeignKey("group_members.id"),
        nullable=False
    )

    paid_by_firebase_uid = Column(
        String(255),
        nullable=True
    )

    split_type = Column(
        String(20),
        nullable=False,
        default="equal"
    )

    expense_date = Column(
        DateTime,
        default=datetime.utcnow,
        nullable=False
    )

    notes = Column(
        Text,
        nullable=True
    )

    created_at = Column(
        DateTime,
        default=datetime.utcnow
    )

    updated_at = Column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow
    )

    group = relationship(
        "Group",
        back_populates="expenses"
    )

    splits = relationship(
        "ExpenseSplit",
        back_populates="expense",
        cascade="all, delete-orphan"
    )

    payer = relationship(
        "GroupMember",
        foreign_keys=[paid_by]
    )

    category = relationship(
        "Category"
    )

    @property
    def payer_name(self) -> Optional[str]:
        if self.payer:
            return self.payer.name
        return None

    @property
    def category_name(self) -> Optional[str]:
        if self.category:
            return self.category.name
        return None