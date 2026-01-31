-- ============================================================================
-- INTEGRATION GUIDE: Adding Baseline Metrics Schema to init-chaos-platform.sql
-- ============================================================================
-- This file shows how to integrate the new baseline metrics schema into
-- the existing chaos_platform database initialization script.
-- ============================================================================

/*
================================================================================
INTEGRATION INSTRUCTIONS
================================================================================

The baseline metrics schema is provided as separate SQL files for clarity:
1. baseline_metrics_schema.sql - CREATE TABLE and ENUM statements
2. baseline_metrics_samples.sql - Sample INSERT and SELECT statements
3. baseline_metrics_indexes.sql - Index strategy and performance notes
4. baseline_metrics_README.md - Complete documentation

TO INTEGRATE:

Option A: Include the files directly in init-chaos-platform.sql
-----------
1. Copy CREATE TABLE statements from baseline_metrics_schema.sql
2. Add after the existing baseline_metrics table (around line 50)
3. Ensure all ENUM types are created first

Option B: Source the files separately during initialization
-----------
-- In init-chaos-platform.sql, add:
\i baseline_metrics_schema.sql
\i baseline_metrics_samples.sql
\i baseline_metrics_indexes.sql

Option C: Migrate from existing baseline_metrics table
-----------
-- The existing baseline_metrics table will be extended with new columns
-- See "MIGRATION" section below

================================================================================
MINIMAL INTEGRATION: Required SQL Additions
================================================================================

This is the MINIMUM SQL needed to add to init-chaos-platform.sql:

*/

-- Add ENUM types if not already present
CREATE TYPE IF NOT EXISTS chaos_platform.metric_type_enum AS ENUM (
    'gauge', 'counter', 'histogram', 'summary', 'derived'
);

CREATE TYPE IF NOT EXISTS chaos_platform.database_system_enum AS ENUM (
    'postgresql', 'mysql', 'mongodb', 'cassandra', 'redis',
    'elasticsearch', 'dynamodb', 'oracle', 'mariadb', 'couchdb',
    'neo4j', 'influxdb', 'other'
);

CREATE TYPE IF NOT EXISTS chaos_platform.baseline_phase_enum AS ENUM (
    'normal_operation', 'peak_load', 'low_load', 'failure_recovery', 'maintenance_window'
);

CREATE TYPE IF NOT EXISTS chaos_platform.baseline_status_enum AS ENUM (
    'collecting', 'processing', 'validated', 'superseded', 'failed', 'deprecated'
);

-- Baseline Statistics Table
CREATE TABLE IF NOT EXISTS chaos_platform.baseline_statistics (
    statistic_id BIGSERIAL PRIMARY KEY,
    metric_id BIGINT NOT NULL,
    baseline_version_id BIGINT NOT NULL,
    phase chaos_platform.baseline_phase_enum DEFAULT 'normal_operation',
    analysis_period_days INTEGER DEFAULT 14,
    data_collection_start TIMESTAMP NOT NULL,
    data_collection_end TIMESTAMP NOT NULL,
    mean_value NUMERIC(18, 6),
    median_value NUMERIC(18, 6),
    stddev_value NUMERIC(18, 6),
    variance NUMERIC(18, 6),
    min_value NUMERIC(18, 6),
    max_value NUMERIC(18, 6),
    range_value NUMERIC(18, 6),
    p1 NUMERIC(18, 6),
    p5 NUMERIC(18, 6),
    p25 NUMERIC(18, 6),
    p50 NUMERIC(18, 6),
    p75 NUMERIC(18, 6),
    p90 NUMERIC(18, 6),
    p95 NUMERIC(18, 6),
    p99 NUMERIC(18, 6),
    p999 NUMERIC(18, 6),
    p9999 NUMERIC(18, 6),
    q1 NUMERIC(18, 6),
    q2 NUMERIC(18, 6),
    q3 NUMERIC(18, 6),
    iqr NUMERIC(18, 6),
    lower_bound_1sigma NUMERIC(18, 6),
    upper_bound_1sigma NUMERIC(18, 6),
    lower_bound_2sigma NUMERIC(18, 6),
    upper_bound_2sigma NUMERIC(18, 6),
    lower_bound_3sigma NUMERIC(18, 6),
    upper_bound_3sigma NUMERIC(18, 6),
    skewness NUMERIC(10, 4),
    kurtosis NUMERIC(10, 4),
    is_normal_distribution BOOLEAN,
    sample_count BIGINT,
    data_completeness_percent NUMERIC(5, 2),
    outlier_count INTEGER,
    zero_value_count BIGINT,
    null_value_count BIGINT,
    histogram_buckets JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(metric_id, baseline_version_id, phase)
);

CREATE INDEX IF NOT EXISTS idx_baseline_statistics_metric ON chaos_platform.baseline_statistics(metric_id);
CREATE INDEX IF NOT EXISTS idx_baseline_statistics_phase ON chaos_platform.baseline_statistics(phase);
CREATE INDEX IF NOT EXISTS idx_baseline_statistics_window ON chaos_platform.baseline_statistics(data_collection_start, data_collection_end);

-- Baseline Versions Table
CREATE TABLE IF NOT EXISTS chaos_platform.baseline_versions (
    baseline_version_id BIGSERIAL PRIMARY KEY,
    metric_id BIGINT NOT NULL,
    version_number INTEGER NOT NULL,
    version_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    data_collection_start TIMESTAMP NOT NULL,
    data_collection_end TIMESTAMP NOT NULL,
    collection_duration_days INTEGER,
    datasource_type VARCHAR(100),
    datasource_name VARCHAR(255),
    datasource_query TEXT,
    aggregation_method VARCHAR(100),
    time_bucketing VARCHAR(100),
    interpolation_method VARCHAR(100),
    status chaos_platform.baseline_status_enum DEFAULT 'processing',
    validation_status VARCHAR(50),
    validation_timestamp TIMESTAMP,
    quality_score NUMERIC(5, 2),
    confidence_level NUMERIC(5, 2),
    total_samples BIGINT,
    valid_samples BIGINT,
    excluded_samples BIGINT,
    exclusion_reason TEXT,
    mean_value NUMERIC(18, 6),
    stddev_value NUMERIC(18, 6),
    p50 NUMERIC(18, 6),
    p95 NUMERIC(18, 6),
    p99 NUMERIC(18, 6),
    superseded_by BIGINT,
    superseded_at TIMESTAMP,
    supersession_reason TEXT,
    created_by VARCHAR(255) DEFAULT 'system',
    notes TEXT,
    tags TEXT[],
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(metric_id, version_number)
);

CREATE INDEX IF NOT EXISTS idx_baseline_versions_metric ON chaos_platform.baseline_versions(metric_id);
CREATE INDEX IF NOT EXISTS idx_baseline_versions_status ON chaos_platform.baseline_versions(status);
CREATE INDEX IF NOT EXISTS idx_baseline_versions_timestamp ON chaos_platform.baseline_versions(version_timestamp);

-- Baseline Correlations Table
CREATE TABLE IF NOT EXISTS chaos_platform.baseline_correlations (
    correlation_id BIGSERIAL PRIMARY KEY,
    metric_id_1 BIGINT NOT NULL,
    metric_id_2 BIGINT NOT NULL,
    pearson_correlation NUMERIC(5, 4),
    spearman_correlation NUMERIC(5, 4),
    is_correlated BOOLEAN,
    metric_1_leads BOOLEAN,
    lead_time_seconds INTEGER,
    phase chaos_platform.baseline_phase_enum DEFAULT 'normal_operation',
    analysis_period_start TIMESTAMP,
    analysis_period_end TIMESTAMP,
    sample_count BIGINT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(metric_id_1, metric_id_2, phase)
);

CREATE INDEX IF NOT EXISTS idx_baseline_correlations_metrics ON chaos_platform.baseline_correlations(metric_id_1, metric_id_2);

-- Baseline Anomalies Table
CREATE TABLE IF NOT EXISTS chaos_platform.baseline_anomalies (
    anomaly_id BIGSERIAL PRIMARY KEY,
    metric_id BIGINT NOT NULL,
    baseline_version_id BIGINT NOT NULL,
    anomaly_type VARCHAR(100),
    severity VARCHAR(50),
    anomaly_start TIMESTAMP NOT NULL,
    anomaly_end TIMESTAMP,
    duration_seconds INTEGER,
    deviation_sigma NUMERIC(10, 4),
    expected_value NUMERIC(18, 6),
    actual_value NUMERIC(18, 6),
    root_cause VARCHAR(255),
    root_cause_description TEXT,
    is_resolved BOOLEAN DEFAULT false,
    resolution_timestamp TIMESTAMP,
    resolution_notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_baseline_anomalies_metric ON chaos_platform.baseline_anomalies(metric_id);
CREATE INDEX IF NOT EXISTS idx_baseline_anomalies_time ON chaos_platform.baseline_anomalies(anomaly_start);

-- Baseline Experiment Mapping Table
CREATE TABLE IF NOT EXISTS chaos_platform.baseline_experiment_mapping (
    mapping_id BIGSERIAL PRIMARY KEY,
    experiment_id INTEGER NOT NULL REFERENCES chaos_platform.experiments(experiment_id),
    metric_id BIGINT NOT NULL,
    mapping_type VARCHAR(100),
    sigma_threshold NUMERIC(5, 2) DEFAULT 2.0,
    critical_sigma NUMERIC(5, 2) DEFAULT 3.0,
    enable_anomaly_detection BOOLEAN DEFAULT true,
    anomaly_method VARCHAR(100),
    is_active BOOLEAN DEFAULT true,
    skip_reason VARCHAR(255),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(experiment_id, metric_id)
);

CREATE INDEX IF NOT EXISTS idx_baseline_experiment_mapping_experiment ON chaos_platform.baseline_experiment_mapping(experiment_id);
CREATE INDEX IF NOT EXISTS idx_baseline_experiment_mapping_metric ON chaos_platform.baseline_experiment_mapping(metric_id);

-- Update baseline_metrics table to add new columns
ALTER TABLE chaos_platform.baseline_metrics ADD COLUMN IF NOT EXISTS database_system chaos_platform.database_system_enum DEFAULT 'postgresql';
ALTER TABLE chaos_platform.baseline_metrics ADD COLUMN IF NOT EXISTS metric_type chaos_platform.metric_type_enum DEFAULT 'gauge';
ALTER TABLE chaos_platform.baseline_metrics ADD COLUMN IF NOT EXISTS current_baseline_version_id BIGINT;

-- Update UNIQUE constraint to include database_system
ALTER TABLE chaos_platform.baseline_metrics DROP CONSTRAINT IF EXISTS baseline_metrics_service_id_metric_name_analysis_date_key;
ALTER TABLE chaos_platform.baseline_metrics ADD UNIQUE(service_name, metric_name, database_system);

-- Add foreign keys
ALTER TABLE chaos_platform.baseline_metrics
ADD CONSTRAINT IF NOT EXISTS fk_baseline_metrics_current_version
FOREIGN KEY (current_baseline_version_id)
REFERENCES chaos_platform.baseline_versions(baseline_version_id)
ON DELETE SET NULL;

ALTER TABLE chaos_platform.baseline_statistics
ADD CONSTRAINT IF NOT EXISTS fk_baseline_statistics_metric
FOREIGN KEY (metric_id)
REFERENCES chaos_platform.baseline_metrics(metric_id)
ON DELETE CASCADE;

ALTER TABLE chaos_platform.baseline_statistics
ADD CONSTRAINT IF NOT EXISTS fk_baseline_statistics_version
FOREIGN KEY (baseline_version_id)
REFERENCES chaos_platform.baseline_versions(baseline_version_id)
ON DELETE CASCADE;

ALTER TABLE chaos_platform.baseline_versions
ADD CONSTRAINT IF NOT EXISTS fk_baseline_versions_metric
FOREIGN KEY (metric_id)
REFERENCES chaos_platform.baseline_metrics(metric_id)
ON DELETE CASCADE;

ALTER TABLE chaos_platform.baseline_versions
ADD CONSTRAINT IF NOT EXISTS fk_baseline_versions_superseded
FOREIGN KEY (superseded_by)
REFERENCES chaos_platform.baseline_versions(baseline_version_id)
ON DELETE SET NULL;

ALTER TABLE chaos_platform.baseline_correlations
ADD CONSTRAINT IF NOT EXISTS fk_baseline_correlations_metric1
FOREIGN KEY (metric_id_1)
REFERENCES chaos_platform.baseline_metrics(metric_id)
ON DELETE CASCADE;

ALTER TABLE chaos_platform.baseline_correlations
ADD CONSTRAINT IF NOT EXISTS fk_baseline_correlations_metric2
FOREIGN KEY (metric_id_2)
REFERENCES chaos_platform.baseline_metrics(metric_id)
ON DELETE CASCADE;

ALTER TABLE chaos_platform.baseline_anomalies
ADD CONSTRAINT IF NOT EXISTS fk_baseline_anomalies_metric
FOREIGN KEY (metric_id)
REFERENCES chaos_platform.baseline_metrics(metric_id)
ON DELETE CASCADE;

ALTER TABLE chaos_platform.baseline_anomalies
ADD CONSTRAINT IF NOT EXISTS fk_baseline_anomalies_version
FOREIGN KEY (baseline_version_id)
REFERENCES chaos_platform.baseline_versions(baseline_version_id)
ON DELETE CASCADE;

-- Create views for common queries
CREATE OR REPLACE VIEW chaos_platform.v_latest_baselines_extended AS
SELECT 
    bm.metric_id,
    bm.service_name,
    bm.database_system,
    bm.metric_name,
    bm.metric_type,
    bm.unit,
    bm.mean_value,
    bm.median_value,
    bm.stddev_value,
    bm.p95,
    bm.p99,
    bm.lower_bound_2sigma,
    bm.upper_bound_2sigma,
    bm.upper_bound_3sigma,
    bm.is_active,
    bv.version_number,
    bv.version_timestamp,
    bv.status,
    bv.quality_score
FROM chaos_platform.baseline_metrics bm
LEFT JOIN chaos_platform.baseline_versions bv ON bm.current_baseline_version_id = bv.baseline_version_id
WHERE bm.is_active = true
ORDER BY bm.service_name, bm.database_system, bm.metric_name;

CREATE OR REPLACE VIEW chaos_platform.v_baseline_experiment_mapping_extended AS
SELECT 
    bem.mapping_id,
    e.experiment_id,
    e.experiment_name,
    s.service_name,
    bm.metric_name,
    bm.database_system,
    bem.mapping_type,
    bem.sigma_threshold,
    bem.is_active,
    bm.mean_value,
    bm.stddev_value
FROM chaos_platform.baseline_experiment_mapping bem
JOIN chaos_platform.experiments e ON bem.experiment_id = e.experiment_id
JOIN chaos_platform.services s ON e.service_id = s.service_id
JOIN chaos_platform.baseline_metrics bm ON bem.metric_id = bm.metric_id
WHERE bem.is_active = true
ORDER BY e.experiment_name, bm.metric_name;

-- Grant permissions
GRANT SELECT, INSERT, UPDATE ON chaos_platform.baseline_statistics TO chaos_app;
GRANT SELECT, INSERT, UPDATE ON chaos_platform.baseline_versions TO chaos_app;
GRANT SELECT, INSERT, UPDATE ON chaos_platform.baseline_correlations TO chaos_app;
GRANT SELECT, INSERT, UPDATE ON chaos_platform.baseline_anomalies TO chaos_app;
GRANT SELECT, INSERT, UPDATE ON chaos_platform.baseline_experiment_mapping TO chaos_app;

GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA chaos_platform TO chaos_app;

GRANT SELECT ON chaos_platform.v_latest_baselines_extended TO chaos_app;
GRANT SELECT ON chaos_platform.v_baseline_experiment_mapping_extended TO chaos_app;

-- Same for chaos_user role
GRANT SELECT, INSERT, UPDATE ON chaos_platform.baseline_statistics TO chaos_user;
GRANT SELECT, INSERT, UPDATE ON chaos_platform.baseline_versions TO chaos_user;
GRANT SELECT, INSERT, UPDATE ON chaos_platform.baseline_correlations TO chaos_user;
GRANT SELECT, INSERT, UPDATE ON chaos_platform.baseline_anomalies TO chaos_user;
GRANT SELECT, INSERT, UPDATE ON chaos_platform.baseline_experiment_mapping TO chaos_user;

GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA chaos_platform TO chaos_user;

GRANT SELECT ON chaos_platform.v_latest_baselines_extended TO chaos_user;
GRANT SELECT ON chaos_platform.v_baseline_experiment_mapping_extended TO chaos_user;

/*
================================================================================
TESTING THE INTEGRATION
================================================================================

After adding the SQL above, test with:

-- 1. Verify ENUM types
SELECT typname FROM pg_type WHERE typnamespace = (
    SELECT oid FROM pg_namespace WHERE nspname = 'chaos_platform'
) AND typname LIKE 'baseline_%enum';

-- 2. Verify tables
SELECT tablename FROM pg_tables WHERE schemaname = 'chaos_platform' AND tablename LIKE 'baseline_%';

-- 3. Insert test data (from baseline_metrics_samples.sql)
INSERT INTO chaos_platform.services (service_name, description, environment, team_name)
VALUES ('postgres', 'PostgreSQL Database Service', 'production', 'Infrastructure')
ON CONFLICT (service_name) DO NOTHING;

INSERT INTO chaos_platform.baseline_metrics (
    service_name, metric_name, database_system, metric_type,
    metric_description, unit, data_source, valid_min, valid_max,
    mean_value, median_value, stddev_value, min_value, max_value,
    p50, p95, p99, sample_count, data_completeness_percent, is_active
) VALUES (
    'postgres', 'postgresql_backends', 'postgresql', 'gauge',
    'Number of active backend connections', 'connections', 'prometheus',
    0, 1000, 45.3, 44.0, 8.2, 20, 92,
    44.0, 62.0, 75.0, 14400, 99.8, true
) ON CONFLICT DO NOTHING;

-- 4. Test query
SELECT * FROM chaos_platform.baseline_metrics WHERE service_name = 'postgres';

-- 5. Verify indexes
SELECT indexname FROM pg_indexes WHERE schemaname = 'chaos_platform' AND tablename LIKE 'baseline_%';

================================================================================
MIGRATION FROM EXISTING baseline_metrics
================================================================================

If you already have data in the existing baseline_metrics table:

1. Add new columns to existing table (DDL above includes IF NOT EXISTS)

2. Backfill database_system based on service_name:
   UPDATE chaos_platform.baseline_metrics
   SET database_system = CASE 
       WHEN service_name = 'postgres' THEN 'postgresql'::chaos_platform.database_system_enum
       WHEN service_name = 'mysql' THEN 'mysql'::chaos_platform.database_system_enum
       WHEN service_name = 'mongodb' THEN 'mongodb'::chaos_platform.database_system_enum
       ELSE 'other'::chaos_platform.database_system_enum
   END;

3. Backfill metric_type based on metric_name:
   UPDATE chaos_platform.baseline_metrics
   SET metric_type = CASE 
       WHEN metric_name LIKE '%latency%' THEN 'summary'::chaos_platform.metric_type_enum
       WHEN metric_name LIKE '%rate%' THEN 'counter'::chaos_platform.metric_type_enum
       ELSE 'gauge'::chaos_platform.metric_type_enum
   END;

4. Create baseline_versions for existing metrics:
   INSERT INTO chaos_platform.baseline_versions (
       metric_id, version_number, status, total_samples, valid_samples,
       data_collection_start, data_collection_end, mean_value, stddev_value, p50, p95, p99
   )
   SELECT 
       metric_id, 1, 'validated'::chaos_platform.baseline_status_enum, 
       sample_count, sample_count, 
       CURRENT_TIMESTAMP - INTERVAL '14 days', CURRENT_TIMESTAMP,
       mean_value, stddev_value, p50, p95, p99
   FROM chaos_platform.baseline_metrics;

5. Update foreign keys:
   UPDATE chaos_platform.baseline_metrics bm
   SET current_baseline_version_id = (
       SELECT baseline_version_id FROM chaos_platform.baseline_versions bv
       WHERE bv.metric_id = bm.metric_id AND bv.version_number = 1
   );

================================================================================
*/

