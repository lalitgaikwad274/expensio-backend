from datetime import datetime
from decimal import Decimal
import pytest
from pydantic import ValidationError

from app.schemas.group import (
    GroupCreate,
    GroupUpdate,
    GroupListItemResponse,
    GroupDetailResponse,
    GroupMemberCreate,
    GroupMemberResponse,
    MemberBalanceResponse,
    DebtSettlementResponse,
    GroupBalancesResponse,
    get_initials,
)
from app.schemas.group_expense import (
    GroupExpenseCreate,
    GroupExpenseListItemResponse,
    ExpenseSplitCreate,
    ExpenseSplitResponse,
    SplitCalculationPreviewResponse,
    SplitMemberCalculation,
    normalize_split_type,
)
from app.schemas.category import CategoryResponse


def test_get_initials():
    assert get_initials("Akshay Salunke") == "AS"
    assert get_initials("Rahul Sharma") == "RS"
    assert get_initials("Sonali Patil") == "SP"
    assert get_initials("Pratik More") == "PM"
    assert get_initials("Goa") == "GO"
    assert get_initials("") == "U"
    assert get_initials(None) == "U"


def test_normalize_split_type():
    assert normalize_split_type("equal") == "equal"
    assert normalize_split_type("Split equally") == "equal"
    assert normalize_split_type("equally") == "equal"
    assert normalize_split_type("exact") == "exact"
    assert normalize_split_type("unequal") == "exact"
    assert normalize_split_type("percentage") == "percentage"
    assert normalize_split_type("shares") == "shares"


def test_group_create_flexible_aliases():
    data = {
        "groupName": "Goa Trip",
        "groupIcon": "🌴",
        "memberIds": [1, 2, 3, 4],
        "memberPhones": ["+91 98765 43210"],
    }
    group = GroupCreate(**data)
    assert group.name == "Goa Trip"
    assert group.icon == "🌴"
    assert group.member_ids == [1, 2, 3, 4]
    assert group.member_phones == ["+91 98765 43210"]


def test_group_create_user_request_flexible_fields():
    data = {
        "groupid": 101,
        "groupnmae": "Trip to Manali",
        "groupdescription": "Winter vacation with friends",
        "groupicon": "❄️",
        "group member": [
            1,
            "+91 98765 43210",
            {"name": "Alice", "email": "alice@example.com"},
        ]
    }
    group = GroupCreate(**data)
    assert group.id == 101
    assert group.name == "Trip to Manali"
    assert group.description == "Winter vacation with friends"
    assert group.icon == "❄️"
    assert len(group.members) == 3
    assert group.members[0].user_id == 1
    assert group.members[1].phone_number == "+91 98765 43210"
    assert group.members[2].name == "Alice"
    assert group.members[2].email == "alice@example.com"


def test_group_member_create_phonenumber_name_role():
    data = {
        "phonenumber": "+91 98765 43210",
        "name": "Rahul Sharma",
        "role": "admin",
    }
    member = GroupMemberCreate(**data)
    assert member.name == "Rahul Sharma"
    assert member.phone_number == "+91 98765 43210"
    assert member.role == "admin"


def test_group_list_item_response_screen4():
    # Matches Screen 4 "Goa Trip" card
    goa_card = GroupListItemResponse(
        id=1,
        name="Goa Trip",
        icon="🌴",
        members_count=4,
        expenses_count=4,
        subtitle="4 members · 4 expenses",
        user_balance=Decimal("1240.00"),
        user_balance_text="You are owed ₹1,240.00",
        user_balance_type="owed",
        created_at=datetime.utcnow(),
    )
    assert goa_card.name == "Goa Trip"
    assert goa_card.user_balance_type == "owed"
    assert goa_card.user_balance == Decimal("1240.00")

    # Matches Screen 4 "Flatmates" card
    flatmates_card = GroupListItemResponse(
        id=2,
        name="Flatmates",
        icon="🏠",
        members_count=3,
        expenses_count=0,
        subtitle="3 members · 0 expenses",
        user_balance=Decimal("-430.00"),
        user_balance_text="You owe ₹430.00",
        user_balance_type="owe",
        created_at=datetime.utcnow(),
    )
    assert flatmates_card.user_balance_type == "owe"

    # Matches Screen 4 "Friends" card
    friends_card = GroupListItemResponse(
        id=3,
        name="Friends",
        icon="🍕",
        members_count=4,
        expenses_count=0,
        subtitle="4 members · 0 expenses",
        user_balance=Decimal("0.00"),
        user_balance_text="Settled up ₹0.00",
        user_balance_type="settled",
        created_at=datetime.utcnow(),
    )
    assert friends_card.user_balance_type == "settled"


def test_group_expense_create_screen1_and_2():
    # Matches Screen 1 & 2: "Dinner", ₹2,400.00, Paid by You (id=1), Split equally between 4 members, Category Food
    payload = {
        "groupId": 1,
        "spendOn": "Dinner",
        "amount": 2400.00,
        "paidBy": 1,
        "splitBetween": [1, 2, 3, 4],
        "splitType": "Split equally",
        "categoryName": "Food",
    }
    expense = GroupExpenseCreate(**payload)
    assert expense.group_id == 1
    assert expense.description == "Dinner"
    assert expense.amount == Decimal("2400.00")
    assert expense.paid_by == 1
    assert expense.split_members == [1, 2, 3, 4]
    assert expense.split_type == "equal"
    assert expense.category_name == "Food"


def test_group_expense_create_exact_split_validation():
    # Valid exact split
    payload = {
        "description": "Cab",
        "amount": Decimal("800.00"),
        "paid_by": 2,
        "split_type": "exact",
        "splits": [
            {"member_id": 1, "amount": Decimal("200.00")},
            {"member_id": 2, "amount": Decimal("200.00")},
            {"member_id": 3, "amount": Decimal("200.00")},
            {"member_id": 4, "amount": Decimal("200.00")},
        ],
    }
    expense = GroupExpenseCreate(**payload)
    assert expense.amount == Decimal("800.00")

    # Invalid exact split: sum does not match total amount
    invalid_payload = {
        "description": "Cab",
        "amount": Decimal("800.00"),
        "paid_by": 2,
        "split_type": "exact",
        "splits": [
            {"member_id": 1, "amount": Decimal("100.00")},
            {"member_id": 2, "amount": Decimal("200.00")},
        ],
    }
    with pytest.raises(ValidationError):
        GroupExpenseCreate(**invalid_payload)


def test_group_expense_create_percentage_validation():
    # Valid percentage split
    payload = {
        "description": "Hotel",
        "amount": Decimal("6000.00"),
        "paid_by": 1,
        "split_type": "percentage",
        "splits": [
            {"member_id": 1, "percentage": Decimal("25.0")},
            {"member_id": 2, "percentage": Decimal("25.0")},
            {"member_id": 3, "percentage": Decimal("25.0")},
            {"member_id": 4, "percentage": Decimal("25.0")},
        ],
    }
    expense = GroupExpenseCreate(**payload)
    assert expense.split_type == "percentage"

    # Invalid percentage split: does not sum to 100%
    invalid_payload = {
        "description": "Hotel",
        "amount": Decimal("6000.00"),
        "paid_by": 1,
        "split_type": "percentage",
        "splits": [
            {"member_id": 1, "percentage": Decimal("40.0")},
            {"member_id": 2, "percentage": Decimal("40.0")},
        ],
    }
    with pytest.raises(ValidationError):
        GroupExpenseCreate(**invalid_payload)


def test_group_expense_list_item_response_screen3():
    # Dinner item from Screen 3
    dinner = GroupExpenseListItemResponse(
        id=1,
        group_id=1,
        description="Dinner",
        amount=Decimal("2400.00"),
        category_name="Food",
        paid_by=1,
        payer_name="You",
        payer_initials="AS",
        split_type="equal",
        members_count=4,
        subtitle="You paid · 4 people",
        user_net_amount=Decimal("1800.00"),
        user_status_text="You get back ₹1,800.00",
        user_status_type="owed",
        expense_date=datetime.utcnow(),
        formatted_date="Today, 8:30 PM",
    )
    assert dinner.description == "Dinner"
    assert dinner.subtitle == "You paid · 4 people"
    assert dinner.user_status_text == "You get back ₹1,800.00"
    assert dinner.user_status_type == "owed"

    # Cab item from Screen 3
    cab = GroupExpenseListItemResponse(
        id=2,
        group_id=1,
        description="Cab",
        amount=Decimal("800.00"),
        category_name="Travel",
        paid_by=2,
        payer_name="Rahul",
        payer_initials="RS",
        split_type="equal",
        members_count=4,
        subtitle="Rahul paid · 4 people",
        user_net_amount=Decimal("-200.00"),
        user_status_text="You owe ₹200.00",
        user_status_type="owe",
        expense_date=datetime.utcnow(),
        formatted_date="Today, 5:30 PM",
    )
    assert cab.description == "Cab"
    assert cab.subtitle == "Rahul paid · 4 people"
    assert cab.user_status_text == "You owe ₹200.00"
    assert cab.user_status_type == "owe"


def test_group_balances_response_screen3():
    balances = GroupBalancesResponse(
        group_id=1,
        user_balance=Decimal("1240.00"),
        user_balance_text="You are owed ₹1,240.00",
        user_balance_type="owed",
        member_balances=[
            MemberBalanceResponse(
                member_id=1,
                name="Akshay Salunke",
                initials="AS",
                net_balance=Decimal("1240.00"),
                status_text="Gets back ₹1,240.00",
                status_type="owed",
                is_you=True,
            ),
            MemberBalanceResponse(
                member_id=2,
                name="Rahul Sharma",
                initials="RS",
                net_balance=Decimal("-200.00"),
                status_text="Owes ₹200.00",
                status_type="owe",
                is_you=False,
            ),
        ],
        settlements=[
            DebtSettlementResponse(
                from_member_id=2,
                from_member_name="Rahul",
                to_member_id=1,
                to_member_name="Akshay",
                amount=Decimal("200.00"),
                formatted_amount="₹200.00",
                text="Rahul owes Akshay ₹200.00",
            )
        ],
    )
    assert balances.group_id == 1
    assert len(balances.member_balances) == 2
    assert len(balances.settlements) == 1
    assert balances.settlements[0].text == "Rahul owes Akshay ₹200.00"
