from datetime import datetime
from decimal import Decimal
from typing import Optional
from pydantic import BaseModel, Field


class BankAccountCreate(BaseModel):
    bank_name: str = Field(..., max_length=100, example="Chase")
    account_name: str = Field(..., max_length=100, example="Primary Checking")
    account_type: str = Field(default="savings", description="savings, checking, or credit_card", example="savings")
    current_balance: Decimal = Field(default=Decimal("0.00"), example=1000.00)


class BankAccountResponse(BaseModel):
    id: int
    user_id: int
    bank_name: str
    account_name: str
    account_type: str
    current_balance: Decimal
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
