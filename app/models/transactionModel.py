from app.database import Base
from sqlalchemy import (
    Column,
    Integer,
    Numeric,
    String,
    DateTime,
    ForeignKey,
)
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship



class Transaction(Base):
    __tablename__ = "transactions"

    id = Column(Integer, primary_key=True, index=True)

    bank_account_id = Column(
        Integer,
        ForeignKey("bank_accounts.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    category_id = Column(
        Integer,
        ForeignKey("categories.id"),
        nullable=True
    )

    amount = Column(
        Numeric(12, 2),
        nullable=False
    )

    transaction_type = Column(
        String(20),
        nullable=False,
        default="expense"
    )

    description = Column(
        String(255),
        nullable=True
    )

    transaction_date = Column(
        DateTime,
        nullable=False
    )

    created_at = Column(
        DateTime,
        server_default=func.now()
    )

    updated_at = Column(
        DateTime,
        server_default=func.now(),
        onupdate=func.now()
    )

    bank_account = relationship(
        "BankAccount",
        back_populates="transactions"
    )

    category = relationship(
        "Category"
    )