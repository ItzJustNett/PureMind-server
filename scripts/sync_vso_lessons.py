#!/usr/bin/env python3
"""
Sync vso_lessons.json to the database
Adds missing lessons from vso_lessons.json
"""
import json
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from database import SessionLocal
from database.models import Course, Lesson
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def main():
    """Add vso_lessons.json to database"""
    logger.info("Loading vso_lessons.json...")

    vso_file = Path(__file__).parent.parent / "vso_lessons.json"
    with open(vso_file, 'r', encoding='utf-8') as f:
        vso_lessons = json.load(f)

    logger.info(f"Found {len(vso_lessons)} lessons in vso_lessons.json")

    db = SessionLocal()
    try:
        # Collect unique courses
        courses_dict = {}
        for lesson_id, lesson in vso_lessons.items():
            course_id = lesson.get("course_id", "unknown")
            if course_id and course_id not in courses_dict:
                title = lesson.get("title", "").split(". ", 1)[0] if lesson.get("title") else course_id
                courses_dict[course_id] = {"course_id": course_id, "title": title}

        logger.info(f"Found {len(courses_dict)} unique courses")

        # Create courses
        course_mapping = {}
        courses_added = 0
        for course_id, course_data in courses_dict.items():
            existing = db.query(Course).filter(Course.course_id == course_id).first()
            if existing:
                course_mapping[course_id] = existing.id
            else:
                course = Course(course_id=course_id, title=course_data["title"])
                db.add(course)
                db.commit()
                db.refresh(course)
                course_mapping[course_id] = course.id
                courses_added += 1

        logger.info(f"Added {courses_added} new courses")

        # Add lessons
        lessons_added = 0
        lessons_skipped = 0

        for lesson_id, lesson in vso_lessons.items():
            # Check if exists
            existing = db.query(Lesson).filter(Lesson.lesson_id == lesson_id).first()
            if existing:
                lessons_skipped += 1
                continue

            course_id = lesson.get("course_id", "unknown")
            course_db_id = course_mapping.get(course_id)

            if not course_db_id:
                logger.warning(f"Course not found for lesson {lesson_id}")
                continue

            lesson_obj = Lesson(
                lesson_id=lesson_id,
                course_id=course_db_id,
                title=lesson.get("title", ""),
                youtube_link=lesson.get("youtube_link", "")
            )
            db.add(lesson_obj)
            db.commit()
            lessons_added += 1

            if lessons_added % 100 == 0:
                logger.info(f"Added {lessons_added} lessons...")

        logger.info(f"✓ Added {lessons_added} new lessons")
        logger.info(f"✓ Skipped {lessons_skipped} existing lessons")

        # Show total
        total = db.query(Lesson).count()
        logger.info(f"✓ Total lessons in database: {total}")

    finally:
        db.close()

if __name__ == "__main__":
    main()
