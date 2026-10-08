from datetime import datetime
from decimal import Decimal
from typing import Optional, List, Any, Union
from pydantic import BaseModel, Field, ConfigDict, model_validator, field_validator


ALLOWED_SPLIT_TYPES = {"equal", "exact", "percentage", "shares"}


def normalize_split_type(val: Any) -> str:
    if not val:
        return "equal"
    val_str = str(val).strip().lower().replace("-", "_").replace(" ", "_")
    if val_str in ["equal", "equally", "split_equally", "even"]:
        return "equal"
    if val_str in ["exact", "unequal", "custom", "amount", "amounts"]:
        return "exact"
    if val_str in ["percentage", "percent", "%"]:
        return "percentage"
    if val_str in ["shares", "share", "ratio"]:
        return "shares"
    return val_str


class ExpenseSplitCreate(BaseModel):
    """
    Split definition for an individual group member.
    """
    member_id: Union[int, str] = Field(..., description="Group member ID or client ID", example=1)
    amount: Optional[Decimal] = Field(None, ge=0, description="Exact amount owed by this member", example=600.00)
    percentage: Optional[Decimal] = Field(None, ge=0, le=100, description="Percentage share (0-100)", example=25.0)
    shares: Optional[Decimal] = Field(None, ge=0, description="Ratio / share count", example=1.0)

    @model_validator(mode="before")
    @classmethod
    def map_flexible_fields(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if "member_id" not in data and "memberId" in data:
                data["member_id"] = data.get("memberId")
            if "member_id" not in data and "id" in data:
                data["member_id"] = data.get("id")
        return data


class ExpenseSplitResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    expense_id: int
    member_id: int
    member_name: Optional[str] = Field(None, description="Display name of the member")
    amount: Decimal = Field(..., description="Calculated or specified amount for this member")
    percentage: Optional[Decimal] = None
    shares: Optional[Decimal] = None


class GroupExpenseCreate(BaseModel):
    """
    Schema for adding a new group expense (Screen 1 & 2):
    - What did you spend on? -> description
    - Amount -> amount
    - Paid by -> paid_by (member ID)
    - Split between -> split_members (list of member IDs)
    - Split type -> split_type ('equal', 'exact', 'percentage', 'shares')
    - Category -> category_id / category_name (e.g. Food, Travel, Stay)
    """
    group_id: Optional[int] = Field(None, description="Target group ID (if not provided in URL path)", example=1)
    description: str = Field(..., max_length=255, description="What did you spend on? (e.g. Dinner, Cab, Hotel)", example="Dinner")
    amount: Decimal = Field(..., gt=0, description="Total expense amount in currency", example=2400.00)
    paid_by: Optional[Union[int, str]] = Field(None, description="Group member ID or client ID of the payer", example=1)

    category_id: Optional[int] = Field(None, description="Category ID (e.g. Food, Travel, Stay)", example=1)
    category_name: Optional[str] = Field(None, description="Category name (optional fallback)", example="Food")

    split_type: str = Field(default="equal", description="equal | exact | percentage | shares", example="equal")
    split_members: Optional[List[Union[int, str]]] = Field(
        default=None,
        description="For equal split: list of member IDs participating in the split (Screen 'Split between')"
    )
    splits: Optional[List[ExpenseSplitCreate]] = Field(
        default=None,
        description="Detailed splits for exact/percentage/shares split modes"
    )

    expense_date: datetime = Field(
        default_factory=datetime.utcnow,
        description="Date and time of expense (defaults to now)"
    )
    notes: Optional[str] = Field(None, description="Optional extra notes")

    @model_validator(mode="before")
    @classmethod
    def map_flexible_fields(cls, data: Any) -> Any:
        if isinstance(data, dict):
            # Description: description, title, name, spendOn, what_did_you_spend_on
            if not data.get("description"):
                for key in ["title", "name", "spendOn", "what_did_you_spend_on", "spend_on"]:
                    if data.get(key):
                        data["description"] = data.get(key)
                        break

            # Amount: amount, total_amount, totalAmount
            if data.get("amount") is None:
                for key in ["total_amount", "totalAmount"]:
                    if data.get(key) is not None:
                        data["amount"] = data.get(key)
                        break

            # Group ID: group_id, groupId
            if "group_id" not in data and "groupId" in data:
                data["group_id"] = data.get("groupId")

            # Paid by: paid_by, paidBy, payer_id, payerId
            if "paid_by" not in data:
                for key in ["paidBy", "payer_id", "payerId"]:
                    if data.get(key) is not None:
                        data["paid_by"] = data.get(key)
                        break

            # Category: category_id, categoryId, category_name, categoryName, category
            if "category_id" not in data and "categoryId" in data:
                data["category_id"] = data.get("categoryId")
            if "category_name" not in data:
                if "categoryName" in data:
                    data["category_name"] = data.get("categoryName")
                elif "category" in data and isinstance(data.get("category"), str):
                    data["category_name"] = data.get("category")

            # Split type normalization
            raw_type = data.get("split_type") or data.get("splitType") or "equal"
            data["split_type"] = normalize_split_type(raw_type)

            # Split between: split_members, splitMembers, splitBetween, split_between, member_ids, memberIds
            if "split_members" not in data:
                for key in ["splitMembers", "splitBetween", "split_between", "member_ids", "memberIds"]:
                    if data.get(key) is not None:
                        data["split_members"] = data.get(key)
                        break

            # Date: expense_date, expenseDate, date
            if "expense_date" not in data:
                for key in ["expenseDate", "date"]:
                    if data.get(key) is not None:
                        data["expense_date"] = data.get(key)
                        break

        return data

    @field_validator("split_type")
    @classmethod
    def validate_split_type(cls, v: str) -> str:
        normalized = normalize_split_type(v)
        if normalized not in ALLOWED_SPLIT_TYPES:
            raise ValueError(f"split_type must be one of {sorted(list(ALLOWED_SPLIT_TYPES))}, got '{v}'")
        return normalized

    @model_validator(mode="after")
    def validate_splits_consistency(self) -> "GroupExpenseCreate":
        # If exact splits provided, check that amounts sum to total amount
        if self.split_type == "exact" and self.splits:
            total_split = sum(s.amount or Decimal("0.00") for s in self.splits)
            if abs(total_split - self.amount) > Decimal("0.05"):
                raise ValueError(
                    f"Sum of split amounts (₹{total_split}) must equal total amount (₹{self.amount})"
                )

        # If percentage splits provided, check that percentages sum to 100%
        if self.split_type == "percentage" and self.splits:
            total_pct = sum(s.percentage or Decimal("0.00") for s in self.splits)
            if abs(total_pct - Decimal("100.00")) > Decimal("0.5"):
                raise ValueError(
                    f"Sum of split percentages ({total_pct}%) must equal 100%"
                )

        return self


class GroupExpenseUpdate(BaseModel):
    description: Optional[str] = Field(None, max_length=255)
    amount: Optional[Decimal] = Field(None, gt=0)
    paid_by: Optional[int] = None
    category_id: Optional[int] = None
    category_name: Optional[str] = None
    split_type: Optional[str] = None
    split_members: Optional[List[int]] = None
    splits: Optional[List[ExpenseSplitCreate]] = None
    expense_date: Optional[datetime] = None
    notes: Optional[str] = None

    @model_validator(mode="before")
    @classmethod
    def map_flexible_fields(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if "split_type" in data or "splitType" in data:
                raw_type = data.get("split_type") or data.get("splitType")
                if raw_type:
                    data["split_type"] = normalize_split_type(raw_type)
            if "paid_by" not in data and "paidBy" in data:
                data["paid_by"] = data.get("paidBy")
            if "category_id" not in data and "categoryId" in data:
                data["category_id"] = data.get("categoryId")
        return data


class GroupExpenseListItemResponse(BaseModel):
    """
    Schema tailored for the expense list item card (Screen 3):
    Displays:
    - Description: 'Dinner'
    - Subtitle: 'You paid · 4 people' / 'Rahul paid · 4 people'
    - Formatted time: 'Today, 8:30 PM'
    - Total amount: ₹2,400.00
    - Status badge: 'You get back ₹1,800.00' (owed) / 'You owe ₹200.00' (owe)
    - Category: Food / Travel / Stay
    """
    model_config = ConfigDict(from_attributes=True)

    id: int
    group_id: int
    description: str = Field(..., description="e.g. Dinner, Cab, Hotel, Snacks")
    amount: Decimal = Field(..., description="Total expense amount, e.g. 2400.00")

    category_id: Optional[int] = None
    category_name: Optional[str] = Field(None, description="e.g. Food, Travel, Stay")

    paid_by: int
    payer_name: str = Field(..., description="e.g. 'You' or 'Rahul Sharma'")
    payer_initials: Optional[str] = Field(None, description="e.g. 'AS', 'RS'")

    split_type: str = "equal"
    members_count: int = Field(default=1, description="Number of members sharing the expense, e.g. 4")
    subtitle: str = Field(..., description="e.g. 'You paid · 4 people' or 'Rahul paid · 4 people'")

    user_net_amount: Optional[Decimal] = Field(
        None,
        description="Amount you get back (positive) or owe (negative) for this expense"
    )
    user_status_text: Optional[str] = Field(
        None,
        description="e.g. 'You get back ₹1,800.00' or 'You owe ₹200.00'"
    )
    user_status_type: Optional[str] = Field(
        None,
        description="'owed' | 'owe' | 'settled' | 'not_involved'"
    )

    expense_date: datetime
    formatted_date: Optional[str] = Field(
        None,
        description="e.g. 'Today, 8:30 PM' or 'Yesterday, 5:30 PM'"
    )


class GroupExpenseResponse(BaseModel):
    """
    Full detailed expense response.
    """
    model_config = ConfigDict(from_attributes=True)

    id: int
    group_id: int
    description: str
    amount: Decimal
    category_id: Optional[int] = None
    category_name: Optional[str] = None
    paid_by: int
    payer_name: Optional[str] = None
    split_type: str
    splits: List[ExpenseSplitResponse] = Field(default_factory=list)
    expense_date: datetime
    notes: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class SplitCalculationPreviewRequest(BaseModel):
    """
    Helper request for calculating splits in real-time on UI
    (e.g. showing '₹600.00 each' when ₹2,400.00 is divided between 4 people).
    """
    amount: Decimal = Field(..., gt=0, example=2400.00)
    split_type: str = Field(default="equal", example="equal")
    member_ids: List[int] = Field(..., example=[1, 2, 3, 4])
    splits: Optional[List[ExpenseSplitCreate]] = None

    @model_validator(mode="before")
    @classmethod
    def map_flexible_fields(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if "split_type" in data or "splitType" in data:
                raw_type = data.get("split_type") or data.get("splitType")
                if raw_type:
                    data["split_type"] = normalize_split_type(raw_type)
            if "member_ids" not in data and "memberIds" in data:
                data["member_ids"] = data.get("memberIds")
        return data


class SplitMemberCalculation(BaseModel):
    member_id: int
    amount: Decimal
    percentage: Optional[Decimal] = None
    shares: Optional[Decimal] = None


class SplitCalculationPreviewResponse(BaseModel):
    split_type: str
    total_amount: Decimal
    per_person_amount: Optional[Decimal] = Field(
        None,
        description="For equal split, e.g. ₹600.00 each"
    )
    splits: List[SplitMemberCalculation]
