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


@router.post("/", response_model=TransactionResponse, status_code=201, include_in_schema=False)
def create_transaction(
    transaction: TransactionCreate,
    firebase_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
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

    # Resolve bank account
    bank_account = None
    if transaction.bank_account_id:
        bank_account = db.query(BankAccount).filter(
            BankAccount.id == transaction.bank_account_id,
            BankAccount.user_id == user.id
        ).first()

    if not bank_account:
        bank_name = transaction.bank_name or "Primary Bank"
        # Try finding existing bank account by bank name for this user
        bank_account = db.query(BankAccount).filter(
            BankAccount.user_id == user.id,
            BankAccount.bank_name == bank_name
        ).first()

        # Or fallback to any bank account of this user
        if not bank_account:
            bank_account = db.query(BankAccount).filter(BankAccount.user_id == user.id).first()

        # If still no bank account, create one for this user
        if not bank_account:
            bank_account = BankAccount(
                user_id=user.id,
                bank_name=bank_name,
                account_name=f"{bank_name} Account",
                account_type="savings",
                current_balance=0.00,
            )
            db.add(bank_account)
            db.commit()
            db.refresh(bank_account)

    # Resolve category
    category_id = transaction.category_id
    if transaction.category_name:
        category = db.query(Category).filter(Category.name.ilike(transaction.category_name)).first()
        if not category:
            category = Category(name=transaction.category_name)
            db.add(category)
            try:
                db.commit()
                db.refresh(category)
            except Exception:
                db.rollback()
                category = db.query(Category).filter(Category.name.ilike(transaction.category_name)).first()
        if category:
            category_id = category.id
    elif category_id is not None:
        category = db.query(Category).filter(Category.id == category_id).first()
        if not category:
            category = Category(
                id=category_id,
                name=f"Category {category_id}"
            )
            db.add(category)
            try:
                db.commit()
                db.refresh(category)
            except Exception:
                db.rollback()
                category = db.query(Category).filter(Category.id == category_id).first()
            if category:
                category_id = category.id

    new_transaction = Transaction(
        bank_account_id=bank_account.id,
        category_id=category_id,
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
@router.get("/", response_model=list[TransactionResponse], include_in_schema=False)
def get_all_transactions(
    firebase_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    firebase_uid = firebase_user.get("uid", "default_user")
    user = db.query(User).filter(User.firebase_uid == firebase_uid).first()
    if not user:
        return []

    user_account_ids = [acc.id for acc in db.query(BankAccount.id).filter(BankAccount.user_id == user.id).all()]
    if not user_account_ids:
        return []

    transactions = (
        db.query(Transaction)
        .filter(Transaction.bank_account_id.in_(user_account_ids))
        .order_by(Transaction.transaction_date.desc())
        .all()
    )
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
    transaction_data: TransactionUpdate,
    firebase_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    transaction = db.query(Transaction).filter(Transaction.id == transaction_id).first()
    if not transaction:
        raise HTTPException(status_code=404, detail="Transaction not found")
    
    if transaction_data.category_id is not None:
        transaction.category_id = transaction_data.category_id
    if transaction_data.amount is not None:
        transaction.amount = transaction_data.amount
    if transaction_data.transaction_type is not None:
        transaction.transaction_type = transaction_data.transaction_type
    if transaction_data.description is not None:
        transaction.description = transaction_data.description
    if transaction_data.transaction_date is not None:
        transaction.transaction_date = transaction_data.transaction_date
    
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