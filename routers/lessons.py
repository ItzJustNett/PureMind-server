"""
Lessons API routes (FastAPI version with async optimization)
"""
from fastapi import APIRouter, HTTPException, Query, Depends
from pydantic import BaseModel
import json
import logging
import lessons_manager
import async_managers
from routers.auth import get_current_user

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/lessons", tags=["lessons"])

# Request models
class TestSubmission(BaseModel):
    score: int
    total_questions: int

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
async def generate_lesson_test(lesson_id: str, user: dict = Depends(get_current_user)):
    """Generate a test for a specific lesson (async with httpx) and save to user profile"""
    try:
        from database import SessionLocal
        from database.models import GeneratedTest, Lesson

        logger.info(f"Generating test for lesson: {lesson_id}")
        result, status = await async_managers.generate_lesson_test_async(lesson_id)
        logger.info(f"Test generation result: status={status}, has_error={'error' in result}")
        if status != 200:
            logger.error(f"Test generation failed: {result.get('error', 'Unknown error')}")
            raise HTTPException(status_code=status, detail=result.get("error", "Error generating test"))

        # Save the generated test to database
        db = SessionLocal()
        try:
            # Get lesson by lesson_id string
            lesson = db.query(Lesson).filter(Lesson.lesson_id == lesson_id).first()
            lesson_pk = lesson.id if lesson else None

            # Create new generated test record
            generated_test = GeneratedTest(
                user_id=int(user["user_id"]),
                lesson_id=lesson_pk,
                title=result.get("title", "Generated Test"),
                test_content=result,
                questions_count=len(result.get("questions", [])),
                is_private=True,
                is_favorite=False
            )

            db.add(generated_test)
            db.commit()
            db.refresh(generated_test)

            logger.info(f"Saved generated test {generated_test.id} for user {user['user_id']}")

            # Add the test ID to the response
            result["saved_test_id"] = generated_test.id

        finally:
            db.close()

        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generating test for {lesson_id}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error generating test: {str(e)}")

@router.get("/{lesson_id}/conspect")
async def generate_conspect(lesson_id: str, user: dict = Depends(get_current_user)):
    """Generate a summary (conspect) for a lesson and save it (async with httpx)"""
    try:
        from database import SessionLocal
        from database.models import Lesson

        result, status = await async_managers.generate_conspect_async(lesson_id)
        if status != 200:
            raise HTTPException(status_code=status, detail=result.get("error", "Error generating conspect"))

        # Save the generated summary to database
        db = SessionLocal()
        try:
            # Find the lesson by lesson_id string
            lesson = db.query(Lesson).filter(Lesson.lesson_id == lesson_id).first()
            if lesson:
                from database.models import SavedSummary

                # Create saved summary
                saved_summary = SavedSummary(
                    user_id=int(user["user_id"]),
                    lesson_id=lesson.id,
                    title=result.get("title", lesson.title),
                    summary=result.get("summary", ""),
                    key_points=result.get("key_points", [])
                )

                db.add(saved_summary)
                db.commit()
                db.refresh(saved_summary)

                logger.info(f"Saved conspect {saved_summary.id} for lesson {lesson_id}")

                # Add saved_id to result
                result["saved_id"] = saved_summary.id
        finally:
            db.close()

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

@router.post("/{lesson_id}/test/submit")
async def submit_test(lesson_id: str, data: TestSubmission, user: dict = Depends(get_current_user)):
    """Submit test results and award meowcoins"""
    try:
        from database import SessionLocal
        from database.models import Profile

        if data.score < 0 or data.total_questions <= 0:
            raise HTTPException(status_code=400, detail="Invalid score or total_questions")

        # Calculate rewards based on score
        # 100% = 20 meowcoins, 90% = 18, etc.
        percentage = (data.score / data.total_questions) * 100
        meowcoins_earned = int((percentage / 100) * 20)
        xp_earned = int((percentage / 100) * 20)

        # Award meowcoins and XP to user
        db = SessionLocal()
        try:
            profile = db.query(Profile).filter(Profile.user_id == int(user["user_id"])).first()

            if not profile:
                raise HTTPException(status_code=404, detail="Profile not found")

            profile.meowcoins += meowcoins_earned
            profile.xp += xp_earned
            profile.tests_completed += 1
            db.commit()

            # Update streak
            from db_managers import profile_manager
            profile_manager.update_streak(db, int(user["user_id"]))

            logger.info(f"Test {lesson_id} completed by user {user['user_id']}, earned {meowcoins_earned} meowcoins")

            return {
                "success": True,
                "score": data.score,
                "total_questions": data.total_questions,
                "percentage": round(percentage, 1),
                "meowcoins_earned": meowcoins_earned,
                "xp_earned": xp_earned,
                "total_meowcoins": profile.meowcoins,
                "total_xp": profile.xp
            }
        finally:
            db.close()
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error submitting test: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error submitting test: {str(e)}")

@router.post("/{lesson_id}/complete")
async def complete_lesson(lesson_id: str, user: dict = Depends(get_current_user)):
    """Mark a lesson as completed and award rewards"""
    try:
        from database import SessionLocal
        from database.models import Profile

        logger.info(f"=== COMPLETE LESSON START: lesson_id={lesson_id}, user_id={user['user_id']} ===")

        db = SessionLocal()
        try:
            # Get user profile
            profile = db.query(Profile).filter(Profile.user_id == int(user["user_id"])).first()
            if not profile:
                logger.error(f"Profile not found for user {user['user_id']}")
                raise HTTPException(status_code=404, detail="Profile not found")

            logger.info(f"Before update: lessons_completed={profile.lessons_completed}, xp={profile.xp}, meowcoins={profile.meowcoins}")

            # Award small XP reward for completing a lesson
            xp_earned = 10
            meowcoins_earned = 5

            old_lessons = profile.lessons_completed
            profile.lessons_completed += 1
            profile.xp += xp_earned
            profile.meowcoins += meowcoins_earned

            logger.info(f"After increment: lessons_completed={profile.lessons_completed} (was {old_lessons})")

            db.commit()
            db.refresh(profile)

            logger.info(f"After commit: lessons_completed={profile.lessons_completed}, xp={profile.xp}, meowcoins={profile.meowcoins}")

            # Update streak
            from db_managers import profile_manager
            profile_manager.update_streak(db, int(user["user_id"]))

            response_data = {
                "success": True,
                "lesson_id": lesson_id,
                "xp_earned": xp_earned,
                "meowcoins_earned": meowcoins_earned,
                "total_xp": profile.xp,
                "total_meowcoins": profile.meowcoins,
                "lessons_completed": profile.lessons_completed
            }

            logger.info(f"=== COMPLETE LESSON END: returning {response_data} ===")
            return response_data
        finally:
            db.close()
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error completing lesson: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error completing lesson: {str(e)}")

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
