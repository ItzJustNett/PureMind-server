"""
Authentication module for the lessons API.
Handles user registration, login, and token management.
Uses PostgreSQL database instead of JSON files.
"""
import logging
from typing import Dict, Optional, Tuple
from sqlalchemy.orm import Session

from db_managers import user_manager, auth_manager
from database import SessionLocal

# Configure logging
logger = logging.getLogger(__name__)


def register_user(username: str, password: str, email: str = "") -> Tuple[Dict, int]:
    """Register a new user"""
    db = SessionLocal()
    try:
        return user_manager.create_user(db, username, password, email)
    finally:
        db.close()


def login_user(username: str, password: str) -> Tuple[Dict, int]:
    """Login a user and generate a token"""
    db = SessionLocal()
    try:
        # Validate password
        if not user_manager.validate_password(db, username, password):
            return {"error": "Invalid username or password"}, 401

        # Get user
        user_data = user_manager.get_user_by_username(db, username)
        if not user_data:
            return {"error": "Invalid username or password"}, 401

        # Create token
        return auth_manager.create_token(db, user_data["id"])
    finally:
        db.close()


def logout_user(token: str) -> Tuple[Dict, int]:
    """Logout a user by invalidating their token"""
    db = SessionLocal()
    try:
        return auth_manager.delete_token(db, token)
    finally:
        db.close()


def validate_token(token: str) -> Optional[Dict]:
    """Validate a token and return user information"""
    db = SessionLocal()
    try:
        return auth_manager.validate_token(db, token)
    finally:
        db.close()


def get_user_by_id(user_id: int) -> Optional[Dict]:
    """Get user by ID"""
    db = SessionLocal()
    try:
        return user_manager.get_user_by_id(db, user_id)
    finally:
        db.close()