# Database Integration Testing Guide

This guide walks through **end-to-end testing** of the PostgreSQL database integration with MCP modules.

---

## Prerequisites

[OK] Database running: `docker-compose up chaos-platform-db`
[OK] Prometheus running: `docker-compose up prometheus`
[OK] Schema initialized: `SELECT count(*) FROM information_schema.tables WHERE table_schema='chaos_platform'` returns 12

---

## Phase 1: Verify Database Connection

```bash
# 1. Check database container is running
docker ps | grep chaos-platform-db

# 2. Test connection
docker exec chaos-platform-db pg_isready -U chaos_admin -d chaos_platform

# 3. Count tables
docker exec chaos-platform-db psql -U chaos_admin -d chaos_platform -c \
  "SELECT count(*) FROM information_schema.tables WHERE table_schema='chaos_platform'"

# Expected output: count = 12
```

---

## Phase 2: Test Baseline Control (mcp_baseline_control.py)

### Test 2A: Initialize Baseline from Prometheus

```bash
# 1. In Python environment with chaos-toolkit installed
cd /home/morgan/dev/src/chaostooling-oss/chaostooling-generic

# 2. Create test script
cat > test_baseline_control.py << 'EOF'
#!/usr/bin/env python
import sys
import json
from chaosgeneric.control.mcp_baseline_control import MCPBaselineControl

# Configuration
config = {
    "prometheus_url": "http://localhost:9090",
    "tempo_url": "http://localhost:3100",
    "loki_url": "http://localhost:3100",
    "grafana_url": "http://localhost:3000",
    "service_name": "postgres",
    "analysis_period_days": 2,  # Use 2 days for quick test
    "db_host": "localhost",
    "db_port": 5434,
    "baseline_file": "./baseline_test.json"
}

# Test baseline control
control = MCPBaselineControl()

try:
    # Mock context
    class Context:
        pass
    
    context = Context()
    
    print("Testing mcp_baseline_control.before_experiment_starts()...")
    control.before_experiment_starts(context, **config)
    
    print("✓ Baseline control test passed")
    print(f"  Service: {config['service_name']}")
    print(f"  Metrics collected: {len(control.baseline_data.get('baseline_metrics', {}))}")
    
except Exception as e:
    print(f"✗ Baseline control test failed: {e}")
    sys.exit(1)
EOF

# 3. Run test
python test_baseline_control.py
```

### Test 2B: Verify Data in Database

```bash
# Query baseline_metrics table
docker exec chaos-platform-db psql -U chaos_admin -d chaos_platform -c "
SELECT 
    bm.baseline_id,
    s.service_name,
    bm.metric_name,
    ROUND(bm.mean_value::numeric, 2) as mean,
    ROUND(bm.stddev_value::numeric, 2) as stddev,
    bm.analysis_timestamp
FROM chaos_platform.baseline_metrics bm
JOIN chaos_platform.services s ON bm.service_id = s.service_id
WHERE s.service_name = 'postgres'
ORDER BY bm.analysis_timestamp DESC
LIMIT 10;
"

# Query slo_targets table
docker exec chaos-platform-db psql -U chaos_admin -d chaos_platform -c "
SELECT 
    st.slo_id,
    s.service_name,
    st.metric_name,
    st.target_value,
    st.threshold_type
FROM chaos_platform.slo_targets st
JOIN chaos_platform.services s ON st.service_id = s.service_id
WHERE s.service_name = 'postgres'
LIMIT 10;
"

# Query audit trail for baseline creation
docker exec chaos-platform-db psql -U chaos_admin -d chaos_platform -c "
SELECT 
    action,
    entity_type,
    actor,
    action_timestamp
FROM chaos_platform.audit_log
WHERE entity_type = 'baseline_metrics'
ORDER BY action_timestamp DESC
LIMIT 5;
"
```

**Expected Results:**
- [VERIFIED] Multiple baseline_metrics rows per metric (mean, stddev, percentiles)
- [VERIFIED] SLO targets with thresholds
- [VERIFIED] Audit trail showing INSERT events

---

## Phase 3: Test Baseline Probe (mcp_baseline_probe.py)

### Test 3A: Verify Baseline Can Be Read

```bash
# Create test script
cat > test_baseline_probe.py << 'EOF'
#!/usr/bin/env python
from chaosgeneric.probes.mcp_baseline_probe import check_metric_within_baseline

config = {
    "metric_name": "pg_stat_activity_count",
    "service_name": "postgres",
    "db_host": "localhost",
    "db_port": 5434,
}

try:
    # This probe reads from database
    result = check_metric_within_baseline(**config)
    print(f"✓ Baseline probe test passed")
    print(f"  Result: {result}")
    
except Exception as e:
    print(f"✗ Baseline probe test failed: {e}")
    import traceback
    traceback.print_exc()
EOF

python test_baseline_probe.py
```

**Expected Results:**
- [OK] Probe successfully reads from database
- [OK] Returns True/False indicating if current metric is within baseline
- [OK] Gracefully falls back to file if database unavailable

---

## Phase 4: Test Metrics Collector (mcp_metrics_collector.py)

### Test 4A: Create Experiment Run

```bash
# First, create an experiment_run entry
docker exec chaos-platform-db psql -U chaos_admin -d chaos_platform -c "
INSERT INTO chaos_platform.experiments (service_id, experiment_name, description, status)
SELECT service_id, 'test-pool-exhaustion', 'Test pool exhaustion scenario', 'in_progress'
FROM chaos_platform.services WHERE service_name = 'postgres'
RETURNING experiment_id;
"

# Capture the experiment_id (should be 1 or higher)
export EXPERIMENT_ID=1

# Then create a run
docker exec chaos-platform-db psql -U chaos_admin -d chaos_platform -c "
INSERT INTO chaos_platform.experiment_runs 
  (experiment_id, status, start_time, run_context)
VALUES 
  (${EXPERIMENT_ID}, 'in_progress', CURRENT_TIMESTAMP, '{}')
RETURNING run_id;
"

# Capture run_id
export RUN_ID=1
```

### Test 4B: Collect Baseline Snapshot

```bash
cat > test_metrics_collector.py << 'EOF'
#!/usr/bin/env python
from chaosgeneric.actions.mcp_metrics_collector import collect_baseline_snapshot

config = {
    "prometheus_url": "http://localhost:9090",
    "metrics": [
        "pg_stat_activity_count",
        "pg_connections_available",
        "pg_query_duration_milliseconds"
    ],
    "service_name": "postgres",
    "output_file": "./baseline_snapshot.json",
    "run_id": 1,  # From experiment_runs table
    "phase": "pre_chaos",
    "db_host": "localhost",
    "db_port": 5434
}

try:
    collect_baseline_snapshot(**config)
    print(f"✓ Metrics collector test passed")
    print(f"  Saved snapshot for run_id={config['run_id']}, phase={config['phase']}")
except Exception as e:
    print(f"✗ Metrics collector test failed: {e}")
    import traceback
    traceback.print_exc()
EOF

python test_metrics_collector.py
```

### Test 4C: Verify Snapshots in Database

```bash
# Query metric_snapshots for the run
docker exec chaos-platform-db psql -U chaos_admin -d chaos_platform -c "
SELECT 
    snapshot_id,
    run_id,
    service_name,
    phase,
    captured_at,
    json_object_keys(metrics_data) as metric_names
FROM chaos_platform.metric_snapshots
WHERE run_id = 1
ORDER BY captured_at DESC;
"

# View actual metric values
docker exec chaos-platform-db psql -U chaos_admin -d chaos_platform -c "
SELECT 
    snapshot_id,
    phase,
    captured_at,
    metrics_data
FROM chaos_platform.metric_snapshots
WHERE run_id = 1 AND phase = 'pre_chaos'
LIMIT 1;
" | grep -o '"[^"]*": [^,}]*' | head -20
```

**Expected Results:**
- [OK] Multiple snapshot rows, one per phase (pre_chaos, during_chaos, post_chaos)
- [OK] Each snapshot contains JSONB metrics data
- [OK] Timestamps increasing across phases

---

## Phase 5: Test Result Analyzer (mcp_result_analyzer.py)

### Test 5A: Run Analysis

```bash
# Collect during_chaos snapshot
python -c "
from chaosgeneric.actions.mcp_metrics_collector import collect_baseline_snapshot
collect_baseline_snapshot(
    prometheus_url='http://localhost:9090',
    metrics=['pg_stat_activity_count'],
    service_name='postgres',
    run_id=1,
    phase='during_chaos',
    db_host='localhost',
    db_port=5434
)
"

# Collect post_chaos snapshot
python -c "
from chaosgeneric.actions.mcp_metrics_collector import collect_baseline_snapshot
collect_baseline_snapshot(
    prometheus_url='http://localhost:9090',
    metrics=['pg_stat_activity_count'],
    service_name='postgres',
    run_id=1,
    phase='post_chaos',
    db_host='localhost',
    db_port=5434
)
"

# Run analysis
cat > test_result_analyzer.py << 'EOF'
#!/usr/bin/env python
from chaosgeneric.actions.mcp_result_analyzer import analyze_experiment_results

config = {
    "service_name": "postgres",
    "output_report": "./postgres-pool-exhaustion-analysis.json",
    "run_id": 1,
    "db_host": "localhost",
    "db_port": 5434
}

try:
    analyze_experiment_results(**config)
    print(f"✓ Result analyzer test passed")
    print(f"  Analysis saved for run_id={config['run_id']}")
except Exception as e:
    print(f"✗ Result analyzer test failed: {e}")
    import traceback
    traceback.print_exc()
EOF

python test_result_analyzer.py
```

### Test 5B: Verify Analysis in Database

```bash
# Query experiment_analysis
docker exec chaos-platform-db psql -U chaos_admin -d chaos_platform -c "
SELECT 
    run_id,
    service_name,
    compliance_status,
    max_degradation_percent,
    recovery_time_seconds,
    analysis_timestamp
FROM chaos_platform.experiment_analysis
WHERE run_id = 1;
"

# Check if experiment_run marked as complete
docker exec chaos-platform-db psql -U chaos_admin -d chaos_platform -c "
SELECT 
    run_id,
    status,
    start_time,
    end_time,
    EXTRACT(EPOCH FROM (end_time - start_time)) as duration_seconds
FROM chaos_platform.experiment_runs
WHERE run_id = 1;
"

# View final audit trail
docker exec chaos-platform-db psql -U chaos_admin -d chaos_platform -c "
SELECT 
    action,
    entity_type,
    actor,
    action_details,
    action_timestamp
FROM chaos_platform.audit_log
WHERE entity_type IN ('experiment_run', 'experiment_analysis')
ORDER BY action_timestamp DESC
LIMIT 10;
"
```

**Expected Results:**
- [VERIFIED] experiment_analysis row with compliance_status, degradation metrics
- [VERIFIED] experiment_run marked as 'completed'
- [VERIFIED] Audit trail shows all actions (INSERT experiments, experiment_runs, metric_snapshots, experiment_analysis)

---

## Phase 6: Verify Compliance Reporting

### Query Compliance Summary

```bash
# View compliance summary across all services
docker exec chaos-platform-db psql -U chaos_admin -d chaos_platform -c "
SELECT 
    service_name,
    total_experiments,
    total_runs,
    passed_runs,
    ROUND(100.0 * passed_runs / total_runs, 2) as pass_rate,
    avg_recovery_time,
    worst_degradation
FROM chaos_platform.v_compliance_summary
ORDER BY service_name;
"

# View recent experiments
docker exec chaos-platform-db psql -U chaos_admin -d chaos_platform -c "
SELECT 
    experiment_name,
    service_name,
    last_run_time,
    last_status,
    total_runs,
    pass_rate
FROM chaos_platform.v_recent_experiments
ORDER BY last_run_time DESC
LIMIT 10;
"

# View latest baselines
docker exec chaos-platform-db psql -U chaos_admin -d chaos_platform -c "
SELECT 
    service_name,
    metric_name,
    mean_value,
    stddev_value,
    p95_value,
    analysis_timestamp
FROM chaos_platform.v_latest_baselines
WHERE service_name = 'postgres'
LIMIT 10;
"
```

---

## Phase 7: Test Database Fallback (Resilience)

### Test 7A: Stop Database, Verify Fallback

```bash
# 1. Stop database
docker stop chaos-platform-db

# 2. Try to read baseline (should use file fallback)
python test_baseline_probe.py

# Expected: Should use JSON file backup if available

# 3. Try to save metrics (should use file backup)
python test_metrics_collector.py

# Expected: Should save to JSON file

# 4. Restart database
docker start chaos-platform-db
docker exec chaos-platform-db pg_isready -U chaos_admin -d chaos_platform

# 5. Verify data still there
docker exec chaos-platform-db psql -U chaos_admin -d chaos_platform -c \
  "SELECT count(*) FROM chaos_platform.metric_snapshots"
```

---

## Phase 8: Performance Benchmarking

```bash
# 1. Count total snapshots
docker exec chaos-platform-db psql -U chaos_admin -d chaos_platform -c \
  "SELECT count(*) as total_snapshots FROM chaos_platform.metric_snapshots"

# 2. Benchmark: Query by run_id (should be <100ms)
time docker exec chaos-platform-db psql -U chaos_admin -d chaos_platform -c \
  "SELECT * FROM chaos_platform.metric_snapshots WHERE run_id = 1"

# 3. Benchmark: Query by service (should be <100ms)
time docker exec chaos-platform-db psql -U chaos_admin -d chaos_platform -c \
  "SELECT * FROM chaos_platform.metric_snapshots WHERE service_name = 'postgres'"

# 4. Benchmark: Time-series range query (should be <200ms)
time docker exec chaos-platform-db psql -U chaos_admin -d chaos_platform -c \
  "SELECT * FROM chaos_platform.metric_snapshots 
   WHERE captured_at > CURRENT_TIMESTAMP - INTERVAL '1 day'"

# 5. Benchmark: Audit trail query (should be <100ms)
time docker exec chaos-platform-db psql -U chaos_admin -d chaos_platform -c \
  "SELECT * FROM chaos_platform.audit_log WHERE entity_type = 'metric_snapshot' LIMIT 100"
```

---

## Phase 9: Migration Test (JSON to Database)

```bash
# If you have existing JSON files from previous experiments
cat > test_migration.py << 'EOF'
#!/usr/bin/env python
import json
from pathlib import Path
from chaosgeneric.data.chaos_db import ChaosDb

db = ChaosDb()

# Find all existing baseline JSON files
for json_file in Path(".").glob("baseline_*.json"):
    try:
        with open(json_file) as f:
            data = json.load(f)
        
        service_name = data.get("service_name", "unknown")
        db.save_baseline_metrics(service_name, data)
        print(f"✓ Migrated {json_file} → database for {service_name}")
    except Exception as e:
        print(f"✗ Failed to migrate {json_file}: {e}")
EOF

python test_migration.py
```

---

## Cleanup & Summary

```bash
# 1. Clean up test files
rm -f test_*.py baseline_*.json *_snapshot.json *_analysis.json

# 2. Verify final database state
docker exec chaos-platform-db psql -U chaos_admin -d chaos_platform -c "
SELECT 
    'services' as table_name, count(*) as row_count FROM chaos_platform.services
UNION ALL
SELECT 'baseline_metrics', count(*) FROM chaos_platform.baseline_metrics
UNION ALL
SELECT 'slo_targets', count(*) FROM chaos_platform.slo_targets
UNION ALL
SELECT 'experiments', count(*) FROM chaos_platform.experiments
UNION ALL
SELECT 'experiment_runs', count(*) FROM chaos_platform.experiment_runs
UNION ALL
SELECT 'metric_snapshots', count(*) FROM chaos_platform.metric_snapshots
UNION ALL
SELECT 'experiment_analysis', count(*) FROM chaos_platform.experiment_analysis
UNION ALL
SELECT 'audit_log', count(*) FROM chaos_platform.audit_log
ORDER BY table_name;
"

# 3. Generate final DORA compliance report
docker exec chaos-platform-db psql -U chaos_admin -d chaos_platform -c "
SELECT * FROM chaos_platform.v_compliance_summary;
"

# 4. Archive database for backup
docker exec chaos-platform-db pg_dump -U chaos_admin -d chaos_platform > \
  ./chaos-platform-backup-$(date +%Y%m%d-%H%M%S).sql
```

---

## Success Criteria

[OK] All tests pass without database errors
[OK] Data flows through database tables in expected order:
   1. baseline_metrics (from mcp_baseline_control)
   2. experiment_runs, metric_snapshots (from mcp_metrics_collector)
   3. experiment_analysis (from mcp_result_analyzer)
   4. audit_log (automatic on all mutations)

[OK] Fallback to JSON files works when database unavailable
[OK] Compliance queries return accurate summaries
[OK] Performance queries execute in <200ms

---

## Troubleshooting

| Problem | Solution |
|---------|----------|
| `psycopg2: connection refused` | Check database running: `docker ps \| grep chaos-platform-db` |
| `database "chaos_platform" does not exist` | Run docker-compose up to initialize schema |
| `permission denied for schema chaos_platform` | Verify user is chaos_admin with correct permissions |
| `metric_snapshots table empty` | Verify mcp_metrics_collector is saving to database (check logs) |
| `audit_log not populated` | Check if ChaosDb._audit_log() is being called (check logs) |
| `Slow queries` | Check indexes: `\d+ chaos_platform.metric_snapshots` (should see index on run_id, captured_at) |

All MCP modules now integrate seamlessly with PostgreSQL database!
