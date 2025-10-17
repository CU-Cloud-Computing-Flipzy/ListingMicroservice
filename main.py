from __future__ import annotations

import os
from datetime import datetime
from typing import Dict, List, Optional
from uuid import UUID

from fastapi import FastAPI, HTTPException, Query, Path

from models.category import CategoryCreate, CategoryRead, CategoryUpdate
from models.media import MediaCreate, MediaRead, MediaUpdate
from models.item import ItemCreate, ItemRead, ItemUpdate, ItemCondition

port = int(os.environ.get("FASTAPIPORT", 8000))

# -----------------------------------------------------------------------------
# In-memory "databases"
# -----------------------------------------------------------------------------
categories: Dict[UUID, CategoryRead] = {}
media_store: Dict[UUID, MediaRead] = {}
items: Dict[UUID, ItemRead] = {}

# -----------------------------------------------------------------------------
# App
# -----------------------------------------------------------------------------
app = FastAPI(
    title="Catalog Items API",
    description="Microservice for displaying Items with Categories and Media.",
    version="0.1.0",
)

# -----------------------------------------------------------------------------
# Category endpoints
# -----------------------------------------------------------------------------
@app.post("/categories", response_model=CategoryRead, status_code=201)
def create_category(payload: CategoryCreate):
    cat = CategoryRead(**payload.model_dump())
    categories[cat.id] = cat
    return cat


@app.get("/categories", response_model=List[CategoryRead])
def list_categories(
    name: Optional[str] = Query(None, description="Filter by category name"),
    q: Optional[str] = Query(None, description="Search in name/description"),
):
    results = list(categories.values())
    if name is not None:
        results = [c for c in results if c.name == name]
    if q is not None:
        ql = q.lower()
        results = [c for c in results if ql in c.name.lower() or ql in c.description.lower()]
    return results


@app.get("/categories/{category_id}", response_model=CategoryRead)
def get_category(category_id: UUID):
    if category_id not in categories:
        raise HTTPException(status_code=404, detail="Category not found")
    return categories[category_id]


@app.patch("/categories/{category_id}", response_model=CategoryRead)
def update_category(category_id: UUID, update: CategoryUpdate):
    if category_id not in categories:
        raise HTTPException(status_code=404, detail="Category not found")
    stored = categories[category_id].model_dump()
    stored.update(update.model_dump(exclude_unset=True))
    stored["updated_at"] = datetime.utcnow()
    categories[category_id] = CategoryRead(**stored)
    return categories[category_id]


# -----------------------------------------------------------------------------
# Media endpoints
# -----------------------------------------------------------------------------
@app.post("/media", response_model=MediaRead, status_code=201)
def create_media(payload: MediaCreate):
    m = MediaRead(**payload.model_dump())
    media_store[m.id] = m
    return m


@app.get("/media", response_model=List[MediaRead])
def list_media(
    type: Optional[str] = Query(None, description='Filter by "image" or "video"'),
    is_primary: Optional[bool] = Query(None, description="Filter by primary flag"),
):
    results = list(media_store.values())
    if type is not None:
        results = [m for m in results if m.type.value == type]
    if is_primary is not None:
        results = [m for m in results if m.is_primary == is_primary]
    return results


@app.get("/media/{media_id}", response_model=MediaRead)
def get_media(media_id: UUID):
    if media_id not in media_store:
        raise HTTPException(status_code=404, detail="Media not found")
    return media_store[media_id]


@app.patch("/media/{media_id}", response_model=MediaRead)
def update_media(media_id: UUID, update: MediaUpdate):
    if media_id not in media_store:
        raise HTTPException(status_code=404, detail="Media not found")
    stored = media_store[media_id].model_dump()
    stored.update(update.model_dump(exclude_unset=True))
    stored["updated_at"] = datetime.utcnow()
    media_store[media_id] = MediaRead(**stored)
    return media_store[media_id]


# -----------------------------------------------------------------------------
# Item endpoints
# -----------------------------------------------------------------------------
@app.post("/items", response_model=ItemRead, status_code=201)
def create_item(payload: ItemCreate):
    item = ItemRead(**payload.model_dump())
    items[item.id] = item
    return item


@app.get("/items", response_model=List[ItemRead])
def list_items(
    q: Optional[str] = Query(None, description="Search in name or description"),
    condition: Optional[ItemCondition] = Query(None, description="Filter by condition"),
    category_name: Optional[str] = Query(None, description="Filter by category name"),
):
    results = list(items.values())

    if q is not None:
        ql = q.lower()
        results = [i for i in results if ql in i.name.lower() or ql in i.description.lower()]

    if condition is not None:
        results = [i for i in results if i.condition == condition]

    if category_name is not None:
        results = [i for i in results if i.category.name == category_name]

    return results


@app.get("/items/{item_id}", response_model=ItemRead)
def get_item(item_id: UUID):
    if item_id not in items:
        raise HTTPException(status_code=404, detail="Item not found")
    return items[item_id]


@app.patch("/items/{item_id}", response_model=ItemRead)
def update_item(item_id: UUID, update: ItemUpdate):
    if item_id not in items:
        raise HTTPException(status_code=404, detail="Item not found")
    stored = items[item_id].model_dump()
    stored.update(update.model_dump(exclude_unset=True))
    stored["updated_at"] = datetime.utcnow()
    items[item_id] = ItemRead(**stored)
    return items[item_id]


# -----------------------------------------------------------------------------
# Root
# -----------------------------------------------------------------------------
@app.get("/")
def root():
    return {"message": "Welcome to the Catalog Items API. See /docs for OpenAPI UI."}


# -----------------------------------------------------------------------------
# Entrypoint
# -----------------------------------------------------------------------------
if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=True)
