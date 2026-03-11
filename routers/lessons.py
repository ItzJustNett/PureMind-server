"""
Lessons API routes (FastAPI version with async optimization)
"""
from fastapi import APIRouter, HTTPException, Query
import json
import logging
import lessons_manager
import async_managers

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/lessons", tags=["lessons"])

@router.get("")
async def list_lessons(
    sort_by: str = Query(None, description="Sort by: title, xp, or recent"),
    grade: str = Query(None, description="Filter by grade"),
    subject: str = Query(None, description="Filter by subject (course)"),
    difficulty: str = Query(None, description="Filter by difficulty")
):
    """List all lessons with optional sorting and filtering"""
    try:
        simplified_list = await async_managers.list_lessons_async()

        # Filter by grade (from course_id ending like "-10")
        if grade:
            simplified_list = [
                lesson for lesson in simplified_list
                if lesson.get('course_id', '').endswith(f'-{grade}')
            ]

        # Filter by subject (course prefix like "biolohiya-i-ekolohiya")
        if subject:
            simplified_list = [
                lesson for lesson in simplified_list
                if lesson.get('course_id', '').startswith(subject)
            ]

        # Filter by difficulty
        if difficulty:
            simplified_list = [
                lesson for lesson in simplified_list
                if lesson.get('difficulty') == difficulty
            ]

        # Sort lessons
        if sort_by == "title":
            simplified_list.sort(key=lambda x: x.get('title', ''))
        elif sort_by == "xp":
            simplified_list.sort(key=lambda x: x.get('xp_reward', 0), reverse=True)
        # "recent" or None keeps original order

        return {"count": len(simplified_list), "lessons": simplified_list}
    except Exception as e:
        logger.error(f"Error listing lessons: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error listing lessons: {str(e)}")

@router.get("/search")
async def search_lessons(q: str = Query(..., min_length=1)):
    """Search lessons by query"""
    try:
        if not q:
            raise HTTPException(status_code=400, detail='Please provide a search query parameter "q"')

        results = await async_managers.search_lessons_async(q)
        return {"count": len(results), "results": results}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error searching lessons: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error searching lessons: {str(e)}")

@router.get("/{lesson_id}")
async def get_lesson(lesson_id: str):
    """Get a specific lesson by ID"""
    try:
        lesson = await async_managers.get_lesson_async(lesson_id)
        if not lesson:
            raise HTTPException(status_code=404, detail="Lesson not found")
        return lesson
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting lesson: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error getting lesson: {str(e)}")

@router.get("/{lesson_id}/youtube")
async def get_youtube_link(lesson_id: str):
    """Get YouTube link for a lesson"""
    try:
        result = await async_managers.get_youtube_link_async(lesson_id)
        if not result:
            raise HTTPException(status_code=404, detail="Lesson not found or no YouTube link available")
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting YouTube link: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error getting YouTube link: {str(e)}")

@router.get("/{lesson_id}/video-url")
async def get_video_url(lesson_id: str):
    """Get only the video URL for a lesson"""
    try:
        url = await async_managers.get_video_url_async(lesson_id)
        if not url:
            raise HTTPException(status_code=404, detail="Lesson not found or no YouTube link available")
        return {"url": url}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting video URL: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error getting video URL: {str(e)}")

@router.get("/{lesson_id}/test")
async def generate_lesson_test(lesson_id: str):
    """Generate a test for a specific lesson (async with httpx)"""
    try:
        result, status = await async_managers.generate_lesson_test_async(lesson_id)
        if status != 200:
            raise HTTPException(status_code=status, detail=result.get("error", "Error generating test"))
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generating test: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error generating test: {str(e)}")

@router.get("/{lesson_id}/conspect")
async def generate_conspect(lesson_id: str):
    """Generate a summary (conspect) for a lesson (async with httpx)"""
    try:
        result, status = await async_managers.generate_conspect_async(lesson_id)
        if status != 200:
            raise HTTPException(status_code=status, detail=result.get("error", "Error generating conspect"))
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generating conspect: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error generating conspect: {str(e)}")

@router.post("")
async def add_lesson(lesson_data: dict):
    """Add a new lesson"""
    try:
        # Validate required fields
        required_fields = ['id', 'title', 'course_id']
        for field in required_fields:
            if field not in lesson_data:
                raise HTTPException(status_code=400, detail=f"Missing required field: {field}")

        # Add lesson
        lessons_manager.lessons_data[lesson_data['id']] = lesson_data

        # Save to file
        with open('lessons.json', 'w', encoding='utf-8') as f:
            json.dump(lessons_manager.lessons_data, f, indent=2, ensure_ascii=False)

        return {"success": True, "message": "Lesson added successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error adding lesson: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error adding lesson: {str(e)}")

@router.get("/test-openrouter")
async def test_openrouter():
    """Test OpenRouter API connection (async)"""
    try:
        result, status = await async_managers.test_openrouter_connection_async()
        if status != 200:
            raise HTTPException(status_code=status, detail=result.get("error", "Error testing OpenRouter"))
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error testing OpenRouter: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error testing OpenRouter: {str(e)}")
