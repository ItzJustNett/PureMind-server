"""
Saved Tests Router - Endpoints for managing user's saved generated tests
"""
from fastapi import APIRouter, HTTPException, Depends
from typing import List, Optional
from pydantic import BaseModel
import logging

from routers.auth import get_current_user
from database import SessionLocal
from database.models import GeneratedTest, Lesson

router = APIRouter(prefix="/api/saved-tests", tags=["saved-tests"])
logger = logging.getLogger(__name__)


class SavedTestResponse(BaseModel):
    id: int
    lesson_id: Optional[int]  # Database ID
    lesson_string_id: Optional[str]  # Lesson identifier for navigation
    lesson_title: Optional[str]
    title: str
    questions_count: int
    is_private: bool
    is_favorite: bool
    created_at: str

    class Config:
        from_attributes = True


class SavedTestDetail(BaseModel):
    id: int
    lesson_id: Optional[int]  # Database ID
    lesson_string_id: Optional[str]  # Lesson identifier for navigation
    lesson_title: Optional[str]
    title: str
    test_content: dict
    questions_count: int
    is_private: bool
    is_favorite: bool
    created_at: str

    class Config:
        from_attributes = True


@router.get("", response_model=List[SavedTestResponse])
async def get_saved_tests(user: dict = Depends(get_current_user)):
    """Get all saved tests for the current user"""
    try:
        db = SessionLocal()
        try:
            tests = db.query(GeneratedTest).filter(
                GeneratedTest.user_id == int(user["user_id"])
            ).order_by(GeneratedTest.created_at.desc()).all()

            results = []
            for test in tests:
                lesson_title = None
                lesson_string_id = None
                if test.lesson_id:
                    lesson = db.query(Lesson).filter(Lesson.id == test.lesson_id).first()
                    if lesson:
                        lesson_title = lesson.title
                        lesson_string_id = lesson.lesson_id  # The string ID for navigation

                results.append({
                    "id": test.id,
                    "lesson_id": test.lesson_id,
                    "lesson_string_id": lesson_string_id,
                    "lesson_title": lesson_title,
                    "title": test.title,
                    "questions_count": test.questions_count,
                    "is_private": test.is_private,
                    "is_favorite": test.is_favorite,
                    "created_at": test.created_at.isoformat()
                })

            return results
        finally:
            db.close()
    except Exception as e:
        logger.error(f"Error getting saved tests: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error getting saved tests: {str(e)}")


@router.get("/{test_id}", response_model=SavedTestDetail)
async def get_saved_test(test_id: int, user: dict = Depends(get_current_user)):
    """Get a specific saved test by ID"""
    try:
        db = SessionLocal()
        try:
            test = db.query(GeneratedTest).filter(
                GeneratedTest.id == test_id,
                GeneratedTest.user_id == int(user["user_id"])
            ).first()

            if not test:
                raise HTTPException(status_code=404, detail="Test not found")

            lesson_title = None
            lesson_string_id = None
            if test.lesson_id:
                lesson = db.query(Lesson).filter(Lesson.id == test.lesson_id).first()
                if lesson:
                    lesson_title = lesson.title
                    lesson_string_id = lesson.lesson_id  # The string ID for navigation

            return {
                "id": test.id,
                "lesson_id": test.lesson_id,
                "lesson_string_id": lesson_string_id,
                "lesson_title": lesson_title,
                "title": test.title,
                "test_content": test.test_content,
                "questions_count": test.questions_count,
                "is_private": test.is_private,
                "is_favorite": test.is_favorite,
                "created_at": test.created_at.isoformat()
            }
        finally:
            db.close()
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting saved test {test_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error getting saved test: {str(e)}")


@router.delete("/{test_id}")
async def delete_saved_test(test_id: int, user: dict = Depends(get_current_user)):
    """Delete a saved test"""
    try:
        db = SessionLocal()
        try:
            test = db.query(GeneratedTest).filter(
                GeneratedTest.id == test_id,
                GeneratedTest.user_id == int(user["user_id"])
            ).first()

            if not test:
                raise HTTPException(status_code=404, detail="Test not found")

            db.delete(test)
            db.commit()

            logger.info(f"Deleted saved test {test_id} for user {user['user_id']}")

            return {"success": True, "message": "Test deleted successfully"}
        finally:
            db.close()
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting saved test {test_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error deleting saved test: {str(e)}")


@router.put("/{test_id}/favorite")
async def toggle_favorite(test_id: int, user: dict = Depends(get_current_user)):
    """Toggle favorite status of a saved test"""
    try:
        db = SessionLocal()
        try:
            test = db.query(GeneratedTest).filter(
                GeneratedTest.id == test_id,
                GeneratedTest.user_id == int(user["user_id"])
            ).first()

            if not test:
                raise HTTPException(status_code=404, detail="Test not found")

            test.is_favorite = not test.is_favorite
            db.commit()

            logger.info(f"Toggled favorite for test {test_id} to {test.is_favorite}")

            return {
                "success": True,
                "is_favorite": test.is_favorite,
                "message": "Favorite updated successfully"
            }
        finally:
            db.close()
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error toggling favorite for test {test_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error toggling favorite: {str(e)}")
