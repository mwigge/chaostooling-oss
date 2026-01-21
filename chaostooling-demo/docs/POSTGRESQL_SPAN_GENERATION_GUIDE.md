# PostgreSQL Span Generation Guide

## Overview

This guide explains how to generate OpenTelemetry spans for PostgreSQL queries to enable:
1. **Service graph visibility** - PostgreSQL appearing as a node in Tempo service graphs
2. **Query-level traces** - Individual database queries as spans with timing and metadata
3. **Distributed tracing** - End-to-end trace correlation from application through database

## Current State vs. Desired State

### What We Have Now ✅
- **Client-side spans**: Chaos Toolkit extensions emit spans when calling PostgreSQL
- **Span attributes**: `peer.service`, `network.peer.address`, `db.system` set correctly
- **PostgreSQL metrics**: OTEL Collector collects operational metrics via `postgresqlreceiver`

### What We Want 🎯
- **Server-side spans**: PostgreSQL emitting spans for each query it executes
- **Query details**: SQL text, execution time, rows affected, plan time
- **Trace context**: Correlation between client spans and server spans

### The Gap
PostgreSQL doesn't natively support OpenTelemetry. We need to build a bridge.

---

## Approach 1: Span Generator from pg_stat_statements (Recommended)

### Complexity: Medium (2-3 days)
### Cost: Low (no infrastructure changes)

This approach monitors PostgreSQL's `pg_stat_statements` extension and generates synthetic server-side spans based on query activity.

### Architecture

```
┌─────────────────┐         ┌──────────────────┐         ┌──────────────┐
│  Chaos Toolkit  │────────▶│    PostgreSQL    │         │     Tempo    │
│   (Client)      │  Query  │                  │         │              │
└────────┬────────┘         └──────────────────┘         └──────────────┘
         │                            │                          ▲
         │ Client Span                │ Query Stats              │
         │ (trace_id, span_id)        │ (pg_stat_statements)     │
         │                            │                          │
         ▼                            ▼                          │
    ┌────────────────────────────────────────────┐              │
    │     Span Generator Service                  │              │
    │  - Polls pg_stat_statements every 5s        │              │
    │  - Matches queries to trace context         │              │
    │  - Generates server-side spans              │──────────────┘
    │  - Exports to OTEL Collector                │   Server Span
    └────────────────────────────────────────────┘
```

### Step 1: Enable pg_stat_statements in PostgreSQL

**Update docker-compose.yml**:

```yaml
postgres-primary-site-a:
  image: postgres:15
  environment:
    POSTGRES_USER: ${POSTGRES_USER:-postgres}
    POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:-postgres}
    POSTGRES_DB: ${POSTGRES_DB:-testdb}
  command:
    - "postgres"
    - "-c"
    - "shared_preload_libraries=pg_stat_statements"
    - "-c"
    - "pg_stat_statements.track=all"
    - "-c"
    - "pg_stat_statements.max=10000"
    - "-c"
    - "track_activity_query_size=2048"
    # ... existing wal_level, max_wal_senders, etc.
```

**Create initialization script** `chaostooling-demo/scripts/enable-pg-stat-statements.sql`:

```sql
-- Enable pg_stat_statements extension
CREATE EXTENSION IF NOT EXISTS pg_stat_statements;

-- Grant access to monitoring role
GRANT pg_monitor TO postgres;

-- Verify it's working
SELECT * FROM pg_stat_statements LIMIT 1;
```

**Add to postgres initialization**:

```yaml
postgres-primary-site-a:
  volumes:
    - ./scripts/enable-pg-stat-statements.sql:/docker-entrypoint-initdb.d/10-pg-stat-statements.sql:ro
```

### Step 2: Create Span Generator Service

**File**: `chaostooling-demo/postgres-span-generator/span_generator.py`

```python
#!/usr/bin/env python3
"""
PostgreSQL Span Generator

Monitors pg_stat_statements and generates OpenTelemetry server-side spans
for PostgreSQL queries.
"""
import os
import time
import psycopg2
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.trace import SpanKind
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class PostgresSpanGenerator:
    def __init__(self):
        # Initialize OTEL tracer
        resource = Resource.create({
            "service.name": "postgres-primary-site-a",
            "service.namespace": "database",
            "db.system": "postgresql",
        })

        provider = TracerProvider(resource=resource)
        processor = BatchSpanProcessor(
            OTLPSpanExporter(
                endpoint=os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://otel-collector:4317"),
                insecure=True
            )
        )
        provider.add_span_processor(processor)
        trace.set_tracer_provider(provider)

        self.tracer = trace.get_tracer(__name__)

        # Database connection
        self.conn = psycopg2.connect(
            host=os.getenv("POSTGRES_HOST", "postgres-primary-site-a"),
            port=os.getenv("POSTGRES_PORT", "5432"),
            database=os.getenv("POSTGRES_DB", "testdb"),
            user=os.getenv("POSTGRES_USER", "postgres"),
            password=os.getenv("POSTGRES_PASSWORD", "postgres"),
        )

        # Track last seen query stats
        self.last_stats = {}

    def fetch_query_stats(self):
        """Fetch current query statistics from pg_stat_statements."""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT
                queryid,
                query,
                calls,
                total_exec_time,
                mean_exec_time,
                rows,
                shared_blks_hit,
                shared_blks_read
            FROM pg_stat_statements
            WHERE calls > 0
            ORDER BY total_exec_time DESC
            LIMIT 1000
        """)

        stats = {}
        for row in cursor.fetchall():
            queryid, query, calls, total_time, mean_time, rows, blks_hit, blks_read = row
            stats[queryid] = {
                "query": query,
                "calls": calls,
                "total_exec_time": total_time,
                "mean_exec_time": mean_time,
                "rows": rows,
                "blks_hit": blks_hit,
                "blks_read": blks_read,
            }

        cursor.close()
        return stats

    def generate_spans_for_new_queries(self, current_stats):
        """Generate spans for queries that have executed since last check."""
        for queryid, stats in current_stats.items():
            last_calls = self.last_stats.get(queryid, {}).get("calls", 0)
            new_calls = stats["calls"] - last_calls

            if new_calls > 0:
                # Generate span for each new execution
                for _ in range(min(new_calls, 10)):  # Limit to 10 spans per query per interval
                    self.generate_query_span(stats)

    def generate_query_span(self, stats):
        """Generate a single server-side span for a query."""
        # Start time: approximate based on mean execution time
        start_time_ns = time.time_ns() - int(stats["mean_exec_time"] * 1_000_000)

        with self.tracer.start_as_current_span(
            name=self.get_span_name(stats["query"]),
            kind=SpanKind.SERVER,
            start_time=start_time_ns,
        ) as span:
            # Set database semantic conventions
            span.set_attribute("db.system", "postgresql")
            span.set_attribute("db.name", os.getenv("POSTGRES_DB", "testdb"))
            span.set_attribute("db.user", os.getenv("POSTGRES_USER", "postgres"))
            span.set_attribute("db.statement", stats["query"][:2048])  # Limit statement length
            span.set_attribute("db.operation", self.extract_operation(stats["query"]))

            # Performance metrics
            span.set_attribute("db.execution_time_ms", stats["mean_exec_time"])
            span.set_attribute("db.rows_affected", stats["rows"])
            span.set_attribute("db.cache_hit_ratio",
                              stats["blks_hit"] / (stats["blks_hit"] + stats["blks_read"] + 1))

            # Network attributes for service graph
            span.set_attribute("network.peer.address", "postgres-primary-site-a:5432")
            span.set_attribute("peer.service", "postgres-primary-site-a")
            span.set_attribute("server.address", "postgres-primary-site-a")
            span.set_attribute("server.port", 5432)

            # End the span (duration is mean_exec_time)
            end_time_ns = start_time_ns + int(stats["mean_exec_time"] * 1_000_000)
            span.end(end_time=end_time_ns)

    def get_span_name(self, query: str) -> str:
        """Extract a human-readable span name from query."""
        query = query.strip().upper()
        if query.startswith("SELECT"):
            return "SELECT"
        elif query.startswith("INSERT"):
            return "INSERT"
        elif query.startswith("UPDATE"):
            return "UPDATE"
        elif query.startswith("DELETE"):
            return "DELETE"
        else:
            return query.split()[0] if query else "QUERY"

    def extract_operation(self, query: str) -> str:
        """Extract operation type from query."""
        return self.get_span_name(query).lower()

    def run(self):
        """Main loop: poll pg_stat_statements and generate spans."""
        logger.info("Starting PostgreSQL Span Generator")
        logger.info(f"Monitoring: {os.getenv('POSTGRES_HOST')}:{os.getenv('POSTGRES_PORT')}")
        logger.info(f"Exporting to: {os.getenv('OTEL_EXPORTER_OTLP_ENDPOINT')}")

        while True:
            try:
                current_stats = self.fetch_query_stats()
                self.generate_spans_for_new_queries(current_stats)
                self.last_stats = current_stats
                time.sleep(5)  # Poll every 5 seconds
            except Exception as e:
                logger.error(f"Error generating spans: {e}")
                time.sleep(10)


if __name__ == "__main__":
    generator = PostgresSpanGenerator()
    generator.run()
```

### Step 3: Create Docker Service

**File**: `chaostooling-demo/postgres-span-generator/Dockerfile`

```dockerfile
FROM python:3.11-slim

WORKDIR /app

RUN pip install --no-cache-dir \
    psycopg2-binary \
    opentelemetry-api \
    opentelemetry-sdk \
    opentelemetry-exporter-otlp-proto-grpc

COPY span_generator.py .

CMD ["python", "span_generator.py"]
```

**Add to docker-compose.yml**:

```yaml
  postgres-span-generator:
    build: ./postgres-span-generator
    environment:
      - POSTGRES_HOST=postgres-primary-site-a
      - POSTGRES_PORT=5432
      - POSTGRES_DB=testdb
      - POSTGRES_USER=postgres
      - POSTGRES_PASSWORD=postgres
      - OTEL_EXPORTER_OTLP_ENDPOINT=http://otel-collector:4317
      - OTEL_SERVICE_NAME=postgres-primary-site-a
    depends_on:
      - postgres-primary-site-a
      - otel-collector
```

### Step 4: Deploy and Test

```bash
# Rebuild PostgreSQL with pg_stat_statements
docker-compose up -d --build postgres-primary-site-a

# Build and start span generator
docker-compose up -d --build postgres-span-generator

# Verify it's running
docker-compose logs -f postgres-span-generator

# Run a chaos experiment to generate queries
docker exec chaostooling-demo-chaos-runner-1 bash -c \
  "cd /experiments/postgres && chaos run test-postgres-simple.json"

# Check Tempo for server-side spans
curl -s "http://localhost:3200/api/search?tags=service.name%3Dpostgres-primary-site-a" | jq
```

### Advantages ✅
- Works immediately with existing infrastructure
- No PostgreSQL code changes required
- Low overhead (polls every 5 seconds)
- Can correlate with client spans via timing heuristics

### Limitations ⚠️
- No native trace context propagation (can't link client and server spans directly)
- Approximate timing (based on mean execution time)
- Limited to queries tracked by pg_stat_statements
- Generates synthetic spans after the fact

---

## Approach 2: PostgreSQL Hook Extension (Advanced)

### Complexity: High (2-3 weeks)
### Cost: Medium (requires PostgreSQL extension development)

Build a PostgreSQL C extension that hooks into query execution and emits real-time spans.

### Architecture

```c
// pg_otel_hook.c - PostgreSQL extension

#include "postgres.h"
#include "executor/executor.h"
#include <curl/curl.h>

// Hook into query execution
static ExecutorStart_hook_type prev_ExecutorStart = NULL;

void otel_ExecutorStart(QueryDesc *queryDesc, int eflags) {
    // Extract trace context from session variables
    char *trace_id = get_session_variable("otel.trace_id");
    char *span_id = get_session_variable("otel.span_id");

    // Start server-side span
    start_otel_span(trace_id, span_id, queryDesc->sourceText);

    // Call original executor
    if (prev_ExecutorStart)
        prev_ExecutorStart(queryDesc, eflags);
    else
        standard_ExecutorStart(queryDesc, eflags);
}

void otel_ExecutorEnd(QueryDesc *queryDesc) {
    // End span and export
    end_otel_span(queryDesc->estate->es_processed);
}
```

### Advantages ✅
- Real-time span generation (not synthetic)
- Native trace context propagation
- Accurate timing and metadata
- True distributed tracing

### Limitations ⚠️
- Requires C development skills
- PostgreSQL recompilation needed
- Maintenance overhead
- Potential performance impact

**Status**: Too complex for immediate implementation. Consider Approach 1 first.

---

## Approach 3: eBPF-Based Instrumentation

### Complexity: High (1-2 weeks)
### Cost: Medium (requires eBPF tooling)

Use eBPF to trace PostgreSQL system calls and generate spans without modifying PostgreSQL.

### Tools
- **Pixie** (CNCF project) - Auto-instrumentation for databases
- **Odigos** - eBPF-based OpenTelemetry collector
- **Custom eBPF probes** using BCC/libbpf

### Example with Pixie

```yaml
# Install Pixie in Kubernetes
kubectl apply -f https://work.withpixie.ai/pixie-cloud-install.yaml

# Pixie automatically instruments PostgreSQL queries
# No code changes required
```

### Advantages ✅
- Zero code changes
- Works with any PostgreSQL version
- Low overhead
- Captures all queries automatically

### Limitations ⚠️
- Requires Kubernetes or eBPF-compatible Linux
- Docker on WSL2 may not support eBPF
- Additional infrastructure complexity

---

## Approach 4: Application-Level Query Wrapping

### Complexity: Low (1-2 days)
### Cost: Low (code changes only)

Modify Chaos Toolkit extensions to emit both client AND synthetic server spans.

### Implementation

Update `postgres_system_metrics.py`:

```python
from chaosotel.core.trace_core import get_current_span
from opentelemetry import trace
from opentelemetry.trace import SpanKind

def run_query_with_server_span(connection, query, operation="query"):
    """Execute query and generate both client and server spans."""
    tracer = trace.get_tracer(__name__)

    # Client span (already exists)
    with tracer.start_as_current_span("postgresql.query", kind=SpanKind.CLIENT) as client_span:
        # Set client attributes
        client_span.set_attribute("peer.service", "postgres-primary-site-a")

        # Generate synthetic server span as child
        with tracer.start_as_current_span("postgresql.execute", kind=SpanKind.SERVER) as server_span:
            # Set server attributes
            server_span.set_attribute("service.name", "postgres-primary-site-a")
            server_span.set_attribute("db.system", "postgresql")
            server_span.set_attribute("db.statement", query)

            # Execute query
            cursor = connection.cursor()
            start_time = time.time()
            cursor.execute(query)
            execution_time = time.time() - start_time

            server_span.set_attribute("db.execution_time_ms", execution_time * 1000)

            return cursor.fetchall()
```

### Advantages ✅
- Simple to implement
- No infrastructure changes
- Works immediately
- Full trace context propagation

### Limitations ⚠️
- Not "real" server-side spans (still generated by client)
- Only covers queries from Chaos Toolkit
- Doesn't capture queries from other sources

---

## Recommended Implementation Path

### Phase 1: Quick Win (1 day)
1. ✅ **Already done**: PostgreSQL receiver for metrics
2. **Implement Approach 4**: Application-level query wrapping for immediate service graph visibility

### Phase 2: Real Server Spans (3 days)
3. **Implement Approach 1**: pg_stat_statements span generator for true server-side spans
4. Enable pg_stat_statements extension
5. Deploy span generator service

### Phase 3: Enhancement (Optional)
6. Add trace context propagation via session variables
7. Implement query sampling (only trace slow queries)
8. Add query plan capture

---

## Query-Level Traces: What You'll Get

Once span generation is implemented, you'll see:

### In Tempo Service Graph
```
chaostoolkit-demo ──────────▶ postgres-primary-site-a
                   5 req/s
                   avg: 23ms
```

### In Trace View
```
Trace ID: 4bf92f3577b34da6a3ce929d0e0e4736
Duration: 145ms

  ├─ chaostoolkit-demo: GET /api/users
  │  Duration: 145ms
  │
  ├──▶ postgres-primary-site-a: SELECT
     │  Duration: 23ms
     │  db.statement: SELECT * FROM users WHERE id = $1
     │  db.rows: 1
     │  db.execution_time_ms: 23
     │
     └──▶ postgres-primary-site-a: UPDATE
        Duration: 12ms
        db.statement: UPDATE users SET last_login = NOW() WHERE id = $1
        db.rows: 1
```

### In Query Analysis Dashboard
- Top 10 slowest queries
- Query frequency heatmap
- Cache hit ratio per query
- Query execution time distribution

---

## Next Steps

Choose one of the approaches above and I can help you implement it. My recommendation:

**Start with Approach 4** (Application-Level) for immediate results, then **move to Approach 1** (pg_stat_statements) for production use.

Which approach would you like to implement first?

---

**Created**: 2026-01-21
**References**:
- [PostgreSQL pg_stat_statements Documentation](https://www.postgresql.org/docs/current/pgstatstatements.html)
- [OpenTelemetry Database Semantic Conventions](https://opentelemetry.io/docs/specs/semconv/database/)
- [PostgreSQL Hooks Documentation](https://www.postgresql.org/docs/current/hooks.html)
