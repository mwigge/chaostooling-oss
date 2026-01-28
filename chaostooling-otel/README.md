# ChaosTooling OTEL

**OpenTelemetry Observability Foundation for Chaos Toolkit**

A production-ready OpenTelemetry instrumentation layer providing distributed tracing, metrics, logging, and compliance tracking for chaos engineering experiments. Serves as the observability foundation for all ChaosTooling extensions.

[![Python Version](https://img.shields.io/badge/python-3.9%2B-blue.svg)](https://www.python.org/downloads/)
[![OpenTelemetry](https://img.shields.io/badge/opentelemetry-1.20%2B-orange.svg)](https://opentelemetry.io/)
[![Chaos Toolkit](https://img.shields.io/badge/chaos--toolkit-compatible-green.svg)](https://chaostoolkit.org/)

---

## Table of Contents

- [Overview](#overview)
- [Architecture](#architecture)
- [Core Components](#core-components)
- [Features](#features)
- [Installation](#installation)
- [Quick Start](#quick-start)
- [Chaos Toolkit Integration](#chaos-toolkit-integration)
- [Instrumentation Patterns](#instrumentation-patterns)
- [Service Graph Generation](#service-graph-generation)
- [Metrics](#metrics)
- [Configuration](#configuration)
- [Examples](#examples)

---

## Overview

ChaosTooling OTEL provides comprehensive OpenTelemetry instrumentation for chaos engineering experiments, enabling full observability across distributed systems. It automatically captures traces, metrics, and logs from chaos actions, making your experiments visible in Grafana, Tempo, Prometheus, and Loki.

### Why ChaosTooling OTEL?

✅ **Unified Observability** - Single library for traces, metrics, logs, and compliance
✅ **Zero-Boilerplate** - 7 decorators for automatic instrumentation
✅ **60+ Built-in Metrics** - Ready-to-use metrics for databases, messaging, experiments
✅ **Service Graph Generation** - Databases and messaging systems automatically appear in Grafana service graphs
✅ **Chaos Toolkit Native** - Deep integration via control hooks and lifecycle management
✅ **Production-Ready** - Error handling, batching, caching, and performance optimizations
✅ **Compliance Tracking** - Built-in SOX, GDPR, PCI-DSS, HIPAA support
✅ **Extensible** - Modular helpers for custom instrumentation

### Key Capabilities

- **Distributed Tracing** via OpenTelemetry (Tempo, Jaeger)
- **Prometheus Metrics** with 60+ built-in metrics
- **Structured Logging** to Loki with trace correlation
- **Service Graphs** automatically showing databases, queues, and services
- **Risk & Complexity Scoring** for experiment assessment
- **Compliance Auditing** with violation tracking
- **Resource Usage Monitoring** (CPU, memory during experiments)

---

## Architecture

### Overall Observability Stack

```
┌─────────────────────────────────────────────────────────────────────┐
│                    Chaos Toolkit Experiment                         │
│         experiment.json with actions/probes/rollbacks               │
└────────────────────────┬────────────────────────────────────────────┘
                         │
                         │ Lifecycle Hooks
                         │
┌────────────────────────▼────────────────────────────────────────────┐
│              chaostooling-otel CONTROL MODULE                       │
│                                                                     │
│  Lifecycle Events:                                                  │
│  • configure_control()         → Initialize OTEL SDK               │
│  • before_experiment_control() → Start root experiment span        │
│  • before_activity_control()   → Start activity span               │
│  • after_activity_control()    → End activity span, record metrics │
│  • after_experiment_control()  → End root span, calculate totals   │
│  • cleanup_control()           → Flush telemetry                   │
└────────────────────────┬────────────────────────────────────────────┘
                         │
                         │ Uses Core Components
                         │
┌────────────────────────▼────────────────────────────────────────────┐
│                    CHAOSTOOLING-OTEL CORE                           │
│                                                                     │
│  ┌────────────────┐  ┌────────────────┐  ┌────────────────┐      │
│  │  MetricsCore   │  │   LogCore      │  │  TraceCore     │      │
│  │                │  │                │  │                │      │
│  │ • 60+ built-in │  │ • Structured   │  │ • DB/msg       │      │
│  │   metrics      │  │   logs         │  │   helpers      │      │
│  │ • Database     │  │ • Audit trail  │  │ • Auto service │      │
│  │ • Messaging    │  │ • Trace context│  │   name mapping │      │
│  │ • Experiments  │  │ • Severity     │  │ • Span attrs   │      │
│  │ • Compliance   │  │   levels       │  │ • System       │      │
│  │ • Custom       │  │                │  │   detection    │      │
│  └────────┬───────┘  └────────┬───────┘  └────────┬───────┘      │
│           │                   │                    │              │
│           └───────────────────┴────────────────────┘              │
│                               │                                   │
│  ┌────────────────────────────▼──────────────────────────────┐   │
│  │             ComplianceCore                                 │   │
│  │  • SOX, GDPR, PCI-DSS, HIPAA tracking                      │   │
│  │  • Violation detection                                     │   │
│  │  • Compliance scoring                                      │   │
│  └────────────────────────────────────────────────────────────┘   │
│                                                                     │
│  ┌────────────────────────────────────────────────────────────┐   │
│  │             INSTRUMENTATION DECORATORS                     │   │
│  │                                                            │   │
│  │  @instrument_action      @track_compliance                │   │
│  │  @instrument_probe       @track_impact                    │   │
│  │  @instrument_rollback    @record_metric                   │   │
│  │                instrumented_section (context manager)     │   │
│  └────────────────────────────────────────────────────────────┘   │
└─────────────────────────────┬───────────────────────────────────────┘
                              │
                              │ OTLP Export
                              │
┌─────────────────────────────▼───────────────────────────────────────┐
│                    OpenTelemetry SDK                                │
│                                                                     │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐            │
│  │ TracerProvider│ │ MeterProvider │ │LoggerProvider │            │
│  │              │  │              │  │              │            │
│  │ • Batch      │  │ • Periodic   │  │ • Batch      │            │
│  │   Span       │  │   Exporter   │  │   Processor  │            │
│  │   Processor  │  │   Reader     │  │              │            │
│  │ • OTLP       │  │ • Prometheus │  │ • OTLP       │            │
│  │   Exporter   │  │ • OTLP       │  │   Exporter   │            │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘            │
│         │                 │                  │                     │
│         │  ┌──────────────▼──────────────────┘                     │
│         │  │  ServiceNameSpanProcessor                             │
│         │  │  (db.system → resource.service.name)                  │
│         │  │  (messaging.system → resource.service.name)           │
│         └──┴──────────────┬────────────────────────────────────────┤
│                           │                                        │
│                    OTLP Protocol (gRPC/HTTP)                       │
└───────────────────────────┼────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────────┐
│                   OpenTelemetry Collector                           │
│                    (Optional - Recommended)                         │
│                                                                     │
│  • Receive OTLP (4317/4318)                                         │
│  • Process/filter/batch telemetry                                   │
│  • Export to multiple backends                                      │
└───────────┬─────────────────────────────────────────────────────────┘
            │
            ├─────────────────┬─────────────────┬───────────────────┐
            ▼                 ▼                 ▼                   ▼
┌───────────────────┐  ┌────────────┐  ┌──────────────┐  ┌──────────────┐
│      Tempo        │  │ Prometheus │  │     Loki     │  │   Grafana    │
│  (Traces)         │  │ (Metrics)  │  │   (Logs)     │  │(Dashboards)  │
└───────────────────┘  └────────────┘  └──────────────┘  └──────────────┘
```

### Core Components Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                        CHAOSTOOLING-OTEL                            │
│                                                                     │
│  ┌────────────────────────────────────────────────────────────┐   │
│  │                    MetricsCore                             │   │
│  │                                                            │   │
│  │  Database Metrics:                                         │   │
│  │  ├─ record_db_query_latency()                             │   │
│  │  ├─ record_db_connection_pool_utilization()               │   │
│  │  ├─ record_db_slow_query_count()                          │   │
│  │  ├─ record_db_deadlock()                                  │   │
│  │  ├─ record_db_lock()                                      │   │
│  │  └─ record_db_error()                                     │   │
│  │                                                            │   │
│  │  Messaging Metrics:                                        │   │
│  │  ├─ record_messaging_operation_latency()                  │   │
│  │  ├─ record_messaging_operation_count()                    │   │
│  │  ├─ record_messaging_connection_failure()                 │   │
│  │  └─ record_messaging_error()                              │   │
│  │                                                            │   │
│  │  Experiment Metrics:                                       │   │
│  │  ├─ record_experiment_start/end()                         │   │
│  │  ├─ record_experiment_risk_level()                        │   │
│  │  ├─ record_experiment_complexity()                        │   │
│  │  └─ record_mttr()                                         │   │
│  │                                                            │   │
│  │  Compliance Metrics:                                       │   │
│  │  ├─ record_compliance_score()                             │   │
│  │  ├─ record_compliance_violation()                         │   │
│  │  └─ record_impact_scope()                                 │   │
│  └────────────────────────────────────────────────────────────┘   │
│                                                                     │
│  ┌────────────────────────────────────────────────────────────┐   │
│  │                       LogCore                              │   │
│  │                                                            │   │
│  │  ├─ log_action_start() / log_action_end()                 │   │
│  │  ├─ log_probe_execution()                                 │   │
│  │  ├─ log_error()                                           │   │
│  │  ├─ log_compliance_check()                                │   │
│  │  ├─ log_custom_event()                                    │   │
│  │  └─ get_audit_trail()                                     │   │
│  └────────────────────────────────────────────────────────────┘   │
│                                                                     │
│  ┌────────────────────────────────────────────────────────────┐   │
│  │                       TraceCore                            │   │
│  │                                                            │   │
│  │  Span Instrumentation:                                     │   │
│  │  ├─ instrument_db_span(name, db_system, ...)              │   │
│  │  ├─ instrument_messaging_span(name, system, ...)          │   │
│  │  ├─ create_instrumented_span(name)                        │   │
│  │  └─ set_db_span_attributes()                              │   │
│  │                                                            │   │
│  │  System Mappings:                                          │   │
│  │  ├─ Database: PostgreSQL, MySQL, MSSQL, MongoDB,          │   │
│  │  │   Redis, Cassandra, DuckDB, SQLite, Oracle             │   │
│  │  └─ Messaging: Kafka, RabbitMQ, ActiveMQ,                 │   │
│  │      NATS, Pulsar, SQS                                     │   │
│  └────────────────────────────────────────────────────────────┘   │
│                                                                     │
│  ┌────────────────────────────────────────────────────────────┐   │
│  │                    ComplianceCore                          │   │
│  │                                                            │   │
│  │  Regulations: SOX | GDPR | PCI-DSS | HIPAA                │   │
│  │                                                            │   │
│  │  ├─ calculate_compliance_score(regulation) → 0-100        │   │
│  │  ├─ add_violation(regulation, severity, description)      │   │
│  │  ├─ get_violations(regulation, severity_filter)           │   │
│  │  ├─ assess_risk(impact, likelihood)                       │   │
│  │  └─ generate_audit_trail()                                │   │
│  └────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Core Components

### 1. MetricsCore

**Purpose**: Unified Prometheus metrics recording interface with 60+ built-in metrics.

**Usage**:
```python
from chaosotel import get_metrics_core, get_metric_tags

metrics = get_metrics_core()
tags = get_metric_tags(db_system="postgresql", db_name="production")

metrics.record_db_query_latency(duration_ms=45.2, tags=tags)
metrics.record_db_connection_pool_utilization(percent=67, tags=tags)
```

### 2. LogCore

**Purpose**: Structured logging interface for Loki with automatic trace correlation.

**Usage**:
```python
from chaosotel import get_log_core

log_core = get_log_core()

log_core.log_action_start(
    action_name="postgres_pool_exhaustion",
    target="postgres-primary",
    severity="medium"
)
```

### 3. TraceCore

**Purpose**: Distributed tracing interface with automatic system detection and service graph support.

**Usage**:
```python
from chaosotel.core.trace_core import instrument_db_span

with instrument_db_span(
    name="query_saturation",
    db_system="postgresql",
    db_name="production",
    db_host="postgres-primary",
    db_port=5432
) as span:
    execute_queries()
```

### 4. ComplianceCore

**Purpose**: Regulatory compliance tracking for SOX, GDPR, PCI-DSS, and HIPAA.

**Usage**:
```python
from chaosotel import get_compliance_core

compliance = get_compliance_core()
compliance.add_violation(
    regulation="SOX",
    severity="high",
    description="Unauthorized database access"
)
score = compliance.calculate_compliance_score("SOX")
```

---

## Features

### Automatic Service Graph Generation

**The Innovation**: `ServiceNameSpanProcessor`

Databases and messaging systems automatically appear in Grafana/Tempo service graphs.

**How it works**:
1. Span attributes `db.system` or `messaging.system` are detected
2. Processor maps to `resource.service.name`
3. Service appears in Grafana service graph

**Supported Systems**:
- **Databases**: PostgreSQL, MySQL, MSSQL, MongoDB, Redis, Cassandra, DuckDB, SQLite, Oracle
- **Messaging**: Kafka, RabbitMQ, ActiveMQ, NATS, Pulsar, SQS

### Zero-Boilerplate Decorators

**7 Decorators** for automatic instrumentation:

```python
from chaosotel.decorators import instrument_action

@instrument_action(
    name="kill_connections",
    target_type="database",
    severity="high"
)
def kill_connections(host, database):
    # Your chaos logic - tracing/metrics/logs automatic
    pass
```

---

## Installation

```bash
pip install chaostooling-otel
```

---

## Quick Start

### 1. Basic Experiment with Observability

Create `experiment.json`:

```json
{
  "version": "1.0.0",
  "title": "Database Test with Observability",
  "controls": [
    {
      "name": "opentelemetry",
      "provider": {
        "type": "python",
        "module": "chaosotel.control"
      }
    }
  ],
  "method": [
    {
      "type": "action",
      "name": "exhaust-pool",
      "provider": {
        "type": "python",
        "module": "chaosdb.actions.postgres.postgres_pool_exhaustion",
        "func": "postgres_pool_exhaustion",
        "arguments": {
          "host": "localhost",
          "num_connections": 100,
          "duration": 60
        }
      }
    }
  ]
}
```

**Configure environment**:
```bash
export OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4318
export OTEL_SERVICE_NAME=chaos-experiment
```

**Run experiment**:
```bash
chaos run experiment.json
```

---

## Chaos Toolkit Integration

ChaosTooling OTEL integrates with Chaos Toolkit via the `control` module:

```json
{
  "controls": [
    {
      "name": "opentelemetry",
      "provider": {
        "type": "python",
        "module": "chaosotel.control"
      }
    }
  ]
}
```

**Lifecycle Hooks**:
1. **`configure_control()`** - Initialize OTEL SDK
2. **`before_experiment_control()`** - Start root experiment span
3. **`before_activity_control()`** - Start activity span
4. **`after_activity_control()`** - End activity span, record metrics
5. **`after_experiment_control()`** - End root span, calculate totals
6. **`cleanup_control()`** - Flush telemetry

---

## Instrumentation Patterns

### Pattern 1: Automatic via Decorators

```python
from chaosotel.decorators import instrument_action

@instrument_action(name="my_chaos", target_type="database", severity="medium")
def my_chaos_action(host: str):
    # Automatic tracing/metrics/logs
    pass
```

### Pattern 2: Manual Span Creation

```python
from chaosotel import get_tracer, ensure_initialized, flush

ensure_initialized()
tracer = get_tracer()

with tracer.start_as_current_span("my_operation") as span:
    span.set_attribute("custom_attr", "value")
    result = do_something()

flush()
```

### Pattern 3: Instrumentation Helpers

```python
from chaosotel.core.trace_core import instrument_db_span

with instrument_db_span(
    name="query_users",
    db_system="postgresql",
    db_name="production",
    db_host="postgres-primary",
    db_port=5432
) as span:
    cursor.execute("SELECT * FROM users")
```

---

## Service Graph Generation

### Multi-Instance Support

**Single Instance**:
```python
span.set_attribute("db.system", "postgresql")
# Service name: "postgresql"
```

**Multi-Instance with Network Peer**:
```python
span.set_attribute("db.system", "postgresql")
span.set_attribute("network.peer.address", "postgres-primary:5432")
# Service name: "postgres-primary"
```

---

## Metrics

### Built-in Metrics (60+)

#### Database Metrics
- `db_query_latency` - Query execution time
- `db_connection_pool_utilization` - Pool usage %
- `db_slow_query_count` - Slow queries
- `db_deadlock_count` - Deadlocks detected
- `db_lock_count` - Active locks

#### Messaging Metrics
- `messaging_operation_latency` - Message operation time
- `messaging_queue_depth` - Queue depth
- `messaging_consumer_lag` - Consumer lag

#### Experiment Metrics
- `experiment_duration_seconds` - Total duration
- `experiment_risk_level` - Risk level (1-4)
- `experiment_complexity_score` - Complexity (0-100)

---

## Configuration

### Environment Variables

```bash
# OTLP exporter
OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4318

# Service identification
OTEL_SERVICE_NAME=chaos-experiment
OTEL_SERVICE_NAMESPACE=chaos-engineering
ENVIRONMENT=production
```

### Programmatic Configuration

```python
from chaosotel import initialize

initialize(
    service_name="chaos-experiment",
    service_version="1.0.0",
    target_type="database",
    regulations=["SOX", "GDPR"]
)
```

---

## Examples

### Service Graph Example

```python
from chaosotel import initialize, get_tracer, flush
from chaosotel.core.trace_core import instrument_db_span, instrument_messaging_span

initialize(service_name="payment-service")
tracer = get_tracer()

with tracer.start_as_current_span("process_payment"):
    # Database call
    with instrument_db_span(
        name="fetch_user",
        db_system="postgresql",
        db_name="users",
        db_host="postgres-primary",
        db_port=5432
    ):
        pass

    # Message queue
    with instrument_messaging_span(
        name="publish_event",
        messaging_system="kafka",
        destination="payments",
        destination_kind="topic"
    ):
        pass

flush()
```

---

## License

[MIT License](../LICENSE)

---

## Related Projects

- **chaostooling-extension-db**: Database and messaging chaos engineering
- **chaostooling-reporting**: Automated experiment reporting
- **chaostooling-generic**: Generic chaos engineering controls
- **chaostooling-demo**: Full demo environment

---

## Acknowledgments

Built with:
- [OpenTelemetry](https://opentelemetry.io/)
- [Chaos Toolkit](https://chaostoolkit.org/)
- [Grafana](https://grafana.com/)
- [Prometheus](https://prometheus.io/)
