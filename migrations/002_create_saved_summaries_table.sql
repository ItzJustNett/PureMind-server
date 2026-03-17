-- Migration: Create saved_summaries table
-- This table stores AI-generated lesson summaries that are automatically saved to user profiles

CREATE TABLE IF NOT EXISTS saved_summaries (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    lesson_id INTEGER REFERENCES lessons(id) ON DELETE SET NULL,
    title VARCHAR(500) NOT NULL,
    summary TEXT NOT NULL,
    key_points JSONB,
    is_favorite BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes for better query performance
CREATE INDEX IF NOT EXISTS idx_saved_summaries_user ON saved_summaries(user_id);
CREATE INDEX IF NOT EXISTS idx_saved_summaries_created ON saved_summaries(created_at);

-- Add comments to table
COMMENT ON TABLE saved_summaries IS 'AI-generated lesson summaries automatically saved to user profiles';
COMMENT ON COLUMN saved_summaries.summary IS 'Main summary text of the lesson';
COMMENT ON COLUMN saved_summaries.key_points IS 'Array of key points from the lesson';
COMMENT ON COLUMN saved_summaries.is_favorite IS 'Whether the user has marked this summary as favorite';
