from __future__ import annotations

import os
import hashlib
import time
from datetime import datetime
from typing import Dict, List, Optional
from uuid import UUID, uuid4
from enum import Enum

from fastapi import FastAPI, HTTPException, Query, Response, Request, BackgroundTasks
from pydantic import BaseModel, Field

from models.category import CategoryCreate, CategoryRead, CategoryUpdate
from models.media import MediaCreate, MediaRead, MediaUpdate
from models.item import ItemCreate, ItemRead, ItemUpdate, ItemCondition, ItemStatus, ItemLinks

port = int(os.environ.get("FASTAPIPORT", 8000))

# -----------------------------------------------------------------------------
# In-memory "databases"
# -----------------------------------------------------------------------------
categories: Dict[UUID, CategoryRead] = {}
media_store: Dict[UUID, MediaRead] = {}
items: Dict[UUID, ItemRead] = {}
jobs: Dict[UUID, "Job"] = {}  # background jobs for async operations


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
    created_at: datetime = Field(..., description="When the job was created (UTC).")
    updated_at: datetime = Field(..., description="Last update time of the job (UTC).")
    result_message: Optional[str] = Field(
        None,
        description="Optional human-readable result or error message.",
    )

# -----------------------------------------------------------------------------
# Async job worker
# -----------------------------------------------------------------------------
def run_publish_job(job_id: UUID) -> None:
    """
    Background task: simulate publishing an item.
    Updates the item's status and the job's status.
    """
    job = jobs.get(job_id)
    if not job:
        return

    # Mark job as in progress
    job.status = JobStatus.IN_PROGRESS
    job.updated_at = datetime.utcnow()
    jobs[job_id] = job

    # Simulate some work
    time.sleep(2)

    item = items.get(job.item_id)
    if not item:
        job.status = JobStatus.FAILED
        job.result_message = "Item no longer exists."
        job.updated_at = datetime.utcnow()
        jobs[job_id] = job
        return

    # "Publish" the item: mark as ACTIVE and update timestamp
    item.status = ItemStatus.ACTIVE
    item.updated_at = datetime.utcnow()
    items[item.id] = item

    # Mark job as completed
    job.status = JobStatus.COMPLETED
    job.result_message = "Item published successfully."
    job.updated_at = datetime.utcnow()
    jobs[job_id] = job


# -----------------------------------------------------------------------------
# App
# -----------------------------------------------------------------------------
app = FastAPI(
    title="Listing API",
    description="Microservice for displaying Items with Categories and Media.",
    version="0.1.0",
)

# -----------------------------------------------------------------------------
# Category endpoints
# -----------------------------------------------------------------------------
@app.post("/categories", response_model=CategoryRead, status_code=201)
def create_category(payload: CategoryCreate, response: Response):
    cat = CategoryRead(**payload.model_dump())
    categories[cat.id] = cat
    response.headers["Location"] = f"/categories/{cat.id}"
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


@app.delete("/categories/{category_id}", status_code=204)
def delete_category(category_id: UUID):
    if category_id not in categories:
        raise HTTPException(status_code=404, detail="Category not found")
    # Prevent deleting a category that items are using
    in_use = any(it.category.id == category_id for it in items.values())
    if in_use:
        raise HTTPException(
            status_code=400,
            detail="Category is referenced by one or more items; delete or update those items first.",
        )
    del categories[category_id]
    return None

# -----------------------------------------------------------------------------
# Media endpoints
# -----------------------------------------------------------------------------
@app.post("/media", response_model=MediaRead, status_code=201)
def create_media(payload: MediaCreate, response: Response):
    m = MediaRead(**payload.model_dump())
    media_store[m.id] = m
    response.headers["Location"] = f"/media/{m.id}"
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


@app.delete("/media/{media_id}", status_code=204)
def delete_media(media_id: UUID):
    if media_id not in media_store:
        raise HTTPException(status_code=404, detail="Media not found")
    # Prevent deleting media that any item still references
    in_use = any(any(m.id == media_id for m in it.media) for it in items.values())
    if in_use:
        raise HTTPException(
            status_code=400,
            detail="Media is referenced by one or more items; delete or update those items first.",
        )
    del media_store[media_id]
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
def create_item(payload: ItemCreate, response: Response):
    item = ItemRead(**payload.model_dump())
    set_item_links(item)
    items[item.id] = item
    response.headers["Location"] = f"/items/{item.id}"
    return item


@app.get("/items", response_model=List[ItemRead])
def list_items(
    q: Optional[str] = Query(None, description="Search in name or description"),
    condition: Optional[ItemCondition] = Query(None, description="Filter by condition"),
    category_name: Optional[str] = Query(None, description="Filter by category name"),
    status: Optional[ItemStatus] = Query(None, description="Filter by status (default: only active items)"),
    include_all: bool = Query(False, description="Include all items regardless of status"),
    page: int = Query(1, ge=1, description="Page number (starting from 1)"),
    page_size: int = Query(10, ge=1, le=100, description="Number of items per page"),
):
    results = list(items.values())

    # Default: only show active items unless include_all is True or specific status is requested
    if not include_all:
        if status is not None:
            results = [i for i in results if i.status == status]
        else:
            # Default to showing only active items
            results = [i for i in results if i.status == ItemStatus.ACTIVE]

    if q is not None:
        ql = q.lower()
        results = [i for i in results if ql in i.name.lower() or ql in i.description.lower()]

    if condition is not None:
        results = [i for i in results if i.condition == condition]

    if category_name is not None:
        results = [i for i in results if i.category.name == category_name]

    # --- Pagination ---
    start = (page - 1) * page_size
    end = start + page_size
    paged_results = results[start:end]

    for item in paged_results:
        set_item_links(item)

    return paged_results


@app.get("/items/{item_id}", response_model=ItemRead)
def get_item(item_id: UUID, request: Request, response: Response):
    if item_id not in items:
        raise HTTPException(status_code=404, detail="Item not found")

    item = items[item_id]
    set_item_links(item)
    etag = generate_item_etag(item)

    incoming_etag = request.headers.get("if-none-match")
    if incoming_etag == etag:
        return Response(status_code=304)

    response.headers["ETag"] = etag
    return item


@app.patch("/items/{item_id}", response_model=ItemRead)
def update_item(item_id: UUID, update: ItemUpdate):
    if item_id not in items:
        raise HTTPException(status_code=404, detail="Item not found")
    stored = items[item_id].model_dump()
    stored.update(update.model_dump(exclude_unset=True))
    stored["updated_at"] = datetime.utcnow()
    items[item_id] = ItemRead(**stored)
    set_item_links(items[item_id])
    return items[item_id]


@app.delete("/items/{item_id}", status_code=204)
def delete_item(item_id: UUID):
    if item_id not in items:
        raise HTTPException(status_code=404, detail="Item not found")
    del items[item_id]
    return None


@app.post("/items/{item_id}/publish", response_model=Job, status_code=202)
def publish_item(
    item_id: UUID,
    background_tasks: BackgroundTasks,
    response: Response,
):
    """
    Asynchronously publish an item.

    Returns 202 Accepted and a Job resource that can be polled for status.
    """
    if item_id not in items:
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

    # Schedule the background task
    background_tasks.add_task(run_publish_job, job.id)

    # Location of the job resource for polling
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
# Root
# -----------------------------------------------------------------------------
@app.get("/")
def root():
    return {"message": "Welcome to the Listing API. See /docs for OpenAPI UI."}

# -----------------------------------------------------------------------------
# Entrypoint
# -----------------------------------------------------------------------------
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=True)
