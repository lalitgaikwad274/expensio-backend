from datetime import datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, Field


class TransactionCreate(BaseModel):
    bank_account_id: int
    category_id: Optional[int] = None

    amount: Decimal = Field(
        gt=0
    )

    transaction_type: str = Field(
        default="expense"
    )

    description: Optional[str] = None

    transaction_date: datetime


class TransactionUpdate(BaseModel):
    category_id: Optional[int] = None
    amount: Optional[Decimal] = Field(
        default=None,
        gt=0
    )
    transaction_type: Optional[str] = None
    description: Optional[str] = None
    transaction_date: Optional[datetime] = None


class TransactionResponse(BaseModel):
    id: int
    bank_account_id: int
    category_id: Optional[int]

    amount: Decimal
    transaction_type: str
    description: Optional[str]

    transaction_date: datetime
    created_at: datetime

    class Config:
        from_attributes = True