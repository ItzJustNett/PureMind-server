"""Database package for Lessons API"""
from database.models import (
    Base,
    User,
    Profile,
    Course,
    Lesson,
    Exercise,
    CompletedExercise,
    GeneratedTest,
    StoreItem,
    Inventory,
    EquippedItem,
    AuthToken,
)
from database.connection import (
    engine,
    SessionLocal,
    get_db,
    get_async_db,
    init_db,
    check_db_connection,
    close_db,
)

__all__ = [
    # Models
    "Base",
    "User",
    "Profile",
    "Course",
    "Lesson",
    "Exercise",
    "CompletedExercise",
    "GeneratedTest",
    "StoreItem",
    "Inventory",
    "EquippedItem",
    "AuthToken",
    # Connection
    "engine",
    "SessionLocal",
    "get_db",
    "get_async_db",
    "init_db",
    "check_db_connection",
    "close_db",
]
