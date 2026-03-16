"""
Database connection and session management.
Provides SQLAlchemy session factory and FastAPI dependency injection.
"""
import os
import logging
from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import QueuePool
from fastapi import Depends
import asyncio
from functools import lru_cache

logger = logging.getLogger(__name__)

# Get database URL from environment
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://lessons_user:password@localhost:5432/lessons_db")

# Create engine with connection pooling
engine = create_engine(
    DATABASE_URL,
    poolclass=QueuePool,
    pool_size=int(os.getenv("DB_POOL_SIZE", 10)),
    max_overflow=int(os.getenv("DB_MAX_OVERFLOW", 20)),
    pool_pre_ping=True,  # Verify connections before using them
    pool_recycle=3600,  # Recycle connections every hour
    echo=False,  # Set to True for SQL logging
)

# Create session factory
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
    expire_on_commit=False,
)


def get_db() -> Session:
    """
    Get a database session for dependency injection in FastAPI.
    Usage: db: Session = Depends(get_db)
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


async def get_async_db() -> Session:
    """
    Async wrapper for get_db dependency.
    Usage: db: Session = Depends(get_async_db)
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """
    Initialize database - create all tables.
    Call this once during application startup.
    """
    try:
        from database.models import Base
        Base.metadata.create_all(bind=engine)
        logger.info("Database tables initialized successfully")
        return True
    except Exception as e:
        logger.error(f"Error initializing database: {e}")
        return False


def check_db_connection() -> bool:
    """
    Check if database connection is working.
    """
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        logger.info("Database connection successful")
        return True
    except Exception as e:
        logger.error(f"Database connection failed: {e}")
        return False


def close_db():
    """
    Close all database connections.
    Call this during application shutdown.
    """
    engine.dispose()
    logger.info("Database connections closed")
