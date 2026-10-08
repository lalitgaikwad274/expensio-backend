from sqlalchemy.orm import relationship
from sqlalchemy import (
    Column,
    Numeric,
    ForeignKey,
    BigInteger
)
from app.database import Base

class ExpenseSplit(Base):
    __tablename__ = "expense_splits"

    id = Column(
        BigInteger,
        primary_key=True,
    )

    expense_id = Column(
        BigInteger,
        ForeignKey(
            "group_expenses.id",
            ondelete="CASCADE"
        ),
        nullable=False
    )

    member_id = Column(
        BigInteger,
        ForeignKey(
            "group_members.id",
            ondelete="CASCADE"
        ),
        nullable=False
    )

    amount = Column(
        Numeric(12, 2),
        nullable=False
    )

    percentage = Column(
        Numeric(5, 2),
        nullable=True
    )

    shares = Column(
        Numeric(10, 2),
        nullable=True
    )

    expense = relationship(
        "GroupExpense",
        back_populates="splits"
    )

    member = relationship(
        "GroupMember"
    )