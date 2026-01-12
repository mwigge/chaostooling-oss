# Changelog

This package has been renamed and modernized as `chaosotel`.

- Observability now uses `chaosotel` metrics/logs/traces cores.
- Legacy references and modules have been removed; use the Chaos Toolkit control `chaosotel.control` for lifecycle instrumentation.
- See repository history for prior releases.

### Added

#### Tracing (`chaosotel/traces.py`, `chaosotel/core/trace_core.py`)
- OTLP/gRPC trace exporter integration for Tempo/Jaeger
- Automatic trace context propagation across experiment lifecycle
- Span creation and management for experiment activities
- TraceCore class providing unified tracing interface

#### Logs (`chaosotel/logs.py`, `chaosotel/core/log_core.py`)
- Structured logging export to Loki via OTLP/HTTP
- LogCore class with action/probe lifecycle logging
- Audit trail support for compliance tracking
- Trace context correlation in log entries

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
- Multi-regulation compliance tracking (SOX, GDPR, PCI-DSS)
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

