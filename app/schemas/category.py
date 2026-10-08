from typing import Optional
from pydantic import BaseModel, ConfigDict, Field


class CategoryBase(BaseModel):
    name: str = Field(..., max_length=100, description="Category name, e.g. Food, Travel, Stay", example="Food")
    icon: Optional[str] = Field(None, max_length=50, description="Icon name or emoji, e.g. food, travel, stay", example="food")


class CategoryCreate(CategoryBase):
    pass


class CategoryResponse(CategoryBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
