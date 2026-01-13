# Changelog

This package has been renamed and modernized as `chaosotel`.

- Observability now uses `chaosotel` metrics/logs/traces cores.
- Legacy references and modules have been removed; use the Chaos Toolkit control `chaosotel.control` for lifecycle instrumentation.
- See repository history for prior releases.

## [Unreleased]

### Added

#### Modular Span Attribute Helpers (`chaosotel/core/trace_core.py`)
- **`set_db_span_attributes()`** - Modular helper for database operations (PostgreSQL, MySQL, MSSQL, Cassandra, Redis, MongoDB, etc.)
  - Automatically sets `db.system`, `db.name`, `db.user`, `db.operation`
  - Sets `network.peer.address` and `network.peer.port` for service graph visibility
  - Sets chaos-specific attributes (`chaos.system`, `chaos.activity`, `chaos.action`, etc.)
  - Works with any database system via `DB_SYSTEM_MAP`
  - Designed for use with `tracer.start_as_current_span()` context managers

- **`set_messaging_span_attributes()`** - Modular helper for messaging operations (Kafka, RabbitMQ, ActiveMQ, NATS, Pulsar, SQS, etc.)
  - Automatically sets `messaging.system`, `messaging.destination`, `messaging.destination_kind`
  - Handles Kafka `bootstrap_servers` parsing automatically (extracts host/port)
  - Sets `network.peer.address` and `network.peer.port` for service graph visibility
  - Auto-detects topic vs queue based on system type
  - Works with any messaging system via `MESSAGING_SYSTEM_MAP`

- **`set_api_span_attributes()`** - Modular helper for API/HTTP operations
  - Sets `http.method`, `http.url`, `http.status_code`
  - Sets `network.peer.address` and `network.peer.port` for service graph visibility
  - Sets chaos-specific attributes

**Benefits:**
- **DRY (Don't Repeat Yourself)**: Shared logic in one place
- **Consistent**: All spans use the same attribute structure
- **Extensible**: Easy to add new databases/messaging systems via mappings
- **Service Graph Visibility**: Ensures `network.peer.address` is set for proper service identification
- **Works with Context Managers**: Designed for `tracer.start_as_current_span()`

**Example Usage:**
```python
from opentelemetry import trace
from chaosotel.core.trace_core import set_db_span_attributes

tracer = trace.get_tracer(__name__)
with tracer.start_as_current_span("slow_transaction.worker.1") as span:
    set_db_span_attributes(
        span,
        db_system="postgresql",
        db_name="testdb",
        host="postgres-primary-site-a",
        port=5432,
        chaos_activity="postgresql_slow_transactions",
        chaos_action="slow_transactions"
    )
    # ... your database code ...
```

### Changed

#### Service Graph Visibility Improvements
- **ServiceNameSpanProcessor** now prioritizes `network.peer.address` over `db.name` for service identification
- This ensures services appear in Grafana service graphs with their hostnames (e.g., `postgres-primary-site-a`) instead of generic names (e.g., `test`)
- All database and messaging action files updated to use modular span helpers
- Service graph now correctly shows all systems: PostgreSQL, MySQL, MSSQL, Cassandra, Kafka, ActiveMQ, RabbitMQ, etc.

#### Metric Naming
- All operation metrics now use `chaos_` prefix for dashboard compatibility:
  - `chaos_operation_success_total`
  - `chaos_operation_error_total`
  - `chaos_probe_success_total`
  - `chaos_probe_error_total`
  - `chaos_db_error_count_total`
  - `chaos_db_slow_query_count_total`
  - `chaos_db_lock_count_total`
  - `chaos_db_deadlock_count_total`
  - `chaos_messaging_error_count_total`
  - And more...

### Fixed

- Fixed service graph missing services (Kafka, ActiveMQ, MSSQL, MySQL, Cassandra) by ensuring `network.peer.address` is set on all spans
- Fixed PostgreSQL showing as "test" in service graph by prioritizing hostname over database name
- Fixed metric naming inconsistencies for dashboard compatibility

## [1.0.0] - Initial Release

### Added

#### Tracing (`chaosotel/traces.py`, `chaosotel/core/trace_core.py`)
- OTLP/gRPC trace exporter integration for Tempo/Jaeger
- Automatic trace context propagation across experiment lifecycle
- Span creation and management for experiment activities
- TraceCore class providing unified tracing interface
- ServiceNameSpanProcessor for automatic service graph visibility

#### Logs (`chaosotel/logs.py`, `chaosotel/core/log_core.py`)
- Structured logging export to Loki via OTLP/HTTP
- LogCore class with action/probe lifecycle logging
- Audit trail support for compliance tracking
- Trace context correlation in log entries
- OpenTelemetry LoggingHandler standard for proper log export

#### Metrics (`chaosotel/metrics.py`, `chaosotel/core/metrics_core.py`)
- OTLP/HTTP metrics exporter for Prometheus integration
- MetricsCore class with 60+ built-in metric types
- Database, operation, transaction, and compliance metrics
- Periodic metric export with configurable intervals

#### Decorators (`chaosotel/decorators.py`)
- Automatic instrumentation decorators for zero-boilerplate observability
- `@instrument_action` - Action execution tracking with metrics/logs/traces
- `@instrument_probe` - Probe execution tracking
- `@instrument_rollback` - Recovery/rollback tracking
- `@record_metric` - Custom metric recording
- `@track_compliance` - Compliance violation detection
- `@track_impact` - Impact scope measurement
- `instrumented_section` - Context manager for code block instrumentation

#### Control (`chaosotel/control.py`)
- Chaos Toolkit lifecycle hooks integration
- Experiment root span management
- Activity span creation as children of experiment spans
- Infrastructure resource snapshot tracking (CPU/memory) per activity
- Automatic experiment phase metrics (active/inactive tracking)
- Comprehensive experiment metrics (success, failure, duration)

#### Compliance (`chaosotel/compliance.py`, `chaosotel/core/compliance_core.py`)
- Multi-regulation compliance tracking (SOX, GDPR, PCI-DSS, HIPAA)
- ComplianceCore class with violation detection and scoring
- Audit trail generation for compliance reporting
- Risk level calculation based on compliance scores and violations
- Action execution tracking with duration and status monitoring

#### Calculator (`chaosotel/calculator.py`)
- Risk level calculation based on experiment parameters
- Complexity score calculation for experiment assessment
- Automatic metric export for risk and complexity
- Integration with experiment lifecycle for automatic scoring

### Changed

- Enhanced type safety across all modules with proper type annotations
- Improved error handling with explicit runtime checks (replaced assert statements)
- Standardized import organization and code formatting
- Unified OpenTelemetry initialization and configuration

### Technical

- Type checking enabled with mypy
- Code formatting with black and isort
- Security scanning with bandit
- All modules follow consistent coding standards

