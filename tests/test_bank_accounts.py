import pytest
from decimal import Decimal
from pydantic import ValidationError
from app.schemas.bank_account import (
    BankAccountCreate,
    BankAccountUpdate,
    BankAccountResponse,
    normalize_account_type,
)


def test_normalize_account_type():
    assert normalize_account_type("Savings") == "savings"
    assert normalize_account_type("SAVINGS") == "savings"
    assert normalize_account_type("saving") == "savings"
    assert normalize_account_type("savings_account") == "savings"

    assert normalize_account_type("Checking") == "checking"
    assert normalize_account_type("current") == "checking"
    assert normalize_account_type("checking_account") == "checking"

    assert normalize_account_type("Credit Card") == "credit_card"
    assert normalize_account_type("creditcard") == "credit_card"
    assert normalize_account_type("credit_card") == "credit_card"


def test_bank_account_create_valid():
    data = {
        "bank_name": "Chase Bank",
        "account_name": "Main Checking",
        "account_type": "checking",
        "current_balance": "5000.50",
    }
    schema = BankAccountCreate(**data)
    assert schema.bank_name == "Chase Bank"
    assert schema.account_name == "Main Checking"
    assert schema.account_type == "checking"
    assert schema.current_balance == Decimal("5000.50")


def test_bank_account_create_flexible_aliases():
    data = {
        "bankName": "Bank of America",
        "accountName": "My Savings",
        "accountType": "Savings",
        "balance": 1500.00,
    }
    schema = BankAccountCreate(**data)
    assert schema.bank_name == "Bank of America"
    assert schema.account_name == "My Savings"
    assert schema.account_type == "savings"
    assert schema.current_balance == Decimal("1500.00")


def test_bank_account_create_auto_account_name():
    data = {
        "bank_name": "Wells Fargo",
        "initialBalance": 200,
    }
    schema = BankAccountCreate(**data)
    assert schema.bank_name == "Wells Fargo"
    assert schema.account_name == "Wells Fargo Account"
    assert schema.account_type == "savings"
    assert schema.current_balance == Decimal("200")


def test_bank_account_create_invalid_account_type():
    with pytest.raises(ValidationError):
        BankAccountCreate(
            bank_name="Test Bank",
            account_type="crypto_wallet"
        )


def test_bank_account_update_flexible():
    data = {
        "accountName": "Updated Checking",
        "currentBalance": 3500.25,
        "accountType": "Checking",
    }
    schema = BankAccountUpdate(**data)
    assert schema.account_name == "Updated Checking"
    assert schema.current_balance == Decimal("3500.25")
    assert schema.account_type == "checking"
