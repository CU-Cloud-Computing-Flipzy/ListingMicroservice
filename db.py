from __future__ import annotations

import os
from datetime import datetime
from uuid import uuid4

from sqlalchemy import (
    Column,
    String,
    Text,
    DateTime,
    Boolean,
    ForeignKey,
    Table,
    create_engine,
)
from sqlalchemy.types import Numeric
from sqlalchemy.orm import declarative_base, relationship, sessionmaker, Session

# ---------------------------------------------------------------------------
# Cloud SQL connection configuration (MySQL)
# ---------------------------------------------------------------------------

DB_USER = os.getenv("DB_USER", "listing-service-user")
DB_PASS = os.getenv("DB_PASS", "")
DB_NAME = os.getenv("DB_NAME", "listing-service")
DB_HOST = os.getenv("DB_HOST")

if DB_HOST:
    # On Cloud Run, connect to Cloud SQL via Unix socket
    SQLALCHEMY_DATABASE_URL = (
        f"mysql+pymysql://{DB_USER}:{DB_PASS}@/{DB_NAME}"
        f"?unix_socket={DB_HOST}"
    )
else:
    # For local development, use TCP (modify as needed)
    DB_PORT = os.getenv("DB_PORT", "3306")
    DB_HOSTNAME = os.getenv("DB_HOSTNAME", "127.0.0.1")
    SQLALCHEMY_DATABASE_URL = (
        f"mysql+pymysql://{DB_USER}:{DB_PASS}@{DB_HOSTNAME}:{DB_PORT}/{DB_NAME}"
    )

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    pool_pre_ping=True,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# ---------------------------------------------------------------------------
# ORM Models
# ---------------------------------------------------------------------------


class CategoryORM(Base):
    __tablename__ = "categories"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=False)

    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    items = relationship("ItemORM", back_populates="category")


class MediaORM(Base):
    __tablename__ = "media"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    url = Column(String(2048), nullable=False)
    type = Column(String(16), nullable=False)  # "image" / "video"
    alt_text = Column(Text, nullable=True)
    is_primary = Column(Boolean, nullable=False, default=False)

    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    items = relationship("ItemORM", secondary="item_media", back_populates="media")


item_media = Table(
    "item_media",
    Base.metadata,
    Column("item_id", String(36), ForeignKey("items.id"), primary_key=True),
    Column("media_id", String(36), ForeignKey("media.id"), primary_key=True),
)


class ItemORM(Base):
    __tablename__ = "items"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    name = Column(String(200), nullable=False)
    description = Column(Text, nullable=False)
    status = Column(String(32), nullable=False)      # "active" / "hidden" / "sold"
    condition = Column(String(32), nullable=False)   # "new" / "used" / "refurbished"
    price = Column(Numeric(10, 2), nullable=False)   # mapped to Pydantic's Decimal

    category_id = Column(String(36), ForeignKey("categories.id"), nullable=False)

    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    category = relationship("CategoryORM", back_populates="items")
    media = relationship("MediaORM", secondary=item_media, back_populates="items")


# -----------------------------------------------------------------------------
# FastAPI Dependencies & Initialization
# -----------------------------------------------------------------------------


def get_db() -> Session:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    """Create all tables at application startup (if they do not already exist)."""
    Base.metadata.create_all(bind=engine)