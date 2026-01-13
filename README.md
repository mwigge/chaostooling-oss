# ChaosTooling OSS

Open source Chaos Engineering toolkit ecosystem built on Chaos Toolkit.

## Overview

ChaosTooling provides a comprehensive set of extensions, observability tools, and demo environments for chaos engineering. This monorepo contains all components needed to run chaos experiments with full observability.

## Architecture

### Core Components

1. **chaostooling-otel** - OpenTelemetry observability for Chaos Toolkit (module: `chaosotel`)
2. **chaostooling-extension-db** - Database and messaging system extensions
3. **chaostooling-extension-compute** - Compute resource extensions
4. **chaostooling-extension-network** - Network extensions
5. **chaostooling-reporting** - Reporting and analytics extension
6. **chaostooling-demo** - Demo environment with full observability stack
7. **chaostooling-experiments** - Example experiments

## Quick Start

### Prerequisites
- Docker and Docker Compose
- Python 3.9+ (for local development)

### Important Notes

- **OpenTelemetry Logging**: All actions and probes use OpenTelemetry logging standard (not Python standard logging). This ensures proper log export to Loki.
- **Service Graph Visibility**: Database and messaging systems automatically appear in Grafana service graphs via `ServiceNameSpanProcessor`.
- **Metric Names**: Operation metrics are exported as `chaos_operation_success_total` and `chaos_operation_error_total` for dashboard compatibility.

### Installation

1. **Clone this repository:**
   ```bash
   git clone <chaostooling-oss-repo>
   cd chaostooling-oss
   ```

2. **Start the demo environment:**
   ```bash
   cd chaostooling-demo
OBS! 
  when using otel-collector in docker and docker stats - a workaround needed might be:  chmod 666 /var/run/docker.sock 
  needed also after reboots or time passed.  

   docker compose up -d
   ```

3. **Run an experiment:**
   ```bash
   docker compose exec chaos-runner chaos run /experiments/postgres/test-postgres-query-saturation.json
   ```

4. **View dashboards:**
   - Grafana: http://localhost:3000 (admin/admin)
   - Prometheus: http://localhost:9090
   - Tempo: http://localhost:3200

## Observability (chaostooling-otel)

ChaosTooling uses OpenTelemetry for unified observability across all experiments.

### Features
- 📊 Structured Logging → Loki via OpenTelemetry (uses OpenTelemetry LoggingHandler standard)
- 📈 Prometheus Metrics → 60+ built-in metrics (includes `chaos_operation_success_total` and `chaos_operation_error_total`)
- 🔍 Distributed Tracing → Tempo via OpenTelemetry (automatic service graph visibility)
- ✅ Compliance Tracking → SOX, GDPR, PCI-DSS, HIPAA
- 🎯 Automatic Instrumentation → Zero-boilerplate decorators
- 🧮 Risk Calculation → Experiment complexity & risk scoring
- 🔄 MTTR Tracking → Mean Time To Recovery metrics
- 🔧 Modular Span Helpers → Reusable span attribute helpers for any database, messaging, or API

### Installation
```bash
pip install chaostooling-otel
```

### Initialization

```python
from chaosotel import initialize

# Initialize at startup
initialize(
    target_type="database",  # or "network", "compute", "messaging"
    service_version="1.0.0",
    regulations=["SOX", "GDPR", "PCI-DSS"],  # Optional
    auto_instrument=True  # Enable automatic instrumentation
)
```

### Traces

Distributed tracing with automatic service graph visibility. All database and messaging systems automatically appear in Grafana service graphs.

#### Modular Span Helpers

Use modular helpers for consistent span attributes across all systems:

**Database Operations (PostgreSQL, MySQL, MSSQL, Cassandra, Redis, MongoDB, etc.):**
```python
from opentelemetry import trace
from chaosotel.core.trace_core import set_db_span_attributes

tracer = trace.get_tracer(__name__)
with tracer.start_as_current_span("slow_transaction.worker.1") as span:
    set_db_span_attributes(
        span,
        db_system="postgresql",  # Works with any DB: "mysql", "mssql", "cassandra", "redis", etc.
        db_name="testdb",
        host="postgres-primary-site-a",
        port=5432,
        chaos_activity="postgresql_slow_transactions",
        chaos_action="slow_transactions",
        chaos_operation="slow_transactions",
        chaos_thread_id=1
    )
    # ... your database code ...
```

**Messaging Operations (Kafka, RabbitMQ, ActiveMQ, NATS, Pulsar, SQS, etc.):**
```python
from opentelemetry import trace
from chaosotel.core.trace_core import set_messaging_span_attributes

tracer = trace.get_tracer(__name__)
with tracer.start_as_current_span("message_flood.producer.1") as span:
    set_messaging_span_attributes(
        span,
        messaging_system="kafka",  # or "rabbitmq", "activemq", etc.
        destination="test-topic",
        bootstrap_servers="kafka:9092",  # For Kafka (auto-parsed)
        # OR host="rabbitmq", port=5672  # For RabbitMQ/ActiveMQ
        chaos_activity="kafka_message_flood",
        chaos_action="message_flood",
        chaos_producer_id=1
    )
    # ... your messaging code ...
```

**API/HTTP Operations:**
```python
from opentelemetry import trace
from chaosotel.core.trace_core import set_api_span_attributes

tracer = trace.get_tracer(__name__)
with tracer.start_as_current_span("api.request") as span:
    set_api_span_attributes(
        span,
        http_method="POST",
        http_url="http://api.example.com/v1/transactions",
        host="api.example.com",
        port=80,
        chaos_activity="api_transaction_flow"
    )
    # ... your API code ...
```

#### Manual Trace Creation

```python
from chaosotel import get_tracer, get_trace_core

# Get tracer
tracer = get_tracer()

# Create span
with tracer.start_as_current_span("my-operation") as span:
    span.set_attribute("operation.name", "test")
    # ... your code ...
    span.set_status(StatusCode.OK)

# Or use TraceCore
traces = get_trace_core()
with traces.span_context("my-operation", {"key": "value"}):
    # ... your code ...
```

### Metrics

60+ built-in metrics exported to Prometheus. All metrics use the `chaos_` prefix for dashboard compatibility.

#### Recording Metrics

```python
from chaosotel import get_metrics_core

metrics = get_metrics_core()

# Record operation metrics
metrics.record_operation_duration(
    name="slow_transaction",
    duration_ms=5000.0,
    status="success",
    severity="high",
    target_type="database"
)

metrics.record_operation_count(
    name="slow_transaction",
    status="success",
    severity="high",
    target_type="database"
)

# Record database metrics
metrics.record_db_query_latency(
    query_time_ms=100.0,
    db_system="postgresql",
    db_name="testdb",
    db_operation="select"
)

metrics.record_db_error(
    db_system="postgresql",
    error_type="ConnectionError",
    db_name="testdb"
)

# Record custom metrics
metrics.record_custom_metric(
    "my.custom.metric",
    value=42.0,
    metric_type="gauge",
    tags={"environment": "production"}
)
```

#### Available Metrics

- **Operation Metrics**: `chaos_operation_success_total`, `chaos_operation_error_total`, `chaos_operation_duration_ms`
- **Probe Metrics**: `chaos_probe_success_total`, `chaos_probe_error_total`, `chaos_probe_duration_ms`
- **Database Metrics**: `chaos_db_error_count_total`, `chaos_db_slow_query_count_total`, `chaos_db_lock_count_total`, `chaos_db_deadlock_count_total`
- **Messaging Metrics**: `chaos_messaging_error_count_total`, `chaos_messaging_slow_operation_count_total`
- **Compliance Metrics**: Compliance scores, violation counts
- **Experiment Metrics**: Risk level, complexity score, duration, success/failure

### Logs

Structured logging with OpenTelemetry LoggingHandler standard. All logs are automatically exported to Loki via OTEL Collector.

#### Logging Standards

All actions and probes use **OpenTelemetry logging standard**:
- Logs are automatically exported to Loki via OTEL Collector
- Proper exception logging with `exc_info=True` for full tracebacks
- Structured logging with trace context (trace_id, span_id)

#### Using Logs

```python
from chaosotel import get_logger, get_log_core

# Get OpenTelemetry logger
logger = get_logger()

# Standard logging (automatically exported to Loki)
logger.info("Action started", extra={"action": "slow_transactions"})
logger.warning("Warning message", exc_info=True)  # Include exception traceback
logger.error("Error occurred", exc_info=True)

# Or use LogCore for structured logging
logs = get_log_core()
logs.log_action_start(
    action_name="slow_transactions",
    target_type="database",
    tags={"db_system": "postgresql"}
)
logs.log_action_end(
    action_name="slow_transactions",
    status="success",
    duration_ms=5000.0
)
```

### Decorators

Zero-boilerplate automatic instrumentation with decorators.

#### @instrument_action

Automatically tracks action execution with metrics, logs, and traces:

```python
from chaosotel import instrument_action

@instrument_action(
    name="kill_active_connections",
    target_type="database",
    severity="high"
)
def kill_connections():
    """Kill active database connections"""
    return 5
```

#### @instrument_probe

Automatically tracks probe execution:

```python
from chaosotel import instrument_probe

@instrument_probe(
    name="check_postgres_connectivity",
    target_type="database"
)
def check_postgres_connectivity():
    return {"connected": True, "status": "healthy"}
```

#### @instrument_rollback

Tracks rollback/recovery operations:

```python
from chaosotel import instrument_rollback

@instrument_rollback(
    name="restore_connections",
    target_type="database"
)
def restore_connections():
    """Restore database connections"""
    pass
```

#### @track_compliance

Tracks compliance violations:

```python
from chaosotel import track_compliance

@track_compliance(
    regulations=["SOX", "GDPR"],
    action_name="data_access"
)
def access_user_data():
    """Access user data - may trigger GDPR compliance check"""
    pass
```

#### @record_metric

Record custom metrics:

```python
from chaosotel import record_metric

@record_metric(
    name="custom.event.count",
    metric_type="counter"
)
def custom_operation():
    pass
```

#### instrumented_section

Context manager for code block instrumentation:

```python
from chaosotel import instrumented_section

with instrumented_section("critical-section", target_type="database"):
    # Your code here
    pass
```

### Control

Chaos Toolkit lifecycle integration. Automatically tracks experiment phases, activities, and infrastructure resources.

#### Usage in Experiments

```json
{
  "controls": [
    {
      "name": "chaosotel",
      "provider": {
        "type": "python",
        "module": "chaosotel.control"
      },
      "configuration": {
        "target_type": "database",
        "service_version": "1.0.0"
      }
    }
  ]
}
```

#### What It Tracks

- **Experiment Lifecycle**: Start, end, duration, success/failure
- **Activity Spans**: Each action/probe gets its own span as child of experiment span
- **Infrastructure Snapshots**: CPU/memory usage per activity (if psutil available)
- **Phase Metrics**: Active/inactive experiment phases
- **Automatic Risk/Complexity**: Calculates and exports risk level and complexity score

### Compliance

Multi-regulation compliance tracking (SOX, GDPR, PCI-DSS, HIPAA) with automatic violation detection.

#### Using Compliance Tracking

```python
from chaosotel import get_compliance_core, Regulation

compliance = get_compliance_core()

# Track action execution
compliance.track_action_execution(
    action_name="slow_transactions",
    target="postgres-primary",
    target_type="database",
    severity="high",
    status="success",
    duration_ms=5000.0
)

# Get compliance scores
sox_score = compliance.get_compliance_score(Regulation.SOX.value)
overall_score = compliance.get_overall_score()

# Get violations
violations = compliance.get_violations(Regulation.GDPR.value)

# Get audit trail
audit_trail = compliance.get_audit_trail()
```

#### Compliance Decorator

```python
from chaosotel import track_compliance

@track_compliance(
    regulations=["SOX", "GDPR"],
    action_name="data_access"
)
def access_user_data():
    """Automatically tracked for compliance"""
    pass
```

### Calculator

Automatic risk level and complexity score calculation with metric export.

#### Risk Level Calculation

```python
from chaosotel import calculate_risk_level

risk = calculate_risk_level({
    "severity": "high",           # low, medium, high, critical
    "blast_radius": 0.4,          # 0.0-1.0 (% of infrastructure)
    "is_production": True,        # True/False
    "has_rollback": True,         # True/False
    "target_systems": 3           # Number of systems
})

print(f"Risk: {risk['level_name']} (Level {risk['level']})")
print(f"Score: {risk['score']}/100")
# Output: Risk: High (Level 3), Score: 72.5/100
```

**Risk Levels:**
- **Level 1 (Low)**: Simple single-system test
- **Level 2 (Medium)**: Multiple systems, basic chaos
- **Level 3 (High)**: Database failover, replication
- **Level 4 (Critical)**: Data loss, cascading failures

#### Complexity Score Calculation

```python
from chaosotel import calculate_complexity_score

complexity = calculate_complexity_score({
    "num_steps": 15,
    "num_probes": 8,
    "num_rollbacks": 3,
    "duration_seconds": 3600,
    "target_types": ["database", "network"]
})

print(f"Difficulty: {complexity['difficulty']}")
print(f"Score: {complexity['score']}/100")
# Output: Difficulty: Advanced, Score: 58.3/100
```

**Difficulty Levels:**
- **1-20 (Simple)**: Basic experiments
- **21-40 (Intermediate)**: Standard chaos scenarios
- **41-60 (Advanced)**: Complex multi-system tests
- **61-80 (Expert)**: Production-scale experiments
- **81-100 (Master)**: Enterprise-grade chaos engineering

#### Automatic Export

```python
from chaosotel import calculate_and_export_metrics

result = calculate_and_export_metrics(
    experiment_name="test-postgres-failover",
    duration_seconds=300,
    success=True,
    target_type="database",
    severity="high",
    is_production=True,
    num_steps=10,
    num_probes=5
)

# Automatically exports to Prometheus:
# - experiment.risk.level
# - experiment.complexity.score
# - experiment.duration.seconds
# - experiment.success
```

### Complete Example

```python
from chaosotel import (
    initialize,
    instrument_action,
    get_metrics_core,
    get_trace_core,
    calculate_and_export_metrics
)
from opentelemetry import trace
from chaosotel.core.trace_core import set_db_span_attributes

# Initialize
initialize(target_type="database", service_version="1.0.0")

# Use decorator for automatic instrumentation
@instrument_action(
    name="slow_transactions",
    target_type="database",
    severity="high"
)
def inject_slow_transactions(host, port, database):
    """Inject slow transactions into database"""
    tracer = trace.get_tracer(__name__)
    
    with tracer.start_as_current_span("slow_transaction.worker.1") as span:
        # Use modular helper for consistent attributes
        set_db_span_attributes(
            span,
            db_system="postgresql",
            db_name=database,
            host=host,
            port=port,
            chaos_activity="postgresql_slow_transactions",
            chaos_action="slow_transactions"
        )
        
        # Your database code here
        # ...
        
        # Record custom metrics
        metrics = get_metrics_core()
        metrics.record_db_slow_query_count(
            db_system="postgresql",
            db_name=database
        )
    
    return {"success": True}

# Calculate and export experiment metrics
result = calculate_and_export_metrics(
    experiment_name="postgres-slow-transactions",
    duration_seconds=300,
    success=True,
    target_type="database",
    severity="high"
)
```

## Extensions

### chaostooling-extension-db
Database and messaging system extensions for:
- **Databases**: PostgreSQL, MySQL, MSSQL, MongoDB, Redis, Cassandra
- **Messaging**: Kafka, RabbitMQ, ActiveMQ

**Installation:**
```bash
pip install chaostooling-extension-db
```

**Usage:**
```json
{
  "probes": [
    {
      "type": "probe",
      "name": "check-postgres",
      "provider": {
        "type": "python",
        "module": "chaosdb.probes.postgres.postgres_connectivity",
        "func": "probe_postgres_connectivity"
      }
    }
  ]
}
```

**Available Probes:**

| System | Probes |
|--------|--------|
| PostgreSQL | `probe_postgres_connectivity`, `probe_query_saturation_status`, `probe_lock_storm_status`, `probe_slow_transactions_status`, `probe_pool_exhaustion_status`, `probe_replication_lag`, `probe_data_consistency`, `collect_postgres_system_metrics`, `probe_transaction_count`, `probe_transaction_integrity`, `probe_api_transaction_flow` |
| MySQL | `probe_mysql_connectivity`, `probe_query_saturation_status`, `probe_lock_storm_status`, `probe_slow_transactions_status`, `probe_pool_exhaustion_status` |
| MSSQL | `probe_mssql_connectivity`, `probe_query_saturation_status`, `probe_lock_storm_status`, `probe_slow_transactions_status`, `probe_pool_exhaustion_status` |
| MongoDB | `probe_mongodb_connectivity`, `probe_query_saturation_status`, `probe_slow_operations_status`, `probe_connection_exhaustion_status`, `probe_document_contention_status` |
| Redis | `probe_redis_connectivity`, `probe_command_saturation_status`, `probe_slow_operations_status`, `probe_connection_exhaustion_status`, `probe_key_contention_status` |
| Cassandra | `probe_cassandra_connectivity`, `probe_query_saturation_status`, `probe_slow_operations_status`, `probe_connection_exhaustion_status`, `probe_row_contention_status` |
| Kafka | `probe_kafka_connectivity`, `probe_topic_saturation_status`, `probe_message_flood_status`, `probe_slow_consumer_status`, `probe_connection_exhaustion_status` |
| RabbitMQ | `probe_rabbitmq_connectivity`, `probe_queue_saturation_status`, `probe_message_flood_status`, `probe_slow_consumer_status`, `probe_connection_exhaustion_status` |
| ActiveMQ | `probe_activemq_connectivity`, `probe_queue_saturation_status`, `probe_message_flood_status`, `probe_slow_consumer_status`, `probe_connection_exhaustion_status` |

### chaostooling-extension-compute
Compute resource extensions for CPU, memory, disk, and process management.

**Installation:**
```bash
pip install chaostooling-extension-compute
```

### chaostooling-extension-network
Network extensions for latency, packet loss, and connectivity testing.

**Installation:**
```bash
pip install chaostooling-extension-network
```

### chaostooling-reporting
Automated reporting extension with:
- Executive summaries
- Compliance reports
- Product owner reports
- Audit trails
- CSV/JSON exports

**Installation:**
```bash
pip install chaostooling-reporting
```

**Usage:**
```json
{
  "controls": [
    {
      "name": "reporting",
      "provider": {
        "type": "python",
        "module": "chaostooling_reporting.control"
      }
    }
  ]
}
```

## Demo Environment (chaostooling-demo)

The demo environment provides a complete observability stack:

### Services
- **Grafana**: Dashboards and visualization
- **Prometheus**: Metrics collection
- **Loki**: Log aggregation
- **Tempo**: Distributed tracing
- **OTEL Collector**: Unified signal collection
- **Application Stack**: HA-Proxy, app servers, databases, messaging systems

### Structure
- `docker-compose.yml` - Main orchestration
- `dashboards/` - Grafana dashboard definitions
- `scripts/` - Setup and utility scripts
- `otel-collector/` - OpenTelemetry collector configuration
- `prometheus.yml` - Prometheus configuration
- `promtail/` - Log collection configuration

### Running Experiments
```bash
cd chaostooling-demo
docker compose up -d
docker compose exec chaos-runner chaos run /experiments/postgres/Extensive-postgres-experiment.json
```

## Background Transaction Load Generator

A dedicated service for generating continuous distributed transaction load across multiple databases and messaging systems. This simulates real-world transaction traffic for chaos engineering experiments.

**Location:** `chaostooling-demo/transaction-load-generator/`

**Features:**
- HTTP API for start/stop/statistics
- Chaos Toolkit actions for integration
- Chaos Toolkit control for automatic start/stop
- OpenTelemetry instrumentation for distributed tracing
- Configurable transactions per second (TPS)

**Documentation:**
- API Guide: `chaostooling-experiments/production-scale/LOAD_GENERATOR_API.md`
- Implementation: `chaostooling-experiments/production-scale/BACKGROUND_LOAD_IMPLEMENTATION.md`

**Usage in Experiments:**
```json
{
  "controls": [
    {
      "name": "load_generator",
      "provider": {
        "type": "python",
        "module": "chaosdb.control.load_generator_control"
      }
    }
  ],
  "configuration": {
    "load_generator_url": "http://transaction-load-generator:5001",
    "load_generator_tps": "2.0",
    "auto_start_load_generator": "true"
  }
}
```

## Experiments (chaostooling-experiments)

Ready-to-use chaos experiments organized by system type:

- `postgres/` - PostgreSQL chaos scenarios
- `mysql/` - MySQL chaos scenarios
- `mongodb/` - MongoDB chaos scenarios
- `redis/` - Redis chaos scenarios
- `kafka/` - Kafka chaos scenarios
- `rabbitmq/` - RabbitMQ chaos scenarios
- `production-scale/` - Production-scale distributed transaction experiments

### Example Experiment
```json
{
  "version": "1.0.0",
  "title": "PostgreSQL Query Saturation Test",
  "steady-state-hypothesis": {
    "probes": [
      {
        "type": "probe",
        "name": "check-postgres",
        "provider": {
          "type": "python",
          "module": "chaosdb.probes.postgres.postgres_connectivity",
          "func": "probe_postgres_connectivity"
        }
      }
    ]
  },
  "method": [
    {
      "type": "action",
      "name": "saturate-queries",
      "provider": {
        "type": "python",
        "module": "chaosdb.actions.postgres.postgres_query_saturation",
        "func": "action_postgres_query_saturation"
      }
    }
  ]
}
```

## Development

### Local Development Setup
```bash
# Install all extensions in development mode
cd chaostooling-otel && pip install -e .
cd ../chaostooling-extension-db && pip install -e .
cd ../chaostooling-reporting && pip install -e .
```

### Running Tests
```bash
# In each extension directory
pytest
```

## License

Apache 2.0

## Author

Morgan Wigge (morgan@wigge.nu)

