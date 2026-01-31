-- Verify Phase 2 & 3 Migration Results

\echo 'Checking Phase 2 & 3 Migration Status...'
\echo ''

-- 1. Check if baseline_experiment_mapping table exists and has correct columns
\echo '1. Baseline Experiment Mapping Table Structure:'
SELECT column_name, data_type, is_nullable
FROM information_schema.columns
WHERE table_schema = 'chaos_platform' AND table_name = 'baseline_experiment_mapping'
ORDER BY ordinal_position;

-- 2. Check if new Phase 3 columns were added
\echo ''
\echo '2. Phase 3 Columns Added (should show 5 rows):'
SELECT COUNT(*) as new_columns_added
FROM information_schema.columns
WHERE table_schema = 'chaos_platform'
    AND table_name = 'baseline_experiment_mapping'
    AND column_name IN ('baseline_version_id', 'used_sigma_threshold', 'used_critical_sigma', 'discovery_method', 'loaded_at');

-- 3. Check indexes
\echo ''
\echo '3. Indexes on baseline_experiment_mapping table:'
SELECT indexname FROM pg_indexes
WHERE schemaname = 'chaos_platform' AND tablename = 'baseline_experiment_mapping'
ORDER BY indexname;

-- 4. Check data in the table
\echo ''
\echo '4. Data in baseline_experiment_mapping table:'
SELECT COUNT(*) as total_rows FROM chaos_platform.baseline_experiment_mapping;

\echo ''
\echo 'Migration verification complete!'
