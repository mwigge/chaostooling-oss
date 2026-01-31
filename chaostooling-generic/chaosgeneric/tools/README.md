# Baseline Management Tools

This directory contains the unified baseline management tooling for the chaostooling platform.

---

## 🎯 Current Tool: baseline_manager.py

**baseline_manager.py** is the unified tool that consolidates all baseline operations into a single CLI with comprehensive features.

**Features:**
- **Sync**: Auto-discover metrics by labels (system, service, platform) → collect baselines → store in chaos_platform database
- **Validate**: Validate baselines in chaos_platform database or JSON files
- **Analyze**: Steady state analysis (baseline calculation, SLO generation, anomaly thresholds)
- **Generate**: Create baseline_metrics.json files (legacy support)
- **Query**: Query baseline data from chaos_platform database

**Usage:**
```bash
# Sync all metrics for a system
python baseline_manager.py sync --system postgres

# Sync metrics for a specific service
python baseline_manager.py sync --service payment-service

# Sync metrics for system + service combination
python baseline_manager.py sync --system postgres --service db-primary

# Sync metrics with custom labels
python baseline_manager.py sync --labels "system=postgres,tier=primary,region=us-east"

# Validate all baselines in chaos_platform database
python baseline_manager.py validate --source database --all-systems

# Steady state analysis: baselines, SLOs, anomaly thresholds (14 days)
python baseline_manager.py analyze --period 14d --output-dir ./analysis

# Query baseline data from chaos_platform database
python baseline_manager.py query --system postgres
```

**Configuration:**

Environment variables:
- `GRAFANA_URL` - Grafana server (default: http://grafana:3000)
- `GRAFANA_API_TOKEN` - Grafana API token (optional, for authenticated access)
- `CHAOS_DB_HOST` - chaos_platform database host (default: postgres-primary-site-a)
- `CHAOS_DB_PORT` - chaos_platform database port (default: 5432)
- `CHAOS_DB_USER` - chaos_platform database user (default: postgres)
- `CHAOS_DB_PASSWORD` - chaos_platform database password

**How It Works:**
- **Metric discovery:** Auto-discover metrics from Prometheus via Grafana using label matching
- **Label-based filtering:** Filter metrics by any combination of labels (system, service, platform, tier, region, etc.)
- **Automatic baseline calculation:** For each discovered metric, calculate statistics (mean, stdev, percentiles)
- **Unique combinations:** Each system/service/platform/label combination gets its own baseline
- **Single datasource:** All queries go through Grafana (avoids multi-datasource complexity)

---

## ⚠️ Deprecated Tools

The following tools have been **CONSOLIDATED** into baseline_manager.py and will be removed in a future release:

### baseline_metrics_sync.py → `baseline_manager.py sync`
**Status:** ⚠️ DEPRECATED  
**Old:** `python baseline_metrics_sync.py --system postgres --all` (required dashboard)  
**New:** `python baseline_manager.py sync --system postgres` (auto-discovers metrics by labels)

### validate_baseline_metrics.py → `baseline_manager.py validate`
**Status:** ⚠️ DEPRECATED  
**Replacement:** `python baseline_manager.py validate --source database --all-systems`

### steady_state_analyzer.py → `baseline_manager.py analyze`
**Status:** ⚠️ DEPRECATED (partial implementation)  
**Replacement:** `python baseline_manager.py analyze --period 14d --output-dir ./analysis`  
**Note:** Implements baseline calculation, SLO generation, and anomaly thresholds. Service topology and cyclical pattern analysis not yet implemented.

---

## 🔄 Migration Guide

### Old: baseline_metrics_sync.py (dashboard-based)
```bash
# OLD - Required pre-built Grafana dashboard
python baseline_metrics_sync.py --system postgres --all
```

### New: baseline_manager.py sync (label-based auto-discovery)
```bash
# NEW - Auto-discovers all metrics for system
python baseline_manager.py sync --system postgres

# Or with multiple label filters
python baseline_manager.py sync --system postgres --service db-primary --labels "tier=primary"
```

### Old: validate_baseline_metrics.py
```bash
# OLD - DEPRECATED
python validate_baseline_metrics.py --all-systems
```

### New: baseline_manager.py validate
```bash
# NEW - RECOMMENDED
python baseline_manager.py validate \
  --source database \
  --all-systems
```

---

## Architecture

baseline_manager.py consolidates functionality from three separate tools:
- ✅ Auto-discovery of metrics by labels (system, service, platform, custom labels)
- ✅ Grafana API integration for querying metrics
- ✅ Statistical baseline calculation (mean, stdev, percentiles)
- ✅ chaos_platform database storage
- ✅ Baseline validation (database + files)
- ✅ Steady state analysis (baselines, SLO targets, anomaly thresholds)
- ✅ Shared utility functions (eliminates 300+ lines of duplicate code)
- ⚠️ Service topology analysis (not yet implemented)
- ⚠️ Cyclical pattern detection (not yet implemented)

---

## 📦 Code Reuse

Other modules can import shared functions from baseline_manager:

```python
from chaosgeneric.tools.baseline_manager import (
    PrometheusClient,
    parse_time_range,
    calculate_statistics,
    BaselineMetric,
    ChaosplatformDatabaseClient
)

# Use shared Prometheus client
prom = PrometheusClient("http://prometheus:9090")
result = prom.query_instant("up")

# Use shared utilities
time_delta = parse_time_range("24h")
stats = calculate_statistics([1.0, 2.0, 3.0, 4.0, 5.0])

# Query chaos_platform database
db = ChaosplatformDatabaseClient(
    host="postgres-primary-site-a",
    port=5432,
    user="postgres",
    password="postgres"
)
db.connect()
baselines = db.query_baselines(service_name="postgres")
```

---

## Workflow Integration

### 1. Initial Baseline Setup (chaos_platform database)
```bash
# Step 1: Sync all systems to chaos_platform database
for system in postgres mysql mongodb redis cassandra kafka rabbitmq mssql; do
  python baseline_manager.py sync \
    --system $system \
    --dashboard /chaos/dashboards/${system}_dashboard.json
done

# Step 2: Validate baselines in chaos_platform database
python baseline_manager.py validate --source database --all-systems

# Step 3: Query specific baseline from chaos_platform database
python baseline_manager.py query --system postgres --metric pg_commits_total
```

### 2. Scheduled Updates (chaos_platform database)
```bash
# Add to cron for weekly baseline refresh
0 2 * * 0 python baseline_manager.py sync --system postgres --dashboard /chaos/dashboards/postgres.json
```

### 3. Steady State Analysis
```bash
# Analyze 14 days of data and generate baselines, SLOs, anomaly thresholds
python baseline_manager.py analyze \
  --period 14d \
  --output-dir /chaos/analysis

# Outputs:
# - baseline_metrics.json (calculated baselines)
# - slo_targets.json (latency/throughput SLOs)
# - anomaly_thresholds.json (warning/critical thresholds)
```

---

## Database Schema (chaos_platform)

All baselines are stored in the **chaos_platform.baseline_metrics** table:

```sql
-- chaos_platform database schema
CREATE TABLE baseline_metrics (
    id SERIAL PRIMARY KEY,
    metric_name VARCHAR(255) NOT NULL,
    service_name VARCHAR(255) NOT NULL,
    metric_type VARCHAR(50),
    unit VARCHAR(50),
    description TEXT,
    mean DOUBLE PRECISION,
    stdev DOUBLE PRECISION,
    min_value DOUBLE PRECISION,
    max_value DOUBLE PRECISION,
    percentile_50 DOUBLE PRECISION,
    percentile_95 DOUBLE PRECISION,
    percentile_99 DOUBLE PRECISION,
    percentile_999 DOUBLE PRECISION,
    min_valid DOUBLE PRECISION,
    max_valid DOUBLE PRECISION,
    datasource VARCHAR(100),
    time_range VARCHAR(50),
    phase VARCHAR(50),
    status VARCHAR(50),
    collection_timestamp TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(metric_name, service_name)
);
```

**Access chaos_platform database:**
```bash
# Connect to chaos_platform database
psql -h postgres-primary-site-a -U postgres -d chaos_platform

# Query baselines
SELECT metric_name, service_name, mean, stdev, percentile_99 
FROM baseline_metrics 
WHERE service_name = 'postgres';
```

---

## 🐳 Container Usage

From within chaos-runner container:

```bash
# Enter container
docker exec -it chaos-runner bash

# Navigate to tools directory
cd /chaos/chaostooling-generic/chaosgeneric/tools

# Sync from Grafana to chaos_platform database
python baseline_manager.py sync \
  --system postgres \
  --dashboard /chaos/chaostooling-demo/dashboards/postgres_dashboard.json

# Validate all baselines in chaos_platform database
python baseline_manager.py validate --source database --all-systems

# Full analysis
python baseline_manager.py analyze --period 7d --output-dir /chaos/analysis

# Query chaos_platform database
python baseline_manager.py query --system postgres
```

---

## Common Use Cases

### Use Case 1: Initial Setup - Populate chaos_platform Database
```bash
# Extract all metrics from Grafana dashboards and store in chaos_platform
for system in postgres mysql mongodb redis cassandra kafka rabbitmq mssql; do
  python baseline_manager.py sync \
    --system $system \
    --dashboard /chaos/dashboards/${system}_dashboard.json
done

# Verify data in chaos_platform
python baseline_manager.py query --system postgres
```

### Use Case 2: Validate Baselines in chaos_platform Database
```bash
# Validate all systems stored in chaos_platform
python baseline_manager.py validate --source database --all-systems

# Validate specific system in chaos_platform
python baseline_manager.py validate --source database --system postgres
```

### Use Case 3: Pre-Experiment Validation
```bash
# Ensure chaos_platform baselines are valid before experiment
python baseline_manager.py validate --source database --all-systems && \
  chaos run experiment.json
```

### Use Case 4: Periodic Baseline Refresh
```bash
# Weekly cron job to update chaos_platform baselines
0 2 * * 0 python baseline_manager.py sync --system postgres --dashboard /chaos/dashboards/postgres.json
```

---

## Troubleshooting

### Issue: "Metric not found in Prometheus"
**Solution:** Verify metric exists and is scraped
```bash
curl "http://prometheus:9090/api/v1/query?query=metric_name"
```

### Issue: "chaos_platform database connection failed"
**Solution:** Check chaos_platform database is running
```bash
# Verify chaos_platform database container
docker ps | grep postgres-primary-site-a

# Test connection to chaos_platform
psql -h postgres-primary-site-a -U postgres -d chaos_platform -c "SELECT 1"

# Check chaos_platform.baseline_metrics table exists
psql -h postgres-primary-site-a -U postgres -d chaos_platform \
  -c "\dt baseline_metrics"
```

### Issue: "No baselines found in chaos_platform database"
**Solution:** Run sync command first
```bash
# Populate chaos_platform database
python baseline_manager.py sync \
  --system postgres \
  --dashboard /chaos/dashboards/postgres_dashboard.json

# Verify data in chaos_platform
python baseline_manager.py query --system postgres
```

---

## Tool Comparison

| Feature | baseline_manager.py | Legacy Tools (deprecated) |
|---------|-------------------|---------------------------|
| **Commands** | 5 (sync, validate, analyze, generate, query) | 3 separate files |
| **Lines of Code** | 1,050 | 1,343 (27% reduction) |
| **Duplicate Code** | 0 | ~300 lines |
| **Database** | chaos_platform only | chaos_platform |
| **Prometheus Client** | Shared (single implementation) | Duplicated 3x |
| **Statistics Calculation** | Shared (single implementation) | Duplicated 2x |
| **Maintenance** | Single file | 3 files |
| **Status** | ✅ Active | ⚠️ Deprecated |

---

## Directory Structure

```
chaostooling-generic/
└── chaosgeneric/
    └── tools/
        ├── __init__.py
        ├── baseline_manager.py                (1,050 lines) ✅ USE THIS
        ├── baseline_metrics_sync.py          (deprecated)
        ├── validate_baseline_metrics.py      (deprecated)
        └── README.md                          (this file)
```

---

## Dependencies

```bash
# Required packages
pip install psycopg2-binary  # chaos_platform database connection
pip install requests          # Prometheus/Grafana API calls
```

---

## Related Documentation

- [TOOL_OVERLAP_ANALYSIS.md](../../../docs_local/TOOL_OVERLAP_ANALYSIS.md) - Tool consolidation analysis
- [BASELINE_TOOLSET_CONSOLIDATION.md](../../../docs_local/BASELINE_TOOLSET_CONSOLIDATION.md) - Consolidation summary
- [BASELINE_METRICS_SYNC_SUMMARY.md](../../../docs_local/BASELINE_METRICS_SYNC_SUMMARY.md) - Sync tool guide
- [DATABASE_EXPERIMENTS_STANDARDIZATION.md](../../../docs_local/DATABASE_EXPERIMENTS_STANDARDIZATION.md) - Multi-system standardization
- [POSTGRES_EXPERIMENTS_STANDARDIZATION.md](../../../docs_local/POSTGRES_EXPERIMENTS_STANDARDIZATION.md) - PostgreSQL baselines

---

**Last Updated:** January 30, 2026  
**Maintainer:** Chaostooling OSS Team  
**Location:** `chaostooling-generic/chaosgeneric/tools/`  
**Database:** All baselines stored in **chaos_platform** database
