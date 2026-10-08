from sqlalchemy.orm import relationship
from sqlalchemy import (
    Column,
    String,
    DateTime,
    ForeignKey,
    Boolean,
    BigInteger,
    UniqueConstraint,
)
from datetime import datetime
from typing import Optional
from app.database import Base


class GroupMember(Base):
    __tablename__ = "group_members"

    id = Column(
        BigInteger,
        primary_key=True,
    )

    group_id = Column(
        BigInteger,
        ForeignKey("groups.id", ondelete="CASCADE"),
        nullable=False
    )

    user_id = Column(
        BigInteger,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False
    )

    role = Column(
        String(20),
        default="member",
        nullable=False
    )

    phone_number = Column(
        String(20),
        nullable=True
    )

    is_active = Column(
        Boolean,
        default=True,
        nullable=False
    )

    joined_at = Column(
        DateTime,
        default=datetime.utcnow
    )

    group = relationship(
        "Group",
        back_populates="members"
    )

    user = relationship(
        "User"
    )

    @property
    def name(self) -> str:
        if self.user and self.user.name:
            return self.user.name
        if self.phone_number:
            return self.phone_number
        return f"User {self.user_id}" if self.user_id else "Member"

    @property
    def email(self) -> Optional[str]:
        return self.user.email if self.user else None

    @property
    def firebase_uid(self) -> Optional[str]:
        return self.user.firebase_uid if self.user else None

    @property
    def status(self) -> str:
        return "active" if self.is_active else "pending"

    @property
    def initials(self) -> str:
        name_str = (self.name or "U").strip()
        parts = name_str.split()
        if len(parts) >= 2:
            return f"{parts[0][0]}{parts[1][0]}".upper()
        return name_str[:2].upper() if name_str else "U"

    @property
    def subtitle(self) -> Optional[str]:
        if self.role == "admin":
            return "Admin"
        return self.phone_number or None

    @property
    def phone(self) -> Optional[str]:
        return self.phone_number

    @property
    def isAdmin(self) -> bool:
        return self.role == "admin"

    @property
    def isCurrentUser(self) -> bool:
        return self.role == "admin" or getattr(self, "is_you", False)

    @property
    def color(self) -> str:
        colors = ["#087AA6", "#845EF7", "#E64980", "#20C997", "#FD7E14", "#4C6EF5"]
        idx = (self.id or 0) % len(colors)
        return colors[idx]

    @property
    def avatar_color(self) -> str:
        return self.color

    __table_args__ = (
        UniqueConstraint(
            "group_id",
            "user_id",
            name="unique_group_member"
        ),
    )