from datetime import datetime
from decimal import Decimal
from typing import Optional, Any
from pydantic import BaseModel, Field, ConfigDict, model_validator, field_validator


ALLOWED_ACCOUNT_TYPES = {"savings", "checking", "credit_card"}


def normalize_account_type(val: Any) -> str:
    if not val:
        return "savings"
    val_str = str(val).strip().lower().replace("-", "_").replace(" ", "_")
    if val_str in ["savings", "saving", "savings_account"]:
        return "savings"
    if val_str in ["checking", "checkings", "current", "checking_account", "current_account"]:
        return "checking"
    if val_str in ["credit_card", "creditcard", "credit"]:
        return "credit_card"
    return val_str


class BankAccountCreate(BaseModel):
    bank_name: str = Field(..., max_length=100, description="Bank name, e.g. Chase, HDFC, SBI", example="Chase")
    account_name: Optional[str] = Field(None, max_length=100, description="Display/nickname for account", example="Primary Checking")
    account_type: str = Field(default="savings", description="Account type: savings, checking, or credit_card", example="savings")
    current_balance: Decimal = Field(default=Decimal("0.00"), description="Starting balance", example=1000.00)

    @model_validator(mode="before")
    @classmethod
    def map_flexible_fields(cls, data: Any) -> Any:
        if isinstance(data, dict):
            # Bank name: bank_name, bankName, bank
            if not data.get("bank_name"):
                data["bank_name"] = data.get("bankName") or data.get("bank")

            # Account name: account_name, accountName, name
            if not data.get("account_name"):
                data["account_name"] = data.get("accountName") or data.get("name")
            if not data.get("account_name") and data.get("bank_name"):
                data["account_name"] = f"{data.get('bank_name')} Account"


            # Current balance: current_balance, currentBalance, balance, initial_balance, initialBalance
            if data.get("current_balance") is None:
                for key in ["currentBalance", "balance", "initial_balance", "initialBalance", "opening_balance"]:
                    if key in data and data.get(key) is not None:
                        data["current_balance"] = data.get(key)
                        break

            # Account type normalization
            raw_type = data.get("account_type") or data.get("accountType") or data.get("type") or "savings"
            data["account_type"] = normalize_account_type(raw_type)

        return data

    @field_validator("account_type")
    @classmethod
    def validate_account_type(cls, v: str) -> str:
        normalized = normalize_account_type(v)
        if normalized not in ALLOWED_ACCOUNT_TYPES:
            raise ValueError(f"account_type must be one of {sorted(list(ALLOWED_ACCOUNT_TYPES))}, got '{v}'")
        return normalized


class BankAccountUpdate(BaseModel):
    bank_name: Optional[str] = Field(None, max_length=100, example="Chase")
    account_name: Optional[str] = Field(None, max_length=100, example="Salary Account")
    account_type: Optional[str] = Field(None, description="savings, checking, or credit_card", example="checking")
    current_balance: Optional[Decimal] = Field(None, example=2500.00)

    @model_validator(mode="before")
    @classmethod
    def map_flexible_fields(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if "bank_name" not in data and "bankName" in data:
                data["bank_name"] = data.get("bankName")
            if "account_name" not in data and "accountName" in data:
                data["account_name"] = data.get("accountName")
            if "current_balance" not in data:
                for key in ["currentBalance", "balance"]:
                    if key in data and data.get(key) is not None:
                        data["current_balance"] = data.get(key)
                        break
            if "account_type" in data or "accountType" in data or "type" in data:
                raw_type = data.get("account_type") or data.get("accountType") or data.get("type")
                if raw_type:
                    data["account_type"] = normalize_account_type(raw_type)

        return data

    @field_validator("account_type")
    @classmethod
    def validate_account_type(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            normalized = normalize_account_type(v)
            if normalized not in ALLOWED_ACCOUNT_TYPES:
                raise ValueError(f"account_type must be one of {sorted(list(ALLOWED_ACCOUNT_TYPES))}, got '{v}'")
            return normalized
        return v


class BankAccountResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    bank_name: str
    account_name: str
    account_type: str
    current_balance: Decimal
    created_at: datetime
    updated_at: datetime
