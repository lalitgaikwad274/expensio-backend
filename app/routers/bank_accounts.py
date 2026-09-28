from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.database import get_db
from app.models import BankAccount, User
from app.schemas.bank_account import BankAccountCreate, BankAccountResponse

router = APIRouter(
    prefix="/api/bank-accounts",
    tags=["Bank Accounts"]
)


def get_or_create_user(db: Session, firebase_user: dict) -> User:
    firebase_uid = firebase_user.get("uid", "default_user")
    user = db.query(User).filter(User.firebase_uid == firebase_uid).first()
    if not user:
        user = User(
            firebase_uid=firebase_uid,
            email=firebase_user.get("email", "user@expensio.app"),
            name=firebase_user.get("name") or firebase_user.get("display_name") or "User",
            password_hash="",
        )
        db.add(user)
        db.commit()
        db.refresh(user)
    return user


@router.post("", response_model=BankAccountResponse, status_code=status.HTTP_201_CREATED)
@router.post("/", response_model=BankAccountResponse, status_code=status.HTTP_201_CREATED, include_in_schema=False)
def create_bank_account(
    account: BankAccountCreate,
    firebase_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    user = get_or_create_user(db, firebase_user)

    new_account = BankAccount(
        user_id=user.id,
        bank_name=account.bank_name,
        account_name=account.account_name,
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
    user = get_or_create_user(db, firebase_user)
    return db.query(BankAccount).filter(BankAccount.user_id == user.id).all()


@router.get("/{account_id}", response_model=BankAccountResponse)
def get_bank_account(
    account_id: int,
    firebase_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    user = get_or_create_user(db, firebase_user)
    account = (
        db.query(BankAccount)
        .filter(BankAccount.id == account_id, BankAccount.user_id == user.id)
        .first()
    )
    if not account:
        raise HTTPException(status_code=404, detail=f"Bank account with id {account_id} not found")
    return account
