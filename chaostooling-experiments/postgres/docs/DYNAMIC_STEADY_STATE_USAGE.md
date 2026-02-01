# Dynamic Steady-State Control - Usage Guide

## Overview

The **Dynamic Steady-State Control** is a Chaos Toolkit control that automatically:
1. Fetches metrics from multiple sources (Grafana, Prometheus, Database, Files)
2. Calculates baseline statistics (mean, stddev, percentiles) over a time period
3. Generates a `steady-state-hypothesis` dynamically
4. Updates your experiment before it runs

## How to Use

### Step 1: Add Control to Your Experiment

Add the control to your experiment's `controls` section:

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

### Step 2: Configure Dynamic Steady-State

Add a `dynamic_steady_state` section to your experiment:

```json
{
  "dynamic_steady_state": {
    "enabled": true,
    "period": "30d",
    "metrics": [
      "postgresql_commits_total",
      "chaos_db_connection_pool_utilization_percent"
    ],
    "sources": ["grafana", "prometheus", "database", "file"],
    "threshold_sigma": 2.0
  }
}
```

### Step 3: Leave steady-state-hypothesis Empty (or Minimal)

The control will populate it automatically:

```json
{
  "steady-state-hypothesis": {
    "title": "Will be dynamically generated from historical metrics",
    "probes": []
  }
}
```

## Configuration Options

### In Experiment JSON

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `enabled` | boolean | `true` | Enable/disable dynamic steady-state |
| `period` | string | `"30d"` | Time range (e.g., "24h", "7d", "30d") |
| `metrics` | array | `[]` | List of metric names to analyze |
| `sources` | array | `["grafana","prometheus","database","file"]` | Data sources to fetch from |
| `threshold_sigma` | float | `2.0` | Sigma threshold for bounds (2.0 = 95% confidence) |

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `DYNAMIC_STEADY_STATE_ENABLED` | `"true"` | Enable/disable globally |
| `DYNAMIC_STEADY_STATE_PERIOD` | `"30d"` | Default time range |
| `DYNAMIC_STEADY_STATE_SOURCES` | `"grafana,prometheus,database,file"` | Default sources |
| `DYNAMIC_STEADY_STATE_BASELINE_FILES` | `""` | Comma-separated paths to baseline JSON files |
| `DYNAMIC_STEADY_STATE_CONSOLE_OUTPUT` | `"true"` | Print results to console |
| `DYNAMIC_STEADY_STATE_VERBOSE` | `"false"` | Print detailed hypothesis |

## Metric Discovery

The control automatically discovers metrics from your experiment in this priority:

1. **Explicit**: `dynamic_steady_state.metrics` (highest priority)
2. **Baseline Config**: `baseline_config.metrics[].metric_name`
3. **Steady-State Probes**: `steady-state-hypothesis.probes[].arguments.metric_name`

## Example: Extensive PostgreSQL Experiment

See the flowchart diagram for a complete visual guide.

### Minimal Configuration

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
    "period": "30d",
    "metrics": ["postgresql_commits_total"]
  }
}
```

### Full Configuration

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
      "chaos_db_connection_pool_utilization_percent",
      "rate(postgresql_commits_total[5m])"
    ],
    "sources": ["grafana", "prometheus", "database", "file"],
    "threshold_sigma": 2.0
  },
  "steady-state-hypothesis": {
    "title": "Dynamically generated",
    "probes": []
  }
}
```

## Output

The control prints a formatted table to the console:

```
================================================================================
DYNAMIC STEADY-STATE CALCULATION
================================================================================
Analyzing 3 metrics over 30d
Sources: grafana, prometheus, database, file

Processing metric: postgresql_commits_total
Processing metric: chaos_db_connection_pool_utilization_percent
Processing metric: rate(postgresql_commits_total[5m])

┌─────────────────────────────────────────────────────────────────────────┐
│ Dynamic Steady-State Summary (30d)                                      │
├─────────────────────────────────────────────────────────────────────────┤
│ Metric                                    │ Mean    │ StdDev │ P95     │
├─────────────────────────────────────────────────────────────────────────┤
│ postgresql_commits_total                  │ 1250.5  │ 45.2   │ 1320.8  │
│ chaos_db_connection_pool_utilization_%   │ 65.3    │ 8.1    │ 78.5    │
│ rate(postgresql_commits_total[5m])      │ 4.2     │ 0.8    │ 5.5     │
└─────────────────────────────────────────────────────────────────────────┘

Dynamic steady-state calculation complete
================================================================================
```

## How It Works

1. **Chaos Toolkit** loads your experiment
2. **Control Hook** (`before_experiment_start`) is called
3. **Metrics Fetcher** retrieves data from all configured sources
4. **Calculator** computes statistics (mean, stddev, percentiles)
5. **Hypothesis Generator** creates steady-state-hypothesis with probes
6. **Experiment Updated** with dynamic steady-state before execution

See the flowchart diagram for detailed flow.
