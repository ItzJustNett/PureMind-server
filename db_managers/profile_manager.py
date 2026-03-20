"""
Profile management - handles user profiles, gamification, streaks, and leaderboards.
Replaces profiles.py data logic.
"""
import logging
from typing import Optional, Dict, List, Tuple
from datetime import datetime, date
from sqlalchemy.orm import Session
from sqlalchemy import desc

from database.models import Profile, User, CompletedExercise, Exercise, StoreItem, Inventory, EquippedItem

logger = logging.getLogger(__name__)

# Valid configurations
VALID_CAT_IDS = [0, 1]
ILLNESSES = {
    0: "None",
    1: "Dyslexia",
    2: "Cerebral Palsy (Motor Impairment)",
    3: "Photosensitivity",
    4: "Epilepsy",
    5: "Color Blindness"
}
ILLNESSES_UA = {
    0: "Немає",
    1: "Дислексія",
    2: "ДЦП (порушення моторики)",
    3: "Світлочутливість",
    4: "Епілепсія",
    5: "Дальтонізм"
}


def create_or_update_profile(
    db: Session,
    user_id: int,
    name: str,
    about: str,
    cat_id: int,
    illness_id: int = 0,
    grade: int = None
) -> Tuple[Dict, int]:
    """Create or update a user profile"""
    try:
        # Validate cat_id
        if cat_id not in VALID_CAT_IDS:
            return {
                "error": f"Invalid cat_id. Must be one of {VALID_CAT_IDS}"
            }, 400

        # Validate illness_id
        if illness_id not in ILLNESSES:
            return {
                "error": f"Invalid illness_id. Must be one of {list(ILLNESSES.keys())}"
            }, 400

        # Validate grade if provided
        if grade is not None and (grade < 6 or grade > 11):
            return {
                "error": "Invalid grade. Must be between 6 and 11"
            }, 400

        # Check if user exists
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            return {"error": "User not found"}, 404

        # Check if profile exists
        profile = db.query(Profile).filter(Profile.user_id == user_id).first()
        is_new = profile is None

        if is_new:
            profile = Profile(user_id=user_id)

        # Update profile fields
        profile.name = name
        profile.about = about
        profile.cat_id = cat_id
        profile.illness_id = illness_id
        if grade is not None:
            profile.grade = grade

        if is_new:
            db.add(profile)

        db.commit()
        db.refresh(profile)

        status_code = 201 if is_new else 200
        logger.info(f"{'Created' if is_new else 'Updated'} profile for user ID: {user_id}")

        return profile_to_dict(profile), status_code
    except Exception as e:
        db.rollback()
        logger.error(f"Error in create_or_update_profile: {e}")
        return {"error": "Failed to create/update profile"}, 500


def get_profile(db: Session, user_id: int) -> Optional[Dict]:
    """Get a profile by user ID"""
    try:
        profile = db.query(Profile).filter(Profile.user_id == user_id).first()
        if profile:
            return profile_to_dict(profile)
        return None
    except Exception as e:
        logger.error(f"Error getting profile: {e}")
        return None


def delete_profile(db: Session, user_id: int) -> Tuple[Dict, int]:
    """Delete a user profile"""
    try:
        profile = db.query(Profile).filter(Profile.user_id == user_id).first()
        if not profile:
            return {"error": "Profile not found"}, 404

        db.delete(profile)
        db.commit()

        logger.info(f"Deleted profile for user ID: {user_id}")
        return {"message": f"Profile for user {user_id} deleted successfully"}, 200
    except Exception as e:
        db.rollback()
        logger.error(f"Error deleting profile: {e}")
        return {"error": "Failed to delete profile"}, 500


def get_leaderboard(db: Session, sort_by: str = 'xp', limit: int = 10) -> List[Dict]:
    """Get the leaderboard sorted by XP, meowcoins, or streak"""
    try:
        valid_sort_options = ['xp', 'meowcoins', 'streak']

        if sort_by not in valid_sort_options:
            logger.warning(f"Invalid sort option: {sort_by}. Using default 'xp'.")
            sort_by = 'xp'

        # Build query
        query = db.query(Profile)

        # Sort by selected criterion
        if sort_by == 'xp':
            query = query.order_by(desc(Profile.xp))
        elif sort_by == 'meowcoins':
            query = query.order_by(desc(Profile.meowcoins))
        elif sort_by == 'streak':
            query = query.order_by(desc(Profile.current_streak))

        # Get top results
        profiles = query.limit(limit).all()

        # Build leaderboard with ranks
        leaderboard = []
        for idx, profile in enumerate(profiles):
            leaderboard.append({
                "user_id": profile.user_id,
                "name": profile.name,
                "xp": profile.xp,
                "meowcoins": profile.meowcoins,
                "current_streak": profile.current_streak,
                "longest_streak": profile.longest_streak,
                "equipped_items": get_equipped_items_list(db, profile.user_id),
                "rank": idx + 1
            })

        return leaderboard
    except Exception as e:
        logger.error(f"Error getting leaderboard: {e}")
        return []


def check_exercise_answers(
    db: Session,
    user_id: int,
    exercise_id: int,
    correct_answers: int
) -> Tuple[Dict, int]:
    """Check exercise answers and award meowcoins and XP"""
    try:
        # Validate input
        if correct_answers < 0:
            return {"error": "correct_answers must be non-negative"}, 400

        # Get user and profile
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            return {"error": "User not found"}, 404

        profile = db.query(Profile).filter(Profile.user_id == user_id).first()
        if not profile:
            return {"error": "Profile not found"}, 404

        # Get exercise
        exercise = db.query(Exercise).filter(Exercise.id == exercise_id).first()
        if not exercise:
            return {"error": "Exercise not found"}, 404

        # Calculate rewards
        meowcoins_earned = min(correct_answers * 2, 20)  # Cap at 20
        xp_earned = min(correct_answers * 2, 20)  # Cap at 20

        # Update profile
        profile.xp += xp_earned
        profile.meowcoins += meowcoins_earned

        # Record completion
        completed = CompletedExercise(
            user_id=user_id,
            profile_id=profile.id,
            exercise_id=exercise_id,
            correct_answers=correct_answers,
            meowcoins_earned=meowcoins_earned,
            xp_earned=xp_earned
        )
        db.add(completed)

        # Update streak
        update_streak(db, user_id)

        db.commit()

        # Get updated streak info
        profile = db.query(Profile).filter(Profile.user_id == user_id).first()
        streak_info = {
            "current_streak": profile.current_streak,
            "longest_streak": profile.longest_streak,
            "last_activity_date": profile.last_activity_date.isoformat() if profile.last_activity_date else None
        }

        logger.info(f"Exercise {exercise_id} completed by user {user_id}, earned {xp_earned} XP")

        return {
            "success": True,
            "exercise_completed": True,
            "meowcoins_earned": meowcoins_earned,
            "xp_earned": xp_earned,
            "total_meowcoins": profile.meowcoins,
            "total_xp": profile.xp,
            "streak": streak_info
        }, 200
    except Exception as e:
        db.rollback()
        logger.error(f"Error checking exercise answers: {e}")
        return {"error": "Failed to check answers"}, 500


def update_streak(db: Session, user_id: int) -> Dict:
    """Update the user's learning streak"""
    try:
        profile = db.query(Profile).filter(Profile.user_id == user_id).first()
        if not profile:
            return {"error": "Profile not found"}

        today = date.today()

        # If this is the first activity ever
        if not profile.last_activity_date:
            profile.current_streak = 1
            profile.longest_streak = 1
            profile.last_activity_date = today
        else:
            last_date = profile.last_activity_date
            delta_days = (today - last_date).days

            # If already logged in today, no change
            if delta_days == 0:
                pass
            # If consecutive day, increment
            elif delta_days == 1:
                profile.current_streak += 1
                if profile.current_streak > profile.longest_streak:
                    profile.longest_streak = profile.current_streak
                profile.last_activity_date = today
            # If more than one day gap, reset
            else:
                profile.current_streak = 1
                profile.last_activity_date = today

        db.commit()

        return {
            "current_streak": profile.current_streak,
            "longest_streak": profile.longest_streak,
            "last_activity_date": profile.last_activity_date.isoformat() if profile.last_activity_date else None
        }
    except Exception as e:
        db.rollback()
        logger.error(f"Error updating streak: {e}")
        return {"error": "Failed to update streak"}


def profile_to_dict(profile: Profile) -> Dict:
    """Convert profile object to dictionary"""
    # Calculate level based on XP (every 1000 XP = 1 level)
    level = (profile.xp // 1000) + 1
    # Calculate XP needed for next level
    max_xp = level * 1000

    return {
        "user_id": profile.user_id,
        "name": profile.name,
        "about": profile.about,
        "cat_id": profile.cat_id,
        "illness_id": profile.illness_id,
        "illness_name": ILLNESSES.get(profile.illness_id, "Unknown"),
        "illness_name_ua": ILLNESSES_UA.get(profile.illness_id, "Невідомо"),
        "grade": profile.grade,
        "level": level,
        "xp": profile.xp,
        "max_xp": max_xp,
        "meowcoins": profile.meowcoins,
        "tests_completed": getattr(profile, 'tests_completed', 0),
        "lessons_completed": getattr(profile, 'lessons_completed', 0),
        "current_streak": profile.current_streak,
        "longest_streak": profile.longest_streak,
        "last_activity_date": profile.last_activity_date.isoformat() if profile.last_activity_date else None,
        "created_at": profile.created_at.isoformat()
    }


def get_equipped_items_list(db: Session, user_id: int) -> List[str]:
    """Get list of equipped item IDs for a user"""
    try:
        equipped = db.query(EquippedItem).filter(EquippedItem.user_id == user_id).all()
        return [item.store_item_id for item in equipped]
    except Exception as e:
        logger.error(f"Error getting equipped items: {e}")
        return []
