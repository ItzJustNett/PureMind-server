#!/usr/bin/env python3
"""
PostgreSQL Migration Script
Migrates data from JSON files to PostgreSQL database.
"""
import json
import os
import shutil
import sys
import logging
from datetime import datetime
from pathlib import Path

# Add parent directory to path to import API modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from database import init_db, SessionLocal
from database.models import (
    User, Profile, Course, Lesson, Exercise, StoreItem,
    Inventory, EquippedItem, CompletedExercise
)
from db_managers import user_manager, profile_manager, lesson_manager, store_manager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
)
logger = logging.getLogger(__name__)

# Paths
API_DIR = Path(__file__).parent.parent
BACKUPS_DIR = API_DIR / "backups"
JSON_BACKUP_DIR = BACKUPS_DIR / f"json_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

def backup_json_files():
    """Backup existing JSON files"""
    logger.info("Backing up JSON files...")
    BACKUPS_DIR.mkdir(exist_ok=True)
    JSON_BACKUP_DIR.mkdir(exist_ok=True)

    json_files = ["users.json", "profiles.json", "lessons.json"]
    for filename in json_files:
        src = API_DIR / filename
        if src.exists():
            dst = JSON_BACKUP_DIR / filename
            shutil.copy2(src, dst)
            logger.info(f"Backed up {filename}")

    logger.info(f"Backups saved to: {JSON_BACKUP_DIR}")

def load_json_file(filename: str) -> dict:
    """Load a JSON file"""
    filepath = API_DIR / filename
    if not filepath.exists():
        logger.warning(f"File not found: {filename}")
        return {}

    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
        logger.info(f"Loaded {filename}: {len(data)} records")
        return data
    except Exception as e:
        logger.error(f"Error loading {filename}: {e}")
        return {}

def migrate_users(db):
    """Migrate users from JSON"""
    logger.info("Migrating users...")
    users_data = load_json_file("users.json")

    user_id_mapping = {}  # Map old user_id to new user_id
    migrated_count = 0

    for username, user_info in users_data.items():
        try:
            # Check if user already exists
            existing = db.query(User).filter(User.username == username).first()
            if existing:
                user_id_mapping[user_info["id"]] = existing.id
                continue

            # Create user
            user = User(
                username=username,
                email=user_info.get("email", ""),
                password_hash=user_info.get("password_hash", "")
            )
            db.add(user)
            db.commit()
            db.refresh(user)

            user_id_mapping[user_info["id"]] = user.id
            migrated_count += 1
        except Exception as e:
            db.rollback()
            logger.error(f"Error migrating user {username}: {e}")

    logger.info(f"Migrated {migrated_count} users")
    return user_id_mapping

def migrate_lessons(db):
    """Migrate lessons from JSON"""
    logger.info("Migrating lessons and courses...")
    lessons_data = load_json_file("lessons.json")

    # First, collect all unique courses
    courses_dict = {}
    for lesson_id, lesson in lessons_data.items():
        course_id = lesson.get("course_id", "unknown")
        if course_id and course_id not in courses_dict:
            courses_dict[course_id] = {
                "course_id": course_id,
                "title": lesson.get("title", "").split(". ", 1)[0] if lesson.get("title") else course_id
            }

    # Create courses
    course_mapping = {}  # Map course_id to database course.id
    for course_id, course_data in courses_dict.items():
        try:
            existing = db.query(Course).filter(Course.course_id == course_id).first()
            if existing:
                course_mapping[course_id] = existing.id
                continue

            course = Course(course_id=course_id, title=course_data["title"])
            db.add(course)
            db.commit()
            db.refresh(course)
            course_mapping[course_id] = course.id
        except Exception as e:
            db.rollback()
            logger.error(f"Error creating course {course_id}: {e}")

    # Create lessons
    migrated_count = 0
    for lesson_id, lesson in lessons_data.items():
        try:
            # Check if lesson already exists
            existing = db.query(Lesson).filter(Lesson.lesson_id == lesson_id).first()
            if existing:
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
            db.refresh(lesson_obj)
            migrated_count += 1
        except Exception as e:
            db.rollback()
            logger.error(f"Error migrating lesson {lesson_id}: {e}")

    logger.info(f"Migrated {migrated_count} lessons into {len(courses_dict)} courses")

def migrate_profiles(db, user_id_mapping):
    """Migrate profiles from JSON"""
    logger.info("Migrating profiles...")
    profiles_data = load_json_file("profiles.json")

    migrated_count = 0
    for old_user_id, profile_data in profiles_data.items():
        try:
            # Find the new user_id
            new_user_id = user_id_mapping.get(old_user_id)
            if not new_user_id:
                logger.warning(f"User not found for profile {old_user_id}")
                continue

            # Check if profile already exists
            existing = db.query(Profile).filter(Profile.user_id == new_user_id).first()
            if existing:
                continue

            # Create profile
            profile = Profile(
                user_id=new_user_id,
                name=profile_data.get("name", ""),
                about=profile_data.get("about", ""),
                cat_id=profile_data.get("cat_id", 0),
                illness_id=profile_data.get("illness_id", 0),
                xp=profile_data.get("xp", 0),
                meowcoins=profile_data.get("meowcoins", 0),
                current_streak=profile_data.get("streak", {}).get("current_streak", 0),
                longest_streak=profile_data.get("streak", {}).get("longest_streak", 0)
            )

            # Parse last_activity_date if present
            last_activity = profile_data.get("streak", {}).get("last_activity_date")
            if last_activity:
                try:
                    from datetime import date
                    profile.last_activity_date = date.fromisoformat(last_activity)
                except:
                    pass

            db.add(profile)
            db.commit()
            db.refresh(profile)

            # Migrate completed exercises
            completed_exercises = profile_data.get("completed_exercises", {})
            for exercise_id, completion_data in completed_exercises.items():
                try:
                    # Try to find the exercise in database
                    exercise = db.query(Exercise).filter(
                        Exercise.exercise_id == exercise_id
                    ).first()

                    if not exercise:
                        # If exercise doesn't exist, skip (it will be created when tests are generated)
                        continue

                    completed = CompletedExercise(
                        user_id=new_user_id,
                        profile_id=profile.id,
                        exercise_id=exercise.id,
                        correct_answers=completion_data.get("correct_answers", 0),
                        meowcoins_earned=completion_data.get("meowcoins_earned", 0),
                        xp_earned=completion_data.get("xp_earned", 0),
                        completion_count=completion_data.get("completion_count", 1)
                    )
                    db.add(completed)
                except Exception as e:
                    logger.debug(f"Error migrating completed exercise {exercise_id}: {e}")

            # Migrate inventory items
            inventory = profile_data.get("inventory", [])
            for item_id in inventory:
                try:
                    store_item = db.query(StoreItem).filter(
                        StoreItem.item_id == item_id
                    ).first()

                    if not store_item:
                        continue

                    inv_item = Inventory(
                        user_id=new_user_id,
                        store_item_id=store_item.id
                    )
                    db.add(inv_item)
                except Exception as e:
                    logger.debug(f"Error migrating inventory item {item_id}: {e}")

            # Migrate equipped items
            equipped = profile_data.get("equipped_items", [])
            for item_id in equipped:
                try:
                    store_item = db.query(StoreItem).filter(
                        StoreItem.item_id == item_id
                    ).first()

                    if not store_item:
                        continue

                    eq_item = EquippedItem(
                        user_id=new_user_id,
                        store_item_id=store_item.id
                    )
                    db.add(eq_item)
                except Exception as e:
                    logger.debug(f"Error migrating equipped item {item_id}: {e}")

            db.commit()
            migrated_count += 1
        except Exception as e:
            db.rollback()
            logger.error(f"Error migrating profile {old_user_id}: {e}")

    logger.info(f"Migrated {migrated_count} profiles")

def insert_store_items(db):
    """Insert store items into database"""
    logger.info("Inserting store items...")

    store_items_data = {
        "sunglasses": {"price": 100, "description": "Cool sunglasses for your cat"},
        "cap": {"price": 150, "description": "A stylish cap for your cat"},
        "moustache": {"price": 200, "description": "A fancy moustache for your cat"},
        "butterfly": {"price": 250, "description": "A cute butterfly accessory for your cat"}
    }

    for item_id, item_data in store_items_data.items():
        try:
            # Check if item already exists
            existing = db.query(StoreItem).filter(StoreItem.item_id == item_id).first()
            if existing:
                continue

            store_item = StoreItem(
                item_id=item_id,
                name=item_id.capitalize(),
                price=item_data["price"],
                description=item_data["description"]
            )
            db.add(store_item)
            db.commit()
            logger.info(f"Inserted store item: {item_id}")
        except Exception as e:
            db.rollback()
            logger.error(f"Error inserting store item {item_id}: {e}")

def verify_migration(db):
    """Verify the migration was successful"""
    logger.info("Verifying migration...")

    counts = {
        "users": db.query(User).count(),
        "profiles": db.query(Profile).count(),
        "courses": db.query(Course).count(),
        "lessons": db.query(Lesson).count(),
        "store_items": db.query(StoreItem).count(),
        "completed_exercises": db.query(CompletedExercise).count(),
        "inventory_items": db.query(Inventory).count(),
    }

    logger.info("Migration Summary:")
    for entity, count in counts.items():
        logger.info(f"  {entity}: {count}")

    return counts

def main():
    """Main migration function"""
    logger.info("Starting PostgreSQL migration...")

    try:
        # Step 1: Backup JSON files
        backup_json_files()

        # Step 2: Initialize database
        logger.info("Initializing database...")
        if not init_db():
            logger.error("Failed to initialize database")
            return False

        # Step 3: Create database session
        db = SessionLocal()

        try:
            # Step 4: Migrate users
            user_id_mapping = migrate_users(db)

            # Step 5: Migrate lessons and courses
            migrate_lessons(db)

            # Step 6: Insert store items
            insert_store_items(db)

            # Step 7: Migrate profiles and related data
            migrate_profiles(db, user_id_mapping)

            # Step 8: Verify migration
            counts = verify_migration(db)

            logger.info("Migration completed successfully!")
            logger.info(f"Backup location: {JSON_BACKUP_DIR}")
            return True

        finally:
            db.close()

    except Exception as e:
        logger.error(f"Migration failed: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
