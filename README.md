# ChaosTooling OSS

Open source Chaos Engineering toolkit ecosystem built on Chaos Toolkit.

**[📖 Documentation Index](README_UPDATE_INDEX.md)** | **[🚀 Quick Start](#quick-start)** | **[🏗️ Architecture](#architecture)** | **[📚 Extensions](#extensions)**

---

## 🎯 Baseline Metrics Integration - Production Ready!

**Status**: ✅ 100% Complete (v0.1.0 Released)  
**Tests**: 100+ tests passing (100% pass rate)  
**Coverage**: >95% code coverage  
**Schedule**: 22.5 hours ahead of plan  

### What's Included

✅ **BaselineLoader Service** - Discovers and manages baseline metrics from steady-state systems  
✅ **BaselineManager Commands** - `discover`, `status`, `suggest` for baseline operations  
✅ **Database Integration** - 5 new columns, 3 optimized indexes, audit trail  
✅ **9 Updated Experiments** - All postgres experiments configured for baseline validation  
✅ **Full Observability** - Traces (Tempo), Metrics (Prometheus), Logs (Loki)  
✅ **Production Documentation** - 5,000+ lines (User Guide, DBA Guide, Deployment Guide)  
✅ **Deployment Ready** - Docker Compose support, rollback scripts  

### Quick Links
- **[START HERE](docs_local/projects/chaostooling-generic/01-project-overview/START_HERE.md)** ← New to the project?
- **[Deployment Guide](docs_local/projects/chaostooling-generic/07-deployment/DEPLOYMENT_GUIDE.md)** - Installation procedures
- **[User Guide](docs_local/projects/chaostooling-generic/05-documentation-guides/README.md)** - Complete documentation
- **[DBA Quick Start](docs_local/projects/chaostooling-generic/05-documentation-guides/DBA_QUICK_START.md)** - Database operations
- **[Release Notes](docs_local/projects/chaostooling-generic/07-deployment/RELEASE_NOTES.md)** - v0.1.0 release information
- **[Full Documentation Index](docs_local/projects/chaostooling-generic/README.md)** - Complete navigation

---

## Overview

ChaosTooling provides a comprehensive set of extensions, observability tools, and demo environments for chaos engineering. This monorepo contains all components needed to run chaos experiments with full observability, baseline metric validation, and automated result storage.

### Key Features

✅ **7-Control Standard** - Unified experiment lifecycle management  
✅ **Database Integration** - Automatic results storage and querying  
✅ **Baseline Metrics** - Pre/during/post chaos comparison (NEW - Production Ready!)  
✅ **Dynamic Steady-State** - Automatic baseline calculation from historical metrics (NEW!)  
✅ **Full Observability** - Traces, metrics, logs via OpenTelemetry  
✅ **60+ Chaos Actions** - Database, network, compute, messaging systems  
✅ **Automated Reporting** - Risk/complexity/quality scores  
✅ **Production-Ready** - Error handling, rollback, compliance tracking  

---

## Quick Start

### Prerequisites

- **Docker & Docker Compose** (for demo environment)
- **Python 3.10+** (for local development)
- **PostgreSQL** (for chaos_platform results database)

### 1. Installation

**Option A: Docker Compose (Recommended)**

```bash
cd chaostooling-demo
docker compose up -d

# Verify services
docker compose ps
```

**Option B: Local Installation**

```bash
# Create virtual environment
python3.10 -m venv venv
source venv/bin/activate

# Install all packages
pip install -e chaostooling-generic
pip install -e chaostooling-extension-db
pip install -e chaostooling-otel
pip install -e chaostooling-extension-compute
pip install -e chaostooling-extension-network
pip install -e chaostooling-extension-app
pip install -e chaostooling-reporting

# Install Chaos Toolkit
pip install chaostoolkit
```

### 2. Environment Configuration

Create `.env` file in experiment directory:

```bash
# Observability
export OTEL_SERVICE_NAME=chaostooling-demo
export OTEL_EXPORTER_OTLP_ENDPOINT=http://otel-collector:4317
export OTEL_EXPORTER_OTLP_PROTOCOL=http/protobuf

# Target Database (what we're testing)
export POSTGRES_HOST=postgres-primary
export POSTGRES_PORT=5432
export POSTGRES_DB=testdb
export POSTGRES_USER=postgres
export POSTGRES_PASSWORD=postgres

# Results Database (chaos_platform)
export CHAOS_DB_HOST=postgres-chaos-platform
export CHAOS_DB_PORT=5432
export CHAOS_DB_NAME=chaos_platform
export CHAOS_DB_USER=chaos_admin
export CHAOS_DB_PASSWORD=changeme

# Observability Backends
export PROMETHEUS_URL=http://prometheus:9090
export TEMPO_URL=http://tempo:3200
export LOKI_URL=http://loki:3100
```

Load environment:

```bash
source .env
```

### 3. Run Your First Experiment

```bash
# Navigate to experiments
cd chaostooling-experiments

# Run PostgreSQL pool exhaustion test
chaos run postgres/mcp-test-postgres-pool-exhaustion.json
```

**Expected Output:**

```
2026-01-30 14:25:34 INFO    Preparing chaos experiment...
2026-01-30 14:25:34 INFO    [experiment-orchestrator] Generated experiment_id=1847291234
2026-01-30 14:25:34 INFO    [env-loader] Loaded 18 environment variables
2026-01-30 14:25:35 INFO    [database-storage] Connected to chaos_platform database
2026-01-30 14:25:35 INFO    Steady state probe (check_baseline_metrics)
2026-01-30 14:25:35 DEBUG   ✅ Baseline: postgresql_commits_total - mean=45.2, current=44.8 (within bounds)
2026-01-30 14:25:35 DEBUG   ✅ Baseline: postgresql_backends - mean=8, current=7 (within bounds)
2026-01-30 14:25:36 INFO    Starting chaos (action: exhaust_connection_pool)
2026-01-30 14:25:36 DEBUG   🔴 During chaos: postgresql_backends=98 (spike detected - expected 8)
2026-01-30 14:25:56 INFO    Stopping chaos (rollback)
2026-01-30 14:25:56 INFO    Recovery metrics collected
2026-01-30 14:25:58 INFO    [database-display] Storing 45 metrics to database
2026-01-30 14:25:58 INFO    [metrics-calculator] Risk: 0.85, Complexity: 0.62, Quality: 0.78
2026-01-30 14:25:59 INFO    [reporting] Generated PDF report: experiment-report-20260130-142559.pdf
2026-01-30 14:25:59 INFO    Experiment completed successfully in 25.2 seconds
```

### 4. View Results

**In Grafana Dashboard:**
- Open http://localhost:3000
- Credentials: admin/changeme (set via GRAFANA_ADMIN_PASSWORD env var)
- Dashboard: "Chaos Experiments"

**From Database:**

```bash
# View experiment runs
docker exec postgres-chaos-platform psql -U chaos_admin -d chaos_platform -c \
  "SELECT run_id, experiment_id, status, duration_seconds FROM experiment_runs ORDER BY created_at DESC LIMIT 5;"

# View collected metrics
docker exec postgres-chaos-platform psql -U chaos_admin -d chaos_platform -c \
  "SELECT metric_name, value, timestamp FROM metric_snapshots WHERE experiment_id = 1847291234 LIMIT 10;"

# View baseline comparison
docker exec postgres-chaos-platform psql -U chaos_admin -d chaos_platform -c \
  "SELECT metric_name, baseline_mean, baseline_stdev, observed_value FROM metric_snapshots WHERE experiment_id = 1847291234;"
```

---

## Architecture

### 7-Control Standard Structure

All experiments follow a standardized 7-control lifecycle:

```
┌─────────────────────────────────────────────────────────────┐
│           Chaos Toolkit Experiment Execution                │
└────────────────────────┬────────────────────────────────────┘
                         │
        ┌────────────────┴────────────────┐
        │    CONTROL EXECUTION ORDER      │
        └────────────────┬────────────────┘
                         │
    1️⃣  experiment-orchestrator (generate experiment_id)
    2️⃣  env-loader (load .env variables)
    3️⃣  database-storage (store to chaos_platform DB)
    4️⃣  database-display (query and display results)
    5️⃣  opentelemetry (traces/metrics/logs)
    6️⃣  reporting (generate reports)
    7️⃣  metrics-calculator (compute quality scores)
```

**Control Responsibilities:**

| Control | Role | Key Features |
|---------|------|--------------|
| **experiment-orchestrator** | Generates stable experiment_id | No DB dependency, pure metadata |
| **env-loader** | Loads environment variables | Supports `.env` files and system vars |
| **database-storage** | Persists results | Auto-creates tables, transaction support |
| **database-display** | Queries and displays data | Real-time result retrieval |
| **opentelemetry** | Observability instrumentation | Traces, metrics, logs, compliance |
| **reporting** | Generates experiment reports | PDF, JSON, HTML formats |
| **metrics-calculator** | Calculates quality metrics | Risk, complexity, test score |
| **dynamic-steady-state** | Automatic baseline calculation | Fetches from Grafana/Prometheus/DB/Files, calculates statistics, generates steady-state-hypothesis |

### Component Architecture

```
┌────────────────────────────────────────────────────────────────┐
│                  Chaos Toolkit Experiment                      │
│         (experiment.json with controls and actions)            │
└────────────────────────────────────────────────────────────────┘
                             │
                             ▼
┌────────────────────────────────────────────────────────────────┐
│                    chaostooling-generic                        │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │ CONTROLS (7-Standard)                                    │  │
│  │ ├─ experiment-orchestrator (metadata generation)         │  │
│  │ ├─ env-loader (environment setup)                        │  │
│  │ ├─ database-storage (results persistence)                │  │
│  │ ├─ database-display (results retrieval)                  │  │
│  │ └─ metrics-calculator (quality scoring)                  │  │
│  └──────────────────────────────────────────────────────────┘  │
└────────────────────────────────────────────────────────────────┘
                             │
                             ▼
┌────────────────────────────────────────────────────────────────┐
│                  Chaos Action Modules                          │
│  ┌──────────────┬──────────────┬──────────────┬────────────┐   │
│  │ extension-db │ extension-   │ extension-   │ extension- │   │
│  │              │ network      │ compute      │ app        │   │
│  │ (60+ actions)│ (40+ actions)│ (30+ actions)│(20+ action)│   │
│  └──────────────┴──────────────┴──────────────┴────────────┘   │
└────────────────────────────────────────────────────────────────┘
                             │
            ┌────────────────┼────────────────┐
            │                │                │
            ▼                ▼                ▼
        ┌────────┐      ┌──────────┐    ┌──────────┐
        │OpenTel │      │chaos_    │    │Reporting │
        │emetry  │      │platform  │    │ Control  │
        │ (otel) │      │ Database │    │ (reports)│
        └────────┘      └──────────┘    └──────────┘
```

### Database Integration

Experiment results are automatically stored in `chaos_platform` database:

**Key Tables:**

```sql
-- Experiment metadata
experiments (experiment_id, title, description, tags, metadata)

-- Individual runs
experiment_runs (run_id, experiment_id, status, start_time, duration_seconds, metrics_collected)

-- Baseline statistics
baseline_metrics (metric_id, service, metric_name, mean_value, stdev_value, min_value, max_value)

-- Collected metrics during experiment
metric_snapshots (snapshot_id, run_id, metric_name, value, timestamp, phase)

-- Action/probe audit trail
audit_log (log_id, action, entity_type, entity_id, actor, action_timestamp, details)
```

**Example Queries:**

```sql
-- Get latest experiment results
SELECT 
    e.title,
    r.run_id,
    r.status,
    r.start_time,
    r.duration_seconds
FROM experiments e
JOIN experiment_runs r ON e.experiment_id = r.experiment_id
ORDER BY r.created_at DESC
LIMIT 10;

-- Compare metrics against baseline
SELECT 
    m.metric_name,
    b.mean_value as baseline_mean,
    b.stdev_value as baseline_stdev,
    m.value as observed_value,
    ROUND(((m.value - b.mean_value) / b.stdev_value)::numeric, 2) as sigma_deviation
FROM metric_snapshots m
JOIN baseline_metrics b ON m.metric_name = b.metric_name
WHERE m.run_id = 'run_12345'
ORDER BY m.timestamp;
```

---

## Extensions

### 🗄️ chaostooling-extension-db

**Database & Messaging System Chaos**

- **60+ Chaos Actions** - Connection pool, query saturation, lock storms, transaction delays, message floods
- **Supported Systems** - PostgreSQL, MySQL, MSSQL, MongoDB, Redis, Cassandra, Kafka, RabbitMQ, ActiveMQ
- **Health Probes** - Connection pool status, replication lag, queue depth, message latency
- **Real-World Scenarios** - Connection exhaustion, slow query injection, deadlock detection

[📖 Full Documentation](chaostooling-extension-db/README.md)

**Example: Connection Pool Exhaustion**

```bash
chaos run postgres/mcp-test-postgres-pool-exhaustion.json
```

### 🌐 chaostooling-extension-network

**Network Chaos & Resilience Testing**

- **Latency/Jitter Injection** - Simulate network delays
- **Packet Loss** - Test timeout handling
- **Bandwidth Limits** - Test rate limiting behavior
- **DNS Failures** - Test DNS resolution fallback

[📖 Full Documentation](chaostooling-extension-network/README.md)

### 💻 chaostooling-extension-compute

**CPU, Memory, and System Resource Chaos**

- **CPU Spike Injection** - Load CPU cores
- **Memory Exhaustion** - Test OOM handling
- **Disk I/O Saturation** - Test I/O limits
- **Process Limits** - Test process creation limits

[📖 Full Documentation](chaostooling-extension-compute/README.md)

### 📱 chaostooling-extension-app

**Application-Level Chaos**

- **Request Injection** - Inject slow/error responses
- **Session Disruption** - Kill sessions and connections
- **Feature Flags** - Toggle features during experiments
- **Configuration Changes** - Dynamic configuration chaos

[📖 Full Documentation](chaostooling-extension-app/README.md)

### 📊 chaostooling-otel

**OpenTelemetry Observability Foundation**

- **Distributed Tracing** - Full request trace visibility (Tempo, Jaeger)
- **Prometheus Metrics** - 60+ built-in metrics
- **Structured Logging** - All logs → Loki with trace correlation
- **Service Graphs** - Databases/queues automatically visible
- **Compliance Tracking** - SOX, GDPR, PCI-DSS, HIPAA

[📖 Full Documentation](chaostooling-otel/README.md)

### 🔧 chaostooling-generic

**Generic Controls & Utilities**

- **env-loader** - Load environment variables from `.env` files
- **experiment-orchestrator** - Generate stable experiment metadata
- **database-storage** - Auto-persist results to chaos_platform
- **database-display** - Query and display results
- **metrics-calculator** - Calculate experiment quality scores
- **Load Generators** - JMeter, Gatling integration

[📖 Full Documentation](chaostooling-generic/README.md)

### 📈 chaostooling-reporting

**Reporting & Analytics**

- **Experiment Reports** - PDF/HTML generation
- **Metrics Analysis** - Statistical analysis of results
- **Baseline Comparison** - Pre/during/post chaos comparison
- **Trend Analysis** - Detect performance changes
- **Compliance Reports** - Regulation-specific reports (SOX, GDPR, PCI-DSS, HIPAA)

[📖 Full Documentation](chaostooling-reporting/README.md)

---

## Configuration

### Environment Variables

All configuration uses environment variables for flexibility:

```bash
# ==== OBSERVABILITY ====
OTEL_SERVICE_NAME=chaostoolkit
OTEL_EXPORTER_OTLP_ENDPOINT=http://otel-collector:4317
OTEL_EXPORTER_OTLP_PROTOCOL=http/protobuf
OTEL_LOG_LEVEL=INFO

# ==== TARGET DATABASE (what we're testing) ====
POSTGRES_HOST=postgres-primary
POSTGRES_PORT=5432
POSTGRES_DB=testdb
POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres
POSTGRES_POOL_MIN_SIZE=2
POSTGRES_POOL_MAX_SIZE=10

# ==== RESULTS DATABASE (chaos_platform) ====
CHAOS_DB_HOST=postgres-chaos-platform
CHAOS_DB_PORT=5432
CHAOS_DB_NAME=chaos_platform
CHAOS_DB_USER=chaos_admin
CHAOS_DB_PASSWORD=chaos_password

# ==== OBSERVABILITY BACKENDS ====
PROMETHEUS_URL=http://prometheus:9090
TEMPO_URL=http://tempo:3200
LOKI_URL=http://loki:3100
GRAFANA_URL=http://grafana:3000

# ==== CHAOS PARAMETERS ====
CHAOS_DURATION_SECONDS=60
CHAOS_INTENSITY=0.8
CHAOS_THREAD_COUNT=5

# ==== DYNAMIC STEADY-STATE (Automatic Baseline Calculation) ====
DYNAMIC_STEADY_STATE_ENABLED=true
DYNAMIC_STEADY_STATE_PERIOD=30d
DYNAMIC_STEADY_STATE_SOURCES=grafana,prometheus,database,file
DYNAMIC_STEADY_STATE_BASELINE_FILES=
DYNAMIC_STEADY_STATE_CONSOLE_OUTPUT=true
DYNAMIC_STEADY_STATE_VERBOSE=false
```

See individual extension READMEs for system-specific variables.

### Dynamic Steady-State Control

The **Dynamic Steady-State Control** automatically calculates baseline metrics from historical data before your experiment runs. It:

1. **Fetches metrics** from multiple sources (Grafana, Prometheus, Database, Files)
2. **Calculates statistics** (mean, stddev, percentiles) over a configurable time period
3. **Generates steady-state-hypothesis** dynamically with appropriate tolerance ranges
4. **Updates your experiment** before execution

**Usage in Experiment:**

```json
{
  "controls": [
    {
      "name": "dynamic-steady-state",
      "provider": {
        "type": "python",
        "module": "chaosgeneric.control.dynamic_steady_state_control"
      }
    }
  ],
  "dynamic_steady_state": {
    "enabled": true,
    "period": "30d",
    "metrics": ["postgresql_commits_total", "rate(postgresql_commits_total[5m])"],
    "sources": ["grafana", "prometheus", "database", "file"],
    "threshold_sigma": 2.0
  }
}
```

**See:**
- **[Usage Guide](docs_local/projects/chaostooling-generic/05-documentation-guides/DYNAMIC_STEADY_STATE_USAGE.md)** - Complete usage instructions
- **[Flowchart Diagram](docs_local/projects/chaostooling-generic/05-documentation-guides/DYNAMIC_STEADY_STATE_FLOWCHART.drawio)** - Visual flow diagram

### .env.example Template

```bash
# Copy to .env and customize
# Required for experiments to run

# Observability Stack
export OTEL_SERVICE_NAME=my-chaos-experiments
export OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4317
export OTEL_EXPORTER_OTLP_PROTOCOL=http/protobuf

# Database to Test (Primary)
export POSTGRES_HOST=localhost
export POSTGRES_PORT=5432
export POSTGRES_DB=my_app_db
export POSTGRES_USER=appuser
export POSTGRES_PASSWORD=secret

# Results Database (Secondary)
export CHAOS_DB_HOST=localhost
export CHAOS_DB_PORT=5433
export CHAOS_DB_NAME=chaos_results
export CHAOS_DB_USER=chaos_user
export CHAOS_DB_PASSWORD=chaos_secret

# Monitoring Backends
export PROMETHEUS_URL=http://localhost:9090
export TEMPO_URL=http://localhost:3200
export LOKI_URL=http://localhost:3100
```

---

## Examples

### 1. PostgreSQL Connection Pool Exhaustion

**File:** `chaostooling-experiments/postgres/mcp-test-postgres-pool-exhaustion.json`

**What it tests:**
- How application handles when all connections are exhausted
- Recovery after connection pool is released
- Impact on transaction throughput

**Run it:**

```bash
cd chaostooling-experiments
chaos run postgres/mcp-test-postgres-pool-exhaustion.json
```

**Expected results (in database):**

```sql
SELECT metric_name, value, phase 
FROM metric_snapshots 
WHERE run_id = (SELECT run_id FROM experiment_runs ORDER BY created_at DESC LIMIT 1)
ORDER BY metric_name;

-- Results show:
-- postgresql_backends: 5 (baseline) → 100 (chaos) → 5 (recovery)
-- chaos_db_query_latency_ms: 50 (baseline) → 5000+ (chaos) → 50 (recovery)
-- chaos_db_connection_errors_total: 0 (baseline) → 45 (chaos) → 0 (recovery)
```

### Custom Experiment Template

Create `my-experiment.json`:

```json
{
  "version": "1.0",
  "title": "My Custom Chaos Experiment",
  "description": "Testing my application",
  "tags": ["database", "custom"],
  
  "configuration": {
    "postgres_host": {
      "type": "env",
      "key": "POSTGRES_HOST",
      "default": "localhost"
    }
  },
  
  "baseline-metrics-summary": {
    "description": "Expected metrics in healthy state",
    "metrics": [
      {
        "name": "postgresql_commits_total",
        "baseline_expected_mean": "50 commits/sec",
        "baseline_expected_stddev": "5 commits/sec"
      }
    ]
  },
  
  "controls": [
    {
      "name": "experiment-orchestrator",
      "provider": {
        "type": "python",
        "module": "chaosgeneric.control.experiment_orchestrator_control"
      }
    },
    {
      "name": "env-loader",
      "provider": {
        "type": "python",
        "module": "chaosgeneric.control.env_loader_control"
      }
    },
    {
      "name": "database-storage",
      "provider": {
        "type": "python",
        "module": "chaosgeneric.control.database_storage_control"
      }
    }
  ],
  
  "steady-state-hypothesis": {
    "title": "System is healthy",
    "probes": [
      {
        "type": "probe",
        "name": "postgres-running",
        "provider": {
          "type": "python",
          "module": "chaosdb.postgres.probes",
          "func": "database_is_healthy",
          "arguments": {
            "host": "${postgres_host}"
          }
        }
      }
    ]
  },
  
  "method": [
    {
      "type": "action",
      "name": "exhaust-connections",
      "provider": {
        "type": "python",
        "module": "chaosdb.postgres.actions",
        "func": "exhaust_connection_pool",
        "arguments": {
          "host": "${postgres_host}",
          "duration": 30
        }
      }
    }
  ]
}
```

---

## Troubleshooting

### Common Issues

#### "No baseline data found"

**Problem:** Experiment says baseline metrics are not configured

**Solution:**
1. Add `baseline-metrics-summary` section to experiment JSON
2. Include actual metrics with mean/stdev values
3. See `baseline_metrics.json` in experiment directories for examples

#### "Database connection failed"

**Problem:** Cannot connect to chaos_platform database

**Solution:**
```bash
# Check database is running
docker compose ps postgres-chaos-platform

# Test connection
docker exec postgres-chaos-platform psql -U chaos_admin -d chaos_platform -c "SELECT 1"

# Check environment variables
echo $CHAOS_DB_HOST $CHAOS_DB_PORT $CHAOS_DB_USER
```

#### "Prometheus not responding"

**Problem:** Cannot reach Prometheus for metrics

**Solution:**
```bash
# Check Prometheus is running
curl http://localhost:9090/api/v1/status/config

# Verify PROMETHEUS_URL environment variable
echo $PROMETHEUS_URL

# Check firewall/network
docker network inspect chaostooling-demo_default
```

#### "Traces not appearing in Tempo"

**Problem:** Traces not visible in Tempo/Grafana

**Solution:**
```bash
# Verify OTEL collector is receiving spans
docker compose logs otel-collector | grep -i span

# Check endpoint is correct
echo $OTEL_EXPORTER_OTLP_ENDPOINT

# Verify service name
echo $OTEL_SERVICE_NAME
```

### Debug Tips

**Enable debug logging:**

```bash
export OTEL_LOG_LEVEL=DEBUG
export CHAOS_DEBUG=true
chaos run experiment.json
```

**View experiment logs:**

```bash
# Docker logs
docker compose logs -f chaos-runner

# File logs
tail -f chaostooling-experiments/chaostoolkit.log
```

**Check database directly:**

```bash
# Connect to results database
docker exec -it postgres-chaos-platform psql -U chaos_admin -d chaos_platform

# View last experiment
SELECT * FROM experiment_runs ORDER BY created_at DESC LIMIT 1;

# View metrics collected
SELECT metric_name, COUNT(*) FROM metric_snapshots GROUP BY metric_name;
```

---

## Advanced Usage

### Creating Custom Actions

Create new action in `chaostooling-extension-db/chaosdb/postgres/actions.py`:

```python
from opentelemetry import trace
from chaosotel import get_tracer, get_metrics_core

def my_custom_chaos(host: str, port: int = 5432, duration: int = 30) -> dict:
    """Custom chaos action with full observability."""
    tracer = get_tracer()
    metrics = get_metrics_core()
    
    with tracer.start_as_current_span("my_custom_chaos") as span:
        span.set_attribute("db.host", host)
        try:
            impact = inject_chaos(host, port, duration)
            metrics.record_operation_count(name="my_custom_chaos", status="success")
            return {"status": "success", "impact": impact}
        except Exception as e:
            metrics.record_operation_count(name="my_custom_chaos", status="error")
            raise
```

### Integrating with CI/CD

Example GitHub Actions workflow:

```yaml
name: Chaos Experiments
on: [push]
jobs:
  chaos-tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - name: Start docker services
        run: cd chaostooling-demo && docker compose up -d
      - name: Run chaos experiments
        run: cd chaostooling-experiments && chaos run postgres/mcp-test-postgres-pool-exhaustion.json
      - name: Check results
        run: |
          docker exec postgres-chaos-platform psql -U chaos_admin -d chaos_platform -c \
            "SELECT status, COUNT(*) FROM experiment_runs GROUP BY status;"
```

---

## Support & Documentation

| Topic | Link |
|-------|------|
| Extension: Database/Messaging | [chaostooling-extension-db](chaostooling-extension-db/README.md) |
| Extension: Network | [chaostooling-extension-network](chaostooling-extension-network/README.md) |
| Extension: Compute | [chaostooling-extension-compute](chaostooling-extension-compute/README.md) |
| Extension: App | [chaostooling-extension-app](chaostooling-extension-app/README.md) |
| Observability | [chaostooling-otel](chaostooling-otel/README.md) |
| Generic Utilities | [chaostooling-generic](chaostooling-generic/README.md) |
| Reporting | [chaostooling-reporting](chaostooling-reporting/README.md) |
| Experiments | [chaostooling-experiments](chaostooling-experiments/) |
| Demo Environment | [chaostooling-demo](chaostooling-demo/) |

---

## License

Apache License 2.0 - See [LICENSE](LICENSE) for details

---

**Last Updated:** January 30, 2026  
**Version:** 0.1.0  
**Chaos Toolkit Version:** 1.42.1+  
**Author:** Morgan Wigge (morgan@wigge.nu)
