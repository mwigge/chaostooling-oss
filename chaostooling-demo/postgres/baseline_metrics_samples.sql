-- ============================================================================
-- BASELINE METRICS: SAMPLE DATA & QUERIES
-- ============================================================================
-- This file demonstrates:
-- 1. Sample INSERT statements for PostgreSQL, MySQL, MongoDB baselines
-- 2. Sample SELECT queries showing how experiments query this data
-- 3. Common patterns for baseline validation and anomaly detection
-- ============================================================================

-- ============================================================================
-- SAMPLE DATA: PostgreSQL Baselines
-- ============================================================================

-- Insert PostgreSQL service (if not exists)
INSERT INTO chaos_platform.services (service_name, description, environment, team_name)
VALUES ('postgres', 'PostgreSQL Database Service', 'production', 'Infrastructure')
ON CONFLICT (service_name) DO NOTHING;

-- Insert PostgreSQL baseline metrics - Connections
INSERT INTO chaos_platform.baseline_metrics (
    service_name, metric_name, database_system, metric_type,
    metric_description, unit, data_source, valid_min, valid_max,
    mean_value, median_value, stddev_value, min_value, max_value,
    p50, p75, p90, p95, p99,
    lower_bound_2sigma, upper_bound_2sigma, upper_bound_3sigma,
    sample_count, data_completeness_percent, is_active
) VALUES (
    'postgres', 'postgresql_backends', 'postgresql', 'gauge',
    'Number of active backend connections to PostgreSQL',
    'connections', 'prometheus',
    0, 1000,
    45.3, 44.0, 8.2, 20, 92,
    44.0, 50.0, 58.0, 62.0, 75.0,
    28.9, 61.7, 69.9,
    14400, 99.8, true
)
ON CONFLICT (service_name, metric_name, database_system) 
DO UPDATE SET 
    mean_value = EXCLUDED.mean_value,
    stddev_value = EXCLUDED.stddev_value,
    updated_at = CURRENT_TIMESTAMP;

-- Insert PostgreSQL baseline metrics - Query Latency
INSERT INTO chaos_platform.baseline_metrics (
    service_name, metric_name, database_system, metric_type,
    metric_description, unit, data_source, valid_min, valid_max,
    mean_value, median_value, stddev_value, min_value, max_value,
    p50, p75, p90, p95, p99,
    lower_bound_2sigma, upper_bound_2sigma, upper_bound_3sigma,
    sample_count, data_completeness_percent, is_active
) VALUES (
    'postgres', 'postgresql_query_latency_ms', 'postgresql', 'summary',
    'P99 query latency measured at connection pool level',
    'ms', 'prometheus',
    1, 5000,
    125.4, 112.0, 45.2, 18, 450,
    112.0, 155.0, 195.0, 215.0, 410.0,
    34.8, 216.0, 261.2,
    14400, 99.8, true
)
ON CONFLICT (service_name, metric_name, database_system) 
DO UPDATE SET 
    mean_value = EXCLUDED.mean_value,
    stddev_value = EXCLUDED.stddev_value,
    updated_at = CURRENT_TIMESTAMP;

-- Insert PostgreSQL baseline metrics - Transaction Rate
INSERT INTO chaos_platform.baseline_metrics (
    service_name, metric_name, database_system, metric_type,
    metric_description, unit, data_source, valid_min, valid_max,
    mean_value, median_value, stddev_value, min_value, max_value,
    p50, p75, p90, p95, p99,
    lower_bound_2sigma, upper_bound_2sigma, upper_bound_3sigma,
    sample_count, data_completeness_percent, is_active
) VALUES (
    'postgres', 'postgresql_transactions_per_sec', 'postgresql', 'counter',
    'Committed transactions per second',
    'tx/sec', 'prometheus',
    0, 50000,
    2845.6, 2850.0, 320.8, 1200, 4250,
    2850.0, 3100.0, 3400.0, 3600.0, 4200.0,
    2203.6, 3487.6, 3808.4,
    14400, 99.8, true
)
ON CONFLICT (service_name, metric_name, database_system) 
DO UPDATE SET 
    mean_value = EXCLUDED.mean_value,
    stddev_value = EXCLUDED.stddev_value,
    updated_at = CURRENT_TIMESTAMP;

-- Insert PostgreSQL baseline metrics - Cache Hit Ratio
INSERT INTO chaos_platform.baseline_metrics (
    service_name, metric_name, database_system, metric_type,
    metric_description, unit, data_source, valid_min, valid_max,
    mean_value, median_value, stddev_value, min_value, max_value,
    p50, p75, p90, p95, p99,
    lower_bound_2sigma, upper_bound_2sigma, upper_bound_3sigma,
    sample_count, data_completeness_percent, is_active
) VALUES (
    'postgres', 'postgresql_cache_hit_ratio', 'postgresql', 'gauge',
    'Buffer cache hit ratio (0-1 scale)',
    'ratio', 'prometheus',
    0, 1,
    0.945, 0.95, 0.02, 0.85, 0.99,
    0.95, 0.96, 0.97, 0.98, 0.99,
    0.905, 0.985, 1.005,
    14400, 99.8, true
)
ON CONFLICT (service_name, metric_name, database_system) 
DO UPDATE SET 
    mean_value = EXCLUDED.mean_value,
    stddev_value = EXCLUDED.stddev_value,
    updated_at = CURRENT_TIMESTAMP;

-- ============================================================================
-- SAMPLE DATA: MySQL Baselines
-- ============================================================================

-- Insert MySQL service
INSERT INTO chaos_platform.services (service_name, description, environment, team_name)
VALUES ('mysql', 'MySQL Database Service', 'production', 'Infrastructure')
ON CONFLICT (service_name) DO NOTHING;

-- Insert MySQL baseline metrics - Connections
INSERT INTO chaos_platform.baseline_metrics (
    service_name, metric_name, database_system, metric_type,
    metric_description, unit, data_source, valid_min, valid_max,
    mean_value, median_value, stddev_value, min_value, max_value,
    p50, p75, p90, p95, p99,
    lower_bound_2sigma, upper_bound_2sigma, upper_bound_3sigma,
    sample_count, data_completeness_percent, is_active
) VALUES (
    'mysql', 'mysql_connections', 'mysql', 'gauge',
    'Number of active MySQL connections',
    'connections', 'prometheus',
    0, 500,
    38.7, 37.0, 6.5, 15, 75,
    37.0, 42.0, 50.0, 54.0, 68.0,
    25.7, 51.7, 58.2,
    14400, 99.5, true
)
ON CONFLICT (service_name, metric_name, database_system) 
DO UPDATE SET 
    mean_value = EXCLUDED.mean_value,
    stddev_value = EXCLUDED.stddev_value,
    updated_at = CURRENT_TIMESTAMP;

-- Insert MySQL baseline metrics - Query Latency
INSERT INTO chaos_platform.baseline_metrics (
    service_name, metric_name, database_system, metric_type,
    metric_description, unit, data_source, valid_min, valid_max,
    mean_value, median_value, stddev_value, min_value, max_value,
    p50, p75, p90, p95, p99,
    lower_bound_2sigma, upper_bound_2sigma, upper_bound_3sigma,
    sample_count, data_completeness_percent, is_active
) VALUES (
    'mysql', 'mysql_query_latency_ms', 'mysql', 'summary',
    'P99 query latency',
    'ms', 'prometheus',
    1, 3000,
    87.3, 78.0, 35.8, 12, 380,
    78.0, 110.0, 145.0, 165.0, 320.0,
    15.7, 158.9, 194.7,
    14400, 99.5, true
)
ON CONFLICT (service_name, metric_name, database_system) 
DO UPDATE SET 
    mean_value = EXCLUDED.mean_value,
    stddev_value = EXCLUDED.stddev_value,
    updated_at = CURRENT_TIMESTAMP;

-- ============================================================================
-- SAMPLE DATA: MongoDB Baselines
-- ============================================================================

-- Insert MongoDB service
INSERT INTO chaos_platform.services (service_name, description, environment, team_name)
VALUES ('mongodb', 'MongoDB Database Service', 'production', 'Infrastructure')
ON CONFLICT (service_name) DO NOTHING;

-- Insert MongoDB baseline metrics - Connections
INSERT INTO chaos_platform.baseline_metrics (
    service_name, metric_name, database_system, metric_type,
    metric_description, unit, data_source, valid_min, valid_max,
    mean_value, median_value, stddev_value, min_value, max_value,
    p50, p75, p90, p95, p99,
    lower_bound_2sigma, upper_bound_2sigma, upper_bound_3sigma,
    sample_count, data_completeness_percent, is_active
) VALUES (
    'mongodb', 'mongodb_connections', 'mongodb', 'gauge',
    'Number of current connections to MongoDB',
    'connections', 'prometheus',
    0, 2000,
    156.4, 155.0, 22.3, 80, 250,
    155.0, 170.0, 195.0, 210.0, 245.0,
    111.8, 200.0, 222.3,
    14400, 99.7, true
)
ON CONFLICT (service_name, metric_name, database_system) 
DO UPDATE SET 
    mean_value = EXCLUDED.mean_value,
    stddev_value = EXCLUDED.stddev_value,
    updated_at = CURRENT_TIMESTAMP;

-- Insert MongoDB baseline metrics - Operation Latency
INSERT INTO chaos_platform.baseline_metrics (
    service_name, metric_name, database_system, metric_type,
    metric_description, unit, data_source, valid_min, valid_max,
    mean_value, median_value, stddev_value, min_value, max_value,
    p50, p75, p90, p95, p99,
    lower_bound_2sigma, upper_bound_2sigma, upper_bound_3sigma,
    sample_count, data_completeness_percent, is_active
) VALUES (
    'mongodb', 'mongodb_operation_latency_ms', 'mongodb', 'summary',
    'P99 operation latency for read/write operations',
    'ms', 'prometheus',
    1, 2000,
    95.2, 88.0, 42.1, 5, 420,
    88.0, 125.0, 160.0, 185.0, 380.0,
    10.0, 180.4, 222.5,
    14400, 99.7, true
)
ON CONFLICT (service_name, metric_name, database_system) 
DO UPDATE SET 
    mean_value = EXCLUDED.mean_value,
    stddev_value = EXCLUDED.stddev_value,
    updated_at = CURRENT_TIMESTAMP;

-- ============================================================================
-- SAMPLE DATA: Cassandra Baselines
-- ============================================================================

-- Insert Cassandra service
INSERT INTO chaos_platform.services (service_name, description, environment, team_name)
VALUES ('cassandra', 'Apache Cassandra Database Service', 'production', 'Infrastructure')
ON CONFLICT (service_name) DO NOTHING;

-- Insert Cassandra baseline metrics
INSERT INTO chaos_platform.baseline_metrics (
    service_name, metric_name, database_system, metric_type,
    metric_description, unit, data_source, valid_min, valid_max,
    mean_value, median_value, stddev_value, min_value, max_value,
    p50, p75, p90, p95, p99,
    lower_bound_2sigma, upper_bound_2sigma, upper_bound_3sigma,
    sample_count, data_completeness_percent, is_active
) VALUES (
    'cassandra', 'cassandra_write_latency_p99_ms', 'cassandra', 'summary',
    'P99 write latency',
    'ms', 'prometheus',
    1, 1000,
    42.7, 38.0, 18.5, 8, 180,
    38.0, 55.0, 75.0, 85.0, 165.0,
    5.7, 79.7, 98.2,
    14400, 99.6, true
)
ON CONFLICT (service_name, metric_name, database_system) 
DO UPDATE SET 
    mean_value = EXCLUDED.mean_value,
    stddev_value = EXCLUDED.stddev_value,
    updated_at = CURRENT_TIMESTAMP;

-- ============================================================================
-- SAMPLE DATA: Baseline Versions (Audit Trail)
-- ============================================================================

-- Create baseline version for PostgreSQL connections
INSERT INTO chaos_platform.baseline_versions (
    metric_id,
    version_number,
    version_timestamp,
    data_collection_start,
    data_collection_end,
    collection_duration_days,
    datasource_type,
    datasource_name,
    datasource_query,
    aggregation_method,
    time_bucketing,
    interpolation_method,
    status,
    validation_status,
    validation_timestamp,
    quality_score,
    confidence_level,
    total_samples,
    valid_samples,
    excluded_samples,
    exclusion_reason,
    mean_value,
    stddev_value,
    p50,
    p95,
    p99,
    created_by,
    notes,
    tags
)
SELECT 
    metric_id,
    1,
    CURRENT_TIMESTAMP - INTERVAL '2 days',
    CURRENT_TIMESTAMP - INTERVAL '14 days',
    CURRENT_TIMESTAMP - INTERVAL '2 days',
    14,
    'prometheus',
    'postgresql_backends',
    'postgres_exporter_backends{job="postgres"}',
    'average',
    '1m',
    'forward_fill',
    'validated',
    'passed',
    CURRENT_TIMESTAMP - INTERVAL '1 day',
    98.5,
    99.0,
    20160,
    20045,
    115,
    'outliers removed (> 3 sigma)',
    45.3,
    8.2,
    44.0,
    62.0,
    75.0,
    'steady-state-analyzer',
    'Initial baseline from 2024-12-01 to 2024-12-15. High confidence level.',
    ARRAY['production', 'validated', 'v1']
FROM chaos_platform.baseline_metrics
WHERE service_name = 'postgres' AND metric_name = 'postgresql_backends'
ON CONFLICT (metric_id, version_number) DO NOTHING;

-- ============================================================================
-- SAMPLE DATA: Baseline Statistics by Phase
-- ============================================================================

-- Get the baseline_version_id to reference (using subquery)
INSERT INTO chaos_platform.baseline_statistics (
    metric_id,
    baseline_version_id,
    phase,
    analysis_period_days,
    data_collection_start,
    data_collection_end,
    mean_value,
    median_value,
    stddev_value,
    variance,
    min_value,
    max_value,
    range_value,
    p50,
    p75,
    p90,
    p95,
    p99,
    q1,
    q2,
    q3,
    iqr,
    lower_bound_2sigma,
    upper_bound_2sigma,
    upper_bound_3sigma,
    skewness,
    kurtosis,
    is_normal_distribution,
    sample_count,
    data_completeness_percent
)
SELECT 
    bm.metric_id,
    bv.baseline_version_id,
    'normal_operation'::chaos_platform.baseline_phase_enum,
    14,
    CURRENT_TIMESTAMP - INTERVAL '14 days',
    CURRENT_TIMESTAMP - INTERVAL '2 days',
    45.3, 44.0, 8.2, 67.24, 20, 92, 72,
    44.0, 50.0, 58.0, 62.0, 75.0,
    39.0, 44.0, 51.0, 12.0,
    28.9, 61.7, 69.9,
    0.25, 0.15, true,
    20045, 99.8
FROM chaos_platform.baseline_metrics bm
CROSS JOIN chaos_platform.baseline_versions bv
WHERE bm.service_name = 'postgres' AND bm.metric_name = 'postgresql_backends'
  AND bv.metric_id = bm.metric_id AND bv.version_number = 1
ON CONFLICT (metric_id, baseline_version_id, phase) DO NOTHING;

-- ============================================================================
-- SAMPLE DATA: Link Experiments to Baselines
-- ============================================================================

-- Get experiment_id for mcp-test-postgres-pool-exhaustion and link to baselines
-- This assumes the experiment exists in the database
INSERT INTO chaos_platform.baseline_experiment_mapping (
    experiment_id,
    metric_id,
    mapping_type,
    sigma_threshold,
    critical_sigma,
    enable_anomaly_detection,
    anomaly_method,
    is_active
)
SELECT 
    e.experiment_id,
    bm.metric_id,
    'threshold_check'::VARCHAR,
    2.0,
    3.0,
    true,
    'zscore'::VARCHAR,
    true
FROM chaos_platform.experiments e
CROSS JOIN chaos_platform.baseline_metrics bm
WHERE e.experiment_name LIKE '%pool%'
  AND bm.service_name = 'postgres'
  AND bm.database_system = 'postgresql'
ON CONFLICT (experiment_id, metric_id) DO NOTHING;

-- ============================================================================
-- SAMPLE QUERIES
-- ============================================================================

-- QUERY 1: Get baseline for a specific metric (used by experiments)
-- Shows how to retrieve baseline thresholds for anomaly detection
SELECT 
    metric_name,
    service_name,
    database_system,
    mean_value,
    stddev_value,
    lower_bound_2sigma,
    upper_bound_2sigma,
    upper_bound_3sigma,
    p95,
    p99
FROM chaos_platform.baseline_metrics
WHERE service_name = 'postgres' 
  AND metric_name = 'postgresql_backends'
  AND is_active = true;

-- QUERY 2: Get all active baselines for a database system
-- Shows all metrics monitored for PostgreSQL
SELECT 
    metric_name,
    metric_type,
    unit,
    mean_value,
    stddev_value,
    p99,
    sample_count,
    last_updated
FROM chaos_platform.baseline_metrics
WHERE service_name = 'postgres' 
  AND database_system = 'postgresql'
  AND is_active = true
ORDER BY metric_name;

-- QUERY 3: Get anomaly detection thresholds for an experiment
-- Shows how experiments determine what constitutes a deviation
SELECT 
    bem.experiment_id,
    e.experiment_name,
    bm.metric_name,
    bm.mean_value,
    bm.stddev_value,
    bem.sigma_threshold,
    (bm.mean_value + bem.sigma_threshold * bm.stddev_value) as upper_threshold,
    (bm.mean_value - bem.sigma_threshold * bm.stddev_value) as lower_threshold,
    bem.critical_sigma,
    (bm.mean_value + bem.critical_sigma * bm.stddev_value) as critical_upper,
    (bm.mean_value - bem.critical_sigma * bm.stddev_value) as critical_lower
FROM chaos_platform.baseline_experiment_mapping bem
JOIN chaos_platform.experiments e ON bem.experiment_id = e.experiment_id
JOIN chaos_platform.baseline_metrics bm ON bem.metric_id = bm.metric_id
WHERE bem.is_active = true
  AND e.experiment_name LIKE '%pool%'
ORDER BY e.experiment_name, bm.metric_name;

-- QUERY 4: Compare baselines across database systems (PostgreSQL vs MySQL)
-- Shows comparative analysis of similar metrics across systems
SELECT 
    bm.service_name,
    bm.database_system,
    bm.metric_name,
    bm.mean_value,
    bm.stddev_value,
    bm.p95,
    bm.p99
FROM chaos_platform.baseline_metrics bm
WHERE (
    (bm.service_name = 'postgres' AND bm.metric_name = 'postgresql_query_latency_ms')
    OR
    (bm.service_name = 'mysql' AND bm.metric_name = 'mysql_query_latency_ms')
)
AND bm.is_active = true
ORDER BY bm.database_system, bm.metric_name;

-- QUERY 5: Get baseline statistics by operational phase
-- Shows how metrics differ between normal, peak, and low-load periods
SELECT 
    bm.metric_name,
    bs.phase,
    bs.mean_value,
    bs.stddev_value,
    bs.p50,
    bs.p95,
    bs.p99,
    bs.sample_count,
    bs.data_collection_start,
    bs.data_collection_end
FROM chaos_platform.baseline_statistics bs
JOIN chaos_platform.baseline_metrics bm ON bs.metric_id = bm.metric_id
WHERE bm.service_name = 'postgres'
  AND bm.database_system = 'postgresql'
ORDER BY bm.metric_name, bs.phase;

-- QUERY 6: Check baseline versions and supersession
-- Shows version history and when baselines were updated
SELECT 
    bm.metric_name,
    bv.version_number,
    bv.status,
    bv.quality_score,
    bv.version_timestamp,
    bv.data_collection_start,
    bv.data_collection_end,
    bv.total_samples,
    bv.mean_value,
    bv.stddev_value,
    bv.p99
FROM chaos_platform.baseline_versions bv
JOIN chaos_platform.baseline_metrics bm ON bv.metric_id = bm.metric_id
WHERE bm.service_name = 'postgres'
  AND bm.database_system = 'postgresql'
ORDER BY bm.metric_name, bv.version_number DESC;

-- QUERY 7: Identify metrics with low data completeness
-- Shows which baselines may need refresh due to data quality issues
SELECT 
    metric_name,
    service_name,
    database_system,
    data_completeness_percent,
    sample_count,
    last_updated
FROM chaos_platform.baseline_metrics
WHERE data_completeness_percent < 95
  AND is_active = true
ORDER BY data_completeness_percent ASC;

-- QUERY 8: Get metrics monitored by active experiments
-- Shows which baselines are actively used in experiments
SELECT 
    DISTINCT bm.metric_name,
    bm.service_name,
    bm.database_system,
    COUNT(bem.experiment_id) as experiment_count,
    bm.mean_value,
    bm.stddev_value
FROM chaos_platform.baseline_metrics bm
LEFT JOIN chaos_platform.baseline_experiment_mapping bem ON bm.metric_id = bem.metric_id
WHERE bem.is_active = true
GROUP BY bm.metric_id, bm.metric_name, bm.service_name, bm.database_system, bm.mean_value, bm.stddev_value
ORDER BY experiment_count DESC, bm.service_name, bm.metric_name;

-- QUERY 9: Anomaly Detection - Find metrics that deviate from baseline
-- Example: Query metric snapshots and compare to baseline
SELECT 
    ms.snapshot_id,
    ms.run_id,
    ms.phase,
    bm.metric_name,
    ms.query_latency_ms as actual_value,
    bm.mean_value as baseline_mean,
    bm.stddev_value,
    ROUND((ms.query_latency_ms - bm.mean_value) / bm.stddev_value, 2) as deviation_sigma,
    CASE 
        WHEN ABS((ms.query_latency_ms - bm.mean_value) / bm.stddev_value) > 3 THEN 'CRITICAL'
        WHEN ABS((ms.query_latency_ms - bm.mean_value) / bm.stddev_value) > 2 THEN 'WARNING'
        ELSE 'NORMAL'
    END as anomaly_level
FROM chaos_platform.metric_snapshots ms
JOIN chaos_platform.experiments e ON (SELECT experiment_id FROM chaos_platform.experiment_runs WHERE run_id = ms.run_id) = e.experiment_id
JOIN chaos_platform.baseline_metrics bm ON ms.service_id = (SELECT service_id FROM chaos_platform.services WHERE service_name = bm.service_name)
WHERE ms.query_latency_ms IS NOT NULL
  AND bm.metric_name = 'postgresql_query_latency_ms'
  AND ms.captured_at > CURRENT_TIMESTAMP - INTERVAL '1 day'
HAVING ABS((ms.query_latency_ms - bm.mean_value) / bm.stddev_value) > 2
ORDER BY deviation_sigma DESC
LIMIT 20;

-- QUERY 10: Baseline Correlation Analysis
-- Shows which metrics are correlated (useful for RCA)
SELECT 
    bm1.metric_name as metric_1,
    bm2.metric_name as metric_2,
    bc.pearson_correlation,
    bc.spearman_correlation,
    bc.is_correlated,
    bc.phase,
    bc.lag_seconds,
    bc.sample_count
FROM chaos_platform.baseline_correlations bc
JOIN chaos_platform.baseline_metrics bm1 ON bc.metric_id_1 = bm1.metric_id
JOIN chaos_platform.baseline_metrics bm2 ON bc.metric_id_2 = bm2.metric_id
WHERE bm1.service_name = 'postgres'
  AND bc.is_correlated = true
  AND bc.phase = 'normal_operation'
ORDER BY ABS(bc.pearson_correlation) DESC;

-- ============================================================================
-- PERFORMANCE TESTING QUERIES
-- ============================================================================

-- QUERY 11: Experiment query - Get baselines for threshold checking (OPTIMIZED)
-- This is the primary query pattern used during experiment execution
-- Should complete in < 10ms with proper indexes
EXPLAIN ANALYZE
SELECT 
    metric_name,
    mean_value,
    stddev_value,
    upper_bound_2sigma,
    upper_bound_3sigma
FROM chaos_platform.baseline_metrics
WHERE service_name = 'postgres' 
  AND metric_name IN ('postgresql_backends', 'postgresql_query_latency_ms')
  AND is_active = true;

-- QUERY 12: Batch baseline retrieval for multiple experiments
-- Shows efficient pattern for loading multiple baselines
EXPLAIN ANALYZE
SELECT 
    bm.metric_id,
    bm.metric_name,
    bm.service_name,
    bm.database_system,
    bm.mean_value,
    bm.stddev_value,
    bem.mapping_type,
    bem.sigma_threshold
FROM chaos_platform.baseline_metrics bm
LEFT JOIN chaos_platform.baseline_experiment_mapping bem ON bm.metric_id = bem.metric_id
WHERE bm.is_active = true
  AND bm.database_system = 'postgresql'
ORDER BY bm.service_name, bm.metric_name;

