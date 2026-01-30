# Quick Reference - Database Integration

## Connection String

```
Host: chaos-platform-db  (localhost if running locally)
Port: 5434
User: chaos_app
Database: chaos_platform
```

## Key Tables

| Table | Purpose | Written By | Queried By |
|-------|---------|-----------|-----------|
| `baseline_metrics` | Steady state stats (mean, stdev, p50, p95, p99) | mcp_baseline_control | mcp_baseline_probe, compliance reports |
| `metric_snapshots` | Time-series data (pre/during/post chaos) | mcp_metrics_collector | mcp_result_analyzer, dashboards |
| `experiment_analysis` | RCA, compliance pass/fail, recommendations | mcp_result_analyzer | DORA reports, post-mortems |
| `audit_log` | Immutable compliance evidence (append-only) | ChaosDb._audit_log() | Regulatory audits, compliance |
| `slo_targets` | Service level objectives | mcp_baseline_control | Compliance checking |
| `experiment_runs` | Execution records | chaos toolkit | Run status, timeline queries |

## Common Queries

### Find latest baseline for a service
```sql
SELECT * FROM chaos_platform.v_latest_baselines 
WHERE service_name = 'postgres' 
LIMIT 10;
```

### Get all metrics from an experiment run
```sql
SELECT * FROM chaos_platform.metric_snapshots 
WHERE run_id = 1 
ORDER BY phase, captured_at;
```

### Check compliance status
```sql
SELECT * FROM chaos_platform.v_compliance_summary;
```

### View recent experiments
```sql
SELECT * FROM chaos_platform.v_recent_experiments 
LIMIT 10;
```

### Get audit trail for experiment
```sql
SELECT * FROM chaos_platform.audit_log 
WHERE entity_type = 'experiment_run' 
ORDER BY action_timestamp DESC 
LIMIT 50;
```

## Module Integration

### Before Experiment (Step 1)
```python
from chaosgeneric.control.mcp_baseline_control import MCPBaselineControl

control = MCPBaselineControl()
control.before_experiment_starts(context, 
    prometheus_url="http://prometheus:9090",
    service_name="postgres",
    db_host="localhost",
    db_port=5434
)
```

### Verify Steady State (Step 2)
```python
from chaosgeneric.probes.mcp_baseline_probe import check_metric_within_baseline

result = check_metric_within_baseline(
    metric_name="pg_stat_activity_count",
    service_name="postgres",
    db_host="localhost",
    db_port=5434
)
```

### Collect Snapshot (Step 3, 4, 5)
```python
from chaosgeneric.actions.mcp_metrics_collector import collect_baseline_snapshot

collect_baseline_snapshot(
    prometheus_url="http://prometheus:9090",
    metrics=["pg_stat_activity_count"],
    service_name="postgres",
    run_id=1,
    phase="pre_chaos",  # or "during_chaos", "post_chaos"
    db_host="localhost",
    db_port=5434
)
```

### Analyze Results (Step 6)
```python
from chaosgeneric.actions.mcp_result_analyzer import analyze_experiment_results

analyze_experiment_results(
    service_name="postgres",
    run_id=1,
    db_host="localhost",
    db_port=5434
)
```

## Direct Database Calls

```python
from chaosgeneric.data.chaos_db import ChaosDb

db = ChaosDb(host="localhost", port=5434)

# Save baseline
db.save_baseline_metrics("postgres", {
    "baseline_metrics": {...}
})

# Save metric snapshot
db.save_metric_snapshot(run_id=1, service_name="postgres", 
                       phase="pre_chaos", metrics={...})

# Save analysis
db.save_experiment_analysis(run_id=1, analysis={...})

# Read baseline
baseline = db.get_baseline_metrics("postgres")

# Get compliance report
compliance = db.get_compliance_report(start_date="2025-01-01")

# Get audit trail
audit = db.get_audit_trail(entity_type="experiment_run")
```

## CLI Commands

```bash
# Check database status
docker exec chaos-platform-db pg_isready -U chaos_admin -d chaos_platform

# Connect to database
docker exec -it chaos-platform-db psql -U chaos_admin -d chaos_platform

# Count rows per table
docker exec chaos-platform-db psql -U chaos_admin -d chaos_platform -c "
SELECT 'services', count(*) FROM chaos_platform.services
UNION ALL
SELECT 'baseline_metrics', count(*) FROM chaos_platform.baseline_metrics
UNION ALL
SELECT 'metric_snapshots', count(*) FROM chaos_platform.metric_snapshots
UNION ALL
SELECT 'experiment_analysis', count(*) FROM chaos_platform.experiment_analysis
UNION ALL
SELECT 'audit_log', count(*) FROM chaos_platform.audit_log;
"

# Backup database
docker exec chaos-platform-db pg_dump -U chaos_admin -d chaos_platform > backup.sql

# View recent audit entries
docker exec chaos-platform-db psql -U chaos_admin -d chaos_platform -c "
SELECT action_timestamp, action, entity_type, actor 
FROM chaos_platform.audit_log 
ORDER BY action_timestamp DESC LIMIT 20;"
```

## Environment Variables

```bash
# In docker-compose or .env
CHAOS_DB_HOST=chaos-platform-db
CHAOS_DB_PORT=5434
CHAOS_DB_NAME=chaos_platform
CHAOS_DB_USER=chaos_app
CHAOS_DB_PASSWORD=chaos_app_secure_password

PROMETHEUS_URL=http://prometheus:9090
TEMPO_URL=http://tempo:3100
LOKI_URL=http://loki:3100
GRAFANA_URL=http://grafana:3000
```

## Troubleshooting

```bash
# Check if database is ready
docker exec chaos-platform-db psql -U chaos_admin -d chaos_platform -c "SELECT 1;"

# View database logs
docker logs chaos-platform-db | tail -50

# Check for connection errors in Python
python -c "import psycopg2; psycopg2.connect('host=localhost port=5434 user=chaos_app dbname=chaos_platform')"

# Reset database (DELETE ALL DATA - use carefully!)
docker exec chaos-platform-db psql -U chaos_admin -d chaos_platform -c "
DROP SCHEMA chaos_platform CASCADE;
CREATE SCHEMA chaos_platform;
-- Then re-run init-chaos-platform.sql
"
```

## Performance Tips

1. **Indexes**: All primary query patterns already indexed (run_id, service_name, captured_at)
2. **Connection pooling**: ChaosDb uses connection pooling automatically
3. **JSONB queries**: Use `metrics_data->>'field'` for fast JSON lookups
4. **Partitioning**: Consider partitioning metric_snapshots by month if >1M rows
5. **Retention**: Run `SELECT chaos_platform.cleanup_old_audit_logs();` monthly

## Compliance Fields

Every experiment generates:
- `compliance_status`: 'pass' or 'fail'
- `max_degradation_percent`: Peak performance drop
- `recovery_time_seconds`: Time to recover
- `root_cause_analysis`: Text explanation
- `recommendations`: Suggested fixes

All stored in `experiment_analysis` table + immutable `audit_log` for regulatory evidence.

## Data Flow Diagram

```
Prometheus → mcp_baseline_control → baseline_metrics + slo_targets
                                  ↓
                            experiment_runs (created)
                                  ↓
             mcp_metrics_collector (3x: pre/during/post)
                                  ↓
                            metric_snapshots (3 rows)
                                  ↓
              mcp_result_analyzer (compares phases)
                                  ↓
                        experiment_analysis (1 row)
                                  ↓
                          audit_log (grows)
                                  ↓
                    DORA Compliance Report
```

---

**For complete details:**
- [DB_INTEGRATION.md](DB_INTEGRATION.md) - Module integration guide
- [DB_INTEGRATION_TESTING.md](DB_INTEGRATION_TESTING.md) - Testing procedures
- [E2E_EXPERIMENT_GUIDE.md](E2E_EXPERIMENT_GUIDE.md) - Complete workflow
- [../chaostooling-demo/CHAOS_PLATFORM_DB.md](../chaostooling-demo/CHAOS_PLATFORM_DB.md) - Schema design
