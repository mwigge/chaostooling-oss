"""
ChaoSOTEL Root Initialization & Coordination

Initializes OpenTelemetry SDK and core signal processing classes.
Provides global accessors for metrics, logs, and traces.

Architecture:
    initialize()
        ↓
    Setup OTEL SDK (providers + exporters)
        ↓
    Create Core Classes (MetricsCore, LogCore, TraceCore, ComplianceCore)
        ↓
    Store in global state
        ↓
    decorators.py uses these globals
"""

import logging
from typing import Any, Optional

from opentelemetry import metrics as otel_metrics
from opentelemetry import trace as otel_trace
from opentelemetry.sdk._logs import LoggerProvider
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.trace import TracerProvider

from .core import ComplianceCore, LogCore, MetricsCore, TraceCore

logger = logging.getLogger("chaosotel.otel")

# Global state
_initialized = False
_meter_provider: Optional[MeterProvider] = None
_tracer_provider: Optional[TracerProvider] = None
_logger_provider: Optional[LoggerProvider] = None

_metrics_core: Optional[MetricsCore] = None
_log_core: Optional[LogCore] = None
_trace_core: Optional[TraceCore] = None
_compliance_core: Optional[ComplianceCore] = None


def initialize(
    target_type: str = "unknown",
    service_version: str = "1.0.0",
    regulations: Optional[list] = None,
    auto_instrument: bool = True,
) -> None:
    """
    Initialize ChaoSOTEL observability layer.

    Sets up OpenTelemetry SDK with:
    - OTLP/gRPC exporter (to OTEL Collector)
    - Metric, Log, and Trace providers
    - Core signal classes (MetricsCore, LogCore, TraceCore, ComplianceCore)

    Args:
        target_type: Type of target (database, network, compute, etc.)
        service_version: Service version for tracing
        regulations: List of regulations to track (SOX, GDPR, PCI-DSS, HIPAA)
        auto_instrument: Whether to auto-instrument popular frameworks

    Example:
        from chaosotel import initialize, get_metric_tags, get_metrics_core

        initialize(
            target_type="database",
            regulations=["SOX", "PCI-DSS"]
        )
    """
    global _initialized
    global _meter_provider, _tracer_provider, _logger_provider
    global _metrics_core, _log_core, _trace_core, _compliance_core

    if _initialized:
        logger.warning("ChaoSOTEL already initialized, skipping")
        return

    try:
        logger.info("Initializing ChaoSOTEL observability layer...")

        # ====================================================================
        # 1. Import and setup signal exporters
        # ====================================================================
        from chaosotel import logs as logs_setup
        from chaosotel import metrics as metrics_setup
        from chaosotel import traces as traces_setup

        # Setup metrics (OTLP HTTP exporter → OTEL Collector → Prometheus)
        _meter_provider = metrics_setup.setup_metrics(
            service_name="chaostoolkit", service_version=service_version
        )
        otel_metrics.set_meter_provider(_meter_provider)
        logger.info("✓ Metrics provider initialized (→ OTEL Collector → Prometheus)")

        # Setup logs (Loki exporter via OTEL)
        _logger_provider = logs_setup.setup_logs(
            service_name="chaostoolkit", service_version=service_version
        )
        logger.info("✓ Logger provider initialized (→ Loki)")

        # Setup traces (Tempo exporter via OTEL)
        _tracer_provider = traces_setup.setup_traces(
            service_name="chaostoolkit", service_version=service_version
        )
        otel_trace.set_tracer_provider(_tracer_provider)
        logger.info("✓ Tracer provider initialized (→ Tempo)")

        # ====================================================================
        # 2. Create core signal classes
        # ====================================================================
        _metrics_core = MetricsCore(_meter_provider)
        logger.info("✓ MetricsCore created")

        _log_core = LogCore(_logger_provider)
        logger.info("✓ LogCore created")

        _trace_core = TraceCore(_tracer_provider)
        logger.info("✓ TraceCore created")

        _compliance_core = ComplianceCore(
            regulations=regulations or ["SOX", "GDPR", "PCI-DSS", "HIPAA"]
        )
        logger.info("✓ ComplianceCore created")

        # ====================================================================
        # 3. Setup auto-instrumentation (optional)
        # ====================================================================
        if auto_instrument:
            try:
                from opentelemetry.instrumentation.requests import RequestsInstrumentor
                from opentelemetry.instrumentation.urllib3 import URLLib3Instrumentor

                RequestsInstrumentor().instrument()
                URLLib3Instrumentor().instrument()

                logger.info("✓ Auto-instrumentation enabled (requests, urllib3)")
            except Exception as e:
                logger.warning(f"Could not setup auto-instrumentation: {e}")

        # ====================================================================
        # 4. Log initialization metrics
        # ====================================================================
        _metrics_core.record_custom_metric(
            "chaosotel.initialization",
            value=1.0,
            metric_type="counter",
            tags={
                "target_type": target_type,
                "regulations": ",".join(regulations or []),
            },
        )

        _log_core.log_event(
            "chaosotel_initialized",
            event_data={
                "target_type": target_type,
                "service_version": service_version,
                "regulations": regulations or [],
            },
        )

        _initialized = True
        logger.info("✓ ChaoSOTEL initialization complete")

    except Exception as e:
        logger.error(f"Error initializing ChaoSOTEL: {e}", exc_info=True)
        raise


def ensure_initialized() -> None:
    """
    Ensure ChaoSOTEL is initialized.

    Raises:
        RuntimeError: If not initialized
    """
    if not _initialized:
        raise RuntimeError("ChaoSOTEL not initialized. Call initialize() first.")


# ============================================================================
# GLOBAL ACCESSORS - Used by decorators and utilities
# ============================================================================


def get_meter_provider() -> MeterProvider:
    """Get global MeterProvider."""
    ensure_initialized()
    if _meter_provider is None:
        raise RuntimeError("MeterProvider not initialized")
    return _meter_provider


def get_tracer_provider() -> TracerProvider:
    """Get global TracerProvider."""
    ensure_initialized()
    if _tracer_provider is None:
        raise RuntimeError("TracerProvider not initialized")
    return _tracer_provider


def get_logger_provider() -> LoggerProvider:
    """Get global LoggerProvider."""
    ensure_initialized()
    if _logger_provider is None:
        raise RuntimeError("LoggerProvider not initialized")
    return _logger_provider


def get_meter(name: str = "chaosotel") -> Any:
    """Get meter from global provider."""
    ensure_initialized()
    if _meter_provider is None:
        raise RuntimeError("MeterProvider not initialized")
    return _meter_provider.get_meter(name)


def get_tracer(name: str = "chaosotel") -> Any:
    """Get tracer from global provider."""
    ensure_initialized()
    if _tracer_provider is None:
        raise RuntimeError("TracerProvider not initialized")
    return _tracer_provider.get_tracer(name)


def get_logger(name: str = "chaosotel") -> Any:
    """Get logger from global provider."""
    ensure_initialized()
    if _logger_provider is None:
        raise RuntimeError("LoggerProvider not initialized")
    return _logger_provider.get_logger(name)


def get_metric_tags(**kwargs: Any) -> dict:
    """
    Build metric tags dictionary from keyword arguments.

    This is a helper function for building metric attribute dictionaries.
    All values are converted to strings for OpenTelemetry compatibility.

    Args:
        **kwargs: Tag key-value pairs

    Returns:
        Dictionary of tag strings

    Example:
        tags = get_metric_tags(db_name="testdb", db_system="postgresql")
    """
    return {str(k): str(v) for k, v in kwargs.items() if v is not None}


# ============================================================================
# CORE CLASS ACCESSORS - Used by decorators
# ============================================================================


def get_metrics_core() -> MetricsCore:
    """Get global MetricsCore instance."""
    ensure_initialized()
    if _metrics_core is None:
        raise RuntimeError("MetricsCore not initialized")
    return _metrics_core


def get_log_core() -> LogCore:
    """Get global LogCore instance."""
    ensure_initialized()
    if _log_core is None:
        raise RuntimeError("LogCore not initialized")
    return _log_core


def get_trace_core() -> TraceCore:
    """Get global TraceCore instance."""
    ensure_initialized()
    if _trace_core is None:
        raise RuntimeError("TraceCore not initialized")
    return _trace_core


def get_compliance_core() -> ComplianceCore:
    """Get global ComplianceCore instance."""
    ensure_initialized()
    if _compliance_core is None:
        raise RuntimeError("ComplianceCore not initialized")
    return _compliance_core


# ============================================================================
# STATUS & SHUTDOWN
# ============================================================================


def get_initialization_status() -> dict:
    """
    Get initialization status.

    Returns:
        Dictionary with initialization details
    """
    return {
        "initialized": _initialized,
        "meter_provider": _meter_provider is not None,
        "tracer_provider": _tracer_provider is not None,
        "logger_provider": _logger_provider is not None,
        "metrics_core": _metrics_core is not None,
        "log_core": _log_core is not None,
        "trace_core": _trace_core is not None,
        "compliance_core": _compliance_core is not None,
    }


def print_status() -> None:
    """Print initialization status."""
    status = get_initialization_status()
    logger.info("=" * 60)
    logger.info("ChaoSOTEL Status")
    logger.info("=" * 60)
    for key, value in status.items():
        symbol = "✓" if value else "✗"
        logger.info(f"{symbol} {key}: {value}")
    logger.info("=" * 60)


def force_flush_telemetry(timeout_ms: int = 30000) -> bool:
    """
    Force flush all telemetry data.

    Args:
        timeout_ms: Flush timeout in milliseconds

    Returns:
        True if successful
    """
    try:
        ensure_initialized()

        logger.info("Flushing telemetry...")

        success = True

        if _meter_provider and hasattr(_meter_provider, "force_flush"):
            success &= _meter_provider.force_flush(timeout_ms)

        if _tracer_provider and hasattr(_tracer_provider, "force_flush"):
            success &= _tracer_provider.force_flush(timeout_ms)

        if _logger_provider and hasattr(_logger_provider, "force_flush"):
            success &= _logger_provider.force_flush(timeout_ms)

        logger.info(f"Telemetry flush complete (success={success})")
        return success

    except Exception as e:
        logger.error(f"Error flushing telemetry: {e}")
        return False


def flush() -> None:
    """Alias for force_flush_telemetry."""
    force_flush_telemetry()


def shutdown() -> None:
    """
    Shutdown ChaoSOTEL and release resources.

    Flushes all pending signals and closes connections.
    """
    global _initialized

    try:
        if not _initialized:
            logger.warning("ChaoSOTEL not initialized, nothing to shutdown")
            return

        logger.info("Shutting down ChaoSOTEL...")

        # Flush all pending data
        force_flush_telemetry()

        # Shutdown core classes
        if _metrics_core:
            _metrics_core.shutdown()

        if _log_core:
            _log_core.shutdown()

        if _trace_core:
            _trace_core.shutdown()

        # Shutdown providers
        if _meter_provider and hasattr(_meter_provider, "shutdown"):
            _meter_provider.shutdown()

        if _tracer_provider and hasattr(_tracer_provider, "shutdown"):
            _tracer_provider.shutdown()

        if _logger_provider and hasattr(_logger_provider, "shutdown"):
            _logger_provider.shutdown()

        _initialized = False
        logger.info("✓ ChaoSOTEL shutdown complete")

    except Exception as e:
        logger.error(f"Error during shutdown: {e}", exc_info=True)
