from typing import Optional
from pydantic import BaseModel, ConfigDict, Field


class UserBase(BaseModel):
    name: Optional[str] = Field(None, max_length=100, description="Full name of the user")
    email: Optional[str] = Field(None, max_length=255, description="Email address")
    phone_number: Optional[str] = Field(None, max_length=20, description="Phone number")


class UserCreate(UserBase):
    firebase_uid: Optional[str] = Field(None, max_length=128, description="Firebase UID")


class UserResponse(UserBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    firebase_uid: str
