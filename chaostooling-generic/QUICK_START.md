# MCP Observability Server - Quick Start Guide

**5-minute setup to enable Claude + Grafana integration**

---

## Prerequisites

✅ Python 3.9+  
✅ Grafana stack running (Prometheus, Tempo, Loki)  
✅ 2+ weeks of historical data in Prometheus  

---

## Step 1: Install

```bash
cd /home/morgan/dev/src/chaostooling-oss/chaostooling-generic
pip install -e .
```

Verify:
```bash
chaos-observability --help
```

---

## Step 2: Configure Environment

```bash
export GRAFANA_URL="http://localhost:3000"
export GRAFANA_API_TOKEN="glc_YOUR_TOKEN"
export PROMETHEUS_URL="http://localhost:9090"
export TEMPO_URL="http://localhost:3100"
export LOKI_URL="http://localhost:3100"
```

**Get Grafana Token**: Administration → API Keys → Create API Key

---

## Step 3: Generate Baselines (Option A - One-time)

```bash
chaos-observability analyze --period-days 14
```

**Output**:
- `baseline_metrics.json` - Service latencies, throughput, errors
- `slo_targets.json` - SLO targets extracted from baselines
- `service_topology.json` - Service dependency graph
- `anomaly_thresholds.json` - Anomaly detection thresholds
- `analysis_report.json` - Human-readable findings

**Takes 2-5 minutes depending on data volume.**

---

## Step 4: Start MCP Server (Option B - For AI Integration)

```bash
chaos-observability mcp-server
```

This starts the Model Context Protocol server for any MCP-compatible AI agent integration. Supported agents include Claude, GPT, and other MCP-supporting AI platforms. They can now:
- Query metrics: "What's the error rate for payment-service?"
- View topology: "Which services are single points of failure?"
- Get traces: "Show me slow traces for order-service"
- Analyze logs: "Are there error patterns in the last 24h?"

---

## Step 5: Test Connectivity

```bash
# Verify Prometheus
curl http://localhost:9090/api/v1/query?query=up

# Verify Tempo
curl http://localhost:3100/ready

# Verify Grafana API
curl -H "Authorization: Bearer $GRAFANA_API_TOKEN" \
  http://localhost:3000/api/datasources
```

---

## Step 6: Connect Your AI Agent

Once MCP server is running, configure your AI agent to connect to it via stdio. For example:

**Claude (via Claude.dev or Claude API)**:
```json
{
  "type": "stdio",
  "command": "chaos-observability",
  "args": ["mcp-server"]
}
```

**Other MCP-compatible agents**: Refer to your agent's documentation for MCP integration setup.

---

## Example: AI Agent Integration

Once MCP server is running, you can ask your AI agent:

```
Q: "What's the steady state for our system?"
Claude uses MCP to:
- Query baseline_metrics.json
- Return: "Order service: 45ms P99, <0.2% error rate, 500 RPS"

Q: "Which services would impact the whole system if they fail?"
Claude uses MCP to:
- Query service_topology.json
- Return: "Payment service and order DB are SPOFs"

Q: "Generate a chaos test hypothesis for us"
Claude uses MCP to:
- Read service_topology.json
- Apply failure patterns
- Suggest: "Test payment service failure - would cascade to 3 downstream services"
```

---

## Command Reference

### Full Analysis with Custom Options

```bash
chaos-observability analyze \
  --prometheus-url http://localhost:9090 \
  --tempo-url http://localhost:3100 \
  --loki-url http://localhost:3100 \
  --period-days 14 \
  --output-dir ./my-analysis
```

### Quick Baseline (Metrics Only)

```bash
chaos-observability baseline \
  --prometheus-url http://localhost:9090 \
  --period-days 7
```

### MCP Server with Custom Port

```bash
chaos-observability mcp-server \
  --port 8000
```

---

## Troubleshooting

| Issue | Solution |
|-------|----------|
| "Connection refused" | Check Prometheus/Tempo/Loki are running: `docker ps` |
| "No data in analysis" | Verify metrics exist: `curl http://localhost:9090/api/v1/targets` |
| "Invalid API token" | Generate new Grafana token (Admin → API Keys) |
| "PromQL errors" | Check metric names in your Prometheus |

---

## Next: Use Baselines in Chaos Experiments

Once you have baselines, you can:

1. **Generate Hypotheses** - Claude reads topology, suggests failure scenarios
2. **Execute Experiments** - Platform runs chaos injection
3. **Verify Results** - Compare experiment metrics to baselines
4. **Generate Evidence** - For DORA/compliance audits

---

## File Locations

| File | Purpose |
|------|---------|
| `chaosgeneric/mcp_observability_server.py` | MCP server (8 tools) |
| `chaosgeneric/steady_state_analyzer.py` | Baseline analysis engine |
| `chaosgeneric/cli.py` | CLI commands |
| `MCP_OBSERVABILITY_SERVER.md` | Full documentation |
| `QUICK_START.md` | This file |

---

## Key Metrics Captured

- **Latency**: P50, P95, P99 per service
- **Throughput**: Requests/second per service
- **Error Rates**: % of requests that error
- **Resource Usage**: CPU, Memory per pod/container
- **Dependencies**: Service call graph
- **Traces**: Sample traces for each service

---

**Questions?** Check [MCP_OBSERVABILITY_SERVER.md](MCP_OBSERVABILITY_SERVER.md) for detailed documentation.
