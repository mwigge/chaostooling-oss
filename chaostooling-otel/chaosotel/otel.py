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


def auto_instrument_databases_and_messaging(
    databases: Optional[list[str]] = None,
    messaging: Optional[list[str]] = None,
) -> None:
    """
    Auto-instrument database and messaging libraries with proper callbacks.

    Automatically detects installed libraries and applies instrumentation with
    callbacks to set peer.service for proper service graph visibility.

    Args:
        databases: List of database systems to instrument (e.g., ["postgresql", "mysql", "redis", "mongodb"])
                  If None, auto-detects installed libraries
        messaging: List of messaging systems to instrument (e.g., ["kafka", "rabbitmq"])
                  If None, auto-detects installed libraries

    Example:
        from chaosotel import auto_instrument_databases_and_messaging

        # Auto-detect and instrument all installed DB/messaging libraries
        auto_instrument_databases_and_messaging()

        # Or specify which ones to instrument
        auto_instrument_databases_and_messaging(
            databases=["postgresql", "mysql"],
            messaging=["kafka"]
        )
    """
    from chaosotel.traces import (
        create_db_span_callback,
        create_mongodb_span_callback,
        create_rabbitmq_span_callback,
        create_redis_span_callback,
    )

    # Default to all supported systems if not specified
    if databases is None:
        databases = ["postgresql", "mysql", "redis", "mongodb"]
    if messaging is None:
        messaging = ["kafka", "rabbitmq"]

    # Instrument PostgreSQL
    if "postgresql" in databases:
        try:
            import psycopg2
            from opentelemetry.instrumentation.psycopg2 import Psycopg2Instrumentor
            _ = psycopg2  # Verify client is available for instrumentation

            Psycopg2Instrumentor().instrument(
                skip_dep_check=True,  # Handle psycopg2-binary
                request_hook=create_db_span_callback(
                    "POSTGRES_HOST", "postgres-primary-site-a"
                ),
            )
            logger.info("✓ PostgreSQL instrumentation enabled")
        except ImportError:
            logger.debug("psycopg2 not installed, skipping PostgreSQL instrumentation")
        except Exception as e:
            logger.warning(f"Failed to instrument PostgreSQL: {e}")

    # Instrument MySQL
    if "mysql" in databases:
        try:
            import pymysql
            from opentelemetry.instrumentation.pymysql import PyMySQLInstrumentor
            _ = pymysql  # Verify client is available for instrumentation

            PyMySQLInstrumentor().instrument(
                request_hook=create_db_span_callback("MYSQL_HOST", "mysql")
            )
            logger.info("✓ MySQL instrumentation enabled")
        except ImportError:
            logger.debug("pymysql not installed, skipping MySQL instrumentation")
        except Exception as e:
            logger.warning(f"Failed to instrument MySQL: {e}")

    # Instrument Redis
    if "redis" in databases:
        try:
            import redis
            from opentelemetry.instrumentation.redis import RedisInstrumentor
            _ = redis  # Verify client is available for instrumentation

            RedisInstrumentor().instrument(
                request_hook=create_redis_span_callback("REDIS_HOST", "redis")
            )
            logger.info("✓ Redis instrumentation enabled")
        except ImportError:
            logger.debug("redis not installed, skipping Redis instrumentation")
        except Exception as e:
            logger.warning(f"Failed to instrument Redis: {e}")

    # Instrument MongoDB
    if "mongodb" in databases:
        try:
            from opentelemetry.instrumentation.pymongo import PymongoInstrumentor
            from pymongo import MongoClient
            _ = MongoClient  # Verify client is available for instrumentation

            PymongoInstrumentor().instrument(
                request_hook=create_mongodb_span_callback("MONGODB_HOST", "mongodb")
            )
            logger.info("✓ MongoDB instrumentation enabled")
        except ImportError:
            logger.debug("pymongo not installed, skipping MongoDB instrumentation")
        except Exception as e:
            logger.warning(f"Failed to instrument MongoDB: {e}")

    # Instrument RabbitMQ
    if "rabbitmq" in messaging:
        try:
            import pika
            from opentelemetry.instrumentation.pika import PikaInstrumentor
            _ = pika  # Verify client is available for instrumentation

            PikaInstrumentor().instrument(
                request_hook=create_rabbitmq_span_callback("RABBITMQ_HOST", "rabbitmq")
            )
            logger.info("✓ RabbitMQ instrumentation enabled")
        except ImportError:
            logger.debug("pika not installed, skipping RabbitMQ instrumentation")
        except Exception as e:
            logger.warning(f"Failed to instrument RabbitMQ: {e}")

    # Instrument ActiveMQ (STOMP protocol via stomp.py)
    if "activemq" in messaging:
        try:
            import stomp
            _ = stomp  # Verify client is available for user code

            # Note: There's no official OpenTelemetry instrumentor for stomp.py
            # ActiveMQ instrumentation is handled via trace_activemq_send/trace_activemq_receive
            # helpers in chaosotel.core.trace_core for manual instrumentation
            logger.info(
                "✓ ActiveMQ (STOMP) support available - use trace_activemq_send/trace_activemq_receive helpers"
            )
        except ImportError:
            logger.debug("stomp not installed, skipping ActiveMQ instrumentation")
        except Exception as e:
            logger.warning(f"Failed to check ActiveMQ support: {e}")

    # Note: Kafka instrumentation is handled via trace_kafka_produce/trace_kafka_consume
    # in chaosotel.core.trace_core, so we don't need to instrument kafka-python here


def initialize(
    target_type: str = "unknown",
    service_name: str = "chaostoolkit",
    service_version: str = "1.0.0",
    regulations: Optional[list[str]] = None,
    auto_instrument: bool = True,
    auto_instrument_databases: bool = False,
    auto_instrument_messaging: bool = False,
) -> None:
    """
    Initialize ChaoSOTEL observability layer.

    Sets up OpenTelemetry SDK with:
    - OTLP/gRPC exporter (to OTEL Collector)
    - Metric, Log, and Trace providers
    - Core signal classes (MetricsCore, LogCore, TraceCore, ComplianceCore)

    Args:
        target_type: Type of target (database, network, compute, etc.)
        service_name: Service name for resource attributes (default: "chaostoolkit")
        service_version: Service version for tracing
        regulations: List of regulations to track (SOX, GDPR, PCI-DSS, HIPAA)
        auto_instrument: Whether to auto-instrument popular frameworks (requests, urllib3)
        auto_instrument_databases: Whether to auto-instrument database libraries (PostgreSQL, MySQL, Redis, MongoDB)
        auto_instrument_messaging: Whether to auto-instrument messaging libraries (Kafka, RabbitMQ)

    Example:
        from chaosotel import initialize, get_metric_tags, get_metrics_core

        initialize(
            target_type="database",
            service_name="payment-service",
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
        logger.info(
            f"Initializing ChaoSOTEL observability layer for service: {service_name}..."
        )

        # ====================================================================
        # 1. Import and setup signal exporters
        # ====================================================================
        from chaosotel import logs as logs_setup
        from chaosotel import metrics as metrics_setup
        from chaosotel import traces as traces_setup

        # Setup metrics (OTLP HTTP exporter → OTEL Collector → Prometheus)
        _meter_provider = metrics_setup.setup_metrics(
            service_name=service_name, service_version=service_version
        )
        otel_metrics.set_meter_provider(_meter_provider)
        logger.info("✓ Metrics provider initialized (→ OTEL Collector → Prometheus)")

        # Setup logs (Loki exporter via OTEL)
        _logger_provider = logs_setup.setup_logs(
            service_name=service_name, service_version=service_version
        )
        logger.info("✓ Logger provider initialized (→ Loki)")

        # Setup traces (Tempo exporter via OTEL)
        _tracer_provider = traces_setup.setup_traces(
            service_name=service_name, service_version=service_version
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

        # Auto-instrument databases and messaging systems
        if auto_instrument_databases or auto_instrument_messaging:
            try:
                auto_instrument_databases_and_messaging(
                    databases=["postgresql", "mysql", "redis", "mongodb"]
                    if auto_instrument_databases
                    else None,
                    messaging=["kafka", "rabbitmq"]
                    if auto_instrument_messaging
                    else None,
                )
            except Exception as e:
                logger.warning(
                    f"Could not setup database/messaging auto-instrumentation: {e}"
                )

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


def get_metric_tags(**kwargs: Any) -> dict[str, str]:
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
