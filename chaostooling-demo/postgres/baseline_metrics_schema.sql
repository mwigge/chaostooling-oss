-- ============================================================================
-- BASELINE METRICS SCHEMA DESIGN
-- ============================================================================
-- Enhanced schema for storing baseline metrics for ALL database systems
-- Supports: PostgreSQL, MySQL, MongoDB, Cassandra, Redis, etc.
-- Features:
-- - Flexible metric types (gauge, counter, histogram, summary)
-- - Multi-database system support
-- - Versioning with timestamps and phases
-- - Performance indexes for experiment queries
-- - Statistical tracking (mean, stdev, percentiles)
-- ============================================================================

-- ============================================================================
-- METRIC TYPES & DATABASE SYSTEMS ENUMERATION
-- ============================================================================

-- Create ENUM for metric types (Prometheus standard)
CREATE TYPE chaos_platform.metric_type_enum AS ENUM (
    'gauge',          -- Point-in-time value (CPU%, memory, connections)
    'counter',        -- Monotonically increasing (total_requests, errors)
    'histogram',      -- Distribution (latency buckets, payload sizes)
    'summary',        -- Percentiles (p50, p95, p99 latency)
    'derived'         -- Calculated/aggregated from other metrics
);

-- Create ENUM for database systems
CREATE TYPE chaos_platform.database_system_enum AS ENUM (
    'postgresql',
    'mysql',
    'mongodb',
    'cassandra',
    'redis',
    'elasticsearch',
    'dynamodb',
    'oracle',
    'mariadb',
    'couchdb',
    'neo4j',
    'influxdb',
    'other'
);

-- Create ENUM for baseline phases
CREATE TYPE chaos_platform.baseline_phase_enum AS ENUM (
    'normal_operation',      -- Regular steady state
    'peak_load',             -- High traffic conditions
    'low_load',              -- Off-peak conditions
    'failure_recovery',      -- Post-failure recovery
    'maintenance_window'     -- During maintenance
);

-- Create ENUM for baseline status
CREATE TYPE chaos_platform.baseline_status_enum AS ENUM (
    'collecting',            -- Data collection in progress
    'processing',            -- Statistical analysis in progress
    'validated',             -- Baseline validated and ready
    'superseded',            -- Newer baseline available
    'failed',                -- Baseline analysis failed
    'deprecated'             -- No longer in use
);

-- ============================================================================
-- CORE BASELINE METRICS TABLE (Enhanced)
-- ============================================================================

-- baseline_metrics: Main table for metric definitions and current statistics
-- Stores ONE row per (service_name + metric_name + database_system) combination
-- References experiments by service_name and metric_name
CREATE TABLE IF NOT EXISTS chaos_platform.baseline_metrics (
    metric_id BIGSERIAL PRIMARY KEY,
    
    -- Metric Identification (allows non-unique service_id reference)
    service_name VARCHAR(255) NOT NULL,      -- e.g., 'postgres', 'mysql', 'mongodb'
    metric_name VARCHAR(512) NOT NULL,       -- e.g., 'postgresql_backends', 'mysql_innodb_buffer_pool_reads'
    database_system chaos_platform.database_system_enum NOT NULL,
    metric_type chaos_platform.metric_type_enum NOT NULL,
    
    -- Metric Description
    metric_description TEXT,
    unit VARCHAR(100),                       -- e.g., 'ms', 'connections', 'requests/sec', '%'
    data_source VARCHAR(255),                -- e.g., 'prometheus', 'datadog', 'custom_exporter'
    
    -- Valid Range (for anomaly detection)
    valid_min NUMERIC(18, 6),
    valid_max NUMERIC(18, 6),
    
    -- Latest Statistics (from most recent baseline)
    mean_value NUMERIC(18, 6),
    median_value NUMERIC(18, 6),
    stddev_value NUMERIC(18, 6),
    min_value NUMERIC(18, 6),
    max_value NUMERIC(18, 6),
    
    -- Percentiles
    p50 NUMERIC(18, 6),
    p75 NUMERIC(18, 6),
    p90 NUMERIC(18, 6),
    p95 NUMERIC(18, 6),
    p99 NUMERIC(18, 6),
    p999 NUMERIC(18, 6),
    
    -- Anomaly Detection Thresholds (standard deviations)
    lower_bound_2sigma NUMERIC(18, 6),
    upper_bound_2sigma NUMERIC(18, 6),
    upper_bound_3sigma NUMERIC(18, 6),
    
    -- Baseline Reference Information
    current_baseline_version_id BIGINT,      -- FK to latest baseline_versions
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- Metadata
    sample_count BIGINT,
    data_completeness_percent NUMERIC(5, 2),
    is_active BOOLEAN DEFAULT true,
    
    -- Time tracking
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- Composite unique constraint: one active baseline per metric per system
    UNIQUE(service_name, metric_name, database_system)
);

CREATE INDEX idx_baseline_metrics_service_metric ON chaos_platform.baseline_metrics(service_name, metric_name);
CREATE INDEX idx_baseline_metrics_system ON chaos_platform.baseline_metrics(database_system);
CREATE INDEX idx_baseline_metrics_active ON chaos_platform.baseline_metrics(is_active, service_name);

-- ============================================================================
-- BASELINE STATISTICS TABLE (Detailed Statistics)
-- ============================================================================

-- baseline_statistics: Detailed statistical information for each metric version
-- Denormalized for fast experiment queries
-- One row per metric + time period + analysis phase
CREATE TABLE IF NOT EXISTS chaos_platform.baseline_statistics (
    statistic_id BIGSERIAL PRIMARY KEY,
    
    -- Reference to metric and baseline version
    metric_id BIGINT NOT NULL REFERENCES chaos_platform.baseline_metrics(metric_id),
    baseline_version_id BIGINT NOT NULL,  -- FK to baseline_versions (added later)
    
    -- Analysis Context
    phase chaos_platform.baseline_phase_enum DEFAULT 'normal_operation',
    analysis_period_days INTEGER DEFAULT 14,
    
    -- Collection Window
    data_collection_start TIMESTAMP NOT NULL,
    data_collection_end TIMESTAMP NOT NULL,
    
    -- Core Statistics
    mean_value NUMERIC(18, 6),
    median_value NUMERIC(18, 6),
    stddev_value NUMERIC(18, 6),
    variance NUMERIC(18, 6),
    min_value NUMERIC(18, 6),
    max_value NUMERIC(18, 6),
    range_value NUMERIC(18, 6),
    
    -- Percentiles for distribution analysis
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
    
    -- Quartile Information
    q1 NUMERIC(18, 6),      -- 25th percentile
    q2 NUMERIC(18, 6),      -- 50th percentile (median)
    q3 NUMERIC(18, 6),      -- 75th percentile
    iqr NUMERIC(18, 6),     -- Interquartile range
    
    -- Anomaly Detection Thresholds
    lower_bound_1sigma NUMERIC(18, 6),
    upper_bound_1sigma NUMERIC(18, 6),
    lower_bound_2sigma NUMERIC(18, 6),
    upper_bound_2sigma NUMERIC(18, 6),
    lower_bound_3sigma NUMERIC(18, 6),
    upper_bound_3sigma NUMERIC(18, 6),
    
    -- Distribution Analysis
    skewness NUMERIC(10, 4),
    kurtosis NUMERIC(10, 4),
    is_normal_distribution BOOLEAN,
    
    -- Data Quality
    sample_count BIGINT,
    data_completeness_percent NUMERIC(5, 2),
    outlier_count INTEGER,
    zero_value_count BIGINT,
    null_value_count BIGINT,
    
    -- Histogram Data (for metric_type='histogram')
    histogram_buckets JSONB,  -- {"bucket_10ms": count, "bucket_50ms": count, ...}
    
    -- Metadata
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- One entry per metric + baseline version + phase
    UNIQUE(metric_id, baseline_version_id, phase)
);

CREATE INDEX idx_baseline_statistics_metric ON chaos_platform.baseline_statistics(metric_id);
CREATE INDEX idx_baseline_statistics_phase ON chaos_platform.baseline_statistics(phase);
CREATE INDEX idx_baseline_statistics_window ON chaos_platform.baseline_statistics(data_collection_start, data_collection_end);

-- ============================================================================
-- BASELINE VERSIONS TABLE (Versioning & Audit Trail)
-- ============================================================================

-- baseline_versions: Complete audit trail of all baseline versions
-- Allows rollback to previous baselines if needed
-- Tracks data source, collection parameters, and validation status
CREATE TABLE IF NOT EXISTS chaos_platform.baseline_versions (
    baseline_version_id BIGSERIAL PRIMARY KEY,
    
    -- Reference
    metric_id BIGINT NOT NULL REFERENCES chaos_platform.baseline_metrics(metric_id),
    
    -- Version Information
    version_number INTEGER NOT NULL,
    version_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- Data Collection Parameters
    data_collection_start TIMESTAMP NOT NULL,
    data_collection_end TIMESTAMP NOT NULL,
    collection_duration_days INTEGER,
    
    -- Data Source Information
    datasource_type VARCHAR(100),           -- 'prometheus', 'datadog', 'custom_exporter'
    datasource_name VARCHAR(255),           -- Query name or job name
    datasource_query TEXT,                  -- PromQL or equivalent
    
    -- Data Processing
    aggregation_method VARCHAR(100),        -- 'average', 'median', 'percentile'
    time_bucketing VARCHAR(100),            -- '1m', '5m', '1h'
    interpolation_method VARCHAR(100),      -- 'linear', 'forward_fill', 'none'
    
    -- Validation & Quality
    status chaos_platform.baseline_status_enum DEFAULT 'processing',
    validation_status VARCHAR(50),          -- 'pending', 'passed', 'failed'
    validation_timestamp TIMESTAMP,
    quality_score NUMERIC(5, 2),            -- 0-100: Data quality percentage
    confidence_level NUMERIC(5, 2),         -- Confidence in baseline validity
    
    -- Sample Information
    total_samples BIGINT,
    valid_samples BIGINT,
    excluded_samples BIGINT,
    exclusion_reason TEXT,                  -- e.g., 'outliers removed', 'sparse periods excluded'
    
    -- Baseline Snapshot (denormalized for fast access)
    mean_value NUMERIC(18, 6),
    stddev_value NUMERIC(18, 6),
    p50 NUMERIC(18, 6),
    p95 NUMERIC(18, 6),
    p99 NUMERIC(18, 6),
    
    -- Superseding Information
    superseded_by BIGINT REFERENCES chaos_platform.baseline_versions(baseline_version_id),
    superseded_at TIMESTAMP,
    supersession_reason TEXT,
    
    -- Metadata
    created_by VARCHAR(255) DEFAULT 'system',
    notes TEXT,
    tags TEXT[],                            -- e.g., ['production', 'validated', 'post-optimization']
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- One entry per metric + version
    UNIQUE(metric_id, version_number)
);

CREATE INDEX idx_baseline_versions_metric ON chaos_platform.baseline_versions(metric_id);
CREATE INDEX idx_baseline_versions_status ON chaos_platform.baseline_versions(status);
CREATE INDEX idx_baseline_versions_timestamp ON chaos_platform.baseline_versions(version_timestamp);

-- ============================================================================
-- BASELINE CORRELATIONS TABLE (Advanced)
-- ============================================================================

-- baseline_correlations: Track correlations between metrics
-- Used for advanced anomaly detection and RCA
CREATE TABLE IF NOT EXISTS chaos_platform.baseline_correlations (
    correlation_id BIGSERIAL PRIMARY KEY,
    
    -- Metric Pair
    metric_id_1 BIGINT NOT NULL REFERENCES chaos_platform.baseline_metrics(metric_id),
    metric_id_2 BIGINT NOT NULL REFERENCES chaos_platform.baseline_metrics(metric_id),
    
    -- Correlation Analysis
    pearson_correlation NUMERIC(5, 4),      -- -1 to 1
    spearman_correlation NUMERIC(5, 4),
    is_correlated BOOLEAN,                  -- true if |correlation| > 0.7
    lag_seconds INTEGER,                    -- Time lag for correlation
    
    -- Causality Information
    metric_1_leads BOOLEAN,                 -- Does metric1 lead metric2?
    lead_time_seconds INTEGER,
    
    -- Analysis Context
    phase chaos_platform.baseline_phase_enum DEFAULT 'normal_operation',
    analysis_period_start TIMESTAMP,
    analysis_period_end TIMESTAMP,
    
    -- Metadata
    sample_count BIGINT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    UNIQUE(metric_id_1, metric_id_2, phase)
);

CREATE INDEX idx_baseline_correlations_metrics ON chaos_platform.baseline_correlations(metric_id_1, metric_id_2);

-- ============================================================================
-- BASELINE ANOMALIES TABLE (Anomaly Catalog)
-- ============================================================================

-- baseline_anomalies: Catalog of known anomalies and their characteristics
-- Used for baseline validation and experiment anomaly detection
CREATE TABLE IF NOT EXISTS chaos_platform.baseline_anomalies (
    anomaly_id BIGSERIAL PRIMARY KEY,
    
    -- Reference
    metric_id BIGINT NOT NULL REFERENCES chaos_platform.baseline_metrics(metric_id),
    baseline_version_id BIGINT NOT NULL REFERENCES chaos_platform.baseline_versions(baseline_version_id),
    
    -- Anomaly Detection
    anomaly_type VARCHAR(100),              -- 'outlier', 'spike', 'drift', 'seasonal', 'trend'
    severity VARCHAR(50),                   -- 'low', 'medium', 'high', 'critical'
    
    -- Temporal Information
    anomaly_start TIMESTAMP NOT NULL,
    anomaly_end TIMESTAMP,
    duration_seconds INTEGER,
    
    -- Statistical Information
    deviation_sigma NUMERIC(10, 4),         -- How many standard deviations away?
    expected_value NUMERIC(18, 6),
    actual_value NUMERIC(18, 6),
    
    -- Root Cause (if known)
    root_cause VARCHAR(255),
    root_cause_description TEXT,
    
    -- Resolution
    is_resolved BOOLEAN DEFAULT false,
    resolution_timestamp TIMESTAMP,
    resolution_notes TEXT,
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_baseline_anomalies_metric ON chaos_platform.baseline_anomalies(metric_id);
CREATE INDEX idx_baseline_anomalies_time ON chaos_platform.baseline_anomalies(anomaly_start);

-- ============================================================================
-- BASELINE EXPERIMENT MAPPING (How Experiments Use Baselines)
-- ============================================================================

-- baseline_experiment_mapping: Links experiments to baselines they monitor
-- Enables experiments to reference baselines by service_name and metric_name
CREATE TABLE IF NOT EXISTS chaos_platform.baseline_experiment_mapping (
    mapping_id BIGSERIAL PRIMARY KEY,
    
    -- Experiment Reference
    experiment_id INTEGER NOT NULL REFERENCES chaos_platform.experiments(experiment_id),
    
    -- Baseline Reference
    metric_id BIGINT NOT NULL REFERENCES chaos_platform.baseline_metrics(metric_id),
    
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

CREATE INDEX idx_baseline_experiment_mapping_experiment ON chaos_platform.baseline_experiment_mapping(experiment_id);
CREATE INDEX idx_baseline_experiment_mapping_metric ON chaos_platform.baseline_experiment_mapping(metric_id);

-- ============================================================================
-- FOREIGN KEY: Update baseline_metrics to reference baseline_versions
-- ============================================================================

ALTER TABLE chaos_platform.baseline_metrics
ADD CONSTRAINT fk_baseline_metrics_current_version
FOREIGN KEY (current_baseline_version_id)
REFERENCES chaos_platform.baseline_versions(baseline_version_id)
ON DELETE SET NULL;

-- ============================================================================
-- FOREIGN KEY: Update baseline_statistics to reference baseline_versions
-- ============================================================================

ALTER TABLE chaos_platform.baseline_statistics
ADD CONSTRAINT fk_baseline_statistics_version
FOREIGN KEY (baseline_version_id)
REFERENCES chaos_platform.baseline_versions(baseline_version_id)
ON DELETE CASCADE;

-- ============================================================================
-- GRANT PERMISSIONS
-- ============================================================================

-- Grant permissions to chaos_app role
GRANT SELECT, INSERT, UPDATE ON ALL TABLES IN SCHEMA chaos_platform TO chaos_app;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA chaos_platform TO chaos_app;

-- Grant permissions to chaos_user role
GRANT SELECT, INSERT, UPDATE ON ALL TABLES IN SCHEMA chaos_platform TO chaos_user;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA chaos_platform TO chaos_user;

-- ============================================================================
-- BASELINE QUERIES & VIEWS
-- ============================================================================

-- View: Latest Baselines for All Systems
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

-- View: Baseline Statistics by Phase
CREATE OR REPLACE VIEW chaos_platform.v_baseline_statistics_by_phase AS
SELECT 
    bm.service_name,
    bm.database_system,
    bm.metric_name,
    bs.phase,
    bs.mean_value,
    bs.stddev_value,
    bs.p50,
    bs.p95,
    bs.p99,
    bs.sample_count,
    bs.data_completeness_percent,
    bs.data_collection_start,
    bs.data_collection_end
FROM chaos_platform.baseline_statistics bs
JOIN chaos_platform.baseline_metrics bm ON bs.metric_id = bm.metric_id
ORDER BY bm.service_name, bm.metric_name, bs.phase;

-- View: Experiments Using Baselines
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

-- ============================================================================
-- GRANT VIEW PERMISSIONS
-- ============================================================================

GRANT SELECT ON chaos_platform.v_latest_baselines_extended TO chaos_app;
GRANT SELECT ON chaos_platform.v_latest_baselines_extended TO chaos_user;
GRANT SELECT ON chaos_platform.v_baseline_statistics_by_phase TO chaos_app;
GRANT SELECT ON chaos_platform.v_baseline_statistics_by_phase TO chaos_user;
GRANT SELECT ON chaos_platform.v_baseline_experiment_mapping_extended TO chaos_app;
GRANT SELECT ON chaos_platform.v_baseline_experiment_mapping_extended TO chaos_user;

