# Observability Queries

This document lists useful `curl` commands for querying the observability stack (Prometheus, Loki, Tempo) in the `chaostooling-demo` environment.

## Loki (Logs)

Loki is used for storing and querying logs from containers and experiment execution.

### List all available labels

```bash
curl -s http://localhost:3100/loki/api/v1/labels | jq .
```

*Explanation: Returns a list of all indexed labels in Loki (e.g., `service_name`, `container_name`).*

### List values for a specific label (service_name)

```bash
curl -s http://localhost:3100/loki/api/v1/label/service_name/values | jq .
```

*Explanation: Shows all unique service names currently sending logs to Loki.*

### Query logs for the chaos runner

```bash
curl -s -G "http://localhost:3100/loki/api/v1/query_range" \
  --data-urlencode 'query={service_name="chaostoolkit-demo"}' \
  --data-urlencode 'limit=50' | jq .
```

*Explanation: Retrieves the last 50 log lines for the `chaostoolkit-demo` service, which includes both container stdout and scraped experiment logs.*

---

## Prometheus (Metrics)

Prometheus stores time-series metrics from the OTel Collector and various exporters.

### List all metric names

```bash
curl -s http://localhost:9090/api/v1/label/__name__/values | jq .
```

*Explanation: Returns a list of all metric names currently available in Prometheus.*

### Query a specific experiment metric

```bash
curl -s "http://localhost:9090/api/v1/query?query=chaos_chaos_experiment_risk_level_ratio" | jq .
```

*Explanation: Returns the current value of the `chaos_chaos_experiment_risk_level_ratio` metric.*

---

## Tempo (Traces)

Tempo stores distributed traces exported via OTLP.

### Search for traces by service name

```bash
curl -s "http://localhost:3200/api/search?tags=service.name=chaostoolkit-demo" | jq .
```

*Explanation: Searches for recent traces associated with the `chaostoolkit-demo` service.*

### Get a specific trace by ID

```bash
curl -s "http://localhost:3200/api/traces/<trace_id>" | jq .
```

*Explanation: Retrieves the full trace data for a given Trace ID.*
