import re
import uuid
from datetime import datetime
from decimal import Decimal
from typing import Optional, List, Any, Union
from fastapi import HTTPException, status
from sqlalchemy.orm import Session, joinedload

from app.database import SessionLocal
from app.models import Group, GroupMember, User, GroupExpense, ExpenseSplit, Category
from app.schemas.group import GroupCreate, GroupMemberCreate
from app.schemas.group_expense import GroupExpenseCreate, normalize_split_type


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

    async def create_group_expense(
        self,
        db: Session,
        group_id: int,
        data: GroupExpenseCreate,
        current_user: Optional[User] = None,
    ) -> GroupExpense:
        """
        Create a group expense and split it among group members based on split_type.
        Supports: 'equal', 'exact', 'percentage', 'shares'.
        """
        group = db.query(Group).filter(Group.id == group_id).first()
        if not group:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Group with ID {group_id} not found."
            )

        members = (
            db.query(GroupMember)
            .options(joinedload(GroupMember.user))
            .filter(GroupMember.group_id == group_id, GroupMember.is_active == True)
            .all()
        )
        if not members:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Group has no active members to share expenses."
            )

        def resolve_member(identifier: Any) -> Optional[GroupMember]:
            if identifier is None:
                return None
            if isinstance(identifier, int):
                for m in members:
                    if m.id == identifier or m.user_id == identifier:
                        return m
            raw_str = str(identifier).strip()
            if raw_str.isdigit():
                int_val = int(raw_str)
                for m in members:
                    if m.id == int_val or m.user_id == int_val:
                        return m
            clean_str = raw_str.lower()
            for m in members:
                if m.user:
                    if m.user.firebase_uid and m.user.firebase_uid.lower() == clean_str:
                        return m
                    if m.user.name and m.user.name.lower() == clean_str:
                        return m
                    if m.user.email and m.user.email.lower() == clean_str:
                        return m
                if m.phone_number and m.phone_number == raw_str:
                    return m
                if m.name and m.name.lower() == clean_str:
                    return m
            return None

        # 1. Resolve Payer
        payer_member = None
        if data.paid_by is not None:
            payer_member = resolve_member(data.paid_by)

        if not payer_member and current_user:
            for m in members:
                if m.user_id == current_user.id:
                    payer_member = m
                    break

        if not payer_member:
            for m in members:
                if m.role == "admin":
                    payer_member = m
                    break
            if not payer_member:
                payer_member = members[0]

        # 2. Resolve Category
        category_id = data.category_id
        if category_id:
            cat = db.query(Category).filter(Category.id == category_id).first()
            if not cat:
                category_id = None
        elif data.category_name and data.category_name.strip():
            cat_name = data.category_name.strip()
            cat = db.query(Category).filter(Category.name.ilike(cat_name)).first()
            if not cat:
                cat = Category(name=cat_name)
                db.add(cat)
                db.flush()
            category_id = cat.id

        total_amount = Decimal(str(data.amount)).quantize(Decimal("0.01"))
        split_type = normalize_split_type(data.split_type or "equal")

        # 3. Calculate splits
        calculated_splits = []

        if split_type == "equal":
            participant_members = []
            if data.splits:
                for s in data.splits:
                    resolved = resolve_member(s.member_id)
                    if resolved and resolved not in participant_members:
                        participant_members.append(resolved)
            elif data.split_members:
                for sm in data.split_members:
                    resolved = resolve_member(sm)
                    if resolved and resolved not in participant_members:
                        participant_members.append(resolved)
            else:
                participant_members = list(members)

            if not participant_members:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="No valid members found to split the expense."
                )

            count = Decimal(len(participant_members))
            base_share = (total_amount / count).quantize(Decimal("0.01"))
            allocated = base_share * count
            remainder = total_amount - allocated

            for i, m in enumerate(participant_members):
                share_amount = base_share + (remainder if i == 0 else Decimal("0.00"))
                pct = ((share_amount / total_amount) * Decimal("100.00")).quantize(Decimal("0.01"))
                calculated_splits.append({
                    "member_id": m.id,
                    "amount": share_amount,
                    "percentage": pct,
                    "shares": Decimal("1.00"),
                })

        elif split_type == "exact":
            if not data.splits:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Detailed splits with amounts must be provided for exact split type."
                )
            running_total = Decimal("0.00")
            for s in data.splits:
                m = resolve_member(s.member_id)
                if not m:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Member '{s.member_id}' not found in group."
                    )
                amt = Decimal(str(s.amount or 0)).quantize(Decimal("0.01"))
                running_total += amt
                pct = (
                    ((amt / total_amount) * Decimal("100.00")).quantize(Decimal("0.01"))
                    if total_amount > 0 else Decimal("0.00")
                )
                calculated_splits.append({
                    "member_id": m.id,
                    "amount": amt,
                    "percentage": pct,
                    "shares": s.shares,
                })

            diff = total_amount - running_total
            if abs(diff) > Decimal("0.05"):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Sum of split amounts (₹{running_total}) must equal total expense amount (₹{total_amount})."
                )
            if diff != Decimal("0.00") and calculated_splits:
                calculated_splits[0]["amount"] += diff

        elif split_type == "percentage":
            if not data.splits:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Detailed splits with percentages must be provided for percentage split type."
                )
            total_pct = sum(Decimal(str(s.percentage or 0)) for s in data.splits)
            if abs(total_pct - Decimal("100.00")) > Decimal("0.5"):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Sum of split percentages ({total_pct}%) must equal 100%."
                )

            running_allocated = Decimal("0.00")
            for s in data.splits:
                m = resolve_member(s.member_id)
                if not m:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Member '{s.member_id}' not found in group."
                    )
                pct = Decimal(str(s.percentage or 0))
                amt = (total_amount * (pct / Decimal("100.00"))).quantize(Decimal("0.01"))
                running_allocated += amt
                calculated_splits.append({
                    "member_id": m.id,
                    "amount": amt,
                    "percentage": pct,
                    "shares": s.shares,
                })
            remainder = total_amount - running_allocated
            if remainder != Decimal("0.00") and calculated_splits:
                calculated_splits[0]["amount"] += remainder

        elif split_type == "shares":
            if not data.splits:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Detailed splits with shares must be provided for shares split type."
                )
            total_shares = sum(Decimal(str(s.shares or 1)) for s in data.splits)
            if total_shares <= Decimal("0.00"):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Total shares must be greater than zero."
                )

            running_allocated = Decimal("0.00")
            for s in data.splits:
                m = resolve_member(s.member_id)
                if not m:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Member '{s.member_id}' not found in group."
                    )
                sh = Decimal(str(s.shares or 1))
                amt = (total_amount * (sh / total_shares)).quantize(Decimal("0.01"))
                pct = ((sh / total_shares) * Decimal("100.00")).quantize(Decimal("0.01"))
                running_allocated += amt
                calculated_splits.append({
                    "member_id": m.id,
                    "amount": amt,
                    "percentage": pct,
                    "shares": sh,
                })
            remainder = total_amount - running_allocated
            if remainder != Decimal("0.00") and calculated_splits:
                calculated_splits[0]["amount"] += remainder

        # 4. Create GroupExpense
        new_expense = GroupExpense(
            group_id=group.id,
            description=data.description.strip(),
            amount=total_amount,
            category_id=category_id,
            paid_by=payer_member.id,
            paid_by_firebase_uid=payer_member.firebase_uid or (payer_member.user.firebase_uid if payer_member.user else "unknown"),
            split_type=split_type,
            expense_date=data.expense_date or datetime.utcnow(),
            notes=data.notes,
        )
        db.add(new_expense)
        db.flush()

        # 5. Create ExpenseSplit rows
        for cs in calculated_splits:
            split_row = ExpenseSplit(
                expense_id=new_expense.id,
                member_id=cs["member_id"],
                amount=cs["amount"],
                percentage=cs.get("percentage"),
                shares=cs.get("shares"),
            )
            db.add(split_row)

        db.commit()
        db.refresh(new_expense)

        # 6. Reload with eager loaded relationships
        reloaded = (
            db.query(GroupExpense)
            .options(
                joinedload(GroupExpense.splits).joinedload(ExpenseSplit.member).joinedload(GroupMember.user),
                joinedload(GroupExpense.payer).joinedload(GroupMember.user),
                joinedload(GroupExpense.category),
            )
            .filter(GroupExpense.id == new_expense.id)
            .first()
        )
        return reloaded or new_expense

    def get_expenses_by_group_id(self, db: Session, group_id: str):
        expenses = (
            db.query(GroupExpense)
            .options(
                joinedload(GroupExpense.splits).joinedload(ExpenseSplit.member).joinedload(GroupMember.user),
                joinedload(GroupExpense.payer).joinedload(GroupMember.user),
                joinedload(GroupExpense.category),
            )
            .filter(GroupExpense.group_id == group_id)
            .all()
        )
        return expenses

    def getAllExpenses(self, db: Session):
        expenses = (
            db.query(GroupExpense)
            .options(
                joinedload(GroupExpense.splits).joinedload(ExpenseSplit.member).joinedload(GroupMember.user),
                joinedload(GroupExpense.payer).joinedload(GroupMember.user),
                joinedload(GroupExpense.category),
            )
            .all()
        )
        return expenses


group_service = GroupService()


