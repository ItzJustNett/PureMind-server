"""
User management - database operations for user accounts.
Replaces auth.py data logic.
"""
import hashlib
import bcrypt
import logging
from typing import Optional, Dict, Tuple
from sqlalchemy.orm import Session

from database.models import User

logger = logging.getLogger(__name__)


def hash_password(password: str) -> str:
    """Hash a password using bcrypt"""
    # Generate salt and hash password
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password.encode('utf-8'), salt)
    return hashed.decode('utf-8')


def verify_password(password: str, hashed: str) -> bool:
    """Verify a password against a bcrypt hash"""
    try:
        return bcrypt.checkpw(password.encode('utf-8'), hashed.encode('utf-8'))
    except Exception as e:
        logger.error(f"Error verifying password: {e}")
        return False


def _legacy_hash_password(password: str) -> str:
    """Legacy SHA-256 hash (for migration compatibility)"""
    return hashlib.sha256(password.encode()).hexdigest()


def create_user(db: Session, username: str, password: str, email: str = "") -> Tuple[Dict, int]:
    """Create a new user account"""
    try:
        # Check if username already exists
        existing_user = db.query(User).filter(User.username == username).first()
        if existing_user:
            return {"error": "Username already exists"}, 400

        # Create new user
        user = User(
            username=username,
            email=email,
            password_hash=hash_password(password)
        )
        db.add(user)
        db.commit()
        db.refresh(user)

        logger.info(f"Created new user: {username} (ID: {user.id})")
        return {
            "success": True,
            "user_id": user.id,
            "username": username
        }, 201
    except Exception as e:
        db.rollback()
        logger.error(f"Error creating user: {e}")
        return {"error": "Failed to create user"}, 500


def get_user_by_username(db: Session, username: str) -> Optional[Dict]:
    """Get user by username"""
    try:
        user = db.query(User).filter(User.username == username).first()
        if user:
            return {
                "id": user.id,
                "username": user.username,
                "email": user.email,
                "created_at": user.created_at.isoformat()
            }
        return None
    except Exception as e:
        logger.error(f"Error getting user by username: {e}")
        return None


def get_user_by_id(db: Session, user_id: int) -> Optional[Dict]:
    """Get user by ID"""
    try:
        user = db.query(User).filter(User.id == user_id).first()
        if user:
            return {
                "id": user.id,
                "username": user.username,
                "email": user.email,
                "created_at": user.created_at.isoformat()
            }
        return None
    except Exception as e:
        logger.error(f"Error getting user by ID: {e}")
        return None


def validate_password(db: Session, username: str, password: str) -> bool:
    """Validate user password (supports both bcrypt and legacy SHA-256)"""
    try:
        user = db.query(User).filter(User.username == username).first()
        if not user:
            return False

        # Try bcrypt first (new format starts with $2b$)
        if user.password_hash.startswith('$2b$'):
            is_valid = verify_password(password, user.password_hash)
            return is_valid

        # Fall back to legacy SHA-256 for old passwords
        if user.password_hash == _legacy_hash_password(password):
            # Auto-upgrade to bcrypt on successful login
            logger.info(f"Upgrading password hash for user {username} to bcrypt")
            user.password_hash = hash_password(password)
            db.commit()
            return True

        return False
    except Exception as e:
        logger.error(f"Error validating password: {e}")
        return False


def update_password(db: Session, user_id: int, new_password: str) -> Tuple[Dict, int]:
    """Update user password"""
    try:
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            return {"error": "User not found"}, 404

        user.password_hash = hash_password(new_password)
        db.commit()

        logger.info(f"Updated password for user ID: {user_id}")
        return {"success": True, "message": "Password updated"}, 200
    except Exception as e:
        db.rollback()
        logger.error(f"Error updating password: {e}")
        return {"error": "Failed to update password"}, 500
