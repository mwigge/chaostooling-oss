"""
ChaoSOTEL - Unified OpenTelemetry Observability for Chaos Toolkit

Production-ready observability layer with:
- Structured logging (Loki)
- Prometheus metrics
- Distributed tracing (Tempo/Jaeger)
- Compliance tracking (SOX, GDPR, PCI-DSS, HIPAA)
- Automatic instrumentation decorators
- Risk and complexity calculation
"""

import logging

__version__ = "1.0.0"
__author__ = "Morgan Wigge"
__email__ = "morgan@wigge.nu"
__license__ = "Apache-2.0"

from .calculator import (
    calculate_and_export_metrics,
    calculate_and_export_metrics_from_dict,
    calculate_complexity_score,
    calculate_risk_level,
)
from .core import ComplianceCore, LogCore, MetricsCore, Regulation, TraceCore
from .decorators import (
    InstrumentedSection,
    init_cores,
    instrument_action,
    instrument_probe,
    instrument_rollback,
    record_metric,
    track_compliance,
    track_impact,
)
from .otel import (
    auto_instrument_databases_and_messaging,
    ensure_initialized,
    flush,
    force_flush_telemetry,
    get_compliance_core,
    get_initialization_status,
    get_log_core,
    get_logger,
    get_logger_provider,
    get_meter,
    get_meter_provider,
    get_metric_tags,
    get_metrics_core,
    get_trace_core,
    get_tracer,
    get_tracer_provider,
    initialize,
    print_status,
    shutdown,
)
from .traces import (
    create_activemq_span_callback,
    create_db_span_callback,
    create_mongodb_span_callback,
    create_rabbitmq_span_callback,
    create_redis_span_callback,
)

__all__ = [
    # Version info
    "__version__",
    "__author__",
    "__email__",
    "__license__",
    # Initialization
    "initialize",
    "auto_instrument_databases_and_messaging",
    "ensure_initialized",
    "get_initialization_status",
    "print_status",
    "flush",
    "force_flush_telemetry",
    "shutdown",
    # Instrumentation callbacks
    "create_db_span_callback",
    "create_redis_span_callback",
    "create_mongodb_span_callback",
    "create_rabbitmq_span_callback",
    "create_activemq_span_callback",
    # Providers (for advanced usage)
    "get_meter_provider",
    "get_tracer_provider",
    "get_logger_provider",
    # Signal accessors
    "get_meter",
    "get_tracer",
    "get_logger",
    "get_metric_tags",
    # Core classes
    "MetricsCore",
    "LogCore",
    "TraceCore",
    "ComplianceCore",
    "Regulation",
    # Core accessors
    "get_metrics_core",
    "get_log_core",
    "get_trace_core",
    "get_compliance_core",
    # Decorators
    "instrument_action",
    "instrument_probe",
    "instrument_rollback",
    "record_metric",
    "track_compliance",
    "track_impact",
    "InstrumentedSection",
    "init_cores",
    # Calculator
    "calculate_risk_level",
    "calculate_complexity_score",
    "calculate_and_export_metrics",
    "calculate_and_export_metrics_from_dict",
]

logger = logging.getLogger("chaosotel")
logger.debug(f"ChaoSOTEL v{__version__} loaded")
