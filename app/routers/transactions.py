from app.auth.dependencies import get_current_user
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import BankAccount, Category, Transaction, User
from app.schemas.transaction import (
    TransactionCreate,
    TransactionUpdate,
    TransactionResponse,
)

router = APIRouter(
    prefix="/api/transactions",
    tags=["Transactions"]
)


@router.post("/", response_model=TransactionResponse, status_code=201)
def create_transaction(
    transaction: TransactionCreate,
    firebase_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    bank_account = db.query(BankAccount).filter(BankAccount.id == transaction.bank_account_id).first()
    if not bank_account:
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

        bank_account = BankAccount(
            id=transaction.bank_account_id,
            user_id=user.id,
            bank_name="Primary Bank",
            account_name="Main Account",
            account_type="savings",
            current_balance=0.00,
        )
        db.add(bank_account)
        try:
            db.commit()
            db.refresh(bank_account)
        except Exception:
            db.rollback()
            bank_account = db.query(BankAccount).filter(BankAccount.id == transaction.bank_account_id).first()

    if transaction.category_id is not None:
        category = db.query(Category).filter(Category.id == transaction.category_id).first()
        if not category:
            category = Category(
                id=transaction.category_id,
                name=f"Category {transaction.category_id}"
            )
            db.add(category)
            try:
                db.commit()
                db.refresh(category)
            except Exception:
                db.rollback()

    new_transaction = Transaction(
        bank_account_id=transaction.bank_account_id,
        category_id=transaction.category_id,
        amount=transaction.amount,
        transaction_type=transaction.transaction_type,
        description=transaction.description,
        transaction_date=transaction.transaction_date,
    )

    db.add(new_transaction)
    db.commit()
    db.refresh(new_transaction)

    return new_transaction

# get all transactions api
@router.get("/", response_model=list[TransactionResponse])
def get_all_transactions(
    firebase_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    transactions = db.query(Transaction).all()
    return transactions 


#get transaction by id
@router.get("/{transaction_id}", response_model=TransactionResponse)
def get_transaction(
    transaction_id: int,
    firebase_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    transaction = db.query(Transaction).filter(Transaction.id == transaction_id).first()
    if not transaction:
        raise HTTPException(status_code=404, detail="Transaction not found")
    return transaction


# update api
@router.put("/{transaction_id}", response_model=TransactionResponse)
def update_transaction(
    transaction_id: int,
    transaction: TransactionUpdate,
    firebase_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    transaction = db.query(Transaction).filter(Transaction.id == transaction_id).first()
    if not transaction:
        raise HTTPException(status_code=404, detail="Transaction not found")
    
    transaction.bank_account_id = transaction.bank_account_id
    transaction.category_id = transaction.category_id
    transaction.amount = transaction.amount
    transaction.transaction_type = transaction.transaction_type
    transaction.description = transaction.description
    transaction.transaction_date = transaction.transaction_date
    
    db.commit()
    db.refresh(transaction)
    
    return transaction



#delete transaction api
@router.delete("/{transaction_id}")
def delete_transaction(
    transaction_id: int,
    firebase_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    transaction = db.query(Transaction).filter(Transaction.id == transaction_id).first()
    if not transaction:
        raise HTTPException(status_code=404, detail="Transaction not found")
    db.delete(transaction)
    db.commit()
    return {"message": "Transaction deleted successfully"}



#filter transaction by date api