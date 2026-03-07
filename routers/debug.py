"""
Debug API routes (FastAPI version)
"""
from fastapi import APIRouter, HTTPException
import logging
import lessons_manager
from database import SessionLocal
from db_managers import lesson_manager as db_lesson_manager

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/debug", tags=["debug"])

@router.get("/overview")
async def debug_overview():
    """Get overview of all lessons and courses"""
    try:
        db = SessionLocal()
        try:
            lessons_list = db_lesson_manager.list_lessons(db)
            lessons = {lesson['lesson_id']: lesson for lesson in lessons_list}
        finally:
            db.close()

        courses = {}
        for lesson_id, lesson in lessons.items():
            course_id = lesson.get('course_id')
            if course_id:
                if course_id not in courses:
                    courses[course_id] = []
                courses[course_id].append({
                    'id': lesson_id,
                    'title': lesson.get('title', 'Unknown')
                })

        return {
            "total_lessons": len(lessons),
            "total_courses": len(courses),
            "courses": courses
        }
    except Exception as e:
        logger.error(f"Error in debug overview: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")

@router.get("/lesson/{lesson_id}")
async def debug_lesson(lesson_id: str):
    """Get detailed debug info about a specific lesson"""
    try:
        db = SessionLocal()
        try:
            lesson = db_lesson_manager.get_lesson(db, lesson_id)
        finally:
            db.close()

        if not lesson:
            raise HTTPException(status_code=404, detail="Lesson not found")

        # Check for missing fields
        expected_fields = ['id', 'title', 'description', 'course_id', 'youtube_link', 'exercises']
        missing_fields = [field for field in expected_fields if field not in lesson]

        suggestions = []
        if 'youtube_link' not in lesson or not lesson.get('youtube_link'):
            suggestions.append("Missing or empty youtube_link - add video URL")
        if 'exercises' not in lesson or not lesson.get('exercises'):
            suggestions.append("No exercises defined for this lesson")
        if 'description' not in lesson or not lesson.get('description'):
            suggestions.append("Missing description")

        return {
            "lesson_id": lesson_id,
            "lesson": lesson,
            "missing_fields": missing_fields,
            "suggestions": suggestions
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in debug lesson: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")

@router.get("/course/{course_id}")
async def debug_course(course_id: str):
    """Get detailed debug info about a specific course"""
    try:
        db = SessionLocal()
        try:
            lessons_list = db_lesson_manager.get_course_lessons(db, course_id)
            lessons = {lesson['lesson_id']: lesson for lesson in lessons_list}
            course_lessons = [
                {'id': lesson['lesson_id'], 'title': lesson.get('title', 'Unknown')}
                for lesson in lessons_list
            ]
        finally:
            db.close()

        if not course_lessons:
            raise HTTPException(status_code=404, detail="Course not found")

        # Check coverage
        lessons_with_exercises = sum(
            1 for lesson in course_lessons
            if lessons.get(lesson['id'], {}).get('exercises')
        )

        lessons_with_youtube = sum(
            1 for lesson in course_lessons
            if lessons.get(lesson['id'], {}).get('youtube_link')
        )

        return {
            "course_id": course_id,
            "total_lessons": len(course_lessons),
            "lessons": course_lessons,
            "coverage": {
                "with_exercises": lessons_with_exercises,
                "with_youtube": lessons_with_youtube,
                "exercise_coverage_percent": (lessons_with_exercises / len(course_lessons) * 100) if course_lessons else 0,
                "youtube_coverage_percent": (lessons_with_youtube / len(course_lessons) * 100) if course_lessons else 0
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in debug course: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")
