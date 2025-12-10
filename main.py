from __future__ import annotations

import os
import hashlib
import time
from datetime import datetime
from typing import Dict, List, Optional
from uuid import UUID, uuid4
from enum import Enum

from fastapi import FastAPI, HTTPException, Query, Response, Request, BackgroundTasks, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import or_

from models.category import CategoryCreate, CategoryRead, CategoryUpdate
from models.media import MediaCreate, MediaRead, MediaUpdate, MediaType
from models.item import (
    ItemCreate,
    ItemRead,
    ItemUpdate,
    ItemCondition,
    ItemStatus,
    ItemLinks,
)

from db import (
    get_db,
    init_db,
    SessionLocal,
    CategoryORM,
    MediaORM,
    ItemORM,
)

port = int(os.environ.get("FASTAPIPORT", 8000))


# -----------------------------------------------------------------------------
# Job models (for async operations)
# -----------------------------------------------------------------------------
class JobStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"


class Job(BaseModel):
    id: UUID = Field(..., description="Job ID.")
    item_id: UUID = Field(..., description="ID of the related item.")
    status: JobStatus = Field(..., description="Current status of the job.")
    created_at: datetime = Field(..., description="Creation time of the job (UTC).")
    updated_at: datetime = Field(..., description="Last update time of the job (UTC).")
    result_message: Optional[str] = Field(
        None,
        description="Optional human-readable result or error message.",
    )


# In-memory job storage
jobs: Dict[UUID, Job] = {}


# -----------------------------------------------------------------------------
# Async job worker: operates on Item records stored in DB
# -----------------------------------------------------------------------------
def run_publish_job(job_id: UUID) -> None:
    """
    Background task: simulate publishing an item.
    Updates the item's status in the DB and the job's status.
    """
    job = jobs.get(job_id)
    if not job:
        return

    # 1. Mark job as in progress
    job.status = JobStatus.IN_PROGRESS
    job.updated_at = datetime.utcnow()
    jobs[job_id] = job

    # 2. Simulate some work
    time.sleep(2)

    db = SessionLocal()
    try:
        db_item = db.query(ItemORM).filter(ItemORM.id == str(job.item_id)).first()
        if not db_item:
            job.status = JobStatus.FAILED
            job.result_message = "Item no longer exists."
            job.updated_at = datetime.utcnow()
            jobs[job_id] = job
            return

        # Update item status in DB
        db_item.status = ItemStatus.ACTIVE.value
        db_item.updated_at = datetime.utcnow()
        db.commit()

        # Update job status
        job.status = JobStatus.COMPLETED
        job.result_message = "Item published successfully."
        job.updated_at = datetime.utcnow()
        jobs[job_id] = job
    finally:
        db.close()


# -----------------------------------------------------------------------------
# FastAPI app
# -----------------------------------------------------------------------------
app = FastAPI(
    title="Listing API",
    description="Microservice for displaying Items with Categories and Media.",
    version="0.1.0",
)


@app.on_event("startup")
def on_startup() -> None:
    # Ensure database tables exist at startup
    init_db()


# -----------------------------------------------------------------------------
# ORM → Pydantic mapping helpers
# -----------------------------------------------------------------------------
def category_to_read(cat: CategoryORM) -> CategoryRead:
    return CategoryRead(
        id=UUID(cat.id),
        name=cat.name,
        description=cat.description,
        created_at=cat.created_at,
        updated_at=cat.updated_at,
    )


def media_to_read(media: MediaORM) -> MediaRead:
    return MediaRead(
        id=UUID(media.id),
        url=media.url,
        type=MediaType(media.type),
        alt_text=media.alt_text,
        is_primary=media.is_primary,
        created_at=media.created_at,
        updated_at=media.updated_at,
    )


def item_to_read(item: ItemORM) -> ItemRead:
    category = category_to_read(item.category) if item.category else None
    media_list = [media_to_read(m) for m in item.media]
    return ItemRead(
        id=UUID(item.id),
        name=item.name,
        description=item.description,
        status=ItemStatus(item.status),
        condition=ItemCondition(item.condition),
        price=item.price,
        category=category,
        media=media_list,
        created_at=item.created_at,
        updated_at=item.updated_at,
        links=None,  # Filled later by set_item_links()
    )


# -----------------------------------------------------------------------------
# Link & ETag helpers
# -----------------------------------------------------------------------------
def set_item_links(item: ItemRead) -> None:
    """
    Populate the `links` field on an ItemRead with relative URLs.
    """
    item.links = ItemLinks(
        self=f"/items/{item.id}",
        category=f"/categories/{item.category.id}" if item.category else None,
        media=[f"/media/{m.id}" for m in item.media] if item.media else [],
    )


def generate_item_etag(item: ItemRead) -> str:
    """
    Generate a strong ETag based on item ID and updated_at timestamp.
    """
    raw = f"{item.id}:{item.updated_at.isoformat()}".encode("utf-8")
    return '"' + hashlib.sha256(raw).hexdigest() + '"'


# -----------------------------------------------------------------------------
# Category endpoints
# -----------------------------------------------------------------------------
@app.post("/categories", response_model=CategoryRead, status_code=201)
def create_category(payload: CategoryCreate, response: Response, db: Session = Depends(get_db)):
    db_cat = CategoryORM(
        name=payload.name,
        description=payload.description,
    )
    db.add(db_cat)
    db.commit()
    db.refresh(db_cat)
    cat = category_to_read(db_cat)
    response.headers["Location"] = f"/categories/{cat.id}"
    return cat


@app.get("/categories", response_model=List[CategoryRead])
def list_categories(
    name: Optional[str] = Query(None, description="Filter by category name"),
    q: Optional[str] = Query(None, description="Search in name/description"),
    db: Session = Depends(get_db),
):
    query = db.query(CategoryORM)
    if name is not None:
        query = query.filter(CategoryORM.name == name)
    if q is not None:
        pattern = f"%{q}%"
        query = query.filter(
            or_(
                CategoryORM.name.ilike(pattern),
                CategoryORM.description.ilike(pattern),
            )
        )
    cats = query.all()
    return [category_to_read(c) for c in cats]


@app.get("/categories/{category_id}", response_model=CategoryRead)
def get_category(category_id: UUID, db: Session = Depends(get_db)):
    db_cat = db.query(CategoryORM).filter(CategoryORM.id == str(category_id)).first()
    if db_cat is None:
        raise HTTPException(status_code=404, detail="Category not found")
    return category_to_read(db_cat)


@app.patch("/categories/{category_id}", response_model=CategoryRead)
def update_category(category_id: UUID, update: CategoryUpdate, db: Session = Depends(get_db)):
    db_cat = db.query(CategoryORM).filter(CategoryORM.id == str(category_id)).first()
    if db_cat is None:
        raise HTTPException(status_code=404, detail="Category not found")

    data = update.model_dump(exclude_unset=True)
    if "name" in data:
        db_cat.name = update.name
    if "description" in data:
        db_cat.description = update.description
    db_cat.updated_at = datetime.utcnow()

    db.commit()
    db.refresh(db_cat)
    return category_to_read(db_cat)


@app.delete("/categories/{category_id}", status_code=204)
def delete_category(category_id: UUID, db: Session = Depends(get_db)):
    db_cat = db.query(CategoryORM).filter(CategoryORM.id == str(category_id)).first()
    if db_cat is None:
        raise HTTPException(status_code=404, detail="Category not found")

    # Prevent deletion if it is still referenced by items
    in_use = (
        db.query(ItemORM)
        .filter(ItemORM.category_id == db_cat.id)
        .first()
        is not None
    )
    if in_use:
        raise HTTPException(
            status_code=400,
            detail="Category is referenced by one or more items; delete or update those items first.",
        )

    db.delete(db_cat)
    db.commit()
    return None


# -----------------------------------------------------------------------------
# Media endpoints
# -----------------------------------------------------------------------------
@app.post("/media", response_model=MediaRead, status_code=201)
def create_media(payload: MediaCreate, response: Response, db: Session = Depends(get_db)):
    db_media = MediaORM(
        url=str(payload.url),
        type=payload.type.value,
        alt_text=payload.alt_text,
        is_primary=payload.is_primary,
    )
    db.add(db_media)
    db.commit()
    db.refresh(db_media)
    m = media_to_read(db_media)
    response.headers["Location"] = f"/media/{m.id}"
    return m


@app.get("/media", response_model=List[MediaRead])
def list_media(
    type: Optional[str] = Query(None, description='Filter by "image" or "video"'),
    is_primary: Optional[bool] = Query(None, description="Filter by primary flag"),
    db: Session = Depends(get_db),
):
    query = db.query(MediaORM)
    if type is not None:
        query = query.filter(MediaORM.type == type)
    if is_primary is not None:
        query = query.filter(MediaORM.is_primary == is_primary)
    media = query.all()
    return [media_to_read(m) for m in media]


@app.get("/media/{media_id}", response_model=MediaRead)
def get_media(media_id: UUID, db: Session = Depends(get_db)):
    db_media = db.query(MediaORM).filter(MediaORM.id == str(media_id)).first()
    if db_media is None:
        raise HTTPException(status_code=404, detail="Media not found")
    return media_to_read(db_media)


@app.patch("/media/{media_id}", response_model=MediaRead)
def update_media(media_id: UUID, update: MediaUpdate, db: Session = Depends(get_db)):
    db_media = db.query(MediaORM).filter(MediaORM.id == str(media_id)).first()
    if db_media is None:
        raise HTTPException(status_code=404, detail="Media not found")

    data = update.model_dump(exclude_unset=True)
    if "url" in data and update.url is not None:
        db_media.url = str(update.url)
    if "type" in data and update.type is not None:
        db_media.type = update.type.value
    if "alt_text" in data:
        db_media.alt_text = update.alt_text
    if "is_primary" in data and update.is_primary is not None:
        db_media.is_primary = update.is_primary

    db_media.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(db_media)
    return media_to_read(db_media)


@app.delete("/media/{media_id}", status_code=204)
def delete_media(media_id: UUID, db: Session = Depends(get_db)):
    db_media = db.query(MediaORM).filter(MediaORM.id == str(media_id)).first()
    if db_media is None:
        raise HTTPException(status_code=404, detail="Media not found")

    # Prevent deletion if it is referenced by items
    if db_media.items:
        raise HTTPException(
            status_code=400,
            detail="Media is referenced by one or more items; delete or update those items first.",
        )

    db.delete(db_media)
    db.commit()
    return None


# -----------------------------------------------------------------------------
# Item endpoints
# -----------------------------------------------------------------------------
# Link helpers
def set_item_links(item: ItemRead) -> None:
    """
    Populate the `links` field on an ItemRead with relative paths.
    """
    item.links = ItemLinks(
        self=f"/items/{item.id}",
        category=f"/categories/{item.category.id}" if item.category else None,
        media=[f"/media/{m.id}" for m in item.media] if item.media else [],
    )

# ETag helpers
def generate_item_etag(item: ItemRead) -> str:
    """
    Generate a strong ETag for an item based on its ID and updated_at timestamp.
    """
    raw = f"{item.id}:{item.updated_at.isoformat()}".encode("utf-8")
    # Wrap in quotes to match typical HTTP ETag format
    return '"' + hashlib.sha256(raw).hexdigest() + '"'


@app.post("/items", response_model=ItemRead, status_code=201)
def create_item(payload: ItemCreate, response: Response, db: Session = Depends(get_db)):
    # Validate that category exists
    category_id = str(payload.category.id)
    db_cat = db.query(CategoryORM).filter(CategoryORM.id == category_id).first()
    if db_cat is None:
        raise HTTPException(status_code=400, detail="Category does not exist")

    # Validate that media exist
    media_objs: List[MediaORM] = []
    for m in payload.media:
        db_media = db.query(MediaORM).filter(MediaORM.id == str(m.id)).first()
        if db_media is None:
            raise HTTPException(status_code=400, detail=f"Media with id {m.id} does not exist")
        media_objs.append(db_media)

    db_item = ItemORM(
        name=payload.name,
        description=payload.description,
        status=payload.status.value,
        condition=payload.condition.value,
        price=payload.price,
        category_id=category_id,
    )
    db_item.media = media_objs

    db.add(db_item)
    db.commit()
    db.refresh(db_item)

    db_item = (
        db.query(ItemORM)
        .options(joinedload(ItemORM.category), joinedload(ItemORM.media))
        .filter(ItemORM.id == db_item.id)
        .first()
    )

    item = item_to_read(db_item)
    set_item_links(item)
    response.headers["Location"] = f"/items/{item.id}"
    return item


@app.get("/items", response_model=List[ItemRead])
def list_items(
    q: Optional[str] = Query(None, description="Search in name or description"),
    condition: Optional[ItemCondition] = Query(None, description="Filter by condition"),
    category_name: Optional[str] = Query(None, description="Filter by category name"),
    status: Optional[ItemStatus] = Query(None, description="Filter by item status"),
    include_all: bool = Query(False, description="Include all items regardless of status"),
    page: int = Query(1, ge=1, description="Page number (starting from 1)"),
    page_size: int = Query(10, ge=1, le=100, description="Number of items per page"),
    db: Session = Depends(get_db),
):
    query = (
        db.query(ItemORM)
        .options(joinedload(ItemORM.category), joinedload(ItemORM.media))
    )

    # By default return only ACTIVE items unless include_all=True
    if not include_all:
        if status is not None:
            query = query.filter(ItemORM.status == status.value)
        else:
            query = query.filter(ItemORM.status == ItemStatus.ACTIVE.value)
    elif status is not None:
        query = query.filter(ItemORM.status == status.value)

    if q is not None:
        pattern = f"%{q}%"
        query = query.filter(
            or_(
                ItemORM.name.ilike(pattern),
                ItemORM.description.ilike(pattern),
            )
        )

    if condition is not None:
        query = query.filter(ItemORM.condition == condition.value)

    if category_name is not None:
        query = query.join(ItemORM.category).filter(CategoryORM.name == category_name)

    # Pagination
    total = query.count()
    offset = (page - 1) * page_size
    db_items = query.offset(offset).limit(page_size).all()

    result: List[ItemRead] = []
    for db_item in db_items:
        item = item_to_read(db_item)
        set_item_links(item)
        result.append(item)

    return result


@app.get("/items/{item_id}", response_model=ItemRead)
def get_item(item_id: UUID, request: Request, response: Response, db: Session = Depends(get_db)):
    db_item = (
        db.query(ItemORM)
        .options(joinedload(ItemORM.category), joinedload(ItemORM.media))
        .filter(ItemORM.id == str(item_id))
        .first()
    )
    if db_item is None:
        raise HTTPException(status_code=404, detail="Item not found")

    item = item_to_read(db_item)
    set_item_links(item)
    etag = generate_item_etag(item)

    incoming_etag = request.headers.get("if-none-match")
    if incoming_etag == etag:
        return Response(status_code=304)

    response.headers["ETag"] = etag
    return item


@app.patch("/items/{item_id}", response_model=ItemRead)
def update_item(item_id: UUID, update: ItemUpdate, db: Session = Depends(get_db)):
    db_item = (
        db.query(ItemORM)
        .options(joinedload(ItemORM.category), joinedload(ItemORM.media))
        .filter(ItemORM.id == str(item_id))
        .first()
    )
    if db_item is None:
        raise HTTPException(status_code=404, detail="Item not found")

    data = update.model_dump(exclude_unset=True)

    if "name" in data and update.name is not None:
        db_item.name = update.name
    if "description" in data and update.description is not None:
        db_item.description = update.description
    if "status" in data and update.status is not None:
        db_item.status = update.status.value
    if "condition" in data and update.condition is not None:
        db_item.condition = update.condition.value
    if "price" in data and update.price is not None:
        db_item.price = update.price

    if "category" in data and update.category is not None:
        new_cat_id = str(update.category.id)
        db_cat = db.query(CategoryORM).filter(CategoryORM.id == new_cat_id).first()
        if db_cat is None:
            raise HTTPException(status_code=400, detail="New category does not exist")
        db_item.category_id = new_cat_id

    if "media" in data:
        new_media_objs: List[MediaORM] = []
        if update.media is not None:
            for m in update.media:
                db_media = db.query(MediaORM).filter(MediaORM.id == str(m.id)).first()
                if db_media is None:
                    raise HTTPException(
                        status_code=400,
                        detail=f"Media with id {m.id} does not exist",
                    )
                new_media_objs.append(db_media)
        db_item.media = new_media_objs

    db_item.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(db_item)

    db_item = (
        db.query(ItemORM)
        .options(joinedload(ItemORM.category), joinedload(ItemORM.media))
        .filter(ItemORM.id == db_item.id)
        .first()
    )

    item = item_to_read(db_item)
    set_item_links(item)
    return item


@app.delete("/items/{item_id}", status_code=204)
def delete_item(item_id: UUID, db: Session = Depends(get_db)):
    db_item = db.query(ItemORM).filter(ItemORM.id == str(item_id)).first()
    if db_item is None:
        raise HTTPException(status_code=404, detail="Item not found")

    db.delete(db_item)
    db.commit()
    return None


@app.post("/items/{item_id}/publish", response_model=Job, status_code=202)
def publish_item(
    item_id: UUID,
    background_tasks: BackgroundTasks,
    response: Response,
    db: Session = Depends(get_db),
):
    """
    Asynchronously publish an item.
    Returns 202 Accepted and a Job resource that can be polled for status.
    """
    db_item = db.query(ItemORM).filter(ItemORM.id == str(item_id)).first()
    if db_item is None:
        raise HTTPException(status_code=404, detail="Item not found")

    now = datetime.utcnow()
    job = Job(
        id=uuid4(),
        item_id=item_id,
        status=JobStatus.PENDING,
        created_at=now,
        updated_at=now,
        result_message="Publish job accepted.",
    )
    jobs[job.id] = job

    # Schedule background task
    background_tasks.add_task(run_publish_job, job.id)

    # Location header for polling job
    response.headers["Location"] = f"/jobs/{job.id}"
    return job


@app.get("/jobs/{job_id}", response_model=Job)
def get_job(job_id: UUID):
    """
    Poll the status of a background job.
    """
    job = jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


# -----------------------------------------------------------------------------
# Root endpoint
# -----------------------------------------------------------------------------
@app.get("/")
def root():
    return {"message": "Welcome to the Listing API. See /docs for OpenAPI UI."}

# -----------------------------------------------------------------------------
# Entrypoint (for local development)
# -----------------------------------------------------------------------------
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=True)
