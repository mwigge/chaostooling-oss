# Dynamic Steady-State Guide

**Version**: 1.0.0  
**Date**: January 31, 2026

## Overview

The Dynamic Steady-State feature automatically retrieves metrics from multiple sources (Grafana, Prometheus, chaos_platform DB, files) and calculates dynamic steady-state and steady-state-hypothesis based on historical data (24h or 30d periods).

## Features

- **Multi-Source Aggregation**: Fetches from Grafana, Prometheus, DB, and files
- **Dynamic Calculation**: Calculates mean, stddev, percentiles from historical data
- **Automatic Integration**: Seamlessly integrates with Chaos Toolkit lifecycle
- **Environment-Driven**: Fully configurable via environment variables
- **Console Output**: Prints formatted steady-state to experiment console

## Quick Start

### 1. Enable the Control

Add to your experiment's `controls` section:

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
  ]
}
```

### 2. Configure Environment Variables

```bash
# Enable feature
export DYNAMIC_STEADY_STATE_ENABLED=true

# Time period (24h or 30d)
export DYNAMIC_STEADY_STATE_PERIOD=30d

# Data sources (comma-separated)
export DYNAMIC_STEADY_STATE_SOURCES=grafana,prometheus,database,file

# Grafana configuration
export GRAFANA_URL=http://grafana:3000
export GRAFANA_DATASOURCE_UID=prometheus
export GRAFANA_API_KEY=your_api_key_here

# Prometheus configuration
export PROMETHEUS_URL=http://prometheus:9090

# Database configuration
export CHAOS_DB_HOST=chaos-platform-db
export CHAOS_DB_PORT=5432

# Baseline files (comma-separated)
export DYNAMIC_STEADY_STATE_BASELINE_FILES=postgres/baseline_metrics.json

# Console output
export DYNAMIC_STEADY_STATE_CONSOLE_OUTPUT=true
export DYNAMIC_STEADY_STATE_VERBOSE=false
```

### 3. Configure Metrics in Experiment

#### Option A: Explicit Metrics

```json
{
  "dynamic_steady_state": {
    "enabled": true,
    "period": "30d",
    "metrics": [
      "postgresql_commits_total",
      "chaos_db_connection_pool_utilization_percent"
    ],
    "sources": ["grafana", "prometheus", "database"],
    "threshold_sigma": 2.0
  }
}
```

#### Option B: Auto-Discovery from baseline_config

```json
{
  "baseline_config": {
    "metrics": [
      {
        "metric_name": "postgresql_commits_total",
        "service_name": "postgres"
      }
    ]
  }
}
```

#### Option C: Auto-Discovery from steady-state-hypothesis

The control automatically extracts `metric_name` from existing probes:

```json
{
  "steady-state-hypothesis": {
    "probes": [
      {
        "provider": {
          "arguments": {
            "metric_name": "postgresql_commits_total"
          }
        }
      }
    ]
  }
}
```

## Example Experiment

```json
{
  "version": "1.0",
  "title": "PostgreSQL Pool Exhaustion with Dynamic Steady-State",
  "configuration": {
    "postgres_host": {
      "type": "env",
      "key": "POSTGRES_HOST",
      "default": "postgres-primary"
    }
  },
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
      "chaos_db_connection_pool_utilization_percent"
    ],
    "threshold_sigma": 2.0
  },
  "steady-state-hypothesis": {
    "title": "Will be dynamically generated",
    "probes": []
  },
  "method": [
    {
      "name": "inject-pool-exhaustion",
      "type": "action",
      "provider": {
        "type": "python",
        "module": "chaosdb.actions.postgres.postgres_pool_exhaustion",
        "func": "inject_connection_pool_exhaustion"
      }
    }
  ]
}
```

## Console Output

When the experiment runs, you'll see:

```
================================================================================
DYNAMIC STEADY-STATE CALCULATION
================================================================================
Analyzing 2 metrics over 30d
Sources: grafana, prometheus, database, file
Processing metric: postgresql_commits_total
Processing metric: chaos_db_connection_pool_utilization_percent

DYNAMIC STEADY-STATE SUMMARY
--------------------------------------------------
Time Period: 30d
Metrics Calculated: 2
Average Quality Score: 92.5%
Data Sources: database, grafana, prometheus

================================================================================
DYNAMIC STEADY-STATE METRICS
================================================================================
Metric                                  Mean         StdDev       P95          P99          Quality
----------------------------------------------------------------------------------------------------
postgresql_commits_total                15.20        3.80         23.80        28.90        95
chaos_db_connection_pool_utilization...  28.50        5.20         40.20        58.30        90
================================================================================
```

## How It Works

1. **Before Experiment Start**: Control hook `before_experiment_start()` is called
2. **Metric Discovery**: Extracts metrics from experiment configuration
3. **Multi-Source Fetching**: Fetches from Grafana, Prometheus, DB, files in parallel
4. **Aggregation**: Combines data from all sources
5. **Statistics Calculation**: Calculates mean, stddev, percentiles
6. **Hypothesis Generation**: Creates steady-state-hypothesis with probes
7. **Experiment Update**: Updates experiment's steady-state-hypothesis dynamically
8. **Console Output**: Prints formatted table to console

## Data Sources

### Grafana
- Queries via Grafana API (datasource-agnostic)
- Supports Prometheus, Mimir, Loki, Tempo
- Requires `GRAFANA_URL` and optional `GRAFANA_API_KEY`

### Prometheus
- Direct PromQL queries
- Requires `PROMETHEUS_URL`

### Chaos Platform DB
- Queries `baseline_snapshots` table
- Requires `CHAOS_DB_HOST` and `CHAOS_DB_PORT`

### Files
- Reads from JSON baseline files
- Supports `baseline_config.metrics[]` format
- Configured via `DYNAMIC_STEADY_STATE_BASELINE_FILES`

## Troubleshooting

### No Metrics Calculated

**Problem**: "No metrics calculated, skipping steady-state update"

**Solutions**:
1. Check that metrics are specified in `dynamic_steady_state.metrics` or `baseline_config.metrics`
2. Verify data sources are accessible (Grafana, Prometheus, DB)
3. Check logs for fetch errors

### Low Quality Scores

**Problem**: Quality scores < 50%

**Solutions**:
1. Increase time period (use 30d instead of 24h)
2. Enable more data sources
3. Ensure baseline files exist and contain metric data

### Source Failures

**Problem**: Warnings about failed fetches

**Solutions**:
1. Verify network connectivity to Grafana/Prometheus
2. Check API keys and credentials
3. Verify database connection
4. System continues with available sources (graceful degradation)

## Best Practices

1. **Use 30d Period**: Provides more stable baselines than 24h
2. **Enable All Sources**: More sources = better quality scores
3. **Explicit Metrics**: Specify metrics explicitly for better control
4. **Monitor Quality Scores**: Aim for >80% quality scores
5. **Test in Staging**: Validate configuration before production

## Environment Variables Reference

| Variable | Default | Description |
|----------|---------|-------------|
| `DYNAMIC_STEADY_STATE_ENABLED` | `true` | Enable/disable feature |
| `DYNAMIC_STEADY_STATE_PERIOD` | `30d` | Time period (24h, 30d) |
| `DYNAMIC_STEADY_STATE_SOURCES` | `grafana,prometheus,database,file` | Comma-separated sources |
| `GRAFANA_URL` | `http://grafana:3000` | Grafana API URL |
| `GRAFANA_DATASOURCE_UID` | `prometheus` | Grafana datasource UID |
| `GRAFANA_API_KEY` | - | Grafana API key (optional) |
| `PROMETHEUS_URL` | `http://prometheus:9090` | Prometheus API URL |
| `CHAOS_DB_HOST` | `chaos-platform-db` | Database host |
| `CHAOS_DB_PORT` | `5432` | Database port |
| `DYNAMIC_STEADY_STATE_BASELINE_FILES` | - | Comma-separated file paths |
| `DYNAMIC_STEADY_STATE_CONSOLE_OUTPUT` | `true` | Print to console |
| `DYNAMIC_STEADY_STATE_VERBOSE` | `false` | Verbose output |

## See Also

- [Architecture Document](../01-project-overview/AUTOMATIC_METRICS_RETRIEVAL_ARCHITECTURE.md)
- [Baseline Metrics Guide](./BASELINE_METRICS_GUIDE.md)
- [Experiment Configuration Guide](./EXPERIMENT_CONFIGURATION_GUIDE.md)
