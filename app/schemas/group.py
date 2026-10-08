import re
from datetime import datetime
from decimal import Decimal
from typing import Optional, List, Any, Union
from pydantic import BaseModel, Field, ConfigDict, model_validator


def get_initials(name: Optional[str]) -> str:
    if not name:
        return "U"
    parts = name.strip().split()
    if len(parts) >= 2:
        return f"{parts[0][0]}{parts[1][0]}".upper()
    return parts[0][:2].upper()


class GroupMemberCreate(BaseModel):
    name: Optional[str] = Field(None, max_length=100, description="Member name, e.g. Rahul Sharma")
    phone_number: Optional[str] = Field(None, max_length=20, description="Phone number, e.g. +91 98765 43210")
    role: str = Field(default="member", description="Role: admin or member")
    user_id: Optional[int] = Field(None, description="Registered User ID", include_in_schema=False)
    client_id: Optional[str] = Field(None, description="Client string ID e.g. user_akshay", include_in_schema=False)
    email: Optional[str] = Field(None, description="Email address", include_in_schema=False)
    initials: Optional[str] = Field(None, description="Avatar initials", include_in_schema=False)
    color: Optional[str] = Field(None, description="Color hex", include_in_schema=False)
    is_current_user: Optional[bool] = Field(default=False, description="Whether this is the current user", include_in_schema=False)

    @model_validator(mode="before")
    @classmethod
    def map_flexible_fields(cls, data: Any) -> Any:
        if isinstance(data, int):
            return {"user_id": data}
        if isinstance(data, str):
            val = data.strip()
            if "@" in val:
                return {"email": val}
            elif any(c.isdigit() for c in val):
                return {"phone_number": val}
            else:
                return {"name": val}
        if isinstance(data, dict):
            # phonenumber / phone_number / phoneNumber / phone / mobile
            if "phone_number" not in data:
                for k in ["phonenumber", "phoneNumber", "phone", "mobile", "contact", "phone_no", "phoneno"]:
                    if k in data and data[k] is not None:
                        data["phone_number"] = data[k]
                        break

            # name / userName / username / memberName / member_name
            if "name" not in data:
                for k in ["userName", "username", "memberName", "member_name", "display_name", "displayName", "membername"]:
                    if k in data and data[k] is not None:
                        data["name"] = data[k]
                        break

            # role / isAdmin
            if "role" not in data:
                if data.get("isAdmin") is True:
                    data["role"] = "admin"
                else:
                    for k in ["member_role", "memberRole", "user_role"]:
                        if k in data and data[k] is not None:
                            data["role"] = data[k]
                            break

            # is_current_user / isCurrentUser / is_you
            if "is_current_user" not in data:
                for k in ["isCurrentUser", "is_current_user", "is_you"]:
                    if k in data and data[k] is not None:
                        data["is_current_user"] = bool(data[k])
                        break

            # color / avatar_color
            if "color" not in data and "avatar_color" in data:
                data["color"] = data["avatar_color"]

            # user_id vs client_id
            raw_id = None
            for k in ["userId", "id", "userid", "user_Id"]:
                if k in data and data[k] is not None:
                    raw_id = data[k]
                    break
            if raw_id is not None:
                if isinstance(raw_id, int):
                    data["user_id"] = raw_id
                elif str(raw_id).isdigit():
                    data["user_id"] = int(raw_id)
                else:
                    data["client_id"] = str(raw_id)

            if "email" not in data:
                for k in ["userEmail", "user_email", "mail"]:
                    if k in data and data[k] is not None:
                        data["email"] = data[k]
                        break
        return data


class GroupMemberSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int = Field(..., description="Group member ID")
    user_id: Optional[int] = None
    name: str = Field(..., description="Member name, e.g. Akshay Salunke")
    phone_number: Optional[str] = Field(None, description="Phone number, e.g. +91 98765 43210")
    initials: str = Field(..., description="Avatar initials, e.g. AS, RS, SP, PM")
    is_you: bool = Field(default=False, description="Whether this member is the requesting user")


class GroupMemberResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: Union[int, str]
    group_id: int
    name: str
    phone_number: Optional[str] = None
    email: Optional[str] = None
    role: str = "member"
    isAdmin: bool = False
    isCurrentUser: bool = False
    is_you: bool = False
    is_active: bool = True
    user_id: Optional[int] = None
    subtitle: Optional[str] = Field(None, description="'You' or phone number, e.g. +91 98765 43210")
    joined_at: Optional[datetime] = None


class GroupCreate(BaseModel):
    id: Optional[Union[int, str]] = Field(None, description="Optional custom group ID, e.g. group_1791370188785", example=1)
    name: str = Field(default="New Group", max_length=100, description="Group name, e.g. Goa Trip", example="Goa Trip")
    icon: Optional[str] = Field(default="🌴", max_length=50, description="Icon emoji or name, e.g. 🌴, 🏠, 🍕, 💼", example="🌴")
    description: Optional[str] = Field(None, description="Optional group description")
    currency: Optional[str] = Field(default="INR", description="Currency code")
    simplify_debts: Optional[bool] = Field(default=True, description="Simplify debts flag")
    default_split: Optional[str] = Field(default="equal", description="Default split type")
    created_by_str: Optional[str] = Field(None, description="Client string ID e.g. user_akshay", include_in_schema=False)
    members: Optional[List[GroupMemberCreate]] = Field(
        default_factory=list,
        description="List of members to add to the group"
    )
    member_ids: Optional[List[int]] = Field(default_factory=list, description="List of user IDs to add as members", include_in_schema=False)
    member_phones: Optional[List[str]] = Field(default_factory=list, description="List of phone numbers to invite", include_in_schema=False)

    @model_validator(mode="before")
    @classmethod
    def map_flexible_fields(cls, data: Any) -> Any:
        if not data or not isinstance(data, dict):
            return {"name": "New Group"}

        # Unwrap if payload is nested under common keys
        for k in ["group", "newGroup", "data", "body", "payload", "groupData"]:
            if k in data and isinstance(data[k], dict):
                data = dict(data[k])
                break

        # 1. groupid / id
        raw_id = None
        for k in ["group_id", "groupId", "groupid", "group_Id", "id"]:
            if k in data and data[k] is not None:
                raw_id = data[k]
                break
        if raw_id is not None:
            if isinstance(raw_id, int):
                data["id"] = raw_id
            else:
                digits = re.sub(r"[^0-9]", "", str(raw_id))
                data["id"] = int(digits) if digits else None

        # 2. groupnmae / name
        if not data.get("name"):
            for k in ["group_name", "groupName", "groupname", "groupnmae", "title", "group_title"]:
                if k in data and data[k]:
                    data["name"] = data[k]
                    break
        if not data.get("name"):
            data["name"] = "New Group"

        # 3. groupdescription / description
        if "description" not in data:
                for k in ["group_description", "groupDescription", "groupdescription", "desc", "group_desc"]:
                    if k in data and data[k] is not None:
                        data["description"] = data[k]
                        break

        # 4. groupicon / icon / avatarIcon
        if "icon" not in data:
            for k in ["avatarIcon", "avatar_icon", "avatar", "group_icon", "groupIcon", "groupicon"]:
                if k in data and data[k] is not None:
                    data["icon"] = data[k]
                    break

        # 5. simplify_debts / simplifyDebts
        if "simplify_debts" not in data and "simplifyDebts" in data:
            data["simplify_debts"] = data["simplifyDebts"]

        # 6. default_split / defaultSplit
        if "default_split" not in data and "defaultSplit" in data:
            data["default_split"] = data["defaultSplit"]

        # 7. created_by_str / createdBy
        if "createdBy" in data:
            data["created_by_str"] = str(data["createdBy"])

        # 8. group member / members
        raw_members = None
        for k in [
            "members",
            "group_members",
            "groupMembers",
            "groupmembers",
            "group_member",
            "groupMember",
            "groupmember",
            "group member",
            "group members",
        ]:
            if k in data and data[k] is not None:
                raw_members = data[k]
                break

        if raw_members is not None:
            if not isinstance(raw_members, list):
                raw_members = [raw_members]
            data["members"] = raw_members

        if "member_ids" not in data and "memberIds" in data:
            data["member_ids"] = data.get("memberIds")
        if "member_phones" not in data and "memberPhones" in data:
            data["member_phones"] = data.get("memberPhones")

        return data


class GroupUpdate(BaseModel):
    name: Optional[str] = Field(None, max_length=100)
    icon: Optional[str] = Field(None, max_length=50)
    description: Optional[str] = None

    @model_validator(mode="before")
    @classmethod
    def map_flexible_fields(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if "name" not in data and "groupName" in data:
                data["name"] = data.get("groupName")
            if "icon" not in data and "groupIcon" in data:
                data["icon"] = data.get("groupIcon")
        return data


class GroupResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: Union[int, str]
    name: str
    icon: Optional[str] = "🌴"
    avatarIcon: Optional[str] = "🌴"
    description: Optional[str] = None
    currency: Optional[str] = "INR"
    simplifyDebts: Optional[bool] = True
    defaultSplit: Optional[str] = "equal"
    created_by: Optional[int] = None
    createdBy: Optional[Union[int, str]] = None
    created_at: Optional[datetime] = None
    createdAt: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    members: List[GroupMemberResponse] = Field(default_factory=list)


class GroupListItemResponse(BaseModel):
    """
    Schema tailored for the 'Group Expenses' screen card (Screen 4):
    Shows: Icon, Group Name, '4 members · 4 expenses', and balance status:
    - 'You are owed ₹1,240.00' (owed)
    - 'You owe ₹430.00' (owe)
    - 'Settled up ₹0.00' (settled)
    """
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    icon: Optional[str] = "🌴"
    members_count: int = Field(default=0, example=4)
    expenses_count: int = Field(default=0, example=4)
    subtitle: Optional[str] = Field(None, description="e.g. '4 members · 4 expenses'", example="4 members · 4 expenses")
    user_balance: Decimal = Field(default=Decimal("0.00"), description="Net balance for current user. Positive=owed, Negative=owe, 0=settled")
    user_balance_text: str = Field(..., description="e.g. 'You are owed ₹1,240.00', 'You owe ₹430.00', 'Settled up ₹0.00'")
    user_balance_type: str = Field(..., description="'owed' | 'owe' | 'settled'")
    created_at: datetime


class GroupDetailResponse(BaseModel):
    """
    Schema for the Group Details header & summary screen (Screen 3).
    Shows Group header, balance card, and list of members.
    """
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    icon: Optional[str] = "🌴"
    description: Optional[str] = None
    members_count: int
    expenses_count: int
    user_balance: Decimal
    user_balance_text: str
    user_balance_type: str
    members: List[GroupMemberResponse] = Field(default_factory=list)
    created_at: datetime


class MemberBalanceResponse(BaseModel):
    """
    Schema for individual member balance in the 'Balances' tab (Screen 3).
    """
    member_id: int
    user_id: Optional[int] = None
    name: str
    initials: str
    phone_number: Optional[str] = None
    net_balance: Decimal = Field(..., description="Positive=gets back, Negative=owes, 0=settled")
    status_text: str = Field(..., description="e.g. 'Gets back ₹1,800.00' or 'Owes ₹200.00' or 'Settled up'")
    status_type: str = Field(..., description="'owed' | 'owe' | 'settled'")
    is_you: bool = False


class DebtSettlementResponse(BaseModel):
    """
    Simplified debt settlement item (e.g. 'Rahul owes Akshay ₹200.00')
    """
    from_member_id: int
    from_member_name: str
    to_member_id: int
    to_member_name: str
    amount: Decimal
    formatted_amount: str = Field(..., description="e.g. '₹200.00'")
    text: str = Field(..., description="e.g. 'Rahul owes Akshay ₹200.00'")


class GroupBalancesResponse(BaseModel):
    """
    Container schema for the 'Balances' tab (Screen 3).
    """
    group_id: int
    user_balance: Decimal
    user_balance_text: str
    user_balance_type: str
    member_balances: List[MemberBalanceResponse] = Field(default_factory=list)
    settlements: List[DebtSettlementResponse] = Field(default_factory=list)
