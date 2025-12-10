## Listing Microservice Overview

This microservice exposes a simple catalog of **Categories**, **Items**, and **Media** for a cloud application.
It is implemented with FastAPI and currently uses **in-memory stores** (Python dicts) for data persistence.

The service is intended to satisfy the course requirements for:

* Query parameters on all collection resources
* Pagination on at least one collection resource
* ETag handling on at least one method/path
* Linked data with relative paths
* Proper `201 Created` and `202 Accepted` responses with `Location` headers
* Asynchronous operation with polling

---

## Data Models

All models are defined using Pydantic and follow a `Base / Create / Update / Read` pattern.

### Category

Represents a logical grouping of items (e.g., “Electronics”).

**Base model:** `CategoryBase`

* `name: str` – category name
* `description: str` – short description

**Read model:** `CategoryRead(CategoryBase)`

* `id: UUID` – server-generated ID
* `created_at: datetime` – creation time (UTC)
* `updated_at: datetime` – last update time (UTC)

Additional models:

* `CategoryCreate(CategoryBase)` – payload for `POST /categories`
* `CategoryUpdate` – partial update (all fields optional)

---

### Media

Represents media attached to an item (e.g., images or videos).

**Base model:** `MediaBase`

* `url: HttpUrl` – public URL of the media
* `type: MediaType` – `"image"` or `"video"`
* `alt_text: str | None` – optional accessibility/SEO text
* `is_primary: bool` – whether this is the primary media for the item

**Read model:** `MediaRead(MediaBase)`

* `id: UUID` – server-generated ID
* `created_at: datetime` – creation time (UTC)
* `updated_at: datetime` – last update time (UTC)

Additional models:

* `MediaCreate(MediaBase)` – payload for `POST /media`
* `MediaUpdate` – partial update (all fields optional)

---

### Item

Represents a listing in the catalog.

**Base model:** `ItemBase`

* `name: str` – item name
* `description: str` – item description
* `status: ItemStatus` – `"active" | "hidden" | "sold"`
* `condition: ItemCondition` – `"new" | "used" | "refurbished"`
* `price: Decimal` – item price
* `category: CategoryRead` – embedded category info for this item
* `media: List[MediaRead]` – embedded media list (images/videos)

**Read model:** `ItemRead(ItemBase)`

* `id: UUID` – server-generated ID
* `created_at: datetime` – creation time (UTC)
* `updated_at: datetime` – last update time (UTC)
* `links: ItemLinks | None` – hypermedia links with **relative paths**:

  * `self: str` – `/items/{id}`
  * `category: str | None` – `/categories/{category_id}`
  * `media: List[str]` – `/media/{media_id}`

Additional models:

* `ItemCreate(ItemBase)` – payload for `POST /items`
* `ItemUpdate` – partial update (all fields optional)

---

## API Endpoints (main.py)

All endpoints are defined directly in `main.py` on the shared `FastAPI` app.

### Categories

1. `@app.post("/categories", response_model=CategoryRead, status_code=201)`
   Create a category. Returns `201 Created` with `Location: /categories/{id}`.

2. `@app.get("/categories", response_model=List[CategoryRead])`
   List categories. Supports query parameters:

   * `name` – exact match on category name
   * `q` – substring search in `name` or `description`

3. `@app.get("/categories/{category_id}", response_model=CategoryRead)`
   Get a single category by ID.

4. `@app.patch("/categories/{category_id}", response_model=CategoryRead)`
   Partially update a category.

5. `@app.delete("/categories/{category_id}", status_code=204)`
   Delete a category (fails with `400` if any item still references it).

---

### Media

6. `@app.post("/media", response_model=MediaRead, status_code=201)`
   Create a media object. Returns `201 Created` with `Location: /media/{id}`.

7. `@app.get("/media", response_model=List[MediaRead])`
   List media. Supports query parameters:

   * `type` – `"image"` or `"video"`
   * `is_primary` – filter by primary flag

8. `@app.get("/media/{media_id}", response_model=MediaRead)`
   Get a single media object by ID.

9. `@app.patch("/media/{media_id}", response_model=MediaRead)`
   Partially update a media object.

10. `@app.delete("/media/{media_id}", status_code=204)`
    Delete a media object (fails with `400` if still referenced by an item).

---

### Items

11. `@app.post("/items", response_model=ItemRead, status_code=201)`
    Create an item. Returns `201 Created` with `Location: /items/{id}`.
    Response includes `links` with relative paths.

12. `@app.get("/items", response_model=List[ItemRead])`
    List items with filtering and pagination. Supports query parameters:

    * `q` – search in `name` or `description`
    * `condition` – `ItemCondition` filter
    * `category_name` – filter by category name
    * `status` – filter by status
    * `include_all` – if `False`, default to only active items
    * `page` – page number (1-based)
    * `page_size` – items per page

13. `@app.get("/items/{item_id}", response_model=ItemRead)`
    Get a single item by ID.

    * Returns an `ETag` header based on `id` and `updated_at`
    * Honors `If-None-Match` and returns `304 Not Modified` when appropriate
    * Includes hypermedia `links` with relative paths

14. `@app.patch("/items/{item_id}", response_model=ItemRead)`
    Partially update an item. Response includes updated `links`.

15. `@app.delete("/items/{item_id}", status_code=204)`
    Delete an item by ID.

---

### Async Jobs (Publish Item)

16. `@app.post("/items/{item_id}/publish", response_model=Job, status_code=202)`
    Start an **asynchronous** publish operation for an item.

    * Returns `202 Accepted`
    * Schedules background work using FastAPI `BackgroundTasks`
    * Sets `Location: /jobs/{job_id}` for polling

17. `@app.get("/jobs/{job_id}", response_model=Job)`
    Poll the status of a background job (`pending`, `in_progress`, `completed`, or `failed`).

---

### Root

18. `@app.get("/")`
    Simple health/welcome endpoint: returns a JSON welcome message.
