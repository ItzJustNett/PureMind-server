"""
Saved Summaries Router - Endpoints for managing user's saved AI-generated summaries
"""
from fastapi import APIRouter, HTTPException, Depends
from typing import List, Optional
from pydantic import BaseModel
import logging

from routers.auth import get_current_user
from database import SessionLocal
from database.models import SavedSummary, Lesson

router = APIRouter(prefix="/api/saved-summaries", tags=["saved-summaries"])
logger = logging.getLogger(__name__)


class SavedSummaryResponse(BaseModel):
    id: int
    lesson_id: Optional[int]
    lesson_title: Optional[str]
    title: str
    summary: str
    key_points: Optional[List[str]]
    is_favorite: bool
    created_at: str

    class Config:
        from_attributes = True


class CreateSummaryRequest(BaseModel):
    lesson_id: int
    title: str
    summary: str
    key_points: Optional[List[str]] = None


@router.get("", response_model=List[SavedSummaryResponse])
async def get_saved_summaries(user: dict = Depends(get_current_user)):
    """Get all saved summaries for the current user"""
    try:
        db = SessionLocal()
        try:
            summaries = db.query(SavedSummary).filter(
                SavedSummary.user_id == int(user["user_id"])
            ).order_by(SavedSummary.created_at.desc()).all()

            results = []
            for summary in summaries:
                lesson_title = None
                if summary.lesson_id:
                    lesson = db.query(Lesson).filter(Lesson.id == summary.lesson_id).first()
                    if lesson:
                        lesson_title = lesson.title

                results.append({
                    "id": summary.id,
                    "lesson_id": summary.lesson_id,
                    "lesson_title": lesson_title,
                    "title": summary.title,
                    "summary": summary.summary,
                    "key_points": summary.key_points,
                    "is_favorite": summary.is_favorite,
                    "created_at": summary.created_at.isoformat()
                })

            return results
        finally:
            db.close()
    except Exception as e:
        logger.error(f"Error getting saved summaries: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error getting saved summaries: {str(e)}")


@router.get("/{summary_id}", response_model=SavedSummaryResponse)
async def get_saved_summary(summary_id: int, user: dict = Depends(get_current_user)):
    """Get a specific saved summary by ID"""
    try:
        db = SessionLocal()
        try:
            summary = db.query(SavedSummary).filter(
                SavedSummary.id == summary_id,
                SavedSummary.user_id == int(user["user_id"])
            ).first()

            if not summary:
                raise HTTPException(status_code=404, detail="Summary not found")

            lesson_title = None
            if summary.lesson_id:
                lesson = db.query(Lesson).filter(Lesson.id == summary.lesson_id).first()
                if lesson:
                    lesson_title = lesson.title

            return {
                "id": summary.id,
                "lesson_id": summary.lesson_id,
                "lesson_title": lesson_title,
                "title": summary.title,
                "summary": summary.summary,
                "key_points": summary.key_points,
                "is_favorite": summary.is_favorite,
                "created_at": summary.created_at.isoformat()
            }
        finally:
            db.close()
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting saved summary {summary_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error getting saved summary: {str(e)}")


@router.post("", response_model=SavedSummaryResponse)
async def create_saved_summary(
    request: CreateSummaryRequest,
    user: dict = Depends(get_current_user)
):
    """Create a new saved summary"""
    try:
        db = SessionLocal()
        try:
            # Verify lesson exists
            lesson = db.query(Lesson).filter(Lesson.id == request.lesson_id).first()
            if not lesson:
                raise HTTPException(status_code=404, detail="Lesson not found")

            # Create new summary
            summary = SavedSummary(
                user_id=int(user["user_id"]),
                lesson_id=request.lesson_id,
                title=request.title,
                summary=request.summary,
                key_points=request.key_points or []
            )

            db.add(summary)
            db.commit()
            db.refresh(summary)

            logger.info(f"Created saved summary {summary.id} for user {user['user_id']}")

            return {
                "id": summary.id,
                "lesson_id": summary.lesson_id,
                "lesson_title": lesson.title,
                "title": summary.title,
                "summary": summary.summary,
                "key_points": summary.key_points,
                "is_favorite": summary.is_favorite,
                "created_at": summary.created_at.isoformat()
            }
        finally:
            db.close()
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating saved summary: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error creating saved summary: {str(e)}")


@router.delete("/{summary_id}")
async def delete_saved_summary(summary_id: int, user: dict = Depends(get_current_user)):
    """Delete a saved summary"""
    try:
        db = SessionLocal()
        try:
            summary = db.query(SavedSummary).filter(
                SavedSummary.id == summary_id,
                SavedSummary.user_id == int(user["user_id"])
            ).first()

            if not summary:
                raise HTTPException(status_code=404, detail="Summary not found")

            db.delete(summary)
            db.commit()

            logger.info(f"Deleted saved summary {summary_id} for user {user['user_id']}")

            return {"success": True, "message": "Summary deleted successfully"}
        finally:
            db.close()
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting saved summary {summary_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error deleting saved summary: {str(e)}")


@router.put("/{summary_id}/favorite")
async def toggle_favorite(summary_id: int, user: dict = Depends(get_current_user)):
    """Toggle favorite status of a saved summary"""
    try:
        db = SessionLocal()
        try:
            summary = db.query(SavedSummary).filter(
                SavedSummary.id == summary_id,
                SavedSummary.user_id == int(user["user_id"])
            ).first()

            if not summary:
                raise HTTPException(status_code=404, detail="Summary not found")

            summary.is_favorite = not summary.is_favorite
            db.commit()

            logger.info(f"Toggled favorite for summary {summary_id} to {summary.is_favorite}")

            return {
                "success": True,
                "is_favorite": summary.is_favorite,
                "message": "Favorite updated successfully"
            }
        finally:
            db.close()
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error toggling favorite for summary {summary_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error toggling favorite: {str(e)}")
