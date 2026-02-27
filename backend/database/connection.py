"""
Database connection and session management.

This module provides database connection setup and session management.
"""

import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from typing import Generator

from .models import Base

# Get database URL from environment variable, default to SQLite for development
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./aura_vip.db")

# Create engine
engine = create_engine(
    DATABASE_URL,
    echo=False,  # Set to True for SQL query logging
    connect_args={"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
)

# Create session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def create_tables() -> None:
    """Create all database tables."""
    Base.metadata.create_all(bind=engine)


def drop_tables() -> None:
    """Drop all database tables (use with caution!)."""
    Base.metadata.drop_all(bind=engine)


def get_db() -> Generator[Session, None, None]:
    """
    Get database session for dependency injection.
    
    Usage in FastAPI:
        @app.get("/api/vips")
        def get_vips(db: Session = Depends(get_db)):
            ...
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
