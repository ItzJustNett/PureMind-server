-- Migration: Update cat_id constraint to allow only 0 and 1
-- Date: 2026-03-20
-- Description: Remove black cat (cat_id=2) from valid options

-- Drop the old constraint
ALTER TABLE profiles DROP CONSTRAINT IF EXISTS valid_cat_id;

-- Add the new constraint
ALTER TABLE profiles ADD CONSTRAINT valid_cat_id CHECK (cat_id IN (0, 1));

-- Update any existing profiles with cat_id=2 to cat_id=0 (orange cat)
UPDATE profiles SET cat_id = 0 WHERE cat_id = 2;
