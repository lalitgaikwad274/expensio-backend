from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.database import get_db
from app.models import BankAccount, User
from app.schemas.bank_account import (
    BankAccountCreate,
    BankAccountUpdate,
    BankAccountResponse,
)

router = APIRouter(
    prefix="/api/bank-accounts",
    tags=["Bank Accounts"]
)


def get_or_create_user(db: Session, firebase_user: dict) -> User:
    """
    Retrieve existing user by Firebase UID, or create a new user record.
    """
    firebase_uid = firebase_user.get("uid", "default_user")
    user = db.query(User).filter(User.firebase_uid == firebase_uid).first()
    if not user:
        email = firebase_user.get("email") or f"{firebase_uid}@expensio.app"
        user = User(
            firebase_uid=firebase_uid,
            email=email,
            name=firebase_user.get("name") or firebase_user.get("display_name") or "User",
            password_hash="",
        )
        db.add(user)
        db.commit()
        db.refresh(user)
    return user


@router.post("/", response_model=BankAccountResponse, status_code=status.HTTP_201_CREATED)
@router.post("/add", response_model=BankAccountResponse, status_code=status.HTTP_201_CREATED, include_in_schema=False)
def add_bank_account(
    account: BankAccountCreate,
    firebase_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Add a new bank account for the authenticated user.
    """
    user = get_or_create_user(db, firebase_user)

    account_name = account.account_name or f"{account.bank_name} Account"

    existing = db.query(BankAccount).filter(
        BankAccount.user_id == user.id,
        BankAccount.account_name == account_name
    ).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Bank account with account name '{account_name}' already exists."
        )

    new_account = BankAccount(
        user_id=user.id,
        bank_name=account.bank_name,
        account_name=account_name,
        account_type=account.account_type,
        current_balance=account.current_balance,
    )
    db.add(new_account)
    db.commit()
    db.refresh(new_account)
    return new_account


@router.get("", response_model=list[BankAccountResponse])
@router.get("/", response_model=list[BankAccountResponse], include_in_schema=False)
def get_bank_accounts(
    firebase_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    List all bank accounts belonging to the authenticated user.
    """
    user = get_or_create_user(db, firebase_user)
    return db.query(BankAccount).filter(BankAccount.user_id == user.id).order_by(BankAccount.id.asc()).all()


@router.get("/{account_id}", response_model=BankAccountResponse)
def get_bank_account(
    account_id: int,
    firebase_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get details of a specific bank account by ID.
    """
    user = get_or_create_user(db, firebase_user)
    account = (
        db.query(BankAccount)
        .filter(BankAccount.id == account_id, BankAccount.user_id == user.id)
        .first()
    )
    if not account:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Bank account with id {account_id} not found"
        )
    return account


@router.put("/{account_id}", response_model=BankAccountResponse)
@router.patch("/{account_id}", response_model=BankAccountResponse, include_in_schema=False)
def update_bank_account(
    account_id: int,
    account_data: BankAccountUpdate,
    firebase_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Update details of an existing bank account.
    """
    user = get_or_create_user(db, firebase_user)
    account = (
        db.query(BankAccount)
        .filter(BankAccount.id == account_id, BankAccount.user_id == user.id)
        .first()
    )
    if not account:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Bank account with id {account_id} not found"
        )

    if account_data.bank_name is not None:
        account.bank_name = account_data.bank_name
    if account_data.account_name is not None:
        account.account_name = account_data.account_name
    if account_data.account_type is not None:
        account.account_type = account_data.account_type
    if account_data.current_balance is not None:
        account.current_balance = account_data.current_balance

    db.commit()
    db.refresh(account)
    return account


@router.delete("/{account_id}", status_code=status.HTTP_200_OK)
def delete_bank_account(
    account_id: int,
    firebase_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Delete a bank account by ID.
    """
    user = get_or_create_user(db, firebase_user)
    account = (
        db.query(BankAccount)
        .filter(BankAccount.id == account_id, BankAccount.user_id == user.id)
        .first()
    )
    if not account:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Bank account with id {account_id} not found"
        )

    db.delete(account)
    db.commit()
    return {
        "status": "success",
        "message": f"Bank account {account_id} deleted successfully"
    }
