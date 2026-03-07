"""
Authentication token management.
Replaces in-memory active_tokens storage.
"""
import secrets
import logging
from typing import Optional, Dict, Tuple
from datetime import datetime, timedelta
from sqlalchemy.orm import Session

from database.models import AuthToken, User

logger = logging.getLogger(__name__)


def create_token(db: Session, user_id: int) -> Tuple[Dict, int]:
    """Create a new authentication token"""
    try:
        # Verify user exists
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            return {"error": "User not found"}, 404

        # Generate token
        token = secrets.token_hex(32)

        # Create auth token (expires in 30 days)
        auth_token = AuthToken(
            token=token,
            user_id=user_id,
            expires_at=datetime.utcnow() + timedelta(days=30)
        )
        db.add(auth_token)
        db.commit()

        logger.info(f"Created auth token for user ID: {user_id}")
        return {
            "success": True,
            "token": token,
            "user_id": user_id
        }, 200
    except Exception as e:
        db.rollback()
        logger.error(f"Error creating token: {e}")
        return {"error": "Failed to create token"}, 500


def validate_token(db: Session, token: str) -> Optional[Dict]:
    """Validate a token and return user information"""
    try:
        auth_token = db.query(AuthToken).filter(AuthToken.token == token).first()

        if not auth_token:
            return None

        # Check if token is expired
        if auth_token.expires_at < datetime.utcnow():
            return None

        # Get user information
        user = db.query(User).filter(User.id == auth_token.user_id).first()
        if not user:
            return None

        return {
            "user_id": user.id,
            "username": user.username,
            "created_at": auth_token.created_at.isoformat()
        }
    except Exception as e:
        logger.error(f"Error validating token: {e}")
        return None


def delete_token(db: Session, token: str) -> Tuple[Dict, int]:
    """Invalidate a token"""
    try:
        auth_token = db.query(AuthToken).filter(AuthToken.token == token).first()

        if not auth_token:
            return {"error": "Token not found"}, 404

        db.delete(auth_token)
        db.commit()

        logger.info(f"Deleted auth token")
        return {"success": True, "message": "Logged out successfully"}, 200
    except Exception as e:
        db.rollback()
        logger.error(f"Error deleting token: {e}")
        return {"error": "Failed to logout"}, 500


def cleanup_expired_tokens(db: Session) -> int:
    """Delete expired tokens. Run periodically as a background task."""
    try:
        deleted_count = db.query(AuthToken).filter(
            AuthToken.expires_at < datetime.utcnow()
        ).delete()
        db.commit()

        if deleted_count > 0:
            logger.info(f"Cleaned up {deleted_count} expired tokens")

        return deleted_count
    except Exception as e:
        db.rollback()
        logger.error(f"Error cleaning up expired tokens: {e}")
        return 0
