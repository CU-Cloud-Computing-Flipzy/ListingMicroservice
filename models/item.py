from __future__ import annotations

from typing import List
from uuid import UUID, uuid4
from decimal import Decimal
from datetime import datetime
from enum import Enum
from pydantic import BaseModel, Field

from .category import CategoryRead
from .media import MediaRead


# =========================
# Item
# =========================

class ItemCondition(str, Enum):
    NEW = "new"
    USED = "used"
    REFURBISHED = "refurbished"


class ItemStatus(str, Enum):
    ACTIVE = "active"
    HIDDEN = "hidden"
    SOLD = "sold"


# =========================
# Ref models
# =========================

class CategoryRef(BaseModel):
    id: UUID


class MediaRef(BaseModel):
    id: UUID


# =========================
# Base
# =========================

class ItemBase(BaseModel):
    owner_user_id: UUID = Field(
        ...,
        description="ID of the user who created/owns this item (logical foreign key to user-service).",
        json_schema_extra={"example": "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"},
    )

    name: str = Field(
        ...,
        min_length=1,
        max_length=200,
        description="Name of the item.",
        json_schema_extra={"example": "Wireless Mouse"},
    )
    description: str = Field(
        ...,
        min_length=1,
        max_length=2000,
        description="Short description of the item.",
        json_schema_extra={"example": "Ergonomic wireless mouse with 2.4GHz USB receiver."},
    )
    status: ItemStatus = Field(
        default=ItemStatus.ACTIVE,
        description="Status of the item.",
        json_schema_extra={"example": "active"},
    )
    condition: ItemCondition = Field(
        default=ItemCondition.NEW,
        description="Condition of the item.",
        json_schema_extra={"example": "new"},
    )
    price: Decimal = Field(
        ...,
        ge=Decimal("0.01"),
        le=Decimal("999999.99"),
        decimal_places=2,
        description="Price of the item.",
        json_schema_extra={"example": "19.99"},
    )
    category: CategoryRead = Field(
        ...,
        description="Category of this item.",
    )
    media: List[MediaRead] = Field(
        default_factory=list,
        max_length=10,
        description="List of media (images/videos) for this item.",
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "owner_user_id": "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
                    "name": "Wireless Mouse",
                    "description": "Ergonomic wireless mouse with 2.4GHz USB receiver.",
                    "condition": "new",
                    "price": "19.99",
                    "category": {
                        "id": "550e8400-e29b-41d4-a716-446655440000",
                        "name": "Electronics",
                        "description": "Devices, gadgets, and electronic accessories.",
                        "created_at": "2025-01-15T10:20:30Z",
                        "updated_at": "2025-01-16T12:00:00Z"
                    },
                    "media": [
                        {
                            "id": "11111111-2222-3333-4444-555555555555",
                            "item_id": "99999999-9999-4999-8999-999999999999",
                            "url": "https://cdn.example.com/items/mouse/front.jpg",
                            "type": "image",
                            "alt_text": "Front view of the wireless mouse",
                            "is_primary": True,
                            "created_at": "2025-01-15T10:20:30Z",
                            "updated_at": "2025-01-16T12:00:00Z"
                        }
                    ]
                }
            ]
        }
    }


# =========================
# Create
# =========================

class ItemCreate(BaseModel):
    """Payload for creating a new item."""
    owner_user_id: UUID
    name: str
    description: str
    status: ItemStatus = ItemStatus.ACTIVE
    condition: ItemCondition = ItemCondition.NEW
    price: Decimal

    category: CategoryRef
    media: List[MediaRef] | None = None


# =========================
# Update
# =========================

class ItemUpdate(BaseModel):
    """Partial update for an item."""

    name: str | None = Field(None, min_length=1, max_length=200, description="Update name.")
    description: str | None = Field(None, min_length=1, max_length=2000, description="Update description.")
    status: ItemStatus | None = Field(None, description="Status of the item.")
    condition: ItemCondition | None = Field(None, description="Update condition.")
    price: Decimal | None = Field(
        None,
        ge=Decimal("0.01"),
        le=Decimal("999999.99"),
        decimal_places=2,
        description="Update price.",
    )

    category: CategoryRef | None = Field(None, description="Update category.")
    media: List[MediaRef] | None = Field(None, max_length=10, description="Update media list.")


# =========================
# Links
# =========================

class ItemLinks(BaseModel):
    self: str = Field(
        ...,
        description="Relative link to this item resource.",
        json_schema_extra={"example": "/items/99999999-9999-4999-8999-999999999999"},
    )
    category: str | None = Field(
        None,
        description="Relative link to this item's category.",
        json_schema_extra={"example": "/categories/550e8400-e29b-41d4-a716-446655440000"},
    )
    media: List[str] | None = Field(
        None,
        description="Relative links to this item's media resources.",
        json_schema_extra={
            "example": [
                "/media/11111111-2222-3333-4444-555555555555"
            ]
        },
    )


# =========================
# Read
# =========================

class ItemRead(ItemBase):
    """Representation returned to clients."""

    id: UUID = Field(
        default_factory=uuid4,
        description="Server-generated item ID.",
        json_schema_extra={"example": "99999999-9999-4999-8999-999999999999"},
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
    links: ItemLinks | None = Field(
        None,
        description="Hypermedia links related to this item.",
    )
