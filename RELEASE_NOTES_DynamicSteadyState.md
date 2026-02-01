# Release Notes - DynamicSteadyState v1.0.0

**Release Date**: January 31, 2026  
**Tag**: `DynamicSteadyState`  
**Status**: ✅ Production Ready

---

## 🎯 Overview

The **Dynamic Steady-State** feature introduces automatic baseline metric calculation and steady-state hypothesis generation for chaos engineering experiments. Instead of manually defining static baselines, experiments now automatically fetch historical metrics from multiple sources, calculate statistical baselines, and generate dynamic steady-state hypotheses before execution.

This release eliminates the need for manual baseline configuration and enables experiments to adapt to changing system behavior automatically.

---

## ✨ Key Features

### 🔄 Automatic Baseline Calculation

- **Multi-Source Data Fetching**: Retrieves metrics from Grafana, Prometheus, PostgreSQL database, and local files
- **Parallel Data Collection**: Uses concurrent fetching for optimal performance
- **Statistical Analysis**: Calculates mean, standard deviation, and percentiles (50, 95, 99, 999) automatically
- **Time Range Flexibility**: Configurable analysis periods (24h, 7d, 30d, custom)

### 📊 Dynamic Steady-State Hypothesis Generation

- **Automatic Probe Creation**: Generates steady-state probes for each metric automatically
- **Sigma-Based Thresholds**: Configurable sigma thresholds (default: 2.0 = 95% confidence). Sigma (σ) represents standard deviations from the mean; a 2.0 sigma threshold means values beyond mean ± (2 × stddev) are flagged as anomalies. [Read more about sigma thresholds](https://en.wikipedia.org/wiki/68%E2%80%9395%E2%80%9399.7_rule)
- **Tolerance Ranges**: Calculates warning and critical bounds based on statistical distribution
- **Real-Time Updates**: Updates experiment configuration before execution

### 🎛️ Flexible Configuration

- **Environment Variable Driven**: Fully configurable via environment variables
- **Experiment-Level Override**: Per-experiment configuration in JSON
- **Source Selection**: Choose which data sources to use (Grafana, Prometheus, DB, Files)
- **Metric Discovery**: Automatic metric extraction from experiment configuration

### 📈 Console Output

- **Formatted Tables**: Beautiful console output with metric statistics
- **Summary Information**: Quick overview of calculated baselines
- **Verbose Mode**: Optional detailed hypothesis output
- **Real-Time Feedback**: See baseline calculation progress

---

## 🚀 Quick Start

### 1. Add Control to Experiment

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

### 2. Configure Dynamic Steady-State

```json
{
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

### 3. Run Experiment

```bash
chaos run Extensive-postgres-experiment.json
```

The control automatically:
1. Fetches metrics from all configured sources
2. Calculates baseline statistics
3. Generates steady-state-hypothesis
4. Updates experiment before execution
5. Prints formatted results to console

---

## 📋 What's Included

### Core Components (~855 lines of code)

- **`DynamicMetricsFetcher`**: Multi-source metric retrieval with parallel fetching
- **`DynamicSteadyStateCalculator`**: Statistical analysis and baseline calculation
- **`SteadyStateFormatter`**: Console output formatting
- **`DynamicSteadyStateControl`**: Chaos Toolkit control hook integration

### Files Added

- `chaosgeneric/tools/dynamic_metrics_fetcher.py`
- `chaosgeneric/tools/dynamic_steady_state_calculator.py`
- `chaosgeneric/tools/steady_state_formatter.py`
- `chaosgeneric/control/dynamic_steady_state_control.py`
- `tests/test_dynamic_steady_state.py` (50+ tests)
- `tests/test_dynamic_steady_state_control.py`

### Data Sources Supported

1. **Grafana**: Query metrics via Grafana API
2. **Prometheus**: Direct Prometheus API queries
3. **PostgreSQL Database**: Read from `chaos_platform.baseline_metrics` table
4. **Local Files**: Load from JSON baseline files

### Integration Points

- **Chaos Toolkit Lifecycle**: Hooks into `before_experiment_start`
- **Experiment Configuration**: Reads from `dynamic_steady_state` section
- **Context Storage**: Stores calculated metrics in experiment context
- **Probe Generation**: Creates steady-state probes automatically

---

## 🎛️ Configuration Options

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `DYNAMIC_STEADY_STATE_ENABLED` | `"true"` | Enable/disable globally |
| `DYNAMIC_STEADY_STATE_PERIOD` | `"30d"` | Time range for analysis |
| `DYNAMIC_STEADY_STATE_SOURCES` | `"grafana,prometheus,database,file"` | Data sources to use |
| `DYNAMIC_STEADY_STATE_BASELINE_FILES` | `""` | Comma-separated paths to baseline JSON files |
| `DYNAMIC_STEADY_STATE_CONSOLE_OUTPUT` | `"true"` | Print results to console |
| `DYNAMIC_STEADY_STATE_VERBOSE` | `"false"` | Print detailed hypothesis |

### Experiment Configuration

```json
{
  "dynamic_steady_state": {
    "enabled": true,              // Enable/disable for this experiment
    "period": "30d",              // Time range: "24h", "7d", "30d", etc.
    "metrics": [                  // Explicit metric list (optional)
      "postgresql_commits_total"
    ],
    "sources": [                  // Data sources to use
      "grafana",
      "prometheus",
      "database",
      "file"
    ],
    "threshold_sigma": 2.0        // Sigma threshold for bounds (2.0 = 95%)
  }
}
```

---

## 📊 Example Output

When you run an experiment, you'll see:

```
================================================================================
DYNAMIC STEADY-STATE CALCULATION
================================================================================
Analyzing 3 metrics over 30d
Sources: grafana, prometheus, database, file

Processing metric: postgresql_commits_total
Processing metric: rate(postgresql_commits_total[5m])
Processing metric: chaos_db_connection_pool_utilization_percent

┌─────────────────────────────────────────────────────────────────────────┐
│ Dynamic Steady-State Summary (30d)                                      │
├─────────────────────────────────────────────────────────────────────────┤
│ Metric                                    │ Mean    │ StdDev │ P95     │
├─────────────────────────────────────────────────────────────────────────┤
│ postgresql_commits_total                  │ 1250.5  │ 45.2   │ 1320.8  │
│ rate(postgresql_commits_total[5m])      │ 4.2     │ 0.8    │ 5.5     │
│ chaos_db_connection_pool_utilization_%   │ 65.3    │ 8.1    │ 78.5    │
└─────────────────────────────────────────────────────────────────────────┘

Dynamic steady-state calculation complete
================================================================================
```

---

## 🎯 Benefits

### For Experiment Authors

- ✅ **No Manual Baseline Configuration**: Baselines calculated automatically
- ✅ **Always Up-to-Date**: Uses recent historical data
- ✅ **Multi-Source Flexibility**: Combine data from multiple sources
- ✅ **Reduced Maintenance**: No need to update static baselines

### For Operations Teams

- ✅ **Adaptive Baselines**: Experiments adapt to system changes
- ✅ **Statistical Rigor**: Proper statistical analysis with percentiles
- ✅ **Visibility**: Clear console output shows calculated baselines
- ✅ **Production Ready**: Error handling, fallbacks, and logging

### For Platform Teams

- ✅ **Standardized Approach**: Consistent baseline calculation across experiments
- ✅ **Extensible**: Easy to add new data sources
- ✅ **Well-Tested**: Comprehensive test coverage (>95%)
- ✅ **Documented**: Complete usage guides and examples

---

## 🔧 Technical Details

### Architecture

```
Experiment JSON
    ↓
Dynamic Steady-State Control (before_experiment_start)
    ↓
DynamicMetricsFetcher (parallel fetch)
    ├─→ Grafana API
    ├─→ Prometheus API
    ├─→ PostgreSQL DB
    └─→ Local Files
    ↓
DynamicSteadyStateCalculator
    ├─→ Aggregate sources
    ├─→ Calculate statistics
    └─→ Generate hypothesis
    ↓
Update experiment["steady-state-hypothesis"]
    ↓
Experiment Execution (with dynamic baselines)
```

### Statistical Methods

- **Mean**: Arithmetic mean of all values
- **Standard Deviation**: Population standard deviation
- **Percentiles**: 50th (median), 95th, 99th, 99.9th percentiles
- **Bounds**: Mean ± (sigma × stddev) for warning/critical thresholds

### Performance

- **Parallel Fetching**: Uses `ThreadPoolExecutor` for concurrent data retrieval
- **Error Handling**: Graceful degradation if sources are unavailable
- **Caching**: Results stored in experiment context for reuse
- **Efficiency**: Only fetches metrics specified in configuration

---

## 📚 Documentation

- **[Usage Guide](docs_local/projects/chaostooling-generic/05-documentation-guides/DYNAMIC_STEADY_STATE_USAGE.md)** - Complete usage instructions
- **[Flowchart Diagram](docs_local/projects/chaostooling-generic/05-documentation-guides/DYNAMIC_STEADY_STATE_FLOWCHART.drawio)** - Visual flow diagram
- **[Example Experiment](chaostooling-experiments/postgres/example-dynamic-steady-state.json)** - Working example

---

## 🧪 Testing

- **Test Coverage**: >95% code coverage
- **Test Count**: 50+ unit and integration tests
- **Test Files**: 
  - `test_dynamic_steady_state.py` (comprehensive feature tests)
  - `test_dynamic_steady_state_control.py` (control integration tests)
- **Mock Support**: Comprehensive mocks for external services (Grafana, Prometheus, DB)
- **Test Quality**: All tests passing, edge cases covered

---

## 🔄 Migration Guide

### From Static Baselines

**Before** (Static):
```json
{
  "steady-state-hypothesis": {
    "probes": [
      {
        "name": "check-commits",
        "tolerance": [1000, 1500],
        "provider": {
          "type": "python",
          "module": "chaosdb.probes.postgres",
          "func": "check_commits"
        }
      }
    ]
  }
}
```

**After** (Dynamic):
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
  },
  "steady-state-hypothesis": {
    "title": "Will be dynamically generated"
  }
}
```

---

## 🐛 Known Limitations

- **Metric Discovery**: Currently extracts metrics from experiment configuration; future versions may support automatic discovery
- **Source Priority**: All sources are weighted equally; future versions may support source prioritization
- **Time Range**: Limited to Prometheus/Grafana retention periods
- **Rate Metrics**: Requires explicit `rate()` wrapper in metric names for counter metrics

---

## 🚀 Future Enhancements

- Automatic metric discovery from service graphs
- Source prioritization and weighting
- Machine learning-based anomaly detection
- Support for additional data sources (Datadog, New Relic, etc.)
- Baseline versioning and comparison

---

## 📦 Dependencies

- **Python 3.9+**
- **chaostoolkit**: Chaos Toolkit framework
- **requests**: HTTP client for API calls
- **psycopg2**: PostgreSQL database access (optional, for database source)

---

## 🙏 Acknowledgments

This feature was developed as part of the RealSteadyState release, following the 4-role quality framework (Architect, Coder, Tester, Reviewer) with comprehensive testing and documentation.

---

## 📝 Changelog

### v1.0.0 (DynamicSteadyState) - January 31, 2026

**Added**:
- Dynamic steady-state control with multi-source fetching
- Automatic baseline calculation and hypothesis generation
- Console output formatting
- Comprehensive test suite (>95% coverage)
- Complete documentation and examples

**Changed**:
- Experiments can now use dynamic baselines instead of static configuration
- Baseline calculation happens automatically before experiment execution

**Fixed**:
- N/A (initial release)

---

**For questions or support, see the [Usage Guide](docs_local/projects/chaostooling-generic/05-documentation-guides/DYNAMIC_STEADY_STATE_USAGE.md)**
