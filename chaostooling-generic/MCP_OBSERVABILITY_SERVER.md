# Observability MCP Server - Grafana Stack Integration

**Module**: `chaostooling-generic`  
**Status**: Ready for implementation  
**Purpose**: Enable any MCP-compatible AI agent to analyze observability data and drive steady state definition

---

## Overview

The Observability MCP (Model Context Protocol) Server bridges any MCP-compatible AI agent and your Grafana observability stack (Tempo, Prometheus, Loki). This enables:

1. **Steady State Definition (Step 1)** - Automatically analyze 2-4 weeks of metrics to establish baselines
2. **Interactive Analysis** - Claude asks questions about services, dependencies, and behavior patterns
3. **Hypothesis Generation (Step 2)** - AI identifies failure scenarios based on topology and history
4. **Evidence Collection** - Automatically gather traces, metrics, and logs for experiment validation

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│ AI Agent (Claude, GPT, or any MCP-compatible model)         │
└─────────────────────────────────────────────────────────────┘
                          ↓ (stdio)
┌─────────────────────────────────────────────────────────────┐
│ MCP Observability Server (chaosgeneric)                     │
│ ├─ query_prometheus()      (metrics)                        │
│ ├─ query_tempo()           (traces)                         │
│ ├─ query_loki()            (logs)                           │
│ ├─ get_dashboard()         (dashboards)                     │
│ └─ list_datasources()      (available data sources)        │
└─────────────────────────────────────────────────────────────┘
                          ↓ (HTTP)
┌──────────────┬──────────────┬──────────────┬──────────────┐
│ Prometheus   │ Tempo        │ Loki         │ Grafana      │
│ (metrics)    │ (traces)     │ (logs)       │ (dashboards) │
└──────────────┴──────────────┴──────────────┴──────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│ Your Observability Data (2+ weeks historical)              │
└─────────────────────────────────────────────────────────────┘
```

---

## Installation

### 1. Install Package

```bash
cd /home/morgan/dev/src/chaostooling-oss/chaostooling-generic
pip install -e ".[dev]"
```

### 2. Set Environment Variables

```bash
export GRAFANA_URL="http://localhost:3000"
export GRAFANA_API_TOKEN="YOUR_GRAFANA_API_TOKEN"
export PROMETHEUS_URL="http://localhost:9090"
export TEMPO_URL="http://localhost:3100"
export LOKI_URL="http://localhost:3100"
```

### 3. Verify Connectivity

```bash
# Test Prometheus
curl http://localhost:9090/api/v1/targets

# Test Tempo
curl http://localhost:3100/api/traces/

# Test Loki
curl http://localhost:3100/loki/api/v1/labels

# Test Grafana
curl -H "Authorization: Bearer $GRAFANA_API_TOKEN" \
  http://localhost:3000/api/datasources
```

---

## Usage

### Option A: CLI - Analyze and Generate Baselines

```bash
# Run full steady state analysis
chaos-observability analyze \
  --prometheus-url http://localhost:9090 \
  --tempo-url http://localhost:3100 \
  --loki-url http://localhost:3100 \
  --period-days 14 \
  --output-dir ./chaos-analysis

# Output files:
# ./chaos-analysis/baseline_metrics.json     (per-service metrics stats)
# ./chaos-analysis/slo_targets.json          (SLO definitions)
# ./chaos-analysis/service_topology.json     (dependencies, SPOFs)
# ./chaos-analysis/anomaly_thresholds.json   (anomaly detection thresholds)
# ./chaos-analysis/analysis_report.json      (human-readable report)
```

### Option B: Start MCP Server (for AI Integration)

```bash
# Start MCP server (listens on stdin/stdout for any MCP-compatible AI)
chaos-observability mcp-server \
  --prometheus-url http://localhost:9090 \
  --tempo-url http://localhost:3100 \
  --loki-url http://localhost:3100 \
  --grafana-url http://localhost:3000 \
  --grafana-token $GRAFANA_API_TOKEN
```

### Option C: Programmatic Usage

```python
from chaosgeneric.steady_state_analyzer import create_steady_state_analyzer
from chaosgeneric.mcp_observability_server import ObservabilityClient

# Analyze baselines
analyzer = create_steady_state_analyzer(
    prometheus_url="http://localhost:9090",
    tempo_url="http://localhost:3100",
    loki_url="http://localhost:3100",
    analysis_period_days=14
)

results = analyzer.analyze()
print(results['baseline_metrics'])
print(results['slo_targets'])
print(results['service_topology'])

# Or query directly
client = ObservabilityClient()
metrics = client.query_prometheus('rate(http_requests_total[5m])')
traces = client.query_tempo(service_name='order-service')
logs = client.query_loki('{service="payment-service"}')
```

---

## MCP Server Tools (for Claude)

### 1. query_prometheus(query, time_range)

Query Prometheus metrics using PromQL.

**Parameters**:
- `query` (required): PromQL query (e.g., `rate(http_requests_total[5m])`)
- `time_range` (optional): Time range (e.g., `1h`, `24h`, `7d`). Default: `1h`

**Example AI Agent Request**:
```
"What is the error rate for payment-service over the last 24 hours?"
→ Tool: query_prometheus
→ Query: rate(http_requests_errors_total{service="payment-service"}[5m])
→ time_range: 24h
```

**Output**:
```json
{
  "status": "success",
  "data": {
    "resultType": "matrix",
    "result": [
      {
        "metric": {"service": "payment-service"},
        "values": [
          [1705095600, "0.002"],
          [1705095660, "0.0021"],
          ...
        ]
      }
    ]
  }
}
```

### 2. query_instant_prometheus(query)

Get current metric value (instant query).

**Example**:
```
"What is the current latency p99 for order-service?"
→ Tool: query_instant_prometheus
→ Query: histogram_quantile(0.99, http_request_duration_seconds{service="order-service"})
```

### 3. query_tempo(service_name, min_duration, time_range)

Query distributed traces.

**Parameters**:
- `service_name` (optional): Filter by service (e.g., `payment-service`)
- `min_duration` (optional): Min span duration (e.g., `100ms`, `1s`)
- `time_range` (optional): Time range. Default: `1h`

**Example**:
```
"Show me slow traces for payment-service (>500ms) from the last hour"
→ Tool: query_tempo
→ service_name: payment-service
→ min_duration: 500ms
→ time_range: 1h
```

### 4. get_trace_detail(trace_id)

Get full trace details for a specific trace ID.

### 5. query_loki(query, time_range)

Query logs using LogQL.

**Example**:
```
"What errors occurred in order-service in the last 6 hours?"
→ Tool: query_loki
→ Query: {service="order-service"} | json | level="ERROR"
→ time_range: 6h
```

### 6. get_datasources()

List all available Grafana datasources.

### 7. list_dashboards()

List all Grafana dashboards.

### 8. get_dashboard(dashboard_id)

Get dashboard definition by UID.

---

## Steady State Analysis Workflow

The `SteadyStateAnalyzer` executes the following steps:

### Phase 1: Data Collection
```
├─ Collect metrics from Prometheus (14 days of data)
│  └─ http_request_duration_seconds
│  └─ http_requests_total
│  └─ http_request_errors_total
│  └─ process_resident_memory_bytes
│  └─ (+ custom metrics from your services)
│
├─ Collect traces from Tempo
│  └─ Service call graphs
│  └─ Latencies per service pair
│
└─ Collect logs from Loki
   └─ Error/warning logs
```

### Phase 2: Baseline Calculation

For each metric and service, calculate:
- **Mean (μ)** - Average value
- **Standard Deviation (σ)** - Variability
- **Percentiles** - P50, P95, P99
- **Min/Max** - Range of values

**Example Output**:
```json
{
  "http_request_duration_seconds": {
    "order-service": {
      "mean": 45.2,
      "median": 42.1,
      "stdev": 12.5,
      "p50": 42,
      "p95": 68,
      "p99": 89,
      "min": 5,
      "max": 250
    },
    "payment-service": {
      "mean": 102.3,
      "median": 95.2,
      "stdev": 28.1,
      "p50": 95,
      "p95": 145,
      "p99": 189,
      "min": 10,
      "max": 500
    }
  }
}
```

### Phase 3: SLO Generation

Generate SLO targets based on baselines:

```json
{
  "latency": {
    "order-service": {
      "p99_ms": 89,
      "slo_target_ms": 98,  // p99 + 10% margin
      "unit": "milliseconds"
    }
  },
  "throughput": {
    "order-service": {
      "baseline_rps": 500,
      "slo_target_rps": 450,  // baseline - 10%
      "unit": "requests_per_second"
    }
  },
  "error_rate": {
    "order-service": {
      "baseline_errors": 0.2,
      "slo_max_percent": 0.5,
      "unit": "percent"
    }
  }
}
```

### Phase 4: Service Topology

Identify:
- Service call graph (who calls whom)
- Critical paths (paths to end-user)
- Single points of failure (services with no redundancy)

```json
{
  "nodes": ["api-gateway", "order-service", "payment-service", "order-db"],
  "edges": [
    {"from": "api-gateway", "to": "order-service", "avg_latency_ms": 15},
    {"from": "order-service", "to": "payment-service", "avg_latency_ms": 120},
    {"from": "order-service", "to": "order-db", "avg_latency_ms": 8}
  ],
  "critical_paths": [
    ["api-gateway", "order-service", "payment-service"]
  ],
  "single_points_of_failure": ["payment-service", "order-db"]
}
```

### Phase 5: Anomaly Thresholds

Dynamic thresholds for anomaly detection:

```json
{
  "http_request_duration_seconds": {
    "order-service": {
      "mean": 45.2,
      "stdev": 12.5,
      "lower_bound": 20.2,           // mean - 2*stdev
      "upper_bound": 70.2,           // mean + 2*stdev
      "critical_upper": 82.7         // mean + 3*stdev
    }
  }
}
```

During chaos experiments, if metrics exceed `upper_bound`, it's worth investigating. If they exceed `critical_upper`, it's a critical issue.

---

## Output Files

### baseline_metrics.json
Per-service metric statistics (mean, stddev, percentiles)

### slo_targets.json
SLO definitions for latency, throughput, error rates

### service_topology.json
Service dependency graph, critical paths, SPOFs

### anomaly_thresholds.json
Dynamic anomaly detection thresholds per metric

### analysis_report.json
Human-readable findings and recommendations:
```json
{
  "summary": {
    "analysis_period_days": 14,
    "services_analyzed": 15,
    "critical_paths": 3,
    "spofs": 4
  },
  "key_findings": [
    "Slowest service: payment-service (P99: 189ms)",
    "Highest error rate: notification-service (0.8%)",
    "Identified 4 single points of failure"
  ],
  "recommendations": [
    "Run chaos tests for identified SPOFs",
    "Service order-service has high latency variance. Consider investigating"
  ],
  "data_completeness": {
    "total_metric_series": 120,
    "estimated_completeness_percent": 87.5
  }
}
```

---

## Example: Complete Workflow

```bash
# 1. Collect 2 weeks of data and analyze
chaos-observability analyze \
  --period-days 14 \
  --output-dir ./baseline-analysis

# 2. Review generated files
cat ./baseline-analysis/analysis_report.json

# 3. Use baselines in chaos experiments
# (Platform will automatically compare experiment results to baselines)

# 4. Later: Start MCP server for Claude integration
chaos-observability mcp-server
# Claude can now ask: "What services are SPOFs?" 
# MCP returns service_topology.json data
```

---

## Integration with Chaos Platform

The steady state baselines feed into the chaos experiment workflow, which can be driven by any MCP-compatible AI agent:

```
Baseline Analysis (This Module)
    ↓
  baseline_metrics.json
  slo_targets.json
  service_topology.json
    ↓
Hypothesis Generation (Step 2)
    ├─ AI Agent (via MCP) reads topology
    ├─ Identifies failure scenarios
    └─ Creates experiment plans
    ↓
Experiment Execution (Step 3)
    ├─ Run chaos scenario
    ├─ Collect metrics/traces/logs
    └─ Compare to baseline
    ↓
Result Verification (Step 4)
    ├─ Metrics outside baseline thresholds?
    ├─ RCA analysis
    └─ Classification (expected/unexpected)
```

---

## Configuration

### Environment Variables

```bash
# Observability stack endpoints
GRAFANA_URL=http://localhost:3000
GRAFANA_API_TOKEN=your-token-here
PROMETHEUS_URL=http://localhost:9090
TEMPO_URL=http://localhost:3100
LOKI_URL=http://localhost:3100

# Analysis settings
ANALYSIS_PERIOD_DAYS=14
OUTPUT_DIRECTORY=./chaos-analysis
```

### Custom Metrics

To include custom metrics in baseline analysis, modify `SteadyStateAnalyzer._collect_metrics()`:

```python
metrics_to_collect = [
    'http_request_duration_seconds_bucket{le="+Inf"}',
    'custom_business_metric_total',  # Your custom metric
    'custom_processing_duration_ms',
    # ... add more
]
```

---

## Testing

```bash
# Test MCP server connectivity
python -c "
from chaosgeneric.mcp_observability_server import ObservabilityClient
client = ObservabilityClient()
result = client.query_instant_prometheus('up')
print(result)
"

# Test steady state analyzer
python -c "
from chaosgeneric.steady_state_analyzer import create_steady_state_analyzer
analyzer = create_steady_state_analyzer()
results = analyzer.analyze()
print(f'Analyzed {len(results[\"baseline_metrics\"])} metrics')
"
```

---

## Troubleshooting

### "Connection refused" error
Verify observability stack is running:
```bash
curl http://localhost:3100/ready  # Tempo
curl http://localhost:9090/api/v1/targets  # Prometheus
curl http://localhost:3100/loki/api/v1/labels  # Loki
```

### "No data" in analysis results
1. Verify metric data exists: `curl http://localhost:9090/api/v1/query?query=up`
2. Increase `analysis_period_days` (may need 7+ days of data)
3. Check metric names match your actual metrics

### Prometheus query errors
Verify PromQL syntax:
```bash
# Test query
curl "http://localhost:9090/api/v1/query?query=rate(http_requests_total%5B5m%5D)"
```

---

## Next Steps

1. **Deploy observability stack** - Docker Compose stack in `chaostooling-demo/`
2. **Collect baseline data** - Run 2 weeks of normal production traffic
3. **Generate baselines** - Run `chaos-observability analyze`
4. **Enable MCP server** - `chaos-observability mcp-server` for Claude
5. **Define hypotheses** - Claude uses topology to generate failure scenarios
6. **Execute experiments** - Run chaos tests with automatic baseline comparison

---

**Document Version**: 1.0  
**Created**: Jan 28, 2026  
**Status**: Ready for deployment
