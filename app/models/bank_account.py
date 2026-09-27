from app.database import Base
from sqlalchemy import (
    Column,
    Integer,
    BigInteger,
    String,
    Numeric,
    DateTime,
    ForeignKey,
    Enum as SQLEnum
)
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship


class BankAccount(Base):
    __tablename__ = "bank_accounts"

    id = Column(Integer, primary_key=True, index=True)

    user_id = Column(
        BigInteger,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    bank_name = Column(String(100), nullable=False)

    account_name = Column(String(100), nullable=False)

    account_type = Column(
        SQLEnum("savings", "checking", "credit_card", name="account_type_enum"),
        nullable=False
    )

    current_balance = Column(
        Numeric(12, 2),
        nullable=False,
        default=0.00
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

    transactions = relationship(
        "Transaction",
        back_populates="bank_account",
        cascade="all, delete-orphan"
    )