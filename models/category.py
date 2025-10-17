from __future__ import annotations

from uuid import UUID, uuid4
from datetime import datetime
from pydantic import BaseModel, Field


# =========================
# Category
# =========================

class CategoryBase(BaseModel):
    name: str = Field(
        ...,
        description="Name of the category.",
        json_schema_extra={"example": "Electronics"},
    )
    description: str = Field(
        ...,
        description="Short description of the category.",
        json_schema_extra={"example": "Devices, gadgets, and electronic accessories."},
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "name": "Electronics",
                    "description": "Devices, gadgets, and electronic accessories.",
                }
            ]
        }
    }


class CategoryCreate(CategoryBase):
    """Payload for creating a new category."""
    pass


class CategoryUpdate(BaseModel):
    """Partial update for a category."""
    name: str | None = Field(None, description="Update category name.")
    description: str | None = Field(None, description="Update category description.")


class CategoryRead(CategoryBase):
    """Representation returned to clients."""
    id: UUID = Field(
        default_factory=uuid4,
        description="Server-generated category ID.",
        json_schema_extra={"example": "550e8400-e29b-41d4-a716-446655440000"},
    )
    created_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="Creation timestamp (UTC).",
        json_schema_extra={"example": "2025-01-15T10:20:30Z"},
    )
    updated_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="Last update timestamp (UTC).",
        json_schema_extra={"example": "2025-01-16T12:00:00Z"},
    )
