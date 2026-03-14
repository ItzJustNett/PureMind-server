-- Migration: Create generated_tests table
-- This table stores AI-generated tests that are automatically saved to user profiles

CREATE TABLE IF NOT EXISTS generated_tests (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    lesson_id INTEGER REFERENCES lessons(id) ON DELETE SET NULL,
    title VARCHAR(500) NOT NULL,
    test_content JSONB NOT NULL,
    questions_count INTEGER NOT NULL DEFAULT 10,
    is_private BOOLEAN NOT NULL DEFAULT TRUE,
    is_favorite BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes for better query performance
CREATE INDEX IF NOT EXISTS idx_generated_tests_user ON generated_tests(user_id);
CREATE INDEX IF NOT EXISTS idx_generated_tests_created ON generated_tests(created_at);

-- Add comment to table
COMMENT ON TABLE generated_tests IS 'AI-generated tests automatically saved to user profiles';
COMMENT ON COLUMN generated_tests.test_content IS 'Full test JSON including questions, options, and correct answers';
COMMENT ON COLUMN generated_tests.is_private IS 'Whether the test is private (default: true)';
COMMENT ON COLUMN generated_tests.is_favorite IS 'Whether the user has marked this test as favorite';
