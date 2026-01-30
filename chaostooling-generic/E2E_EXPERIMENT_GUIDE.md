# Complete End-to-End Experiment with Database Backend

This guide shows how to run a **production-ready chaos engineering experiment** with full PostgreSQL database integration, compliance tracking, and audit trails.

---

## Overview: 6-Step Chaos Workflow with Database

```
Step 1: Define Steady State (14 days of historical data)
   └─ MCP Baseline Control loads metrics from Prometheus
   └─ Analyzes trends, calculates mean/stdev/percentiles
   └─ Saves to database: baseline_metrics, slo_targets
   └─ Audit log entry: "INSERT baseline_metrics"

Step 2: Verify Steady State (sanity check)
   └─ MCP Baseline Probe reads from database
   └─ Compares current metrics to baseline (2-sigma)
   └─ Confirms system ready for chaos

Step 3: Collect Pre-Chaos Metrics (baseline snapshot)
   └─ MCP Metrics Collector queries Prometheus
   └─ Captures metrics before chaos injection
   └─ Saves to database: metric_snapshots (phase='pre_chaos')

Step 4: Inject Chaos & Collect During-Chaos Metrics
   └─ Experiment runs (connection pool exhaustion, latency spike, etc.)
   └─ MCP Metrics Collector captures metrics every 5 seconds
   └─ Saves to database: metric_snapshots (phase='during_chaos')

Step 5: Recover & Collect Post-Chaos Metrics
   └─ Chaos stops, system recovers
   └─ MCP Metrics Collector captures recovery metrics
   └─ Saves to database: metric_snapshots (phase='post_chaos')

Step 6: Analyze Results & Generate Compliance Report
   └─ MCP Result Analyzer compares all phases to baseline
   └─ Calculates: impact (%), recovery time, RCA, compliance pass/fail
   └─ Saves to database: experiment_analysis, marks run as complete
   └─ Generates DORA evidence in audit_log
```

---

## Prerequisites

```bash
# 1. Start observability stack
cd /home/morgan/dev/src/chaostooling-oss/chaostooling-demo
docker-compose up -d chaos-platform-db prometheus grafana loki tempo

# 2. Verify services running
docker-compose ps

# 3. Generate some metrics (optional, for faster baseline collection)
# If prometheus has no recent metrics, analyze period may be empty
# Run your app or use load generator to create metrics

# 4. Install chaos toolkit extensions
pip install chaos-toolkit chaostoolkit-gremlin  # or your chaos scenarios
```

---

## Complete Experiment JSON with Database Integration

Create `mcp-e2e-experiment.json`:

```json
{
  "version": "1.0.0",
  "title": "E2E Chaos Engineering Experiment with Database Backend",
  "description": "Complete 6-step workflow with PostgreSQL storage, compliance tracking, and audit trails",
  "tags": ["postgres", "connection-pool", "resilience", "database-backed"],
  
  "configuration": {
    "prometheus_url": "http://prometheus:9090",
    "tempo_url": "http://tempo:3100",
    "loki_url": "http://loki:3100",
    "grafana_url": "http://grafana:3000",
    "grafana_api_token": "${GRAFANA_API_TOKEN}",
    
    "service_name": "postgres",
    "target_host": "postgres",
    "target_port": 5433,
    
    "database_host": "chaos-platform-db",
    "database_port": 5434,
    
    "chaos_scenarios": ["connection-pool-exhaustion"],
    "analysis_period_days": 14
  },

  "controls": [
    {
      "name": "baseline-loader",
      "description": "Step 1: Load 14-day baseline from Prometheus",
      "provider": {
        "type": "python",
        "module": "chaosgeneric.control.mcp_baseline_control",
        "func": "MCPBaselineControl",
        "config": {
          "prometheus_url": "${prometheus_url}",
          "tempo_url": "${tempo_url}",
          "loki_url": "${loki_url}",
          "grafana_url": "${grafana_url}",
          "service_name": "${service_name}",
          "analysis_period_days": "${analysis_period_days}",
          "db_host": "${database_host}",
          "db_port": "${database_port}",
          "baseline_file": "./baseline_metrics.json"
        }
      }
    }
  ],

  "steady-state-hypothesis": {
    "title": "Postgres Connection Pool within Baseline",
    "probes": [
      {
        "name": "verify-baseline-connections",
        "type": "probe",
        "description": "Step 2: Verify current connection count is within 2-sigma of baseline",
        "provider": {
          "type": "python",
          "module": "chaosgeneric.probes.mcp_baseline_probe",
          "func": "check_metric_within_baseline",
          "arguments": {
            "metric_name": "pg_stat_activity_count",
            "service_name": "${service_name}",
            "db_host": "${database_host}",
            "db_port": "${database_port}",
            "baseline_file": "./baseline_metrics.json"
          }
        }
      }
    ]
  },

  "method": [
    {
      "name": "collect-pre-chaos-snapshot",
      "type": "action",
      "description": "Step 3: Collect baseline metrics before chaos injection",
      "provider": {
        "type": "python",
        "module": "chaosgeneric.actions.mcp_metrics_collector",
        "func": "collect_baseline_snapshot",
        "arguments": {
          "prometheus_url": "${prometheus_url}",
          "metrics": [
            "pg_stat_activity_count",
            "pg_connections_available",
            "pg_query_duration_milliseconds",
            "pg_transaction_duration_milliseconds",
            "pg_checkpoint_wal_flushed_bytes"
          ],
          "service_name": "${service_name}",
          "output_file": "./metrics_pre_chaos.json",
          "run_id": "${RUN_ID}",
          "phase": "pre_chaos",
          "db_host": "${database_host}",
          "db_port": "${database_port}"
        }
      }
    },
    
    {
      "name": "inject-connection-pool-exhaustion",
      "type": "action",
      "description": "Step 4: Inject chaos - exhaust connection pool",
      "provider": {
        "type": "python",
        "module": "chaosgeneric.actions.postgres_actions",
        "func": "exhaust_connection_pool",
        "arguments": {
          "target_host": "${target_host}",
          "target_port": "${target_port}",
          "duration_seconds": 120,
          "connection_count": 100
        }
      },
      "pauses": {
        "before": 5,
        "after": 10
      }
    },

    {
      "name": "collect-during-chaos-snapshot",
      "type": "action",
      "description": "Step 4: Collect metrics during chaos",
      "provider": {
        "type": "python",
        "module": "chaosgeneric.actions.mcp_metrics_collector",
        "func": "collect_baseline_snapshot",
        "arguments": {
          "prometheus_url": "${prometheus_url}",
          "metrics": [
            "pg_stat_activity_count",
            "pg_connections_available",
            "pg_query_duration_milliseconds"
          ],
          "service_name": "${service_name}",
          "output_file": "./metrics_during_chaos.json",
          "run_id": "${RUN_ID}",
          "phase": "during_chaos",
          "db_host": "${database_host}",
          "db_port": "${database_port}"
        }
      }
    },

    {
      "name": "observe-recovery",
      "type": "action",
      "description": "Step 5: Wait for system recovery",
      "provider": {
        "type": "python",
        "module": "chaosgeneric.actions.mcp_metrics_collector",
        "func": "wait_for_recovery",
        "arguments": {
          "metric_name": "pg_stat_activity_count",
          "baseline_threshold": 2.0,
          "max_wait_seconds": 300,
          "check_interval_seconds": 5
        }
      }
    },

    {
      "name": "collect-post-chaos-snapshot",
      "type": "action",
      "description": "Step 5: Collect metrics after recovery",
      "provider": {
        "type": "python",
        "module": "chaosgeneric.actions.mcp_metrics_collector",
        "func": "collect_baseline_snapshot",
        "arguments": {
          "prometheus_url": "${prometheus_url}",
          "metrics": [
            "pg_stat_activity_count",
            "pg_connections_available",
            "pg_query_duration_milliseconds"
          ],
          "service_name": "${service_name}",
          "output_file": "./metrics_post_chaos.json",
          "run_id": "${RUN_ID}",
          "phase": "post_chaos",
          "db_host": "${database_host}",
          "db_port": "${database_port}"
        }
      }
    }
  ],

  "rollbacks": [
    {
      "name": "cleanup-connections",
      "description": "Ensure all test connections are closed",
      "provider": {
        "type": "python",
        "module": "chaosgeneric.actions.postgres_actions",
        "func": "cleanup_test_connections",
        "arguments": {
          "target_host": "${target_host}",
          "target_port": "${target_port}"
        }
      }
    }
  ]
}
```

---

## Step-by-Step Execution

### Step 1: Create Experiment Entry in Database

```bash
cd /home/morgan/dev/src/chaostooling-oss/chaostooling-demo

# Insert experiment metadata
docker exec chaos-platform-db psql -U chaos_admin -d chaos_platform -c "
INSERT INTO chaos_platform.experiments (service_id, experiment_name, description, status)
SELECT service_id, 'Connection Pool Exhaustion Test', 'E2E experiment with database backend', 'pending'
FROM chaos_platform.services WHERE service_name = 'postgres'
RETURNING experiment_id;
"

# Capture experiment_id (note it, e.g., 1)
export EXPERIMENT_ID=1

# Create experiment run entry
docker exec chaos-platform-db psql -U chaos_admin -d chaos_platform -c "
INSERT INTO chaos_platform.experiment_runs 
  (experiment_id, status, start_time, run_context)
VALUES 
  (${EXPERIMENT_ID}, 'in_progress', CURRENT_TIMESTAMP, 
   '{\"chaos_scenario\": \"connection_pool_exhaustion\", \"target_rps\": 100}')
RETURNING run_id;
"

# Capture run_id (note it, e.g., 1)
export RUN_ID=1
```

### Step 2: Run Experiment with Database Context

```bash
# Set environment variables for experiment
export RUN_ID=1
export PROMETHEUS_URL=http://prometheus:9090
export GRAFANA_API_TOKEN=glc_your_token

# Run the chaos toolkit experiment
chaos run mcp-e2e-experiment.json \
  --experiment-id ${EXPERIMENT_ID} \
  --run-id ${RUN_ID} \
  --var database_host=chaos-platform-db \
  --var database_port=5434

# The experiment will:
# 1. ✓ Load baseline from Prometheus (saves to baseline_metrics table)
# 2. ✓ Verify steady state (queries v_latest_baselines)
# 3. ✓ Collect pre-chaos snapshot (saves to metric_snapshots, phase='pre_chaos')
# 4. ✓ Inject chaos (exhaust connection pool)
# 5. ✓ Collect during-chaos snapshot (saves to metric_snapshots, phase='during_chaos')
# 6. ✓ Wait for recovery
# 7. ✓ Collect post-chaos snapshot (saves to metric_snapshots, phase='post_chaos')
```

### Step 3: Run Analysis After Experiment Completes

```bash
# Trigger final analysis
python << 'EOF'
from chaosgeneric.actions.mcp_result_analyzer import analyze_experiment_results

analyze_experiment_results(
    service_name="postgres",
    run_id=1,  # Use same run_id from experiment
    output_report="./postgres-pool-exhaustion-final-analysis.json",
    db_host="chaos-platform-db",
    db_port=5434
)

print("✓ Analysis complete - results stored in database")
EOF

# The analysis will:
# 1. Load all snapshots (pre_chaos, during_chaos, post_chaos)
# 2. Compare to baseline metrics
# 3. Calculate: degradation %, recovery time, RCA
# 4. Save to experiment_analysis table
# 5. Mark experiment_run as 'completed'
# 6. Create audit trail entry
```

---

## Query Results from Database

### View Raw Metrics from All Phases

```bash
docker exec chaos-platform-db psql -U chaos_admin -d chaos_platform -c "
SELECT 
    snapshot_id,
    run_id,
    phase,
    captured_at,
    metrics_data->>'pg_stat_activity_count' as connection_count,
    metrics_data->>'pg_query_duration_milliseconds' as query_latency_ms
FROM chaos_platform.metric_snapshots
WHERE run_id = 1
ORDER BY phase DESC, captured_at DESC;
"
```

### View Complete Analysis Results

```bash
docker exec chaos-platform-db psql -U chaos_admin -d chaos_platform -c "
SELECT 
    run_id,
    service_name,
    max_degradation_percent,
    recovery_time_seconds,
    mean_recovery_rate,
    compliance_status,
    root_cause_analysis,
    recommendations,
    analysis_timestamp
FROM chaos_platform.experiment_analysis
WHERE run_id = 1
\gx  -- Use expanded display
"
```

### View Experiment Timeline

```bash
docker exec chaos-platform-db psql -U chaos_admin -d chaos_platform -c "
SELECT 
    'experiment_run' as event_type,
    start_time as event_time,
    status,
    EXTRACT(EPOCH FROM (end_time - start_time))::integer as duration_seconds
FROM chaos_platform.experiment_runs
WHERE run_id = 1

UNION ALL

SELECT 
    'baseline_metrics',
    analysis_timestamp,
    'baseline',
    0
FROM chaos_platform.baseline_metrics
WHERE service_id = 1
LIMIT 1

UNION ALL

SELECT 
    'metric_snapshot_' || phase,
    captured_at,
    phase,
    0
FROM chaos_platform.metric_snapshots
WHERE run_id = 1

ORDER BY event_time ASC;
"
```

### Audit Trail - Complete History

```bash
docker exec chaos-platform-db psql -U chaos_admin -d chaos_platform -c "
SELECT 
    action_timestamp,
    action,
    entity_type,
    actor,
    action_details
FROM chaos_platform.audit_log
WHERE action_timestamp > CURRENT_TIMESTAMP - INTERVAL '1 hour'
ORDER BY action_timestamp DESC;
"
```

---

## DORA Compliance Evidence

After running multiple experiments, generate compliance report:

```bash
# Pass rate for all experiments in past 30 days
docker exec chaos-platform-db psql -U chaos_admin -d chaos_platform -c "
SELECT 
    s.service_name,
    COUNT(DISTINCT er.run_id) as total_runs,
    SUM(CASE WHEN ea.compliance_status = 'pass' THEN 1 ELSE 0 END) as passed_runs,
    ROUND(100.0 * SUM(CASE WHEN ea.compliance_status = 'pass' THEN 1 ELSE 0 END) / 
          COUNT(DISTINCT er.run_id), 2) as pass_rate,
    ROUND(AVG(ea.recovery_time_seconds), 2) as avg_recovery_seconds,
    ROUND(MAX(ea.max_degradation_percent), 2) as worst_degradation_percent
FROM chaos_platform.experiments e
JOIN chaos_platform.services s ON e.service_id = s.service_id
JOIN chaos_platform.experiment_runs er ON e.experiment_id = er.experiment_id
LEFT JOIN chaos_platform.experiment_analysis ea ON er.run_id = ea.run_id
WHERE er.end_time > CURRENT_TIMESTAMP - INTERVAL '30 days'
GROUP BY s.service_name
ORDER BY s.service_name;
"

# Export for compliance audit
docker exec chaos-platform-db pg_dump -U chaos_admin -d chaos_platform \
  --table=chaos_platform.audit_log \
  --table=chaos_platform.experiment_analysis \
  --table=chaos_platform.experiment_runs > \
  ./chaos-dora-evidence-$(date +%Y-%m-%d).sql
```

---

## Database Backup for Compliance

```bash
# Create point-in-time backup
docker exec chaos-platform-db pg_dump -U chaos_admin -d chaos_platform \
  --format=custom --compress=9 > \
  ./backups/chaos-platform-$(date +%Y%m%d-%H%M%S).dump

# Set retention: Keep 90 days of backups
find ./backups -name "chaos-platform-*.dump" -mtime +90 -delete

# Restore from backup if needed
# pg_restore --dbname=chaos_platform ./backups/chaos-platform-20250101-120000.dump
```

---

## Troubleshooting

| Issue | Solution |
|-------|----------|
| `run_id not found in metric_snapshots` | Ensure RUN_ID environment variable is set before experiment runs |
| `baseline_metrics table empty` | Run baseline loader first, or wait for Prometheus to have 14 days of data |
| `experiment_analysis shows null values` | Verify all 3 snapshots (pre, during, post) were collected before analysis |
| `audit_log not populated` | Check ChaosDb._audit_log() calls in module code (verify logs) |
| `Database connection timeout` | Check docker-compose is running: `docker-compose ps chaos-platform-db` |

---

## Summary

✅ **Complete production-ready workflow** with:
- Automated baseline discovery from Prometheus
- Steady-state verification before chaos
- Multi-phase metric collection (pre/during/post)
- Automatic RCA and compliance analysis
- Immutable audit trails for regulatory evidence
- SQL-queryable compliance reports

✅ **All data persisted in PostgreSQL** for:
- Historical trending
- Compliance reporting
- Team collaboration
- Automated alerting

✅ **Graceful fallback** to JSON files if database unavailable

Ready for production chaos engineering with enterprise compliance!
