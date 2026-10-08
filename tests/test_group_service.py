from decimal import Decimal
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from fastapi import HTTPException

from app.database import Base
from app.models import User, Group, GroupMember, GroupExpense, ExpenseSplit
from app.schemas.group import GroupCreate, GroupResponse
from app.schemas.group_expense import GroupExpenseCreate, ExpenseSplitCreate, GroupExpenseResponse
from app.services.group_service import GroupService


@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:")
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.mark.asyncio
async def test_create_group_basic(db_session):
    service = GroupService()
    user = User(
        firebase_uid="uid_123",
        email="creator@expensio.app",
        name="Akshay Salunke",
        password_hash="",
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    data = GroupCreate(name="Goa Trip", icon="🌴", description="Weekend trip")
    group = await service.create_group(data=data, db=db_session, user=user)

    assert group.id is not None
    assert group.name == "Goa Trip"
    assert group.icon == "🌴"
    assert group.description == "Weekend trip"
    assert group.created_by == user.id

    # Check creator member
    members = db_session.query(GroupMember).filter(GroupMember.group_id == group.id).all()
    assert len(members) == 1
    assert members[0].user_id == user.id
    assert members[0].role == "admin"

    # Validate response schema
    response = GroupResponse.model_validate(group)
    assert response.id == group.id
    assert response.name == "Goa Trip"


@pytest.mark.asyncio
async def test_create_group_with_members_and_phones(db_session):
    service = GroupService()
    creator = User(
        firebase_uid="uid_admin",
        email="admin@expensio.app",
        name="Admin",
        password_hash="",
    )
    member_user = User(
        firebase_uid="uid_member",
        email="member@expensio.app",
        name="Rahul Sharma",
        password_hash="",
    )
    db_session.add_all([creator, member_user])
    db_session.commit()
    db_session.refresh(creator)
    db_session.refresh(member_user)

    data = GroupCreate(
        name="Flatmates",
        icon="🏠",
        member_ids=[member_user.id],
        member_phones=["+91 98765 43210"],
    )
    group = await service.create_group(data=data, db=db_session, user=creator)

    members = db_session.query(GroupMember).filter(GroupMember.group_id == group.id).all()
    assert len(members) == 3

    roles = {m.role for m in members}
    assert "admin" in roles
    assert "member" in roles


@pytest.mark.asyncio
async def test_create_group_empty_name_error(db_session):
    service = GroupService()
    user = User(firebase_uid="uid_test", email="test@expensio.app", name="Test", password_hash="")
    db_session.add(user)
    db_session.commit()

    with pytest.raises(HTTPException) as exc_info:
        await service._create_group_internal(db=db_session, user=user, data=GroupCreate(name="   "))

    assert exc_info.value.status_code == 400


@pytest.mark.asyncio
async def test_create_group_with_user_request_fields(db_session):
    service = GroupService()
    creator = User(
        firebase_uid="uid_creator",
        email="creator@expensio.app",
        name="Creator",
        password_hash="",
    )
    db_session.add(creator)
    db_session.commit()
    db_session.refresh(creator)

    # Payload using exactly: groupid, groupnmae, groupdescription, groupicon, group member
    payload = {
        "groupid": 42,
        "groupnmae": "Weekend Trek",
        "groupdescription": "Hiking in Sahyadris",
        "groupicon": "⛰️",
        "group member": [
            {"phonenumber": "+91 99999 11111", "name": "Rohan", "role": "admin"},
            {"phonenumber": "+91 88888 22222", "name": "Sneha", "role": "member"},
        ]
    }
    data = GroupCreate(**payload)
    assert data.id == 42
    assert data.name == "Weekend Trek"
    assert data.description == "Hiking in Sahyadris"
    assert data.icon == "⛰️"
    assert len(data.members) == 2

    group = await service.create_group(data=data, db=db_session, user=creator)
    assert group.id == 42
    assert group.name == "Weekend Trek"
    assert group.description == "Hiking in Sahyadris"
    assert group.icon == "⛰️"

    # Members: 1 admin (creator) + 2 invited members
    members = db_session.query(GroupMember).filter(GroupMember.group_id == group.id).all()
    assert len(members) == 3

    member_names = {m.name for m in members}
    assert "Creator" in member_names
    assert "Rohan" in member_names
    assert "Sneha" in member_names

    # GroupResponse validation
    response = GroupResponse.model_validate(group)
    assert response.id == 42
    assert response.name == "Weekend Trek"
    assert len(response.members) == 3


@pytest.mark.asyncio
async def test_create_group_frontend_payload(db_session):
    service = GroupService()
    payload = {
        "id": "group_1791370188785",
        "name": "Goa trio",
        "avatarIcon": "🌴",
        "currency": "INR",
        "createdBy": "user_akshay",
        "createdAt": "2026-10-07T10:49:48.786Z",
        "members": [
            {
                "id": "user_akshay",
                "name": "Akshay Salunke",
                "phone": "+91 98765 00000",
                "email": "akshay@example.com",
                "initials": "AS",
                "color": "#087AA6",
                "isCurrentUser": True,
                "isAdmin": True
            },
            {
                "id": "user_rahul",
                "name": "Rahul Sharma",
                "phone": "+91 98765 43210",
                "email": "rahul@example.com",
                "initials": "RS",
                "color": "#845EF7"
            },
            {
                "id": "user_sonali",
                "name": "Sonali Patil",
                "phone": "+91 98765 43211",
                "email": "sonali@example.com",
                "initials": "SP",
                "color": "#E64980"
            }
        ],
        "simplifyDebts": True,
        "defaultSplit": "equal"
    }
    data = GroupCreate(**payload)
    assert data.id == 1791370188785
    assert data.name == "Goa trio"
    assert data.icon == "🌴"
    assert len(data.members) == 3

    group = await service.create_group(data=data, db=db_session, user=None)
    assert group.id == 1791370188785
    assert group.name == "Goa trio"

    members = db_session.query(GroupMember).filter(GroupMember.group_id == group.id).all()
    assert len(members) == 3

    response = GroupResponse.model_validate(group)
    assert response.name == "Goa trio"
    assert response.avatarIcon == "🌴"
    assert response.currency == "INR"
    assert response.simplifyDebts is True
    assert len(response.members) == 3
    assert response.members[0].phone == "+91 98765 00000"
    assert response.members[0].isAdmin is True


@pytest.mark.asyncio
async def test_create_group_expense_equal_split(db_session):
    service = GroupService()
    creator = User(firebase_uid="uid_c1", email="c1@expensio.app", name="Akshay", password_hash="")
    m2_user = User(firebase_uid="uid_m2", email="m2@expensio.app", name="Rahul", password_hash="")
    m3_user = User(firebase_uid="uid_m3", email="m3@expensio.app", name="Sonali", password_hash="")
    db_session.add_all([creator, m2_user, m3_user])
    db_session.commit()

    group_data = GroupCreate(
        name="Goa Trip",
        members=[
            {"user_id": creator.id, "name": "Akshay", "role": "admin"},
            {"user_id": m2_user.id, "name": "Rahul", "role": "member"},
            {"user_id": m3_user.id, "name": "Sonali", "role": "member"},
        ]
    )
    group = await service.create_group(data=group_data, db=db_session, user=creator)

    expense_data = GroupExpenseCreate(
        description="Dinner at Brittos",
        amount=Decimal("3000.00"),
        paid_by=creator.id,
        split_type="equal",
        category_name="Food & Dining",
    )
    expense = await service.create_group_expense(
        db=db_session,
        group_id=group.id,
        data=expense_data,
        current_user=creator,
    )

    assert expense.id is not None
    assert expense.description == "Dinner at Brittos"
    assert expense.amount == Decimal("3000.00")
    assert expense.split_type == "equal"
    assert len(expense.splits) == 3

    # ₹3000 / 3 = ₹1000 each
    for split in expense.splits:
        assert split.amount == Decimal("1000.00")
        assert split.percentage == Decimal("33.33") or split.percentage == Decimal("33.34")

    # Validate response schema
    resp = GroupExpenseResponse.model_validate(expense)
    assert resp.description == "Dinner at Brittos"
    assert len(resp.splits) == 3


@pytest.mark.asyncio
async def test_create_group_expense_exact_split(db_session):
    service = GroupService()
    user1 = User(firebase_uid="uid_e1", email="e1@expensio.app", name="User 1", password_hash="")
    user2 = User(firebase_uid="uid_e2", email="e2@expensio.app", name="User 2", password_hash="")
    db_session.add_all([user1, user2])
    db_session.commit()

    group = await service.create_group(
        data=GroupCreate(name="Flat", member_ids=[user2.id]),
        db=db_session,
        user=user1,
    )
    members = db_session.query(GroupMember).filter(GroupMember.group_id == group.id).all()
    m1_id, m2_id = members[0].id, members[1].id

    expense_data = GroupExpenseCreate(
        description="Electricity Bill",
        amount=Decimal("1500.00"),
        paid_by=m1_id,
        split_type="exact",
        splits=[
            {"member_id": m1_id, "amount": Decimal("900.00")},
            {"member_id": m2_id, "amount": Decimal("600.00")},
        ]
    )
    expense = await service.create_group_expense(
        db=db_session,
        group_id=group.id,
        data=expense_data,
        current_user=user1,
    )

    assert len(expense.splits) == 2
    amounts = {s.amount for s in expense.splits}
    assert Decimal("900.00") in amounts
    assert Decimal("600.00") in amounts
