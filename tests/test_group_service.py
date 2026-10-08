import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from fastapi import HTTPException

from app.database import Base
from app.models import User, Group, GroupMember
from app.schemas.group import GroupCreate, GroupResponse
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
