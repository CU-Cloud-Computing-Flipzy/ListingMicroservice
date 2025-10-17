from __future__ import annotations

from typing import Optional
from uuid import UUID, uuid4
from datetime import datetime
from enum import Enum
from pydantic import BaseModel, Field, HttpUrl


# =========================
# Media
# =========================

class MediaType(str, Enum):
    IMAGE = "image"
    VIDEO = "video"


class MediaBase(BaseModel):
    url: HttpUrl = Field(
        ...,
        description="Public URL of the media file.",
        json_schema_extra={"example": "https://cdn.example.com/items/mouse/front.jpg"},
    )
    type: MediaType = Field(
        default=MediaType.IMAGE,
        description="Type of media.",
        json_schema_extra={"example": "image"},
    )
    alt_text: Optional[str] = Field(
        None,
        description="Optional descriptive text for accessibility/SEO.",
        json_schema_extra={"example": "Front view of the wireless mouse"},
    )
    is_primary: bool = Field(
        default=False,
        description="Whether this is the primary media for the item.",
        json_schema_extra={"example": True},
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "url": "https://cdn.example.com/items/mouse/front.jpg",
                    "type": "image",
                    "alt_text": "Front view of the wireless mouse",
                    "is_primary": True,
                }
            ]
        }
    }


class MediaCreate(MediaBase):
    """Payload for creating a new media entry."""
    pass


class MediaUpdate(BaseModel):
    """Partial update; supply only fields to change."""
    url: Optional[HttpUrl] = Field(None, description="Update media URL.")
    type: Optional[MediaType] = Field(None, description="Update media type.")
    alt_text: Optional[str] = Field(None, description="Update alt text.")
    is_primary: Optional[bool] = Field(None, description="Toggle primary flag.")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {"alt_text": "Updated front image"},
                {"is_primary": True},
            ]
        }
    }


class MediaRead(MediaBase):
    """Representation returned to clients."""
    id: UUID = Field(
        default_factory=uuid4,
        description="Server-generated media ID.",
        json_schema_extra={"example": "11111111-2222-3333-4444-555555555555"},
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
