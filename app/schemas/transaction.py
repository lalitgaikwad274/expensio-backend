from datetime import datetime
from decimal import Decimal
from typing import Optional, Any

from pydantic import BaseModel, Field, model_validator


class TransactionCreate(BaseModel):
    bank_account_id: Optional[int] = None
    category_id: Optional[int] = None
    category_name: Optional[str] = None
    bank_name: Optional[str] = None

    amount: Decimal = Field(
        gt=0
    )

    transaction_type: str = Field(
        default="expense"
    )

    description: Optional[str] = None

    transaction_date: datetime = Field(
        default_factory=datetime.utcnow
    )

    @model_validator(mode="before")
    @classmethod
    def map_flexible_fields(cls, data: Any) -> Any:
        if isinstance(data, dict):
            # Map bank_account_id / bank_id / bankId
            if "bank_account_id" not in data or data.get("bank_account_id") is None:
                bank_id = data.get("bank_id") or data.get("bankId")
                if isinstance(bank_id, int):
                    data["bank_account_id"] = bank_id
                elif isinstance(bank_id, str) and bank_id.isdigit():
                    data["bank_account_id"] = int(bank_id)

            # Map bank_name / bankName
            if "bank_name" not in data and "bankName" in data:
                data["bank_name"] = data.get("bankName")

            # Map type -> transaction_type
            if ("transaction_type" not in data or not data.get("transaction_type")) and "type" in data:
                t = str(data.get("type", "")).lower()
                data["transaction_type"] = "income" if t in ["income", "credit"] else "expense"

            # Map title / notes -> description
            if "description" not in data or not data.get("description"):
                title = data.get("title")
                notes = data.get("notes")
                if title and notes:
                    data["description"] = f"{title} - {notes}"
                elif title:
                    data["description"] = title
                elif notes:
                    data["description"] = notes

            # Map category / categoryId
            if "category_id" not in data and "categoryId" in data:
                cat_id = data.get("categoryId")
                if isinstance(cat_id, int):
                    data["category_id"] = cat_id
                elif isinstance(cat_id, str) and cat_id.isdigit():
                    data["category_id"] = int(cat_id)
            if "category" in data and isinstance(data.get("category"), str):
                data["category_name"] = data["category"]

            # Map date -> transaction_date
            if "transaction_date" not in data or data.get("transaction_date") is None:
                date_val = data.get("date")
                if isinstance(date_val, datetime):
                    data["transaction_date"] = date_val
                elif isinstance(date_val, str):
                    try:
                        data["transaction_date"] = datetime.fromisoformat(date_val.replace("Z", "+00:00"))
                    except Exception:
                        data["transaction_date"] = datetime.utcnow()
                else:
                    data["transaction_date"] = datetime.utcnow()

        return data


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