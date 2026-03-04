"""
Profiles and Gamification API routes (FastAPI version)
"""
from fastapi import APIRouter, HTTPException, Header, Depends
from pydantic import BaseModel, Optional
import logging
import profiles
from routers.auth import get_current_user

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["profiles", "gamification"])

# Request models
class ProfileRequest(BaseModel):
    name: str
    about: Optional[str] = None
    cat_id: Optional[int] = 0
    illness_id: Optional[int] = 0

class ExerciseCheckRequest(BaseModel):
    correct_answers: int

class BuyItemRequest(BaseModel):
    item_id: str

class EquipItemRequest(BaseModel):
    item_id: str

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

@router.post("/profiles")
async def create_or_update_profile(data: ProfileRequest, user: dict = Depends(get_current_user)):
    """Create or update current user's profile"""
    try:
        profile_data = data.dict()
        result, status = profiles.create_or_update_profile(user["user_id"], profile_data)

        if status != 200:
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
        profile_data = data.dict()
        result, status = profiles.create_or_update_profile(user["user_id"], profile_data)

        if status != 200:
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
