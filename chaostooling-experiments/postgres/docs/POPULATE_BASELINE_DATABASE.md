# How to Populate Baseline Database from Grafana/Prometheus

This guide explains how to populate the `chaos_platform` database with baseline metrics from Grafana or Prometheus.

---

## 📋 Overview

There are **two approaches** to getting baseline data:

1. **Manual Sync** (one-time setup): Use `baseline_manager.py sync` to populate the database
2. **Dynamic Steady-State** (runtime): The dynamic steady-state control reads from Grafana/Prometheus/DB/files during experiments

---

## 🔧 Required Environment Variables

### For Grafana Access

| Variable | Description | Default | Required |
|----------|-------------|---------|----------|
| `GRAFANA_URL` | Grafana API URL | `http://grafana:3000` | ✅ Yes |
| `GRAFANA_API_KEY` | Grafana API token (for authentication) | (empty) | ⚠️ If auth enabled |
| `GRAFANA_API_TOKEN` | Alternative name for Grafana token | (empty) | ⚠️ If auth enabled |

### For Prometheus Access

| Variable | Description | Default | Required |
|----------|-------------|---------|----------|
| `PROMETHEUS_URL` | Prometheus API URL | `http://prometheus:9090` | ✅ Yes |

### For Database Access

| Variable | Description | Default | Required |
|----------|-------------|---------|----------|
| `CHAOS_DB_HOST` | Chaos platform database host | `chaos-platform-db` | ✅ Yes |
| `CHAOS_DB_PORT` | Chaos platform database port | `5432` | ✅ Yes |
| `CHAOS_DB_NAME` | Database name | `chaos_platform` | ✅ Yes |
| `CHAOS_DB_USER` | Database user | `chaos_admin` | ✅ Yes |
| `CHAOS_DB_PASSWORD` | Database password | (empty) | ✅ Yes |

---

## 📝 Setting Environment Variables in Experiment File

You can set these in the `configuration` section of your experiment JSON:

```json
{
  "configuration": {
    "grafana_url": {
      "type": "env",
      "key": "GRAFANA_URL",
      "default": "http://grafana:3000"
    },
    "grafana_api_key": {
      "type": "env",
      "key": "GRAFANA_API_KEY",
      "default": ""
    },
    "prometheus_url": {
      "type": "env",
      "key": "PROMETHEUS_URL",
      "default": "http://prometheus:9090"
    },
    "chaos_db_host": {
      "type": "env",
      "key": "CHAOS_DB_HOST",
      "default": "chaos-platform-db"
    },
    "chaos_db_port": {
      "type": "env",
      "key": "CHAOS_DB_PORT",
      "default": "5432"
    },
    "chaos_db_name": {
      "type": "env",
      "key": "CHAOS_DB_NAME",
      "default": "chaos_platform"
    },
    "chaos_db_user": {
      "type": "env",
      "key": "CHAOS_DB_USER",
      "default": "chaos_admin"
    },
    "chaos_db_password": {
      "type": "env",
      "key": "CHAOS_DB_PASSWORD",
      "default": ""
    }
  }
}
```

---

## 🚀 Method 1: Manual Sync (Populate Database)

Use `baseline_manager.py` to sync metrics from Grafana/Prometheus to the database.

### Step 1: Run Sync Command

From within the `chaos-runner` container:

```bash
# Enter container
docker exec -it chaostooling-demo-chaos-runner-1 bash

# Navigate to tools directory
cd /chaostooling-oss/chaostooling-generic/chaosgeneric/tools

# Sync from Grafana to database
python baseline_manager.py sync \
  --system postgres \
  --time-range 30d \
  --grafana-url http://grafana:3000 \
  --grafana-token YOUR_GRAFANA_TOKEN \
  --db-host chaos-platform-db \
  --db-port 5432 \
  --db-user chaos_admin \
  --db-password chaos_admin_secure_password
```

### Step 2: Verify Data

```bash
# Query baselines from database
python baseline_manager.py query \
  --system postgres \
  --db-host chaos-platform-db \
  --db-port 5432 \
  --db-user chaos_admin \
  --db-password chaos_admin_secure_password
```

### Sync Options

```bash
# Sync by system (postgres, mysql, mongodb, etc.)
python baseline_manager.py sync --system postgres

# Sync by service name
python baseline_manager.py sync --service postgres-primary-site-a

# Sync by custom labels
python baseline_manager.py sync --labels "system=postgres,service=api"

# Sync with custom time range
python baseline_manager.py sync --system postgres --time-range 7d
```

---

## 🔄 Method 2: Dynamic Steady-State (Runtime Fetching)

The dynamic steady-state control automatically fetches metrics during experiments. It reads from multiple sources but **does not write to the database**.

### Configuration in Experiment

Add to your experiment JSON:

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
    "metrics": [
      "postgresql_commits_total",
      "rate(postgresql_commits_total[5m])"
    ],
    "sources": ["grafana", "prometheus", "database", "file"],
    "threshold_sigma": 2.0
  }
}
```

### How It Works

1. **Before experiment starts**: Control fetches metrics from configured sources
2. **Calculates statistics**: Mean, stddev, percentiles
3. **Generates steady-state hypothesis**: Creates probes with tolerance ranges
4. **Stores in context**: Makes baselines available to probes via `context["loaded_baselines"]`

### Source Priority

The control tries sources in this order:
1. **Grafana**: Queries via Grafana API (requires `GRAFANA_URL`, `GRAFANA_API_KEY`)
2. **Prometheus**: Direct Prometheus queries (requires `PROMETHEUS_URL`)
3. **Database**: Reads from `chaos_platform.baseline_metrics` table (requires `CHAOS_DB_*` vars)
4. **Files**: Reads from JSON baseline files (requires `DYNAMIC_STEADY_STATE_BASELINE_FILES`)

---

## 📊 Example: Adding to Extensive-postgres-experiment.json

Add these to the `configuration` section:

```json
{
  "configuration": {
    // ... existing config ...
    
    "grafana_url": {
      "type": "env",
      "key": "GRAFANA_URL",
      "default": "http://grafana:3000"
    },
    "grafana_api_key": {
      "type": "env",
      "key": "GRAFANA_API_KEY",
      "default": ""
    },
    "prometheus_url": {
      "type": "env",
      "key": "PROMETHEUS_URL",
      "default": "http://prometheus:9090"
    },
    "chaos_db_host": {
      "type": "env",
      "key": "CHAOS_DB_HOST",
      "default": "chaos-platform-db"
    },
    "chaos_db_port": {
      "type": "env",
      "key": "CHAOS_DB_PORT",
      "default": "5432"
    },
    "chaos_db_name": {
      "type": "env",
      "key": "CHAOS_DB_NAME",
      "default": "chaos_platform"
    },
    "chaos_db_user": {
      "type": "env",
      "key": "CHAOS_DB_USER",
      "default": "chaos_admin"
    },
    "chaos_db_password": {
      "type": "env",
      "key": "CHAOS_DB_PASSWORD",
      "default": "chaos_admin_secure_password"
    }
  }
}
```

---

## 🔍 Verifying Setup

### Check Environment Variables

```bash
# In chaos-runner container
echo $GRAFANA_URL
echo $PROMETHEUS_URL
echo $CHAOS_DB_HOST
```

### Test Grafana Connection

```bash
curl -H "Authorization: Bearer $GRAFANA_API_KEY" \
  http://grafana:3000/api/health
```

### Test Prometheus Connection

```bash
curl http://prometheus:9090/api/v1/query?query=up
```

### Test Database Connection

```bash
psql -h chaos-platform-db -U chaos_admin -d chaos_platform \
  -c "SELECT COUNT(*) FROM baseline_metrics WHERE service_name = 'postgres';"
```

---

## 🎯 Recommended Workflow

1. **Initial Setup** (one-time):
   ```bash
   # Populate database with baseline metrics
   python baseline_manager.py sync --system postgres --time-range 30d
   ```

2. **Verify Database**:
   ```bash
   python baseline_manager.py query --system postgres
   ```

3. **Run Experiment**:
   - Dynamic steady-state control will:
     - Try to read from database first (fastest)
     - Fall back to Grafana/Prometheus if needed
     - Calculate statistics and generate hypothesis

---

## 📚 Related Documentation

- [Dynamic Steady-State Usage Guide](DYNAMIC_STEADY_STATE_USAGE.md)
- [Baseline Manager README](../../chaosgeneric/tools/README.md)
- [Database Schema](../../chaosgeneric/tools/README.md#database-schema)

---

## ❓ Troubleshooting

### Issue: "No baseline data found"

**Solution**: Run manual sync first:
```bash
python baseline_manager.py sync --system postgres --time-range 30d
```

### Issue: "Grafana authentication failed"

**Solution**: Set `GRAFANA_API_KEY` environment variable:
```bash
export GRAFANA_API_KEY="your-token-here"
```

### Issue: "Database connection failed"

**Solution**: Verify database credentials:
```bash
psql -h chaos-platform-db -U chaos_admin -d chaos_platform
```

---

**Last Updated**: February 1, 2026
