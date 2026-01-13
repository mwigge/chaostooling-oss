# chaostooling-otel

OpenTelemetry extensions for Chaos Toolkit.

## Overview

`chaostooling-otel` provides comprehensive observability (metrics, logs, and traces) for chaos engineering experiments using OpenTelemetry. It integrates with Tempo/Jaeger for distributed tracing, enabling visualization of service graphs and transaction flows across complex distributed systems.

## Features

- **Distributed Tracing**: Full OpenTelemetry trace support with automatic service graph generation
- **Metrics**: Prometheus-compatible metrics collection
- **Logs**: Structured logging with OpenTelemetry
- **Service Graph Visibility**: Automatic mapping of database and messaging systems to service names
- **Modular Tracing Helpers**: Easy-to-use instrumentation for databases and messaging systems

## Quick Start

### Installation

```bash
pip install chaostooling-otel
```

### Basic Usage

```python
from chaosotel.control import initialize_observability

# Initialize in your experiment configuration
initialize_observability(
    tempo_endpoint="http://tempo:4317",
    service_name="my-chaos-experiment"
)
```

## Distributed Tracing

### Automatic Service Name Mapping

The `ServiceNameSpanProcessor` automatically maps database and messaging system attributes to `resource.service.name`, ensuring all systems appear in Grafana/Tempo service graphs.

**Supported Database Systems:**
- PostgreSQL, MySQL, MSSQL, MongoDB, Redis, Cassandra, DuckDB, SQLite, Oracle

**Supported Messaging Systems:**
- Kafka, RabbitMQ, ActiveMQ, NATS, Pulsar, SQS

The processor automatically:
- Maps `db.system` → `resource.service.name` (e.g., "postgresql", "mysql")
- Maps `messaging.system` → `resource.service.name` (e.g., "kafka", "rabbitmq")
- Works with both existing and new instrumentation

### Span Instrumentation Helpers

The `trace_core` module provides convenient helpers for instrumenting database and messaging operations:

#### Database Instrumentation

```python
from chaosotel.core.trace_core import instrument_db_span, InstrumentedSpan

# Simple usage
with InstrumentedSpan(instrument_db_span(
    "query.execute",
    db_system="postgresql",
    db_name="mydb",
    db_host="localhost",
    db_port=5432
)) as span:
    # Your database operation here
    cursor.execute("SELECT * FROM users")
```

#### Messaging Instrumentation

```python
from chaosotel.core.trace_core import instrument_messaging_span, InstrumentedSpan

# Messaging operations
with InstrumentedSpan(instrument_messaging_span(
    "message.publish",
    messaging_system="kafka",
    destination="user-events",
    destination_kind="topic"
)) as span:
    # Your messaging operation here
    producer.send("user-events", message)
```

#### Auto-Detection

The helpers can auto-detect the system from the calling module:

```python
from chaosotel.core.trace_core import create_instrumented_span

# System name auto-detected from module path
span = create_instrumented_span("operation.execute")
# Automatically sets db.system or messaging.system based on module
```

### Custom System Mappings

You can extend support for new databases or messaging systems via environment variables:

```bash
# Add custom database system mapping
export CHAOS_DB_SYSTEM_MAP='{"duckdb": "duckdb", "clickhouse": "clickhouse"}'

# Add custom messaging system mapping
export CHAOS_MESSAGING_SYSTEM_MAP='{"nats": "nats", "pulsar": "pulsar"}'
```

The mappings are JSON objects that extend the default system maps.

### Migration from Existing Code

If you have existing code that sets `db.system` or `messaging.system` manually, the `ServiceNameSpanProcessor` will automatically enhance those spans. No code changes required!

For new code, use the helpers for better consistency:

```python
# Old way (still works, but less convenient)
span.set_attribute("db.system", "postgresql")
span.set_attribute("db.name", "mydb")

# New way (recommended)
from chaosotel.core.trace_core import instrument_db_span, InstrumentedSpan
with InstrumentedSpan(instrument_db_span(
    "query.execute",
    db_system="postgresql",
    db_name="mydb"
)) as span:
    # Your code
```

## Architecture

### Components

- **`traces.py`**: Trace exporter setup and `ServiceNameSpanProcessor`
- **`core/trace_core.py`**: Core tracing interface and span instrumentation helpers
- **`core/metrics_core.py`**: Metrics collection
- **`core/log_core.py`**: Structured logging
- **`core/compliance_core.py`**: Compliance tracking

### Service Name Processor

The `ServiceNameSpanProcessor` runs automatically when tracing is initialized. It:

1. Intercepts all spans before export
2. Checks for `db.system` or `messaging.system` attributes
3. Maps them to `resource.service.name` using system mappings
4. Ensures service graph visibility in Grafana/Tempo

This happens transparently - no changes needed to existing code.

## Integration with Chaos Extensions

### extension-db

The `chaostooling-extension-db` package re-exports the span helpers for convenience:

```python
# Both work the same way
from chaosotel.core.trace_core import instrument_db_span
from chaosdb.common import instrument_db_span  # Re-exported
```

### extension-compute

Compute stress actions automatically create traces with proper instrumentation.

### extension-network

Network chaos actions are traced with network-specific attributes.

## Configuration

### Environment Variables

- `CHAOS_DB_SYSTEM_MAP`: JSON mapping for custom database systems
- `CHAOS_MESSAGING_SYSTEM_MAP`: JSON mapping for custom messaging systems
- `TEMPO_ENDPOINT`: Tempo OTLP endpoint (default: `http://localhost:4317`)
- `SERVICE_NAME`: Service name for traces (default: `chaos-experiment`)

### Experiment Configuration

```json
{
  "configuration": {
    "tempo_endpoint": {
      "type": "env",
      "key": "TEMPO_ENDPOINT",
      "default": "http://tempo:4317"
    }
  },
  "controls": [
    {
      "name": "chaosotel",
      "provider": {
        "type": "python",
        "module": "chaosotel.control",
        "arguments": {
          "tempo_endpoint": "${tempo_endpoint}",
          "service_name": "production-chaos-experiment"
        }
      }
    }
  ]
}
```

## Service Graph Visualization

With proper instrumentation, all systems appear in Grafana/Tempo service graphs:

- **Databases**: PostgreSQL, MySQL, MSSQL, MongoDB, Redis, Cassandra
- **Messaging**: Kafka, RabbitMQ, ActiveMQ
- **Application Services**: App servers, payment services, order services
- **Infrastructure**: HA-Proxy, load balancers

The service graph query should include all system names:

```traceql
{ resource.service.name =~ ".*(postgresql|mysql|mssql|mongodb|redis|cassandra|kafka|rabbitmq|activemq).*" }
```

## Best Practices

1. **Use Helpers**: Prefer `instrument_db_span()` and `instrument_messaging_span()` over manual attribute setting
2. **Context Managers**: Use `InstrumentedSpan` for automatic span lifecycle management
3. **System Names**: Use standard OpenTelemetry system names (e.g., "postgresql", not "postgres")
4. **Custom Mappings**: Add new systems via environment variables, not code changes
5. **Service Names**: Let the processor handle `resource.service.name` - don't set it manually

## Troubleshooting

### Systems Not Appearing in Service Graph

1. Check that `ServiceNameSpanProcessor` is registered (automatic if using `chaosotel.control`)
2. Verify spans have `db.system` or `messaging.system` attributes
3. Check dashboard query includes the system name
4. Ensure traces are being exported to Tempo

### Custom Systems Not Working

1. Verify environment variable JSON is valid
2. Check system name matches exactly (case-sensitive)
3. Ensure the system is in the correct map (DB vs Messaging)

## Contributing

When adding support for new databases or messaging systems:

1. Add to `DB_SYSTEM_MAP` or `MESSAGING_SYSTEM_MAP` in `trace_core.py`
2. Add aliases if needed (e.g., "postgres" → "postgresql")
3. Update this README with the new system
4. Test with service graph visualization

## License

See main project LICENSE file.
