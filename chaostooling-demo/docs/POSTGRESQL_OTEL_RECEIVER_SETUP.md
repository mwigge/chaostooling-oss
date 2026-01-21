# PostgreSQL OTEL Collector Receiver Setup

## Overview

This document explains how to set up the OpenTelemetry Collector to collect metrics directly from PostgreSQL databases using the PostgreSQL receiver.

## What Was Changed

### 1. OTEL Collector Builder Configuration

**File**: [chaostooling-demo/otel-collector/builder-config.yaml](otel-collector/builder-config.yaml)

Added PostgreSQL receiver module:
```yaml
receivers:
  - gomod: github.com/open-telemetry/opentelemetry-collector-contrib/receiver/postgresqlreceiver v0.117.0
```

### 2. OTEL Collector Runtime Configuration

**File**: [chaostooling-demo/otel-collector/config.yaml](otel-collector/config.yaml)

Added two PostgreSQL receiver instances:

**Primary Database Receiver**:
```yaml
postgresql:
  endpoint: postgres-primary-site-a:5432
  transport: tcp
  username: postgres
  password: postgres
  databases:
    - testdb
  collection_interval: 10s
  initial_delay: 10s
  tls:
    insecure: true
```

**Replica Database Receiver**:
```yaml
postgresql/replica:
  endpoint: postgres-replica-site-a:5432
  transport: tcp
  username: postgres
  password: postgres
  databases:
    - testdb
  collection_interval: 10s
```

**Updated Metrics Pipeline**:
```yaml
metrics:
  receivers: [otlp, prometheus, docker_stats, postgresql, postgresql/replica, servicegraph]
  processors: [batch]
  exporters: [prometheus]
```

## PostgreSQL-Side Requirements

### ✅ No Configuration Changes Required!

The PostgreSQL receiver uses standard PostgreSQL statistics views that are **enabled by default**:

- `pg_stat_database` - database-level statistics
- `pg_stat_bgwriter` - background writer statistics
- `pg_database` - database metadata and size
- `pg_stat_activity` - connection and backend information

### Database Permissions

The `postgres` superuser (already configured in docker-compose) has all necessary permissions. No additional grants are needed.

### Optional: Enable Extended Statistics

If you want more detailed query-level metrics in the future, you can enable `pg_stat_statements`:

**Add to PostgreSQL command in docker-compose.yml**:
```yaml
postgres-primary-site-a:
  command:
    - "postgres"
    - "-c"
    - "shared_preload_libraries=pg_stat_statements"
    - "-c"
    - "pg_stat_statements.track=all"
    # ... existing wal_level, max_wal_senders, etc.
```

**Note**: This is NOT required for the OTEL Collector PostgreSQL receiver to work. This is only if you want query-level statistics later.

## Metrics Collected

The PostgreSQL receiver collects the following metrics:

### Connection Metrics
- `postgresql.backends` - Number of active connections
- `postgresql.connections` - Total connection count
- `postgresql.database.count` - Number of databases

### Transaction Metrics
- `postgresql.commits` - Committed transactions per second
- `postgresql.rollbacks` - Rolled back transactions per second
- `postgresql.deadlocks` - Deadlock count

### I/O Metrics
- `postgresql.blocks_read` - Blocks read from disk vs cache
- `postgresql.bgwriter.buffers.allocated` - Buffers allocated by bgwriter
- `postgresql.bgwriter.buffers.writes` - Buffers written by bgwriter

### Storage Metrics
- `postgresql.db.size` - Database size in bytes
- `postgresql.temp_files` - Temporary files created

### Row Operations
- `postgresql.rows` - Rows fetched, inserted, updated, deleted
- `postgresql.operations` - DML operation counts

## Deployment Steps

### Step 1: Rebuild OTEL Collector Image

Since we added a new receiver module, the collector must be rebuilt:

```bash
cd chaostooling-demo
docker-compose build otel-collector
```

**Expected output**:
```
Building otel-collector
[+] Building 45.3s (14/14) FINISHED
 => [builder] RUN go install go.opentelemetry.io/collector/cmd/builder@v0.117.0
 => [builder] COPY builder-config.yaml .
 => [builder] RUN builder --config builder-config.yaml
 => [stage-1] COPY --from=builder /app/otelcol-custom/otelcol-custom /usr/local/bin/
```

### Step 2: Restart OTEL Collector

```bash
docker-compose restart otel-collector
```

**Verify it started successfully**:
```bash
docker-compose logs -f otel-collector | head -50
```

**Expected logs**:
```
otel-collector | 2026-01-21T10:00:00.000Z info service@v0.117.0/service.go:161 Starting otelcol-custom...
otel-collector | 2026-01-21T10:00:00.005Z info receiver/postgresql.go:42 Starting PostgreSQL receiver {"endpoint": "postgres-primary-site-a:5432"}
otel-collector | 2026-01-21T10:00:00.010Z info receiver/postgresql.go:42 Starting PostgreSQL receiver {"endpoint": "postgres-replica-site-a:5432"}
```

### Step 3: Verify Metrics Collection

**Check PostgreSQL metrics in Prometheus** (wait 30 seconds after restart):

```bash
# Check if PostgreSQL metrics are being collected
curl -s 'http://localhost:9090/api/v1/query?query=postgresql_backends' | jq '.data.result'

# Check database size metric
curl -s 'http://localhost:9090/api/v1/query?query=postgresql_db_size' | jq '.data.result'

# Check connection metrics
curl -s 'http://localhost:9090/api/v1/query?query=postgresql_connections' | jq '.data.result'
```

**Expected output**:
```json
[
  {
    "metric": {
      "__name__": "postgresql_backends",
      "database_name": "testdb",
      "instance": "otel-collector:8889",
      "job": "otel-collector",
      "postgresql_database_name": "testdb"
    },
    "value": [1737454800, "3"]
  }
]
```

### Step 4: Check OTEL Collector Self-Metrics

```bash
# Check collector's own metrics endpoint
curl -s http://localhost:8889/metrics | grep postgresql_

# Expected output shows receiver metrics:
# otelcol_receiver_accepted_metric_points{receiver="postgresql",transport="tcp"} 150
# otelcol_receiver_refused_metric_points{receiver="postgresql",transport="tcp"} 0
```

## Troubleshooting

### Error: "connection refused" in OTEL Collector logs

**Symptom**:
```
Error: failed to connect to PostgreSQL: dial tcp: connection refused
```

**Solution**:
- Ensure PostgreSQL containers are running: `docker-compose ps postgres-primary-site-a`
- Check network connectivity: `docker-compose exec otel-collector ping postgres-primary-site-a`
- Verify PostgreSQL is listening: `docker-compose exec postgres-primary-site-a pg_isready`

### Error: "password authentication failed"

**Symptom**:
```
Error: pq: password authentication failed for user "postgres"
```

**Solution**:
- Check credentials in `config.yaml` match docker-compose environment variables
- Default credentials are `postgres:postgres`
- Verify with: `docker-compose exec postgres-primary-site-a psql -U postgres -c "SELECT 1"`

### No Metrics Appearing in Prometheus

**Checks**:

1. **Verify receiver is configured in pipeline**:
```bash
docker-compose exec otel-collector cat /etc/otelcol-custom/config.yaml | grep postgresql
```

2. **Check collector logs for errors**:
```bash
docker-compose logs otel-collector | grep -i error | tail -20
```

3. **Verify Prometheus is scraping collector**:
```bash
curl -s http://localhost:9090/api/v1/targets | jq '.data.activeTargets[] | select(.labels.job=="otel-collector")'
```

4. **Check if metrics are being exported**:
```bash
curl -s http://localhost:8889/metrics | grep "^postgresql_" | head -10
```

### Metrics Have Wrong Labels

**Issue**: Metrics from primary and replica aren't distinguishable

**Solution**: Add resource attributes to distinguish instances. Update `config.yaml`:

```yaml
processors:
  resource:
    attributes:
      - key: postgresql.instance
        value: primary
        action: insert

# Then in pipeline:
metrics:
  receivers: [postgresql]
  processors: [resource, batch]
  exporters: [prometheus]
```

## What This Enables

### 1. Database Metrics in Prometheus

You can now query PostgreSQL metrics directly:

```promql
# Current active connections
postgresql_backends{database_name="testdb"}

# Database size over time
postgresql_db_size{database_name="testdb"}

# Transaction rate
rate(postgresql_commits[5m])

# Deadlock rate
rate(postgresql_deadlocks[5m])
```

### 2. Database Panels in Grafana Dashboards

Add panels like:

**Active Connections**:
- Query: `postgresql_backends{database_name="testdb"}`
- Visualization: Time series

**Database Size**:
- Query: `postgresql_db_size{database_name="testdb"}`
- Visualization: Gauge
- Unit: bytes

**Transaction Throughput**:
- Query: `rate(postgresql_commits[5m]) + rate(postgresql_rollbacks[5m])`
- Visualization: Time series
- Legend: Transactions/sec

### 3. Still NOT Service Graph Visibility

**Important**: This PostgreSQL receiver collects **metrics**, NOT **traces**.

The service graph visibility issue remains because:
- Service graphs require **bidirectional traces** (client + server spans)
- PostgreSQL receiver only collects **metrics** (statistics snapshots)
- To appear in service graph, PostgreSQL would need to:
  - Emit OpenTelemetry traces for each query
  - Include trace context propagation
  - Generate server-side spans

**What you GET**:
- ✅ PostgreSQL metrics in Prometheus (connections, size, transactions, etc.)
- ✅ Database health monitoring in dashboards
- ✅ Historical metric analysis

**What you DON'T GET** (yet):
- ❌ PostgreSQL node in service graph
- ❌ Query-level traces
- ❌ Distributed tracing through database

## Next Steps for Service Graph Visibility

If you still want PostgreSQL to appear in the service graph, you need to implement **span generation** from database metrics. Options:

### Option 1: Span Metrics Connector (Recommended)

Add a processor that generates synthetic server-side spans from the client-side spans we already emit:

```yaml
processors:
  spanmetrics:
    metrics_exporter: prometheus
    dimensions:
      - name: peer.service
```

This would create pseudo-server spans for PostgreSQL based on our existing client spans.

### Option 2: PostgreSQL Query Tracer (Advanced)

Build a custom component that:
1. Monitors `pg_stat_statements` for query activity
2. Generates server-side spans for each query
3. Correlates with client trace context if available

**Complexity**: High (2-3 weeks development)

### Option 3: Use Table Panel (Current Solution)

Continue using the "Database Interactions" table panel from previous work, which shows database activity via span metrics.

## Summary

### What Changed
- ✅ Added PostgreSQL receiver to OTEL Collector builder config
- ✅ Configured PostgreSQL receiver for primary and replica databases
- ✅ Updated metrics pipeline to include PostgreSQL receivers

### PostgreSQL Side
- ✅ No changes required - uses default statistics views
- ✅ Existing `postgres` user has sufficient permissions
- ⚠️ Optional: Can enable `pg_stat_statements` for future query-level metrics

### What You Get
- ✅ PostgreSQL metrics in Prometheus
- ✅ Database health monitoring capabilities
- ✅ Historical metric analysis

### What You DON'T Get
- ❌ Service graph visibility (still requires span generation)
- ❌ Query-level traces (would need pg_stat_statements + custom exporter)

### Next Action
```bash
# Rebuild and restart OTEL Collector
cd chaostooling-demo
docker-compose build otel-collector
docker-compose restart otel-collector

# Wait 30 seconds, then verify
curl -s 'http://localhost:9090/api/v1/query?query=postgresql_backends' | jq
```

---

**Created**: 2026-01-21
**References**:
- [PostgreSQL Receiver Documentation](https://github.com/open-telemetry/opentelemetry-collector-contrib/tree/main/receiver/postgresqlreceiver)
- [OTEL Collector Builder](https://github.com/open-telemetry/opentelemetry-collector/tree/main/cmd/builder)
- [PostgreSQL Statistics Views](https://www.postgresql.org/docs/15/monitoring-stats.html)
