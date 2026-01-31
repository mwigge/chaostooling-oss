-- Migration: Add p999 (99.9th percentile) column to baseline_metrics table
-- Date: 2026-01-31
-- Description: The code expects a p999 column for tracking 99.9th percentile values
--              This migration adds the missing column to the schema

-- Add p999 column if it doesn't exist
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema = 'chaos_platform'
        AND table_name = 'baseline_metrics'
        AND column_name = 'p999'
    ) THEN
        ALTER TABLE chaos_platform.baseline_metrics
        ADD COLUMN p999 NUMERIC(12, 4);

        RAISE NOTICE 'Added p999 column to chaos_platform.baseline_metrics';
    ELSE
        RAISE NOTICE 'Column p999 already exists in chaos_platform.baseline_metrics';
    END IF;
END $$;
