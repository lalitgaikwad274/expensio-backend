import json
import logging
import os
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session, joinedload

from app.auth.firebase import verify_firebase_token
from app.database import get_db
from app.models import Group, GroupMember, User, GroupExpense, ExpenseSplit, Category
from app.schemas.group import (
    GroupCreate,
    GroupResponse,
    GroupMemberCreate,
    GroupMemberResponse,
)
from app.schemas.group_expense import (
    GroupExpenseCreate,
    GroupExpenseResponse,
)
from app.services.group_service import GroupService, group_service

logger = logging.getLogger("uvicorn.error")

router = APIRouter(
    prefix="/groups",
    tags=["Group"]
)

optional_bearer = HTTPBearer(auto_error=False)


def get_current_user_optional(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(optional_bearer)
) -> Optional[dict]:
    """
    Allow authentication if Bearer token is provided, without blocking unauthenticated requests.
    """
    if not credentials:
        return None
    token = credentials.credentials
    if os.getenv("APP_ENV", "development").lower() in ["development", "test"] and token in ["dev_token", "test_token", "default_user"]:
        return {
            "uid": "default_user",
            "email": "user@expensio.app",
            "name": "Default User",
        }
    return verify_firebase_token(token)


# Create group
@router.post("/", response_model=GroupResponse, status_code=status.HTTP_201_CREATED)
@router.post("", response_model=GroupResponse, status_code=status.HTTP_201_CREATED, include_in_schema=False)
async def create_group(
    request: Request,
    group: Optional[GroupCreate] = None,
    firebase_user: Optional[dict] = Depends(get_current_user_optional),
    db: Session = Depends(get_db)
):
    """
    Create a new group.
    Supports flexible field aliases and handles payloads from body, query params, or wrappers.
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
    print("########### ", request , "################")
    raw_body = await request.body()
    raw_str = raw_body.decode("utf-8", errors="replace")
    logger.info(f"POST /groups: content-type={request.headers.get('content-type')}")
    logger.info(f"POST /groups query_params={dict(request.query_params)}")
    logger.info(f"POST /groups raw_body={raw_str}")
    print("#####################",raw_str,"#####################")
    payload = {}
    if raw_str.strip():
        try:
            payload = json.loads(raw_str)
        except Exception:
            pass

    # If body was empty, check query params
    if not payload and request.query_params:
        payload = dict(request.query_params)

    # Unwrap if wrapped under 'group', 'newGroup', 'data', 'body'
    if isinstance(payload, dict):
        for k in ["group", "newGroup", "data", "body"]:
            if k in payload and isinstance(payload[k], dict):
                payload = payload[k]
                break

    # If payload found from raw body/query, build GroupCreate from it
    if payload:
        data_to_use = GroupCreate(**payload)
    elif group is not None:
        data_to_use = group
    else:
        data_to_use = GroupCreate()

    user = None
    if firebase_user:
        user = GroupService.get_or_create_user(db, firebase_user)

    new_group = await group_service.create_group(data=data_to_use, db=db, user=user)

    # Reload with joined members and users for clean serialization
    reloaded = (
        db.query(Group)
        .options(joinedload(Group.members).joinedload(GroupMember.user))
        .filter(Group.id == new_group.id)
        .first()
    )
    return reloaded or new_group


# List groups
@router.get("/", response_model=List[GroupResponse])
@router.get("", response_model=List[GroupResponse], include_in_schema=False)
def list_groups(
    firebase_user: Optional[dict] = Depends(get_current_user_optional),
    db: Session = Depends(get_db)
):
    """
    List groups. If authenticated, returns groups where user is creator or member.
    """
    query = db.query(Group).options(joinedload(Group.members).joinedload(GroupMember.user))
    if firebase_user:
        user = db.query(User).filter(User.firebase_uid == firebase_user.get("uid")).first()
        if user:
            member_group_ids = db.query(GroupMember.group_id).filter(GroupMember.user_id == user.id).scalar_subquery()
            return query.filter((Group.created_by == user.id) | (Group.id.in_(member_group_ids))).all()
    return query.all()


# Get all expenses across all groups
@router.get("/expenses", response_model=List[GroupExpenseResponse])
@router.get("/expenses/", response_model=List[GroupExpenseResponse], include_in_schema=False)
def get_all_expenses(db: Session = Depends(get_db)):
    """
    Get all group expenses across all groups.
    """
    return group_service.getAllExpenses(db)


# Get group by ID
@router.get("/{group_id}", response_model=GroupResponse)
def get_group(group_id: int, db: Session = Depends(get_db)):
    """
    Get group details by ID, including its members.
    """
    group = (
        db.query(Group)
        .options(joinedload(Group.members).joinedload(GroupMember.user))
        .filter(Group.id == group_id)
        .first()
    )
    if not group:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Group with ID {group_id} not found."
        )
    return group


# Add member to group
@router.post("/{group_id}/members", response_model=GroupMemberResponse, status_code=status.HTTP_201_CREATED)
def add_group_member(
    group_id: int,
    member: GroupMemberCreate,
    db: Session = Depends(get_db)
):
    """
    Add a member to an existing group.
    """
    group = db.query(Group).filter(Group.id == group_id).first()
    if not group:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Group with ID {group_id} not found."
        )

    target_user = GroupService.resolve_or_create_member_user(
        db,
        user_id=member.user_id,
        phone_number=member.phone_number,
        email=member.email,
        name=member.name,
    )
    if not target_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Could not resolve user from provided member information."
        )

    existing = db.query(GroupMember).filter(
        GroupMember.group_id == group_id,
        GroupMember.user_id == target_user.id
    ).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"User {target_user.name or target_user.id} is already a member of this group."
        )

    new_member = GroupMember(
        group_id=group_id,
        user_id=target_user.id,
        role=member.role or "member",
        phone_number=member.phone_number,
        is_active=True,
    )
    db.add(new_member)
    db.commit()
    db.refresh(new_member)
    return new_member

@router.delete("/{group_id}")
def delete_group(
    group_id: int,
    db: Session = Depends(get_db)
):
    """
    Delete a group.
    """
    group = db.query(Group).filter(Group.id == group_id).first()
    if not group:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Group with ID {group_id} not found."
        )
    db.delete(group)
    db.commit()
    return {"message": f"Group with ID {group_id} deleted successfully."}

@router.post("/{group_id}/expenses", response_model=GroupExpenseResponse, status_code=status.HTTP_201_CREATED)
@router.post("/{group_id}/expenses/", response_model=GroupExpenseResponse, status_code=status.HTTP_201_CREATED, include_in_schema=False)
async def add_group_expense(
    group_id: int,
    request: Request,
    expense_data: Optional[GroupExpenseCreate] = None,
    firebase_user: Optional[dict] = Depends(get_current_user_optional),
    db: Session = Depends(get_db)
):
    """
    Add an expense to a group and automatically split it among group members.
    Supports split types: 'equal' (default), 'exact', 'percentage', 'shares'.
    """
    group = db.query(Group).filter(Group.id == group_id).first()
    if not group:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Group with ID {group_id} not found."
        )

    # Flexible payload extraction from raw body, query params, or wrappers
    raw_body = await request.body()
    raw_str = raw_body.decode("utf-8", errors="replace")
    logger.info(f"POST /groups/{group_id}/expenses raw_body={raw_str}")
    payload = {}
    if raw_str.strip():
        try:
            payload = json.loads(raw_str)
        except Exception:
            pass

    if not payload and request.query_params:
        payload = dict(request.query_params)

    # Unwrap if wrapped under 'expense', 'newExpense', 'data', 'body'
    if isinstance(payload, dict):
        for k in ["expense", "newExpense", "data", "body"]:
            if k in payload and isinstance(payload[k], dict):
                payload = payload[k]
                break

    if payload:
        if "group_id" not in payload:
            payload["group_id"] = group_id
        data_to_use = GroupExpenseCreate(**payload)
    elif expense_data is not None:
        data_to_use = expense_data
        data_to_use.group_id = group_id
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Expense payload is required."
        )

    user = None
    if firebase_user:
        user = GroupService.get_or_create_user(db, firebase_user)

    created_expense = await group_service.create_group_expense(
        db=db,
        group_id=group_id,
        data=data_to_use,
        current_user=user,
    )
    return created_expense


@router.get("/{group_id}/expenses", response_model=List[GroupExpenseResponse])
@router.get("/{group_id}/expenses/", response_model=List[GroupExpenseResponse], include_in_schema=False)
def list_group_expenses(
    group_id: int,
    db: Session = Depends(get_db)
):
    """
    List all expenses for a group along with their splits.
    """
    group = db.query(Group).filter(Group.id == group_id).first()
    if not group:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Group with ID {group_id} not found."
        )

    expenses = (
        db.query(GroupExpense)
        .options(
            joinedload(GroupExpense.splits).joinedload(ExpenseSplit.member).joinedload(GroupMember.user),
            joinedload(GroupExpense.payer).joinedload(GroupMember.user),
            joinedload(GroupExpense.category),
        )
        .filter(GroupExpense.group_id == group_id)
        .order_by(GroupExpense.expense_date.desc(), GroupExpense.id.desc())
        .all()
    )
    return expenses


@router.get("/{group_id}/expenses/{expense_id}", response_model=GroupExpenseResponse)
def get_group_expense(
    group_id: int,
    expense_id: int,
    db: Session = Depends(get_db)
):
    """
    Get a specific group expense by ID with its splits.
    """
    expense = (
        db.query(GroupExpense)
        .options(
            joinedload(GroupExpense.splits).joinedload(ExpenseSplit.member).joinedload(GroupMember.user),
            joinedload(GroupExpense.payer).joinedload(GroupMember.user),
            joinedload(GroupExpense.category),
        )
        .filter(GroupExpense.group_id == group_id, GroupExpense.id == expense_id)
        .first()
    )
    if not expense:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Expense with ID {expense_id} not found in group {group_id}."
        )
    return expense

@router.delete("/{group_id}/expenses/{expense_id}", status_code=status.HTTP_200_OK)
def delete_group_expense(
    group_id: int,
    expense_id: int,
    db: Session = Depends(get_db)
):
    """
    Delete a specific group expense by ID.
    """
    expense = db.query(GroupExpense).filter(GroupExpense.group_id == group_id, GroupExpense.id == expense_id).first()
    if not expense:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Expense with ID {expense_id} not found in group {group_id}."
        )
    db.delete(expense)
    db.commit()
    return {"message": f"Expense with ID {expense_id} deleted successfully."}