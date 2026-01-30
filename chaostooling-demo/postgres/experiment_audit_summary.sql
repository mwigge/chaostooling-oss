-- ============================================================================
-- EXPERIMENT AUDIT SUMMARY QUERY
-- Shows complete experiment information including:
-- - Experiment metadata (ID, title, service)
-- - Run history (run_id, run_number, status, timestamps)
-- - Scores (risk, complexity, test quality)
-- - Audit trail (all events logged)
--
-- Usage:
-- SELECT chaos_platform.experiment_audit_summary(<experiment_id>);
-- Example: SELECT chaos_platform.experiment_audit_summary(641958425);
-- ============================================================================

CREATE OR REPLACE FUNCTION chaos_platform.experiment_audit_summary(
    p_experiment_id INTEGER
)
RETURNS TABLE (
    experiment_id INTEGER,
    experiment_name VARCHAR,
    experiment_title VARCHAR,
    service_name VARCHAR,
    run_id INTEGER,
    run_number INTEGER,
    status VARCHAR,
    risk_score INTEGER,
    complexity_score INTEGER,
    test_quality INTEGER,
    risk_level VARCHAR,
    success_rate NUMERIC,
    start_time TIMESTAMP,
    end_time TIMESTAMP,
    steady_state_passed BOOLEAN,
    audit_log_entries TEXT,
    last_audit_action VARCHAR,
    last_audit_timestamp TIMESTAMP
) AS $$
SELECT
    er.experiment_id,
    e.experiment_name,
    -- Get title from audit_log details if available
    COALESCE(
        (
            SELECT (al.details->>'title')
            FROM chaos_platform.audit_log al
            WHERE al.entity_type = 'experiment_run'
            AND al.entity_id = er.run_id
            AND al.action = 'created_experiment_run'
            LIMIT 1
        ),
        e.experiment_name
    ) AS experiment_title,
    s.service_name,
    er.run_id,
    er.run_number,
    er.status,
    er.risk_score,
    er.complexity_score,
    er.test_quality,
    er.risk_level,
    er.success_rate,
    er.start_time,
    er.end_time,
    er.steady_state_passed,
    -- Aggregate all audit events for this run
    STRING_AGG(
        al.action || ' at ' || al.action_timestamp::TEXT,
        ' | ' ORDER BY al.action_timestamp
    ) AS audit_log_entries,
    -- Most recent audit action
    (
        SELECT al2.action
        FROM chaos_platform.audit_log al2
        WHERE al2.entity_type = 'experiment_run'
        AND al2.entity_id = er.run_id
        ORDER BY al2.action_timestamp DESC
        LIMIT 1
    ) AS last_audit_action,
    -- Most recent audit timestamp
    (
        SELECT al2.action_timestamp
        FROM chaos_platform.audit_log al2
        WHERE al2.entity_type = 'experiment_run'
        AND al2.entity_id = er.run_id
        ORDER BY al2.action_timestamp DESC
        LIMIT 1
    ) AS last_audit_timestamp
FROM
    chaos_platform.experiment_runs er
    JOIN chaos_platform.experiments e ON er.experiment_id = e.experiment_id
    JOIN chaos_platform.services s ON e.service_id = s.service_id
    LEFT JOIN chaos_platform.audit_log al ON al.entity_type = 'experiment_run'
        AND al.entity_id = er.run_id
WHERE
    er.experiment_id = p_experiment_id
GROUP BY
    er.run_id,
    er.experiment_id,
    er.run_number,
    er.status,
    er.risk_score,
    er.complexity_score,
    er.test_quality,
    er.risk_level,
    er.success_rate,
    er.start_time,
    er.end_time,
    er.steady_state_passed,
    e.experiment_name,
    s.service_name
ORDER BY
    er.run_number DESC;
$$ LANGUAGE SQL STABLE;

-- ============================================================================
-- DETAILED EXPERIMENT AUDIT SUMMARY
-- Shows audit_log details (JSON) for each run
-- ============================================================================

CREATE OR REPLACE FUNCTION chaos_platform.experiment_audit_detail(
    p_experiment_id INTEGER
)
RETURNS TABLE (
    experiment_id INTEGER,
    experiment_name VARCHAR,
    experiment_title VARCHAR,
    run_id INTEGER,
    run_number INTEGER,
    log_id INTEGER,
    audit_action VARCHAR,
    audit_details JSONB,
    audit_actor VARCHAR,
    audit_timestamp TIMESTAMP
) AS $$
SELECT
    e.experiment_id,
    e.experiment_name,
    COALESCE(
        (
            SELECT (al.details->>'title')
            FROM chaos_platform.audit_log al
            WHERE al.entity_type = 'experiment_run'
            AND al.entity_id = er.run_id
            AND al.action = 'created_experiment_run'
            LIMIT 1
        ),
        e.experiment_name
    ) AS experiment_title,
    er.run_id,
    er.run_number,
    al.log_id,
    al.action,
    al.details,
    al.actor,
    al.action_timestamp
FROM
    chaos_platform.experiment_runs er
    JOIN chaos_platform.experiments e ON er.experiment_id = e.experiment_id
    LEFT JOIN chaos_platform.audit_log al ON al.entity_type = 'experiment_run'
        AND al.entity_id = er.run_id
WHERE
    er.experiment_id = p_experiment_id
ORDER BY
    er.run_number DESC,
    al.action_timestamp DESC;
$$ LANGUAGE SQL STABLE;

-- ============================================================================
-- EXAMPLE USAGE
-- ============================================================================
-- 
-- Get summary of all runs for experiment 641958425:
--   SELECT * FROM chaos_platform.experiment_audit_summary(641958425);
--
-- Get detailed audit trail for experiment 641958425:
--   SELECT * FROM chaos_platform.experiment_audit_detail(641958425);
--
-- Get just experiment title, run counts, and latest scores:
--   SELECT
--       experiment_id,
--       title,
--       COUNT(*) as total_runs,
--       MAX(run_number) as latest_run_number,
--       AVG(risk_score) as avg_risk_score,
--       MAX(test_quality) as best_test_quality
--   FROM chaos_platform.experiment_audit_summary(641958425)
--   GROUP BY experiment_id, title;
--
-- ============================================================================
