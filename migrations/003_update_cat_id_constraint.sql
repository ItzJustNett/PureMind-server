-- Migration: Fix cat_id constraint to properly allow all three cats
-- Date: 2026-03-20
-- Description: Ensure all three cats (0=orange, 1=gray, 2=black) are allowed

-- Drop the old constraint if it exists
ALTER TABLE profiles DROP CONSTRAINT IF EXISTS valid_cat_id;

-- Add the correct constraint allowing all three cats
ALTER TABLE profiles ADD CONSTRAINT valid_cat_id CHECK (cat_id IN (0, 1, 2));
