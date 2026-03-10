#!/usr/bin/env python3
"""
Import VSO Lessons Script
Imports scraped lessons from vso_lessons.json into PostgreSQL database.
"""
import json
import os
import sys
import logging
from pathlib import Path
from typing import Dict, List

# Add parent directory to path to import API modules
sys.path.insert(0, str(Path(__file__).parent.parent))

# Load environment variables from parent directory BEFORE importing database modules
from dotenv import load_dotenv
env_path = Path(__file__).parent.parent / '.env'
load_dotenv(dotenv_path=env_path)

from database import SessionLocal
from database.models import Course, Lesson
from db_managers import lesson_manager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
)
logger = logging.getLogger(__name__)

def load_vso_lessons(filepath: str) -> Dict:
    """Load VSO lessons JSON file"""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
        logger.info(f"Loaded {len(data)} lessons from {filepath}")
        return data
    except Exception as e:
        logger.error(f"Error loading {filepath}: {e}")
        return {}

def extract_courses(lessons_data: Dict) -> Dict[str, Dict]:
    """Extract unique courses from lessons data"""
    courses_dict = {}

    for lesson_id, lesson in lessons_data.items():
        course_id = lesson.get("course_id", "unknown")
        subject = lesson.get("subject", "inshi")
        grade = lesson.get("grade")

        if course_id and course_id not in courses_dict:
            # Create a descriptive course title
            if grade:
                title = f"{subject.replace('_', ' ').title()} - Grade {grade}"
            else:
                title = subject.replace('_', ' ').title()

            courses_dict[course_id] = {
                "course_id": course_id,
                "title": title,
                "description": f"Lessons for {title}"
            }

    return courses_dict

def create_courses(db, courses_dict: Dict[str, Dict]) -> Dict[str, int]:
    """Create courses in database"""
    course_mapping = {}
    created_count = 0

    for course_id, course_data in courses_dict.items():
        try:
            # Check if course exists
            existing = db.query(Course).filter(Course.course_id == course_id).first()
            if existing:
                course_mapping[course_id] = existing.id
                logger.debug(f"Course {course_id} already exists")
                continue

            # Create new course
            course = Course(
                course_id=course_id,
                title=course_data["title"],
                description=course_data["description"]
            )
            db.add(course)
            db.commit()
            db.refresh(course)

            course_mapping[course_id] = course.id
            created_count += 1
            logger.info(f"Created course: {course_id}")

        except Exception as e:
            db.rollback()
            logger.error(f"Error creating course {course_id}: {e}")

    logger.info(f"Created {created_count} new courses, {len(courses_dict) - created_count} already existed")
    return course_mapping

def import_lessons(db, lessons_data: Dict, course_mapping: Dict[str, int]) -> int:
    """Import lessons into database"""
    imported_count = 0
    skipped_count = 0
    error_count = 0

    for lesson_id, lesson in lessons_data.items():
        try:
            # Check if lesson already exists
            existing = db.query(Lesson).filter(Lesson.lesson_id == lesson_id).first()
            if existing:
                skipped_count += 1
                logger.debug(f"Lesson {lesson_id} already exists")
                continue

            course_id = lesson.get("course_id", "unknown")
            course_db_id = course_mapping.get(course_id)

            if not course_db_id:
                logger.warning(f"Course not found for lesson {lesson_id}")
                error_count += 1
                continue

            # Create lesson
            lesson_obj = Lesson(
                lesson_id=lesson_id,
                course_id=course_db_id,
                title=lesson.get("title", ""),
                youtube_link=lesson.get("youtube_link", "")
            )
            db.add(lesson_obj)
            db.commit()
            db.refresh(lesson_obj)

            imported_count += 1

            if imported_count % 100 == 0:
                logger.info(f"Progress: {imported_count} lessons imported...")

        except Exception as e:
            db.rollback()
            error_count += 1
            logger.error(f"Error importing lesson {lesson_id}: {e}")

    logger.info(f"Import complete: {imported_count} imported, {skipped_count} skipped, {error_count} errors")
    return imported_count

def verify_import(db):
    """Verify the import was successful"""
    logger.info("Verifying import...")

    total_courses = db.query(Course).count()
    total_lessons = db.query(Lesson).count()

    logger.info(f"Database now contains:")
    logger.info(f"  Courses: {total_courses}")
    logger.info(f"  Lessons: {total_lessons}")

    # Count lessons by subject
    from sqlalchemy import func
    course_stats = db.query(
        Course.course_id,
        func.count(Lesson.id).label('lesson_count')
    ).join(Lesson).group_by(Course.course_id).order_by(func.count(Lesson.id).desc()).limit(10).all()

    logger.info("Top 10 courses by lesson count:")
    for course_id, count in course_stats:
        logger.info(f"  {course_id}: {count} lessons")

def main():
    """Main import function"""
    # Get the VSO lessons file path (in the API directory)
    vso_lessons_path = Path(__file__).parent.parent / "vso_lessons.json"

    if not vso_lessons_path.exists():
        logger.error(f"VSO lessons file not found: {vso_lessons_path}")
        logger.info("Expected location: API/vso_lessons.json")
        return False

    logger.info(f"Starting VSO lessons import from {vso_lessons_path}")

    try:
        # Load lessons data
        lessons_data = load_vso_lessons(vso_lessons_path)
        if not lessons_data:
            logger.error("No lessons data to import")
            return False

        # Extract courses
        logger.info("Extracting courses...")
        courses_dict = extract_courses(lessons_data)
        logger.info(f"Found {len(courses_dict)} unique courses")

        # Create database session
        db = SessionLocal()

        try:
            # Create courses
            logger.info("Creating courses...")
            course_mapping = create_courses(db, courses_dict)

            # Import lessons
            logger.info("Importing lessons...")
            imported_count = import_lessons(db, lessons_data, course_mapping)

            # Verify import
            verify_import(db)

            logger.info("Import completed successfully!")
            return True

        finally:
            db.close()

    except Exception as e:
        logger.error(f"Import failed: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
