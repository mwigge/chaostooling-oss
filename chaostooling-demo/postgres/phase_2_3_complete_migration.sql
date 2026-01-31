-- ============================================================================
-- COMPLETE MIGRATION: Phase 2 & 3 - Baseline Experiment Mapping
-- ============================================================================
-- This script includes:
-- 1. Creation of baseline_experiment_mapping table (Phase 2 prerequisite)
-- 2. Phase 3 schema enhancements (5 new columns)
-- 3. Phase 3 audit view creation
--
-- Safe to run multiple times (uses IF NOT EXISTS, IF NOT)
-- ============================================================================

-- ============================================================================
-- PHASE 2: Create baseline_experiment_mapping table (if not exists)
-- ============================================================================

CREATE TABLE IF NOT EXISTS chaos_platform.baseline_experiment_mapping (
    mapping_id BIGSERIAL PRIMARY KEY,
    
    -- Experiment Reference
    experiment_id INTEGER NOT NULL REFERENCES chaos_platform.experiments(experiment_id),
    
    -- Baseline Reference  
    metric_id BIGINT NOT NULL REFERENCES chaos_platform.baseline_metrics(baseline_id),
    
    -- Mapping Details
    mapping_type VARCHAR(100),              -- 'threshold_check', 'anomaly_detect', 'regression_detect'
    sigma_threshold NUMERIC(5, 2) DEFAULT 2.0,  -- Alert if deviation > 2 sigma
    critical_sigma NUMERIC(5, 2) DEFAULT 3.0,
    
    -- Anomaly Detection Strategy
    enable_anomaly_detection BOOLEAN DEFAULT true,
    anomaly_method VARCHAR(100),            -- 'zscore', 'iqr', 'mad', 'isolation_forest'
    
    -- Test Status
    is_active BOOLEAN DEFAULT true,
    skip_reason VARCHAR(255),
    
    -- Metadata
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    UNIQUE(experiment_id, metric_id)
);

-- Indexes for Phase 2
CREATE INDEX IF NOT EXISTS idx_baseline_experiment_mapping_experiment 
    ON chaos_platform.baseline_experiment_mapping(experiment_id);
CREATE INDEX IF NOT EXISTS idx_baseline_experiment_mapping_metric 
    ON chaos_platform.baseline_experiment_mapping(metric_id);

-- ============================================================================
-- PHASE 3: Add audit trail columns to baseline_experiment_mapping
-- ============================================================================

-- 1. Add baseline_version_id column
ALTER TABLE chaos_platform.baseline_experiment_mapping
ADD COLUMN IF NOT EXISTS baseline_version_id BIGINT;

-- Add comment for baseline_version_id
COMMENT ON COLUMN chaos_platform.baseline_experiment_mapping.baseline_version_id IS 
'References which version of the baseline was used for this mapping. Allows tracking different baseline iterations.';

-- 2. Add used_sigma_threshold column
ALTER TABLE chaos_platform.baseline_experiment_mapping
ADD COLUMN IF NOT EXISTS used_sigma_threshold NUMERIC(5, 2) DEFAULT 2.0;

-- Add comment for used_sigma_threshold
COMMENT ON COLUMN chaos_platform.baseline_experiment_mapping.used_sigma_threshold IS 
'Sigma threshold actually used for this experiment. May differ from baseline defaults.';

-- 3. Add used_critical_sigma column
ALTER TABLE chaos_platform.baseline_experiment_mapping
ADD COLUMN IF NOT EXISTS used_critical_sigma NUMERIC(5, 2) DEFAULT 3.0;

-- Add comment for used_critical_sigma
COMMENT ON COLUMN chaos_platform.baseline_experiment_mapping.used_critical_sigma IS 
'Critical sigma threshold actually used for this experiment. May differ from baseline defaults.';

-- 4. Add discovery_method column with constraint
ALTER TABLE chaos_platform.baseline_experiment_mapping
ADD COLUMN IF NOT EXISTS discovery_method VARCHAR(50);

-- Add CHECK constraint for valid discovery methods
ALTER TABLE chaos_platform.baseline_experiment_mapping
ADD CONSTRAINT IF NOT EXISTS check_valid_discovery_method
CHECK (discovery_method IN ('system', 'service', 'explicit', 'labels', NULL));

-- Add comment for discovery_method
COMMENT ON COLUMN chaos_platform.baseline_experiment_mapping.discovery_method IS 
'How this baseline was discovered: system (by system_id), service (by service_id), explicit (by metric_id), or labels (by Grafana labels).';

-- 5. Add loaded_at column
ALTER TABLE chaos_platform.baseline_experiment_mapping
ADD COLUMN IF NOT EXISTS loaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP;

-- Add comment for loaded_at
COMMENT ON COLUMN chaos_platform.baseline_experiment_mapping.loaded_at IS 
'When the baseline was loaded for this experiment.';

-- ============================================================================
-- PHASE 3: Add foreign key constraint to baseline_versions (if exists)
-- ============================================================================

-- Check if baseline_versions table exists before adding constraint
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.tables 
               WHERE table_schema = 'chaos_platform' 
               AND table_name = 'baseline_versions') THEN
        ALTER TABLE chaos_platform.baseline_experiment_mapping
        ADD CONSTRAINT IF NOT EXISTS fk_baseline_experiment_mapping_version
        FOREIGN KEY (baseline_version_id)
        REFERENCES chaos_platform.baseline_versions(baseline_version_id)
        ON DELETE SET NULL;
    END IF;
END $$;

-- ============================================================================
-- PHASE 3: Create indexes for new columns
-- ============================================================================

-- Index for baseline_version_id (used in JOINs)
CREATE INDEX IF NOT EXISTS idx_baseline_experiment_mapping_version
    ON chaos_platform.baseline_experiment_mapping(baseline_version_id)
    WHERE baseline_version_id IS NOT NULL;

-- Index for discovery_method (used in filtering)
CREATE INDEX IF NOT EXISTS idx_baseline_experiment_mapping_discovery_method
    ON chaos_platform.baseline_experiment_mapping(discovery_method)
    WHERE discovery_method IS NOT NULL;

-- Index for loaded_at (used in time-range queries)
CREATE INDEX IF NOT EXISTS idx_baseline_experiment_mapping_loaded_at
    ON chaos_platform.baseline_experiment_mapping(loaded_at);

-- ============================================================================
-- PHASE 3: Populate discovery_method for existing rows (migration)
-- ============================================================================

-- Set default discovery_method for existing records that don't have it
UPDATE chaos_platform.baseline_experiment_mapping
SET discovery_method = 'system'
WHERE discovery_method IS NULL;

-- ============================================================================
-- PHASE 3: Create audit trail view
-- ============================================================================

CREATE OR REPLACE VIEW chaos_platform.v_experiment_baselines AS
SELECT
    bem.mapping_id,
    bem.experiment_id,
    exp.experiment_title,
    exp.description AS experiment_description,
    bem.metric_id,
    bm.metric_name,
    svc.service_name,
    bm.baseline_id,
    bem.baseline_version_id,
    bv.version_number,
    bv.created_at AS version_created_at,
    bem.discovery_method,
    bem.loaded_at,
    bem.mapping_type,
    bem.sigma_threshold,
    bem.critical_sigma,
    bem.used_sigma_threshold,
    bem.used_critical_sigma,
    bem.enable_anomaly_detection,
    bem.anomaly_method,
    bem.is_active,
    bem.skip_reason,
    bem.created_at AS mapping_created_at,
    bem.updated_at AS mapping_updated_at,
    -- Calculated warning bounds
    ROUND((bm.mean_value - (bem.used_sigma_threshold * bm.stddev_value))::NUMERIC, 4) AS warning_lower_bound,
    ROUND((bm.mean_value + (bem.used_sigma_threshold * bm.stddev_value))::NUMERIC, 4) AS warning_upper_bound,
    -- Calculated critical bounds
    ROUND((bm.mean_value - (bem.used_critical_sigma * bm.stddev_value))::NUMERIC, 4) AS critical_lower_bound,
    ROUND((bm.mean_value + (bem.used_critical_sigma * bm.stddev_value))::NUMERIC, 4) AS critical_upper_bound,
    -- Status calculation
    CASE
        WHEN bem.is_active = false THEN 'INACTIVE'
        WHEN bem.skip_reason IS NOT NULL THEN 'SKIPPED'
        ELSE 'ACTIVE'
    END AS status,
    -- Baseline reference for reference queries
    bm.mean_value,
    bm.stddev_value,
    bm.min_value,
    bm.max_value
FROM chaos_platform.baseline_experiment_mapping bem
INNER JOIN chaos_platform.experiments exp 
    ON bem.experiment_id = exp.experiment_id
INNER JOIN chaos_platform.baseline_metrics bm 
    ON bem.metric_id = bm.baseline_id
LEFT JOIN chaos_platform.services svc 
    ON bm.service_id = svc.service_id
LEFT JOIN chaos_platform.baseline_versions bv 
    ON bem.baseline_version_id = bv.baseline_version_id
ORDER BY bem.experiment_id, bem.loaded_at DESC, bm.metric_name;

-- Grant permissions on view
GRANT SELECT ON chaos_platform.v_experiment_baselines TO chaos_app;
GRANT SELECT ON chaos_platform.v_experiment_baselines TO chaos_user;

-- Add comment to view
COMMENT ON VIEW chaos_platform.v_experiment_baselines IS
'Comprehensive audit trail view showing all baselines mapped to experiments, including discovery method, version, thresholds used, and calculated bounds. Enables compliance tracking and baseline usage analysis.';

-- ============================================================================
-- VERIFICATION QUERIES
-- ============================================================================

-- Verify Phase 3 columns were added
-- Expected: 5 rows (baseline_version_id, used_sigma_threshold, used_critical_sigma, discovery_method, loaded_at)
SELECT column_name, data_type, is_nullable 
FROM information_schema.columns
WHERE table_schema = 'chaos_platform'
    AND table_name = 'baseline_experiment_mapping'
    AND column_name IN ('baseline_version_id', 'used_sigma_threshold', 'used_critical_sigma', 'discovery_method', 'loaded_at')
ORDER BY ordinal_position;

-- Verify Phase 3 view was created
-- Expected: 1 row for v_experiment_baselines
SELECT table_name, table_type 
FROM information_schema.tables
WHERE table_schema = 'chaos_platform'
    AND table_name = 'v_experiment_baselines';

-- Verify indexes were created
-- Expected: 5 indexes (3 new Phase 3 indexes + 2 from Phase 2)
SELECT indexname 
FROM pg_indexes
WHERE schemaname = 'chaos_platform'
    AND tablename = 'baseline_experiment_mapping'
ORDER BY indexname;

-- Sample query: Show all baselines loaded in the last 7 days with discovery methods
SELECT 
    bem.mapping_id,
    exp.experiment_title,
    bm.metric_name,
    bem.discovery_method,
    bem.loaded_at,
    bem.used_sigma_threshold,
    bem.is_active
FROM chaos_platform.baseline_experiment_mapping bem
INNER JOIN chaos_platform.experiments exp ON bem.experiment_id = exp.experiment_id
INNER JOIN chaos_platform.baseline_metrics bm ON bem.metric_id = bm.baseline_id
WHERE bem.loaded_at > NOW() - INTERVAL '7 days'
ORDER BY bem.loaded_at DESC
LIMIT 10;

-- Sample query: Show active baselines for a specific experiment (using view)
-- (Replace 1 with actual experiment_id)
SELECT 
    mapping_id,
    metric_name,
    discovery_method,
    warning_lower_bound,
    warning_upper_bound,
    critical_lower_bound,
    critical_upper_bound,
    status
FROM chaos_platform.v_experiment_baselines
WHERE experiment_id = 1
    AND status = 'ACTIVE'
ORDER BY metric_name;

-- ============================================================================
-- COMPLETION MESSAGE
-- ============================================================================

\echo ''
\echo '============================================================================'
\echo 'MIGRATION COMPLETE: Phase 2 & 3 - Baseline Experiment Mapping'
\echo '============================================================================'
\echo ''
\echo 'Phase 2: baseline_experiment_mapping table created'
\echo 'Phase 3: 5 new columns added for audit trail'
\echo 'Phase 3: v_experiment_baselines view created for compliance tracking'
\echo ''
\echo 'New columns:'
\echo '  - baseline_version_id: Track which baseline version was used'
\echo '  - used_sigma_threshold: Actual warning threshold used'
\echo '  - used_critical_sigma: Actual critical threshold used'
\echo '  - discovery_method: How baseline was discovered (system/service/explicit/labels)'
\echo '  - loaded_at: When baseline was loaded'
\echo ''
\echo 'New indexes created for performance:'
\echo '  - idx_baseline_experiment_mapping_version'
\echo '  - idx_baseline_experiment_mapping_discovery_method'
\echo '  - idx_baseline_experiment_mapping_loaded_at'
\echo ''
\echo 'New view: v_experiment_baselines'
\echo '  - 30 columns with calculated thresholds'
\echo '  - Joins experiments, baselines, services, and versions'
\echo '  - Supports compliance and audit requirements'
\echo ''
\echo 'Migration safe to re-run (uses IF NOT EXISTS)'
\echo '============================================================================'
