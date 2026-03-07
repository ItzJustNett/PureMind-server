"""
SQLAlchemy ORM models for the Lessons API database.
Defines all tables and their relationships.
"""
from datetime import datetime, timedelta
from sqlalchemy import (
    Column, Integer, String, Float, DateTime, Boolean, ForeignKey,
    JSON, CheckConstraint, Index, Text, Date
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship

Base = declarative_base()


class User(Base):
    """User account table"""
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(255), unique=True, nullable=False, index=True)
    email = Column(String(255), nullable=True)
    password_hash = Column(String(255), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    profile = relationship("Profile", back_populates="user", uselist=False, cascade="all, delete-orphan")
    completed_exercises = relationship("CompletedExercise", back_populates="user", cascade="all, delete-orphan")
    inventory = relationship("Inventory", back_populates="user", cascade="all, delete-orphan")
    equipped_items = relationship("EquippedItem", back_populates="user", cascade="all, delete-orphan")
    auth_tokens = relationship("AuthToken", back_populates="user", cascade="all, delete-orphan")


class Profile(Base):
    """User profile with gamification data"""
    __tablename__ = "profiles"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, unique=True, index=True)
    name = Column(String(255), nullable=False)
    about = Column(Text, nullable=True, default="")
    cat_id = Column(Integer, nullable=False, default=0)
    illness_id = Column(Integer, nullable=False, default=0)

    # Gamification fields
    xp = Column(Integer, nullable=False, default=0)
    meowcoins = Column(Integer, nullable=False, default=0)

    # Streak tracking
    current_streak = Column(Integer, nullable=False, default=0)
    longest_streak = Column(Integer, nullable=False, default=0)
    last_activity_date = Column(Date, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Constraints
    __table_args__ = (
        CheckConstraint("cat_id IN (0, 1, 10)", name="valid_cat_id"),
        CheckConstraint("illness_id BETWEEN 0 AND 5", name="valid_illness_id"),
        CheckConstraint("xp >= 0", name="non_negative_xp"),
        CheckConstraint("meowcoins >= 0", name="non_negative_meowcoins"),
        CheckConstraint("current_streak >= 0", name="non_negative_current_streak"),
        CheckConstraint("longest_streak >= 0", name="non_negative_longest_streak"),
        Index("idx_profile_xp", "xp"),
        Index("idx_profile_meowcoins", "meowcoins"),
        Index("idx_profile_streak", "current_streak"),
    )

    # Relationships
    user = relationship("User", back_populates="profile")
    completed_exercises = relationship("CompletedExercise", back_populates="profile", cascade="all, delete-orphan")


class Course(Base):
    """Normalized course table"""
    __tablename__ = "courses"

    id = Column(Integer, primary_key=True, autoincrement=True)
    course_id = Column(String(255), unique=True, nullable=False, index=True)
    title = Column(String(255), nullable=True)
    description = Column(Text, nullable=True)

    # Relationships
    lessons = relationship("Lesson", back_populates="course", cascade="all, delete-orphan")


class Lesson(Base):
    """Lesson content table"""
    __tablename__ = "lessons"

    id = Column(Integer, primary_key=True, autoincrement=True)
    lesson_id = Column(String(255), unique=True, nullable=False, index=True)
    course_id = Column(Integer, ForeignKey("courses.id"), nullable=False, index=True)
    title = Column(String(255), nullable=False, index=True)
    youtube_link = Column(String(500), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    course = relationship("Course", back_populates="lessons")
    exercises = relationship("Exercise", back_populates="lesson", cascade="all, delete-orphan")


class Exercise(Base):
    """Quiz exercises for lessons"""
    __tablename__ = "exercises"

    id = Column(Integer, primary_key=True, autoincrement=True)
    exercise_id = Column(String(255), unique=True, nullable=False, index=True)
    lesson_id = Column(Integer, ForeignKey("lessons.id"), nullable=False, index=True)
    question = Column(Text, nullable=False)
    options = Column(JSON, nullable=False)  # Array of option strings
    correct_option = Column(Integer, nullable=False)  # Index of correct answer
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    lesson = relationship("Lesson", back_populates="exercises")
    completed_exercises = relationship("CompletedExercise", back_populates="exercise")


class CompletedExercise(Base):
    """Tracks user exercise completions with rewards"""
    __tablename__ = "completed_exercises"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    profile_id = Column(Integer, ForeignKey("profiles.id"), nullable=False, index=True)
    exercise_id = Column(Integer, ForeignKey("exercises.id"), nullable=False, index=True)

    correct_answers = Column(Integer, nullable=False, default=0)
    meowcoins_earned = Column(Integer, nullable=False, default=0)
    xp_earned = Column(Integer, nullable=False, default=0)
    completion_count = Column(Integer, nullable=False, default=1)

    completed_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    user = relationship("User", back_populates="completed_exercises")
    profile = relationship("Profile", back_populates="completed_exercises")
    exercise = relationship("Exercise", back_populates="completed_exercises")

    __table_args__ = (
        Index("idx_completed_user_exercise", "user_id", "exercise_id"),
    )


class StoreItem(Base):
    """Purchasable cat accessories (normalized)"""
    __tablename__ = "store_items"

    id = Column(Integer, primary_key=True, autoincrement=True)
    item_id = Column(String(255), unique=True, nullable=False, index=True)
    name = Column(String(255), nullable=False)
    price = Column(Integer, nullable=False)
    description = Column(Text, nullable=True)

    # Relationships
    inventory_items = relationship("Inventory", back_populates="store_item", cascade="all, delete-orphan")
    equipped_items = relationship("EquippedItem", back_populates="store_item", cascade="all, delete-orphan")


class Inventory(Base):
    """User-owned store items"""
    __tablename__ = "inventory"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    store_item_id = Column(Integer, ForeignKey("store_items.id"), nullable=False, index=True)
    purchased_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    user = relationship("User", back_populates="inventory")
    store_item = relationship("StoreItem", back_populates="inventory_items")

    __table_args__ = (
        Index("idx_inventory_user_item", "user_id", "store_item_id", unique=True),
    )


class EquippedItem(Base):
    """Currently equipped accessories"""
    __tablename__ = "equipped_items"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    store_item_id = Column(Integer, ForeignKey("store_items.id"), nullable=False, index=True)
    equipped_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    user = relationship("User", back_populates="equipped_items")
    store_item = relationship("StoreItem", back_populates="equipped_items")

    __table_args__ = (
        Index("idx_equipped_user_item", "user_id", "store_item_id", unique=True),
    )


class AuthToken(Base):
    """Authentication tokens (replaces in-memory storage)"""
    __tablename__ = "auth_tokens"

    id = Column(Integer, primary_key=True, autoincrement=True)
    token = Column(String(255), unique=True, nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    expires_at = Column(DateTime, default=lambda: datetime.utcnow() + timedelta(days=30), nullable=False)

    # Relationships
    user = relationship("User", back_populates="auth_tokens")

    __table_args__ = (
        Index("idx_token_expires", "expires_at"),
    )
