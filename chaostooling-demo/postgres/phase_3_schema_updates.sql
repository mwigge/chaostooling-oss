-- ============================================================================
-- Phase 3: Database Schema Updates
-- Task 3.1: Add Columns to baseline_experiment_mapping
-- Task 3.2: Create v_experiment_baselines View
-- ============================================================================
-- Date: January 31, 2026
-- Purpose: Add audit trail columns and create view for baseline-experiment tracking
-- ============================================================================

-- ============================================================================
-- TASK 3.1: Add Columns to baseline_experiment_mapping Table
-- ============================================================================

-- These columns track:
-- - baseline_version_id: Which version of the baseline was used
-- - used_sigma_threshold: Actual sigma threshold used for this experiment
-- - used_critical_sigma: Actual critical sigma threshold used
-- - discovery_method: How the baseline was discovered (system, service, explicit, labels)
-- - loaded_at: When the baseline was loaded for this experiment

ALTER TABLE chaos_platform.baseline_experiment_mapping 
ADD COLUMN IF NOT EXISTS baseline_version_id BIGINT 
AFTER metric_id
COMMENT 'Version of the baseline metric used for this mapping';

ALTER TABLE chaos_platform.baseline_experiment_mapping 
ADD COLUMN IF NOT EXISTS used_sigma_threshold NUMERIC(5, 2) DEFAULT 2.0 
COMMENT 'Sigma threshold actually used for this experiment';

ALTER TABLE chaos_platform.baseline_experiment_mapping 
ADD COLUMN IF NOT EXISTS used_critical_sigma NUMERIC(5, 2) DEFAULT 3.0 
COMMENT 'Critical sigma threshold actually used for this experiment';

ALTER TABLE chaos_platform.baseline_experiment_mapping 
ADD COLUMN IF NOT EXISTS discovery_method VARCHAR(50) DEFAULT 'system' 
CHECK (discovery_method IN ('system', 'service', 'explicit', 'labels'))
COMMENT 'How this baseline was discovered: system, service, explicit, or labels';

ALTER TABLE chaos_platform.baseline_experiment_mapping 
ADD COLUMN IF NOT EXISTS loaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP 
COMMENT 'When the baseline was loaded for this experiment';

-- Add foreign key to baseline_versions if it exists
ALTER TABLE chaos_platform.baseline_experiment_mapping
ADD CONSTRAINT fk_baseline_experiment_mapping_version
FOREIGN KEY (baseline_version_id) 
REFERENCES chaos_platform.baseline_versions(baseline_version_id)
ON DELETE SET NULL
ON UPDATE CASCADE;

-- Create indexes on new columns for query performance
CREATE INDEX IF NOT EXISTS idx_baseline_experiment_mapping_version 
ON chaos_platform.baseline_experiment_mapping(baseline_version_id);

CREATE INDEX IF NOT EXISTS idx_baseline_experiment_mapping_discovery_method 
ON chaos_platform.baseline_experiment_mapping(discovery_method);

CREATE INDEX IF NOT EXISTS idx_baseline_experiment_mapping_loaded_at 
ON chaos_platform.baseline_experiment_mapping(loaded_at);

-- Update existing records to have discovery_method = 'system' (default)
UPDATE chaos_platform.baseline_experiment_mapping 
SET discovery_method = 'system' 
WHERE discovery_method IS NULL 
OR discovery_method = '';

-- ============================================================================
-- TASK 3.2: Create v_experiment_baselines View
-- ============================================================================

-- This view provides a comprehensive audit trail showing:
-- - Which baselines were loaded for each experiment
-- - When they were loaded and why (discovery method)
-- - The baseline statistics at the time of the experiment
-- - Whether the mapping is still active

CREATE OR REPLACE VIEW chaos_platform.v_experiment_baselines AS
SELECT 
    bem.mapping_id,
    bem.experiment_id,
    e.title AS experiment_title,
    bem.metric_id,
    bm.metric_name,
    bm.service_name,
    bm.system,
    bem.baseline_version_id,
    bv.version_number,
    bv.version_timestamp AS baseline_collected_at,
    bem.used_sigma_threshold,
    bem.used_critical_sigma,
    bem.discovery_method,
    bem.loaded_at,
    bem.mapping_type,
    bem.enable_anomaly_detection,
    bem.anomaly_method,
    -- Baseline statistics at time of experiment
    bm.mean AS baseline_mean,
    bm.stdev AS baseline_stdev,
    bm.min_value,
    bm.max_value,
    bm.percentile_50,
    bm.percentile_95,
    bm.percentile_99,
    bm.percentile_999,
    bm.upper_bound_2sigma,
    bm.upper_bound_3sigma,
    bm.quality_score,
    -- Calculated thresholds
    (bm.mean - bem.used_sigma_threshold * bm.stdev)::NUMERIC(18, 6) AS warning_lower_bound,
    (bm.mean + bem.used_sigma_threshold * bm.stdev)::NUMERIC(18, 6) AS warning_upper_bound,
    (bm.mean - bem.used_critical_sigma * bm.stdev)::NUMERIC(18, 6) AS critical_lower_bound,
    (bm.mean + bem.used_critical_sigma * bm.stdev)::NUMERIC(18, 6) AS critical_upper_bound,
    -- Status information
    bem.is_active,
    bem.created_at,
    bem.updated_at,
    CASE 
        WHEN bem.is_active THEN 'ACTIVE'
        WHEN bem.skip_reason IS NOT NULL THEN 'SKIPPED'
        ELSE 'INACTIVE'
    END AS mapping_status,
    bem.skip_reason
FROM chaos_platform.baseline_experiment_mapping bem
JOIN chaos_platform.experiments e ON bem.experiment_id = e.experiment_id
JOIN chaos_platform.baseline_metrics bm ON bem.metric_id = bm.metric_id
LEFT JOIN chaos_platform.baseline_versions bv ON bem.baseline_version_id = bv.baseline_version_id
ORDER BY bem.experiment_id, bem.loaded_at DESC, bm.metric_name;

-- Add comment to view
COMMENT ON VIEW chaos_platform.v_experiment_baselines IS 
'Audit trail showing which baselines were loaded for each experiment. 
Tracks discovery method, timing, threshold configuration, and baseline statistics.
Key columns: experiment_id, metric_name, discovery_method, loaded_at, mapping_status.
Used for: experiment analysis, baseline validation, compliance auditing.';

-- Grant permissions to application roles
GRANT SELECT ON chaos_platform.v_experiment_baselines TO chaos_app;
GRANT SELECT ON chaos_platform.v_experiment_baselines TO chaos_user;

-- ============================================================================
-- VERIFICATION QUERIES
-- ============================================================================

-- Verify table columns were added
SELECT column_name, data_type, is_nullable
FROM information_schema.columns
WHERE table_schema = 'chaos_platform'
  AND table_name = 'baseline_experiment_mapping'
ORDER BY ordinal_position;

-- Verify view was created
SELECT table_name, table_type
FROM information_schema.tables
WHERE table_schema = 'chaos_platform'
  AND table_name = 'v_experiment_baselines';

-- Sample query: Show baseline discovery methods used in recent experiments
SELECT 
    discovery_method,
    COUNT(*) as count,
    MAX(loaded_at) as latest_load
FROM chaos_platform.v_experiment_baselines
WHERE loaded_at > CURRENT_TIMESTAMP - INTERVAL '7 days'
GROUP BY discovery_method
ORDER BY count DESC;

-- Sample query: Show all active baselines for a specific experiment
SELECT 
    experiment_id,
    experiment_title,
    metric_name,
    discovery_method,
    baseline_mean,
    baseline_stdev,
    warning_lower_bound,
    warning_upper_bound,
    loaded_at
FROM chaos_platform.v_experiment_baselines
WHERE experiment_id = 1
  AND is_active = true
ORDER BY metric_name;
