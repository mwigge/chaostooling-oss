# Service Graph Workaround for Databases

## Problem

Grafana's nodeGraph panel with Tempo's service graph only shows services that have BOTH client and server spans. Since databases like PostgreSQL don't emit OpenTelemetry traces, they don't appear in the default service graph even though we've correctly set `peer.service` attributes.

## Solution: Alternative Visualizations

### Option 1: Table Panel with Database Connections

Instead of nodeGraph, use a **Table panel** that queries Prometheus for span metrics grouped by `peer_service`:

```promql
sum by (service_name, peer_service, db_system) (
  rate(traces_span_metrics_calls_total{peer_service!=""}[5m])
)
```

**Panel Config**:
- Type: Table
- Transform: Group by `peer_service`
- Shows: service_name → peer_service with request rate

### Option 2: Sankey Diagram (Flow Visualization)

Use the Sankey panel plugin to show service → database flows:

```promql
sum by (service_name, peer_service) (
  increase(traces_span_metrics_calls_total{peer_service=~".*postgres.*|.*mysql.*|.*redis.*"}[1h])
)
```

### Option 3: Custom Node Graph with TraceQL

Query Tempo directly using TraceQL to find database interactions:

```traceql
{span.peer.service = "postgres-primary-site-a"}
```

Then aggregate in Grafana to build a custom node list.

### Option 4: Documentation Panel

Add a simple text panel explaining the database connections:

```markdown
## Database Connections

The following databases are accessed by this experiment:

- **PostgreSQL Primary**: postgres-primary-site-a:5432
- **PostgreSQL Replica**: postgres-replica-site-a:5432

Note: Databases don't appear in the service graph because they don't emit
OpenTelemetry traces. Check the "Database Span Metrics" panel below for
interaction statistics.
```

## Implemented Solution

We've added a **"Database Interactions" table panel** to the dashboard template that shows:
- Service making the call
- Database being called (peer_service)
- Database type (db.system)
- Request rate
- Error rate

This provides better visibility than the service graph for database-only services.

## Future Enhancement

If you need full service graph visualization including databases, you would need to:

1. **Instrument PostgreSQL** with OpenTelemetry (requires pg_stat_statements + custom exporter)
2. **Use a sidecar** that generates synthetic server spans for database calls
3. **Use Tempo's virtual nodes** feature (requires Tempo 2.4+ with specific config)

For now, the table/metrics approach provides complete visibility into database interactions.
