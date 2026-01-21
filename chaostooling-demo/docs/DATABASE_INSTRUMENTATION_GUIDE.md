# Database & Messaging System Instrumentation Guide

## Overview

This guide explains how to make databases and messaging systems emit OpenTelemetry traces so they appear as proper nodes in Tempo service graphs.

## Why Databases Don't Emit Traces by Default

Databases (PostgreSQL, MySQL, Redis, etc.) and messaging systems (Kafka, RabbitMQ, etc.) are **not instrumented with OpenTelemetry** out of the box. They:
- Don't export OTLP traces
- Don't have built-in OpenTelemetry SDKs
- Can't create server-side spans

This is why they don't appear in service graphs even when client applications correctly set `peer.service` attributes.

## Solutions (Ranked by Effort)

### Option 1: Use Sidecar Exporters (Recommended) ⭐

Deploy OpenTelemetry collectors as sidecars that generate synthetic server spans based on database/messaging system metrics.

#### For PostgreSQL

**Method A: OpenTelemetry Collector with PostgreSQL Receiver**

```yaml
# otel-collector-postgres-sidecar.yaml
receivers:
  postgresql:
    endpoint: postgres-primary-site-a:5432
    username: ${POSTGRES_USER}
    password: ${POSTGRES_PASSWORD}
    databases:
      - testdb
    collection_interval: 10s

processors:
  # Create synthetic server spans from metrics
  spanmetrics:
    metrics_exporter: prometheus
    dimensions:
      - name: db.system
        default: postgresql
      - name: db.name
      - name: peer.service
        default: postgres-primary-site-a

  resource:
    attributes:
      - key: service.name
        value: postgres-primary-site-a
        action: upsert
      - key: db.system
        value: postgresql
        action: upsert

exporters:
  otlp:
    endpoint: otel-collector:4317
  prometheus:
    endpoint: "0.0.0.0:8889"

service:
  pipelines:
    metrics:
      receivers: [postgresql]
      processors: [resource, spanmetrics]
      exporters: [prometheus, otlp]
```

**Docker Compose Addition**:
```yaml
  postgres-otel-sidecar:
    image: otel/opentelemetry-collector-contrib:latest
    command: ["--config=/etc/otel-collector-config.yaml"]
    volumes:
      - ./otel-collectors/postgres-sidecar.yaml:/etc/otel-collector-config.yaml:ro
    environment:
      - POSTGRES_USER=postgres
      - POSTGRES_PASSWORD=postgres
    networks:
      - chaos-network
    depends_on:
      - postgres-primary-site-a
      - otel-collector
```

**Method B: pg_stat_statements + Span Generator**

Create a custom span generator that reads `pg_stat_statements`:

```python
# postgres_span_generator.py
import psycopg2
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
import time

# Initialize OpenTelemetry
provider = TracerProvider()
processor = BatchSpanProcessor(OTLPSpanExporter(endpoint="otel-collector:4317", insecure=True))
provider.add_span_processor(processor)
trace.set_tracer_provider(provider)

tracer = trace.get_tracer("postgres-server", "1.0.0")

def generate_server_spans():
    """Read pg_stat_statements and generate synthetic server spans."""
    conn = psycopg2.connect(
        host="postgres-primary-site-a",
        port=5432,
        database="testdb",
        user="postgres",
        password="postgres"
    )
    cursor = conn.cursor()

    # Enable pg_stat_statements
    cursor.execute("CREATE EXTENSION IF NOT EXISTS pg_stat_statements;")

    while True:
        # Read recent queries
        cursor.execute("""
            SELECT
                queryid,
                query,
                calls,
                total_exec_time,
                mean_exec_time
            FROM pg_stat_statements
            WHERE calls > 0
            ORDER BY last_exec_time DESC
            LIMIT 100
        """)

        for row in cursor.fetchall():
            queryid, query, calls, total_time, mean_time = row

            # Create synthetic server span
            with tracer.start_as_current_span(
                f"postgres.query.{queryid}",
                kind=trace.SpanKind.SERVER
            ) as span:
                span.set_attribute("service.name", "postgres-primary-site-a")
                span.set_attribute("db.system", "postgresql")
                span.set_attribute("db.statement", query[:200])
                span.set_attribute("db.operation", "query")
                span.set_attribute("span.kind", "server")

        time.sleep(10)  # Poll every 10 seconds

if __name__ == "__main__":
    generate_server_spans()
```

**Docker Service**:
```yaml
  postgres-span-generator:
    build: ./span-generators/postgres
    environment:
      - OTEL_EXPORTER_OTLP_ENDPOINT=http://otel-collector:4317
      - POSTGRES_HOST=postgres-primary-site-a
      - POSTGRES_PASSWORD=postgres
    depends_on:
      - postgres-primary-site-a
```

#### For MySQL

```yaml
# otel-collector-mysql-sidecar.yaml
receivers:
  mysql:
    endpoint: mysql:3306
    username: ${MYSQL_USER}
    password: ${MYSQL_PASSWORD}
    collection_interval: 10s

processors:
  resource:
    attributes:
      - key: service.name
        value: mysql
        action: upsert
      - key: db.system
        value: mysql
        action: upsert

exporters:
  otlp:
    endpoint: otel-collector:4317

service:
  pipelines:
    metrics:
      receivers: [mysql]
      processors: [resource]
      exporters: [otlp]
```

#### For Redis

```yaml
# otel-collector-redis-sidecar.yaml
receivers:
  redis:
    endpoint: redis:6379
    collection_interval: 10s

processors:
  resource:
    attributes:
      - key: service.name
        value: redis
        action: upsert
      - key: db.system
        value: redis
        action: upsert

exporters:
  otlp:
    endpoint: otel-collector:4317

service:
  pipelines:
    metrics:
      receivers: [redis]
      processors: [resource]
      exporters: [otlp]
```

#### For Kafka

```yaml
# otel-collector-kafka-sidecar.yaml
receivers:
  kafkametrics:
    brokers: kafka:9092
    protocol_version: 2.0.0
    collection_interval: 10s

processors:
  resource:
    attributes:
      - key: service.name
        value: kafka
        action: upsert
      - key: messaging.system
        value: kafka
        action: upsert

exporters:
  otlp:
    endpoint: otel-collector:4317

service:
  pipelines:
    metrics:
      receivers: [kafkametrics]
      processors: [resource]
      exporters: [otlp]
```

#### For RabbitMQ

```yaml
# otel-collector-rabbitmq-sidecar.yaml
receivers:
  rabbitmq:
    endpoint: http://rabbitmq:15672
    username: ${RABBITMQ_USER}
    password: ${RABBITMQ_PASSWORD}
    collection_interval: 10s

processors:
  resource:
    attributes:
      - key: service.name
        value: rabbitmq
        action: upsert
      - key: messaging.system
        value: rabbitmq
        action: upsert

exporters:
  otlp:
    endpoint: otel-collector:4317

service:
  pipelines:
    metrics:
      receivers: [rabbitmq]
      processors: [resource]
      exporters: [otlp]
```

### Option 2: Database Plugins/Extensions

Some databases support OpenTelemetry extensions:

#### PostgreSQL with pg_tracing (Experimental)

```sql
-- Install pg_tracing extension
CREATE EXTENSION pg_tracing;

-- Configure tracing
ALTER SYSTEM SET pg_tracing.enabled = on;
ALTER SYSTEM SET pg_tracing.sample_rate = 0.1;
SELECT pg_reload_conf();
```

Note: This is experimental and may not be production-ready.

#### Redis with OpenTelemetry Module

```bash
# Load OpenTelemetry module (requires custom Redis build)
redis-server --loadmodule /path/to/redis-otel.so \
  --otel-endpoint http://otel-collector:4317 \
  --otel-service-name redis
```

### Option 3: Proxy-Based Instrumentation

Deploy instrumented proxies that sit between applications and databases:

#### SQL Proxy with OpenTelemetry

```python
# sql_proxy.py - Instrumented SQL proxy
from opentelemetry import trace
from opentelemetry.instrumentation.psycopg2 import Psycopg2Instrumentor
import socket

# Instrument psycopg2
Psycopg2Instrumentor().instrument()

# Create proxy server that forwards SQL traffic
# while generating server-side spans
```

This approach requires custom development and adds latency.

### Option 4: eBPF-Based Instrumentation (Advanced)

Use eBPF to capture database protocol traffic and generate spans:

```yaml
# Using Beyla or similar eBPF-based auto-instrumentation
services:
  beyla-postgres:
    image: grafana/beyla:latest
    privileged: true
    environment:
      - BEYLA_SERVICE_NAME=postgres-primary-site-a
      - BEYLA_OPEN_PORT=5432
      - BEYLA_OTEL_EXPORTER_ENDPOINT=http://otel-collector:4317
    volumes:
      - /sys/kernel/debug:/sys/kernel/debug:ro
```

## Recommended Implementation Plan

### Phase 1: Quick Win (1-2 hours)

Deploy OpenTelemetry Collector sidecars for key services:

1. **PostgreSQL Primary**: Add postgres-otel-sidecar
2. **Redis**: Add redis-otel-sidecar
3. **Kafka**: Add kafka-otel-sidecar

```yaml
# Add to docker-compose.yml
  postgres-otel-sidecar:
    image: otel/opentelemetry-collector-contrib:latest
    command: ["--config=/etc/otel-collector-config.yaml"]
    volumes:
      - ./otel-collectors/postgres-sidecar.yaml:/etc/otel-collector-config.yaml:ro
    environment:
      - POSTGRES_USER=postgres
      - POSTGRES_PASSWORD=postgres
    networks:
      - chaos-network

  redis-otel-sidecar:
    image: otel/opentelemetry-collector-contrib:latest
    command: ["--config=/etc/otel-collector-config.yaml"]
    volumes:
      - ./otel-collectors/redis-sidecar.yaml:/etc/otel-collector-config.yaml:ro
    networks:
      - chaos-network

  kafka-otel-sidecar:
    image: otel/opentelemetry-collector-contrib:latest
    command: ["--config=/etc/otel-collector-config.yaml"]
    volumes:
      - ./otel-collectors/kafka-sidecar.yaml:/etc/otel-collector-config.yaml:ro
    networks:
      - chaos-network
```

### Phase 2: Span Generation (1-2 days)

Create synthetic server span generators:

1. Read database metrics (pg_stat_statements, Redis INFO, etc.)
2. Generate server-side spans matching client spans
3. Correlate via trace context propagation

### Phase 3: Full Instrumentation (1-2 weeks)

- Deploy eBPF-based instrumentation
- Implement trace context propagation in protocols
- Add custom plugins/extensions where available

## Testing & Validation

After deploying sidecars:

```bash
# 1. Verify sidecar is running
docker logs postgres-otel-sidecar

# 2. Check metrics are being collected
curl http://localhost:8889/metrics | grep postgres

# 3. Check service graph now includes databases
curl -s 'http://localhost:9090/api/v1/query?query=traces_service_graph_request_total' | \
  jq -r '.data.result[].metric.server' | grep postgres

# 4. Verify in Grafana service graph
open http://localhost:3000/d/extensive-postgres
```

## Troubleshooting

### Sidecar not collecting metrics

```bash
# Check sidecar logs
docker logs postgres-otel-sidecar --tail 50

# Verify database is accessible
docker exec postgres-otel-sidecar ping postgres-primary-site-a

# Test database connection
docker exec postgres-otel-sidecar curl postgres-primary-site-a:5432
```

### Spans not correlating

Ensure trace context propagation:
- Client sets trace ID in span
- Sidecar reads trace ID from metrics/logs
- Sidecar creates server span with same trace ID

### Performance Impact

Monitor overhead:
- Sidecar CPU/memory usage
- Database query latency increase
- Network traffic overhead

## Production Considerations

1. **Resource Allocation**: Sidecars need CPU/memory
2. **High Cardinality**: Limit span dimensions to avoid metric explosion
3. **Sampling**: Use sampling for high-traffic databases
4. **Security**: Secure credentials for database access
5. **Monitoring**: Monitor sidecar health

## Summary

| Method | Effort | Accuracy | Performance Impact |
|--------|--------|----------|-------------------|
| OTEL Collector Sidecar | Low | Medium | Low |
| pg_stat_statements Generator | Medium | High | Low |
| Database Extensions | High | High | Medium |
| Proxy-Based | High | High | High |
| eBPF | Very High | Very High | Very Low |

**Recommendation**: Start with OTEL Collector sidecars (Option 1A). They're easy to deploy, have minimal performance impact, and provide adequate visibility for service graphs.
