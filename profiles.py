"""
Profiles module for the lessons API.
Manages user profiles including name, about section, cat selection, meowcoins, XP, and completed exercises.
Uses PostgreSQL database instead of JSON files.
"""
import logging
from typing import Dict, Optional, List, Tuple

from db_managers import profile_manager, store_manager
from database import SessionLocal

# Configure logging
logger = logging.getLogger(__name__)


def get_profile(user_id: int) -> Optional[Dict]:
    """Get a profile by user ID"""
    db = SessionLocal()
    try:
        return profile_manager.get_profile(db, user_id)
    finally:
        db.close()


def create_or_update_profile(
    user_id: int, name: str, about: str, cat_id: int, illness_id: int = 0
) -> Tuple[Dict, int]:
    """Create or update a user profile"""
    db = SessionLocal()
    try:
        return profile_manager.create_or_update_profile(db, user_id, name, about, cat_id, illness_id)
    finally:
        db.close()


def delete_profile(user_id: int) -> Tuple[Dict, int]:
    """Delete a user profile"""
    db = SessionLocal()
    try:
        return profile_manager.delete_profile(db, user_id)
    finally:
        db.close()


def list_profiles() -> List[Dict]:
    """List all profiles (for admin use)"""
    db = SessionLocal()
    try:
        profiles = db.query(db.query(db.query).from_statement("SELECT * FROM profiles")).all()
        return [profile_manager.profile_to_dict(p) for p in profiles]
    except Exception as e:
        logger.error(f"Error listing profiles: {e}")
        return []
    finally:
        db.close()


def get_leaderboard(sort_by: str = 'xp', limit: int = 10) -> List[Dict]:
    """Get the leaderboard sorted by XP or meowcoins"""
    db = SessionLocal()
    try:
        return profile_manager.get_leaderboard(db, sort_by, limit)
    finally:
        db.close()


def get_streak(user_id: int) -> Tuple[Dict, int]:
    """Get a user's streak information"""
    db = SessionLocal()
    try:
        profile = profile_manager.get_profile(db, user_id)
        if not profile:
            return {"error": "Profile not found"}, 404
        return {
            "current_streak": profile.get("current_streak", 0),
            "longest_streak": profile.get("longest_streak", 0),
            "last_activity_date": profile.get("last_activity_date")
        }, 200
    finally:
        db.close()


def check_exercise_answers(user_id: int, exercise_id: int, correct_answers: int) -> Tuple[Dict, int]:
    """Check exercise answers and award meowcoins and XP"""
    if not isinstance(correct_answers, int) or correct_answers < 0:
        return {"error": "correct_answers must be a non-negative integer"}, 400

    db = SessionLocal()
    try:
        return profile_manager.check_exercise_answers(db, user_id, exercise_id, correct_answers)
    finally:
        db.close()


def get_store_items() -> List[Dict]:
    """Get the list of items available in the store"""
    db = SessionLocal()
    try:
        return store_manager.get_store_items(db)
    finally:
        db.close()


def buy_item(user_id: int, item_id: str) -> Tuple[Dict, int]:
    """Buy an item from the store"""
    db = SessionLocal()
    try:
        return store_manager.buy_item(db, user_id, item_id)
    finally:
        db.close()


def equip_item(user_id: int, item_id: str) -> Tuple[Dict, int]:
    """Equip an item from the user's inventory"""
    db = SessionLocal()
    try:
        return store_manager.equip_item(db, user_id, item_id)
    finally:
        db.close()


def unequip_item(user_id: int, item_id: str) -> Tuple[Dict, int]:
    """Unequip an item"""
    db = SessionLocal()
    try:
        return store_manager.unequip_item(db, user_id, item_id)
    finally:
        db.close()
