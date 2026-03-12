"""
Profiles and Gamification API routes (FastAPI version)
"""
from fastapi import APIRouter, HTTPException, Header, Depends
from pydantic import BaseModel
from typing import Optional
import logging
import profiles
import async_managers
from routers.auth import get_current_user

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["profiles", "gamification"])

# Request models
class ProfileRequest(BaseModel):
    name: str
    about: Optional[str] = None
    cat_id: Optional[int] = 0
    illness_id: Optional[int] = 0
    grade: Optional[int] = None

class SetupRequest(BaseModel):
    grade: int  # User's grade/class (6-11)
    cat_id: int  # User's cat selection (0, 1, 2)

class ExerciseCheckRequest(BaseModel):
    correct_answers: int

class BuyItemRequest(BaseModel):
    item_id: str

class EquipItemRequest(BaseModel):
    item_id: str

class UpdateEmailRequest(BaseModel):
    email: str

class UpdateUsernameRequest(BaseModel):
    username: str

class UpdatePasswordRequest(BaseModel):
    current_password: str
    new_password: str

# Endpoints
@router.get("/profiles/me")
async def get_my_profile(user: dict = Depends(get_current_user)):
    """Get current user's profile"""
    try:
        profile = profiles.get_profile(user["user_id"])
        if not profile:
            raise HTTPException(status_code=404, detail="Profile not found")
        return profile
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting profile: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error getting profile: {str(e)}")

@router.get("/profiles/{user_id}")
async def get_profile(user_id: str):
    """Get a specific user's profile"""
    try:
        profile = profiles.get_profile(user_id)
        if not profile:
            raise HTTPException(status_code=404, detail="Profile not found")
        return profile
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting profile: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error getting profile: {str(e)}")

@router.post("/profiles/setup")
async def complete_setup(data: SetupRequest, user: dict = Depends(get_current_user)):
    """Complete initial setup by setting user's grade and cat"""
    try:
        if data.grade < 6 or data.grade > 11:
            raise HTTPException(status_code=400, detail="Grade must be between 6 and 11")

        if data.cat_id not in [0, 1, 2]:
            raise HTTPException(status_code=400, detail="Cat ID must be 0, 1, or 2")

        # Get user info for default name
        user_info = await async_managers.get_user_by_id_async(user["user_id"])
        default_name = user_info.get("username", "User") if user_info else "User"

        # Create profile with defaults for name and about
        from database import SessionLocal
        from db_managers import profile_manager
        db = SessionLocal()
        try:
            result, status = profile_manager.create_or_update_profile(
                db,
                int(user["user_id"]),
                default_name,
                "",
                data.cat_id,
                0,
                data.grade
            )
        finally:
            db.close()

        if status not in [200, 201]:
            raise HTTPException(status_code=status, detail=result.get("error", "Failed to complete setup"))

        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error completing setup: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error completing setup: {str(e)}")

@router.post("/profiles")
async def create_or_update_profile(data: ProfileRequest, user: dict = Depends(get_current_user)):
    """Create or update current user's profile"""
    try:
        from database import SessionLocal
        from db_managers import profile_manager

        db = SessionLocal()
        try:
            result, status = profile_manager.create_or_update_profile(
                db,
                int(user["user_id"]),
                data.name,
                data.about or "",
                data.cat_id or 0,
                data.illness_id or 0
            )
        finally:
            db.close()

        if status not in [200, 201]:
            raise HTTPException(status_code=status, detail=result.get("error", "Failed to save profile"))

        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating profile: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error updating profile: {str(e)}")

@router.put("/profiles")
async def update_profile(data: ProfileRequest, user: dict = Depends(get_current_user)):
    """Update current user's profile (PUT alternative)"""
    try:
        from database import SessionLocal
        from db_managers import profile_manager

        db = SessionLocal()
        try:
            result, status = profile_manager.create_or_update_profile(
                db,
                int(user["user_id"]),
                data.name,
                data.about or "",
                data.cat_id or 0,
                data.illness_id or 0
            )
        finally:
            db.close()

        if status not in [200, 201]:
            raise HTTPException(status_code=status, detail=result.get("error", "Failed to save profile"))

        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating profile: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error updating profile: {str(e)}")

@router.delete("/profiles")
async def delete_profile(user: dict = Depends(get_current_user)):
    """Delete current user's profile"""
    try:
        result, status = profiles.delete_profile(user["user_id"])

        if status != 200:
            raise HTTPException(status_code=status, detail=result.get("error", "Failed to delete profile"))

        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting profile: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error deleting profile: {str(e)}")

@router.get("/profiles/all")
async def list_profiles():
    """List all profiles (admin only)"""
    try:
        result = profiles.list_profiles()
        return {"profiles": result, "count": len(result)}
    except Exception as e:
        logger.error(f"Error listing profiles: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error listing profiles: {str(e)}")

# Streak endpoints
@router.get("/streaks")
async def get_streak(user: dict = Depends(get_current_user)):
    """Get current user's streak info"""
    try:
        result = profiles.get_streak(user["user_id"])
        if not result:
            raise HTTPException(status_code=404, detail="Streak not found")
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting streak: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error getting streak: {str(e)}")

@router.post("/streaks/update")
async def update_streak(user: dict = Depends(get_current_user)):
    """Manually update user's streak"""
    try:
        result, status = profiles.update_streak(user["user_id"])

        if status != 200:
            raise HTTPException(status_code=status, detail=result.get("error", "Failed to update streak"))

        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating streak: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error updating streak: {str(e)}")

# Leaderboard endpoint
@router.get("/leaderboard")
async def get_leaderboard(sort_by: str = "xp"):
    """Get the leaderboard"""
    try:
        result = profiles.get_leaderboard(sort_by)
        return {"leaderboard": result, "count": len(result)}
    except Exception as e:
        logger.error(f"Error getting leaderboard: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error getting leaderboard: {str(e)}")

# Exercise endpoint
@router.post("/exercises/{exercise_id}/check")
async def check_exercise_answers(exercise_id: str, data: ExerciseCheckRequest, user: dict = Depends(get_current_user)):
    """Submit exercise answers and award rewards"""
    try:
        result, status = profiles.check_exercise_answers(user["user_id"], exercise_id, data.correct_answers)

        if status != 200:
            raise HTTPException(status_code=status, detail=result.get("error", "Failed to check exercise"))

        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error checking exercise: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error checking exercise: {str(e)}")

# Store endpoints
@router.get("/store")
async def get_store_items():
    """Get list of items available in the store"""
    try:
        items = profiles.get_store_items()
        return {"items": items, "count": len(items)}
    except Exception as e:
        logger.error(f"Error getting store items: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error getting store items: {str(e)}")

@router.post("/store/buy")
async def buy_item(data: BuyItemRequest, user: dict = Depends(get_current_user)):
    """Buy an item from the store"""
    try:
        result, status = profiles.buy_item(user["user_id"], data.item_id)

        if status != 200:
            raise HTTPException(status_code=status, detail=result.get("error", "Failed to buy item"))

        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error buying item: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error buying item: {str(e)}")

# Inventory endpoints
@router.post("/inventory/equip")
async def equip_item(data: EquipItemRequest, user: dict = Depends(get_current_user)):
    """Equip an item from inventory"""
    try:
        result, status = profiles.equip_item(user["user_id"], data.item_id)

        if status != 200:
            raise HTTPException(status_code=status, detail=result.get("error", "Failed to equip item"))

        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error equipping item: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error equipping item: {str(e)}")

@router.post("/inventory/unequip")
async def unequip_item(data: EquipItemRequest, user: dict = Depends(get_current_user)):
    """Unequip an item"""
    try:
        result, status = profiles.unequip_item(user["user_id"], data.item_id)

        if status != 200:
            raise HTTPException(status_code=status, detail=result.get("error", "Failed to unequip item"))

        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error unequipping item: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error unequipping item: {str(e)}")

# Account Settings endpoints
@router.put("/account/email")
async def update_email(data: UpdateEmailRequest, user: dict = Depends(get_current_user)):
    """Update user's email"""
    try:
        from database import SessionLocal
        from database.models import User

        db = SessionLocal()
        try:
            db_user = db.query(User).filter(User.id == int(user["user_id"])).first()
            if not db_user:
                raise HTTPException(status_code=404, detail="User not found")

            db_user.email = data.email
            db.commit()

            return {"success": True, "message": "Email updated successfully"}
        finally:
            db.close()
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating email: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error updating email: {str(e)}")

@router.put("/account/username")
async def update_username(data: UpdateUsernameRequest, user: dict = Depends(get_current_user)):
    """Update user's username"""
    try:
        from database import SessionLocal
        from database.models import User

        db = SessionLocal()
        try:
            # Check if username is taken
            existing = db.query(User).filter(User.username == data.username).first()
            if existing and existing.id != int(user["user_id"]):
                raise HTTPException(status_code=400, detail="Username already taken")

            db_user = db.query(User).filter(User.id == int(user["user_id"])).first()
            if not db_user:
                raise HTTPException(status_code=404, detail="User not found")

            db_user.username = data.username
            db.commit()

            return {"success": True, "message": "Username updated successfully"}
        finally:
            db.close()
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating username: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error updating username: {str(e)}")

@router.put("/account/password")
async def update_password(data: UpdatePasswordRequest, user: dict = Depends(get_current_user)):
    """Update user's password"""
    try:
        import auth
        from database import SessionLocal
        from database.models import User

        db = SessionLocal()
        try:
            db_user = db.query(User).filter(User.id == int(user["user_id"])).first()
            if not db_user:
                raise HTTPException(status_code=404, detail="User not found")

            # Verify current password
            if not auth.verify_password(data.current_password, db_user.password_hash):
                raise HTTPException(status_code=400, detail="Current password is incorrect")

            # Update to new password
            db_user.password_hash = auth.hash_password(data.new_password)
            db.commit()

            return {"success": True, "message": "Password updated successfully"}
        finally:
            db.close()
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating password: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error updating password: {str(e)}")
