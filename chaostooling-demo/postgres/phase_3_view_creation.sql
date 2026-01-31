-- ============================================================================
-- Phase 3: Create Audit Trail View - Corrected Version
-- ============================================================================
-- This view supports baseline usage tracking without depending on
-- baseline_versions table (which may not exist yet).
-- ============================================================================

DROP VIEW IF EXISTS chaos_platform.v_experiment_baselines CASCADE;

CREATE VIEW chaos_platform.v_experiment_baselines AS
SELECT
    bem.mapping_id,
    bem.experiment_id,
    exp.experiment_name,
    exp.experiment_file,
    exp.description AS experiment_description,
    bem.metric_id,
    bm.metric_name,
    bm.baseline_id,
    svc.service_name,
    bem.baseline_version_id,
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
    -- Baseline reference
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
ORDER BY bem.experiment_id, bem.loaded_at DESC, bm.metric_name;

-- Grant permissions on view
GRANT SELECT ON chaos_platform.v_experiment_baselines TO chaos_app;
GRANT SELECT ON chaos_platform.v_experiment_baselines TO chaos_user;

-- Add comment to view
COMMENT ON VIEW chaos_platform.v_experiment_baselines IS
'Comprehensive audit trail view showing all baselines mapped to experiments, including discovery method, version, thresholds used, and calculated bounds. Enables compliance tracking and baseline usage analysis.';

\echo 'Phase 3 view v_experiment_baselines created successfully!'
