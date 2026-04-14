-- Migration: Add completed_lessons table to track unique lesson completions
-- Run this migration on your database

CREATE TABLE IF NOT EXISTS completed_lessons (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    lesson_id VARCHAR(255) NOT NULL,
    completed_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Create unique index to prevent duplicate completions
CREATE UNIQUE INDEX IF NOT EXISTS idx_completed_user_lesson
ON completed_lessons(user_id, lesson_id);

-- Create index for faster queries
CREATE INDEX IF NOT EXISTS idx_completed_lessons_user_id ON completed_lessons(user_id);
CREATE INDEX IF NOT EXISTS idx_completed_lessons_lesson_id ON completed_lessons(lesson_id);

-- Migration complete
