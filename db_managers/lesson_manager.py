"""
Lesson management - handles lesson queries and exercises.
Replaces lessons_manager.py data logic.
"""
import logging
from typing import Optional, Dict, List, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import or_

from database.models import Lesson, Exercise, Course

logger = logging.getLogger(__name__)


def get_lesson(db: Session, lesson_id: str) -> Optional[Dict]:
    """Get a lesson by lesson_id"""
    try:
        lesson = db.query(Lesson).filter(Lesson.lesson_id == lesson_id).first()
        if lesson:
            return lesson_to_dict(lesson, db)
        return None
    except Exception as e:
        logger.error(f"Error getting lesson: {e}")
        return None


def list_lessons(db: Session) -> List[Dict]:
    """List all lessons"""
    try:
        lessons = db.query(Lesson).all()
        return [lesson_to_dict(lesson, db) for lesson in lessons]
    except Exception as e:
        logger.error(f"Error listing lessons: {e}")
        return []


def search_lessons(db: Session, query: str) -> List[Dict]:
    """Search lessons by title or ID"""
    try:
        if not query:
            return []

        search_term = f"%{query.lower()}%"
        lessons = db.query(Lesson).filter(
            or_(
                Lesson.lesson_id.ilike(search_term),
                Lesson.title.ilike(search_term)
            )
        ).all()

        return [lesson_to_dict(lesson, db) for lesson in lessons]
    except Exception as e:
        logger.error(f"Error searching lessons: {e}")
        return []


def get_course_lessons(db: Session, course_id: str) -> List[Dict]:
    """Get all lessons for a specific course"""
    try:
        course = db.query(Course).filter(Course.course_id == course_id).first()
        if not course:
            return []

        lessons = db.query(Lesson).filter(Lesson.course_id == course.id).all()
        return [lesson_to_dict(lesson, db) for lesson in lessons]
    except Exception as e:
        logger.error(f"Error getting course lessons: {e}")
        return []


def create_lesson(
    db: Session,
    lesson_id: str,
    course_id_str: str,
    title: str,
    youtube_link: str = ""
) -> Tuple[Dict, int]:
    """Create a new lesson"""
    try:
        # Check if lesson already exists
        existing = db.query(Lesson).filter(Lesson.lesson_id == lesson_id).first()
        if existing:
            return {"error": "Lesson already exists"}, 400

        # Get or create course
        course = db.query(Course).filter(Course.course_id == course_id_str).first()
        if not course:
            course = Course(course_id=course_id_str)
            db.add(course)
            db.commit()

        # Create lesson
        lesson = Lesson(
            lesson_id=lesson_id,
            course_id=course.id,
            title=title,
            youtube_link=youtube_link
        )
        db.add(lesson)
        db.commit()
        db.refresh(lesson)

        logger.info(f"Created lesson: {lesson_id}")
        return lesson_to_dict(lesson, db), 201
    except Exception as e:
        db.rollback()
        logger.error(f"Error creating lesson: {e}")
        return {"error": "Failed to create lesson"}, 500


def add_exercise(
    db: Session,
    exercise_id: str,
    lesson_id: str,
    question: str,
    options: List[str],
    correct_option: int
) -> Tuple[Dict, int]:
    """Add an exercise to a lesson"""
    try:
        # Get lesson
        lesson = db.query(Lesson).filter(Lesson.lesson_id == lesson_id).first()
        if not lesson:
            return {"error": "Lesson not found"}, 404

        # Check if exercise already exists
        existing = db.query(Exercise).filter(Exercise.exercise_id == exercise_id).first()
        if existing:
            return {"error": "Exercise already exists"}, 400

        # Create exercise
        exercise = Exercise(
            exercise_id=exercise_id,
            lesson_id=lesson.id,
            question=question,
            options=options,
            correct_option=correct_option
        )
        db.add(exercise)
        db.commit()
        db.refresh(exercise)

        logger.info(f"Created exercise: {exercise_id} for lesson {lesson_id}")
        return {
            "exercise_id": exercise.exercise_id,
            "lesson_id": lesson.lesson_id,
            "question": exercise.question,
            "options": exercise.options,
            "correct_option": exercise.correct_option
        }, 201
    except Exception as e:
        db.rollback()
        logger.error(f"Error adding exercise: {e}")
        return {"error": "Failed to add exercise"}, 500


def get_lesson_exercises(db: Session, lesson_id: str) -> List[Dict]:
    """Get all exercises for a lesson"""
    try:
        lesson = db.query(Lesson).filter(Lesson.lesson_id == lesson_id).first()
        if not lesson:
            return []

        exercises = db.query(Exercise).filter(Exercise.lesson_id == lesson.id).all()
        return [
            {
                "exercise_id": e.exercise_id,
                "question": e.question,
                "options": e.options,
                "correct_option": e.correct_option
            }
            for e in exercises
        ]
    except Exception as e:
        logger.error(f"Error getting exercises: {e}")
        return []


def lesson_to_dict(lesson: Lesson, db: Session) -> Dict:
    """Convert lesson object to dictionary"""
    exercises = get_lesson_exercises(db, lesson.lesson_id)
    return {
        "id": lesson.lesson_id,
        "lesson_id": lesson.lesson_id,
        "title": lesson.title,
        "youtube_link": lesson.youtube_link,
        "course_id": lesson.course.course_id if lesson.course else "",
        "exercises": exercises,
        "created_at": lesson.created_at.isoformat()
    }
