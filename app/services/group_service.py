import re
import uuid
from typing import Optional, List
from fastapi import HTTPException, status
from sqlalchemy.orm import Session, joinedload

from app.database import SessionLocal
from app.models import Group, GroupMember, User
from app.schemas.group import GroupCreate, GroupMemberCreate


class GroupService:
    @staticmethod
    def get_or_create_user(db: Session, firebase_user: dict) -> User:
        """
        Retrieve existing user by Firebase UID, or create a new user record.
        """
        firebase_uid = firebase_user.get("uid", "default_user")
        user = db.query(User).filter(User.firebase_uid == firebase_uid).first()
        if not user:
            email = firebase_user.get("email") or f"{firebase_uid}@expensio.app"
            name = (
                firebase_user.get("name")
                or firebase_user.get("display_name")
                or "User"
            )
            user = User(
                firebase_uid=firebase_uid,
                email=email,
                name=name,
                password_hash="",
            )
            db.add(user)
            db.commit()
            db.refresh(user)
        return user

    @staticmethod
    def resolve_or_create_member_user(
        db: Session,
        phone_number: Optional[str] = None,
        name: Optional[str] = None,
        user_id: Optional[int] = None,
        email: Optional[str] = None,
        client_id: Optional[str] = None,
    ) -> Optional[User]:
        """
        Resolve an existing User by phone_number, name, user_id, email, or client_id;
        or provision a new User record if not found.
        """
        # 0. By client_id if provided (e.g. "user_akshay")
        if client_id and str(client_id).strip():
            cid = str(client_id).strip()
            user = db.query(User).filter(User.firebase_uid == cid).first()
            if user:
                if name and (not user.name or user.name.startswith("user_")):
                    user.name = name.strip()
                    db.flush()
                return user

        # 1. By email if provided
        if email and email.strip():
            email_clean = email.strip()
            user = db.query(User).filter(User.email == email_clean).first()
            if user:
                if name and (not user.name or user.name.startswith("phone_")):
                    user.name = name.strip()
                    db.flush()
                return user

        # 2. By phone_number (primary)
        if phone_number and str(phone_number).strip():
            phone_str = str(phone_number).strip()
            phone_clean = re.sub(r"[^0-9]", "", phone_str)
            phone_uid = client_id or (f"phone_{phone_clean}" if phone_clean else f"phone_{uuid.uuid4().hex[:8]}")
            user = db.query(User).filter(User.firebase_uid == phone_uid).first()
            if not user and phone_clean:
                user = db.query(User).filter(User.firebase_uid.like(f"%{phone_clean}%")).first()

            if user:
                if name and name.strip() and (not user.name or user.name.startswith("phone_")):
                    user.name = name.strip()
                    db.flush()
                return user

            user_email = email.strip() if email and email.strip() else f"{phone_uid}@expensio.app"
            user = User(
                firebase_uid=phone_uid,
                name=name.strip() if name and name.strip() else phone_str,
                email=user_email,
                password_hash="",
            )
            db.add(user)
            db.flush()
            return user

        # 3. By name (if phone_number not provided)
        if name and name.strip():
            name_clean = name.strip()
            user = db.query(User).filter(User.name == name_clean).first()
            if user:
                return user
            safe_name = re.sub(r"[^a-zA-Z0-9]", "_", name_clean.lower())
            guest_uid = client_id or f"member_{safe_name}_{uuid.uuid4().hex[:6]}"
            user = User(
                firebase_uid=guest_uid,
                name=name_clean,
                email=email.strip() if email and email.strip() else f"{guest_uid}@expensio.app",
                password_hash="",
            )
            db.add(user)
            db.flush()
            return user

        # 4. By user_id (fallback)
        if user_id:
            user = db.query(User).filter(User.id == user_id).first()
            if user:
                return user
            uid_str = client_id or f"user_{user_id}_{uuid.uuid4().hex[:6]}"
            user = User(
                id=user_id,
                firebase_uid=uid_str,
                name=name or f"User {user_id}",
                email=email or f"user_{user_id}@expensio.app",
                password_hash="",
            )
            try:
                db.add(user)
                db.flush()
                return user
            except Exception:
                db.rollback()
                user = User(
                    firebase_uid=uid_str,
                    name=name or f"User {user_id}",
                    email=email or f"user_{user_id}@expensio.app",
                    password_hash="",
                )
                db.add(user)
                db.flush()
                return user

        return None

    async def create_group(
        self,
        data: GroupCreate,
        db: Optional[Session] = None,
        user: Optional[User] = None,
    ) -> Group:
        """
        Create a new group with the given payload, setting the creator as admin
        and attaching invited members.
        """
        if db is None:
            with SessionLocal() as session:
                return await self._create_group_internal(session, user, data)
        return await self._create_group_internal(db, user, data)

    async def _create_group_internal(
        self,
        db: Session,
        user: Optional[User],
        data: GroupCreate,
    ) -> Group:
        group_name = data.name.strip() if data.name else ""
        if not group_name:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Group name is required and cannot be empty."
            )

        # Check if custom group ID already exists
        if data.id is not None:
            existing = db.query(Group).filter(Group.id == data.id).first()
            if existing:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Group with ID {data.id} already exists."
                )

        # If user is not authenticated via Firebase, resolve from members payload
        if user is None:
            creator_member = None
            if data.members:
                for m in data.members:
                    if m.is_current_user or (data.created_by_str and (m.client_id == data.created_by_str or str(m.user_id) == data.created_by_str)):
                        creator_member = m
                        break
            if creator_member:
                user = self.resolve_or_create_member_user(
                    db,
                    phone_number=creator_member.phone_number,
                    name=creator_member.name,
                    email=creator_member.email,
                    client_id=creator_member.client_id,
                )
            elif data.created_by_str:
                user = self.resolve_or_create_member_user(
                    db,
                    client_id=data.created_by_str,
                    name=data.created_by_str.replace("user_", "").capitalize(),
                )

        if user is None:
            user = db.query(User).first()
            if not user:
                user = User(
                    firebase_uid="default_user",
                    name="Default User",
                    email="user@expensio.app",
                    password_hash="",
                )
                db.add(user)
                db.commit()
                db.refresh(user)

        group_kwargs = {
            "name": group_name,
            "icon": data.icon or "🌴",
            "description": data.description,
            "created_by": user.id if user else None,
        }
        if data.id is not None:
            group_kwargs["id"] = data.id

        new_group = Group(**group_kwargs)
        db.add(new_group)
        db.flush()

        added_user_ids = set()

        # Add creator as admin
        if user:
            creator_member = GroupMember(
                group_id=new_group.id,
                user_id=user.id,
                role="admin",
                is_active=True,
            )
            db.add(creator_member)
            added_user_ids.add(user.id)

        # 1. Process data.members (GroupMemberCreate items)
        if data.members:
            for m in data.members:
                target_user = self.resolve_or_create_member_user(
                    db,
                    phone_number=m.phone_number,
                    name=m.name,
                    user_id=m.user_id,
                    email=m.email,
                    client_id=m.client_id,
                )
                if target_user and target_user.id not in added_user_ids:
                    existing = db.query(GroupMember).filter(
                        GroupMember.group_id == new_group.id,
                        GroupMember.user_id == target_user.id,
                    ).first()
                    if not existing:
                        db.add(
                            GroupMember(
                                group_id=new_group.id,
                                user_id=target_user.id,
                                role=m.role or "member",
                                phone_number=m.phone_number,
                                is_active=True,
                            )
                        )
                    added_user_ids.add(target_user.id)

        # 2. Process data.member_ids
        if data.member_ids:
            for mid in data.member_ids:
                if mid not in added_user_ids:
                    target_user = self.resolve_or_create_member_user(db, user_id=mid)
                    if target_user and target_user.id not in added_user_ids:
                        existing = db.query(GroupMember).filter(
                            GroupMember.group_id == new_group.id,
                            GroupMember.user_id == target_user.id,
                        ).first()
                        if not existing:
                            db.add(
                                GroupMember(
                                    group_id=new_group.id,
                                    user_id=target_user.id,
                                    role="member",
                                    is_active=True,
                                )
                            )
                        added_user_ids.add(target_user.id)

        # 3. Process data.member_phones
        if data.member_phones:
            for phone in data.member_phones:
                target_user = self.resolve_or_create_member_user(db, phone_number=phone)
                if target_user and target_user.id not in added_user_ids:
                    existing = db.query(GroupMember).filter(
                        GroupMember.group_id == new_group.id,
                        GroupMember.user_id == target_user.id,
                    ).first()
                    if not existing:
                        db.add(
                            GroupMember(
                                group_id=new_group.id,
                                user_id=target_user.id,
                                role="member",
                                phone_number=phone,
                                is_active=True,
                            )
                        )
                    added_user_ids.add(target_user.id)

        db.commit()
        db.refresh(new_group)
        return new_group


group_service = GroupService()
