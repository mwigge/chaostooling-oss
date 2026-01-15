"""
TraceCore - Distributed tracing interface for Tempo/Jaeger.

Records:
- Span creation and lifecycle
- Span attributes
- Events within spans
- Exception tracking
- Span status

Also provides span instrumentation helpers for database and messaging systems.
"""

import inspect
import json
import logging
import os
from typing import Any, Dict, Optional

from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.trace import Status, StatusCode

logger = logging.getLogger("chaosotel.trace_core")

# ============================================================================
# SPAN INSTRUMENTATION HELPERS
# ============================================================================

# System name mappings - easily extensible for new databases/messaging systems
DB_SYSTEM_MAP = {
    "postgresql": "postgresql",
    "postgres": "postgresql",  # alias
    "mysql": "mysql",
    "mariadb": "mysql",  # alias
    "mssql": "mssql",
    "sqlserver": "mssql",  # alias
    "mongodb": "mongodb",
    "mongo": "mongodb",  # alias
    "redis": "redis",
    "cassandra": "cassandra",
    "duckdb": "duckdb",  # Future-proof: already supported!
    "sqlite": "sqlite",
    "oracle": "oracle",
    # Add new databases here - no code changes needed elsewhere
}

MESSAGING_SYSTEM_MAP = {
    "kafka": "kafka",
    "rabbitmq": "rabbitmq",
    "activemq": "activemq",
    "nats": "nats",  # Future-proof
    "pulsar": "pulsar",  # Future-proof
    "sqs": "sqs",  # Future-proof
    # Add new messaging systems here
}

# Environment variable override for custom mappings
CUSTOM_DB_MAP = os.getenv("CHAOS_DB_SYSTEM_MAP", "")
CUSTOM_MESSAGING_MAP = os.getenv("CHAOS_MESSAGING_SYSTEM_MAP", "")


def _load_custom_mappings():
    """Load custom mappings from environment variables (JSON format)."""
    global DB_SYSTEM_MAP, MESSAGING_SYSTEM_MAP

    if CUSTOM_DB_MAP:
        try:
            custom_db = json.loads(CUSTOM_DB_MAP)
            DB_SYSTEM_MAP.update(custom_db)
            logger.info(f"Loaded custom DB system mappings: {list(custom_db.keys())}")
        except json.JSONDecodeError:
            logger.warning(f"Invalid CHAOS_DB_SYSTEM_MAP format: {CUSTOM_DB_MAP}")

    if CUSTOM_MESSAGING_MAP:
        try:
            custom_messaging = json.loads(CUSTOM_MESSAGING_MAP)
            MESSAGING_SYSTEM_MAP.update(custom_messaging)
            logger.info(
                f"Loaded custom messaging system mappings: {list(custom_messaging.keys())}"
            )
        except json.JSONDecodeError:
            logger.warning(
                f"Invalid CHAOS_MESSAGING_SYSTEM_MAP format: {CUSTOM_MESSAGING_MAP}"
            )


# Load custom mappings at module import
_load_custom_mappings()


def get_system_name_from_module(module_name: str) -> Optional[str]:
    """
    Extract system name from module path.

    Examples:
        "chaosdb.actions.postgres.postgres_slow_transactions" -> "postgresql"
        "chaosdb.actions.kafka.kafka_message_flood" -> "kafka"
        "chaosdb.actions.duckdb.duckdb_query" -> "duckdb"

    Args:
        module_name: Full module path (e.g., "chaosdb.actions.postgres.query")

    Returns:
        System name (e.g., "postgresql", "kafka") or None if not found
    """
    parts = module_name.split(".")
    if len(parts) >= 3:
        system_part = parts[2]  # e.g., "postgres", "kafka", "duckdb"
        system_normalized = system_part.lower()

        if system_normalized in DB_SYSTEM_MAP:
            return DB_SYSTEM_MAP[system_normalized]
        if system_normalized in MESSAGING_SYSTEM_MAP:
            return MESSAGING_SYSTEM_MAP[system_normalized]
        if system_normalized in DB_SYSTEM_MAP.values():
            return system_normalized
        if system_normalized in MESSAGING_SYSTEM_MAP.values():
            return system_normalized

    return None


def get_system_type(system_name: str) -> str:
    """
    Determine if system is database or messaging.

    Args:
        system_name: System name (e.g., "postgresql", "kafka")

    Returns:
        "database", "messaging", or "unknown"
    """
    if not system_name:
        return "unknown"

    system_lower = system_name.lower()
    if system_lower in DB_SYSTEM_MAP or system_lower in DB_SYSTEM_MAP.values():
        return "database"
    if (
        system_lower in MESSAGING_SYSTEM_MAP
        or system_lower in MESSAGING_SYSTEM_MAP.values()
    ):
        return "messaging"
    return "unknown"


# Removed _update_resource_service_name as it was unreliable due to resource immutability.
# We now use the standard peer.service span attribute instead.


def create_instrumented_span(
    span_name: str,
    system_name: Optional[str] = None,
    system_type: Optional[str] = None,
    **attributes,
) -> trace.Span:
    """
    Create a span with automatic system instrumentation.

    Automatically sets db.system/messaging.system attributes and resource.service.name.

    Args:
        span_name: Name of the span
        system_name: Explicit system name (e.g., "postgresql", "kafka")
                    If None, will be inferred from calling module
        system_type: "database" or "messaging" (auto-detected if None)
        **attributes: Additional span attributes

    Returns:
        OpenTelemetry span with proper instrumentation
    """
    tracer = trace.get_tracer(__name__)

    # Auto-detect system name from calling module if not provided
    if system_name is None:
        try:
            frame = inspect.currentframe()
            if frame and frame.f_back:
                caller_frame = frame.f_back
                module_name = caller_frame.f_globals.get("__name__", "")
                system_name = get_system_name_from_module(module_name)
        except Exception as e:
            logger.debug(f"Could not auto-detect system name: {e}")

    # Auto-detect system type if not provided
    if system_type is None and system_name:
        system_type = get_system_type(system_name)

    # Create span
    span = tracer.start_span(span_name)

    # Set system-specific attributes
    if system_type == "database" and system_name:
        normalized_system = DB_SYSTEM_MAP.get(system_name.lower(), system_name)
        span.set_attribute("db.system", normalized_system)
    elif system_type == "messaging" and system_name:
        normalized_system = MESSAGING_SYSTEM_MAP.get(system_name.lower(), system_name)
        span.set_attribute("messaging.system", normalized_system)

    # Set standard chaos attributes
    if system_name:
        span.set_attribute("chaos.system", system_name)
    if system_type:
        span.set_attribute("chaos.system_type", system_type)

    # Set additional attributes
    for key, value in attributes.items():
        if value is not None:
            try:
                span.set_attribute(key, value)
            except Exception as e:
                logger.debug(f"Could not set attribute {key}: {e}")

    # Update resource service name for service graph visibility
    # This logic is now handled by peer.service in set_db_span_attributes and set_messaging_span_attributes
    # if system_name:
    #     if system_type == "database":
    #         service_name = DB_SYSTEM_MAP.get(system_name.lower(), system_name)
    #     elif system_type == "messaging":
    #         service_name = MESSAGING_SYSTEM_MAP.get(system_name.lower(), system_name)
    #     else:
    #         service_name = system_name

    #     _update_resource_service_name(span, service_name)

    return span


def set_db_span_attributes(
    span: trace.Span,
    db_system: Optional[str] = None,
    db_name: Optional[str] = None,
    db_user: Optional[str] = None,
    db_operation: Optional[str] = None,
    host: Optional[str] = None,
    port: Optional[int] = None,
    chaos_activity: Optional[str] = None,
    chaos_action: Optional[str] = None,
    chaos_operation: Optional[str] = None,
    **additional_attributes,
) -> None:
    """
    Set standard database span attributes on an existing span.

    This is a modular helper that works with any database system and can be used
    with context managers like `tracer.start_as_current_span()`. Uses environment
    variables for defaults when parameters are not provided.

    Args:
        span: OpenTelemetry span (from tracer.start_as_current_span())
        db_system: Database system name (e.g., "postgresql", "mysql", "mssql", "cassandra", "redis")
                   Defaults to DB_SYSTEM env var or "postgresql"
        db_name: Database name (optional, defaults to DB_NAME env var)
        db_user: Database user (optional, defaults to DB_USER env var)
        db_operation: Database operation (e.g., "connect", "query", "slow_transaction")
        host: Database host address (defaults to DB_HOST or POSTGRES_HOST/MYSQL_HOST/etc env var)
        port: Database port (defaults to DB_PORT or POSTGRES_PORT/MYSQL_PORT/etc env var)
        chaos_activity: Chaos activity name (e.g., "postgresql_slow_transactions")
        chaos_action: Chaos action type (e.g., "slow_transactions", "lock_storm")
        chaos_operation: Chaos operation name (e.g., "slow_transactions")
        **additional_attributes: Additional span attributes (e.g., chaos.thread_id, chaos.num_threads)

    Example:
        from opentelemetry import trace
        from chaosotel.core.trace_core import set_db_span_attributes

        tracer = trace.get_tracer(__name__)
        with tracer.start_as_current_span("slow_transaction.worker.1") as span:
            # Helper automatically uses environment variables for defaults if not provided
            # You can pass None or omit parameters to use env vars:
            # - db_system: DB_SYSTEM env var (defaults to "postgresql")
            # - db_name: POSTGRES_DB/MYSQL_DB/etc env var
            # - host: POSTGRES_HOST/MYSQL_HOST/etc env var
            # - port: POSTGRES_PORT/MYSQL_PORT/etc env var
            set_db_span_attributes(
                span,
                db_system=None,  # Will use DB_SYSTEM env var or "postgresql"
                db_name=None,    # Will use POSTGRES_DB/MYSQL_DB/etc env var
                host=None,       # Will use POSTGRES_HOST/MYSQL_HOST/etc env var
                port=None,       # Will use POSTGRES_PORT/MYSQL_PORT/etc env var
                chaos_activity="postgresql_slow_transactions",
                chaos_action="slow_transactions",
                chaos_operation="slow_transactions",
                chaos_thread_id=1
            )
            # Or pass explicit values (takes precedence over env vars):
            set_db_span_attributes(
                span,
                db_system="postgresql",
                db_name="testdb",
                host="postgres-primary-site-a",
                port=5432,
                chaos_activity="postgresql_slow_transactions",
                chaos_action="slow_transactions"
            )
            # ... your database code here ...
    """
    # Get defaults from environment variables if not provided
    if not db_system:
        db_system = os.getenv("DB_SYSTEM", "postgresql")

    if not db_name:
        # Try system-specific env vars first, then generic
        db_name = (
            os.getenv("POSTGRES_DB")
            or os.getenv("MYSQL_DB")
            or os.getenv("MSSQL_DB")
            or os.getenv("CASSANDRA_KEYSPACE")
            or os.getenv("REDIS_DB")
            or os.getenv("MONGODB_DB")
            or os.getenv("DB_NAME")
        )

    if not db_user:
        db_user = (
            os.getenv("POSTGRES_USER")
            or os.getenv("MYSQL_USER")
            or os.getenv("MSSQL_USER")
            or os.getenv("DB_USER")
        )

    if not host:
        # Try system-specific env vars first, then generic
        host = (
            os.getenv("POSTGRES_HOST")
            or os.getenv("POSTGRES_PRIMARY_HOST")
            or os.getenv("MYSQL_HOST")
            or os.getenv("MSSQL_HOST")
            or os.getenv("CASSANDRA_HOST")
            or os.getenv("REDIS_HOST")
            or os.getenv("MONGODB_HOST")
            or os.getenv("DB_HOST", "localhost")
        )

    if not port:
        # Try system-specific env vars first, then generic
        port_str = (
            os.getenv("POSTGRES_PORT")
            or os.getenv("MYSQL_PORT")
            or os.getenv("MSSQL_PORT")
            or os.getenv("CASSANDRA_PORT")
            or os.getenv("REDIS_PORT")
            or os.getenv("MONGODB_PORT")
            or os.getenv("DB_PORT", "5432")
        )
        try:
            port = int(port_str)
        except (ValueError, TypeError):
            port = None

    # Normalize db_system
    normalized_db_system = DB_SYSTEM_MAP.get(db_system.lower(), db_system.lower())

    # Set standard database attributes
    span.set_attribute("db.system", normalized_db_system)
    if db_name:
        span.set_attribute("db.name", db_name)
    if db_user:
        span.set_attribute("db.user", db_user)
    if db_operation:
        span.set_attribute("db.operation", db_operation)

    # Set network attributes (critical for service graph visibility)
    if host:
        span.set_attribute("network.peer.address", host)
        # Set peer.service for service graph visibility (standard OTEL way)
        span.set_attribute("peer.service", host)
        # Also set service.name as span attribute for backward compatibility
        span.set_attribute("service.name", host)
    if port:
        span.set_attribute("network.peer.port", port)

    # Set chaos-specific attributes
    span.set_attribute("chaos.system", normalized_db_system)
    if chaos_activity:
        span.set_attribute("chaos.activity", chaos_activity)
    if chaos_action:
        span.set_attribute("chaos.action", chaos_action)
    if chaos_operation:
        span.set_attribute("chaos.operation", chaos_operation)
    span.set_attribute("chaos.activity.type", "action")

    # Set additional attributes
    for key, value in additional_attributes.items():
        if value is not None:
            try:
                span.set_attribute(key, value)
            except Exception as e:
                logger.debug(f"Could not set attribute {key}: {e}")


def set_messaging_span_attributes(
    span: trace.Span,
    messaging_system: Optional[str] = None,
    destination: Optional[str] = None,
    destination_kind: Optional[str] = None,
    host: Optional[str] = None,
    port: Optional[int] = None,
    bootstrap_servers: Optional[str] = None,  # For Kafka-style systems
    chaos_activity: Optional[str] = None,
    chaos_action: Optional[str] = None,
    chaos_operation: Optional[str] = None,
    **additional_attributes,
) -> None:
    """
    Set standard messaging span attributes on an existing span.

    This is a modular helper that works with any messaging system (Kafka, RabbitMQ, ActiveMQ, etc.)
    and can be used with context managers like `tracer.start_as_current_span()`.

    Args:
        span: OpenTelemetry span (from tracer.start_as_current_span())
        messaging_system: Messaging system name (e.g., "kafka", "rabbitmq", "activemq")
        destination: Topic/queue name
        destination_kind: "topic" or "queue" (auto-detected if None)
        host: Messaging host address (for non-Kafka systems)
        port: Messaging port (for non-Kafka systems)
        bootstrap_servers: Bootstrap servers string (for Kafka, format: "host:port" or "host1:port1,host2:port2")
        chaos_activity: Chaos activity name (e.g., "kafka_message_flood")
        chaos_action: Chaos action type (e.g., "message_flood", "topic_saturation")
        chaos_operation: Chaos operation name (e.g., "message_flood")
        **additional_attributes: Additional span attributes (e.g., chaos.producer_id, chaos.num_producers)

    Example:
        from opentelemetry import trace
        from chaosotel.core.trace_core import set_messaging_span_attributes

        tracer = trace.get_tracer(__name__)
        with tracer.start_as_current_span("message_flood.producer.1") as span:
            # Helper automatically uses environment variables for defaults if not provided
            # You can pass None or omit parameters to use env vars:
            # - messaging_system: MESSAGING_SYSTEM env var (defaults to "kafka")
            # - destination: KAFKA_TOPIC/RABBITMQ_QUEUE/etc env var
            # - bootstrap_servers: KAFKA_BOOTSTRAP_SERVERS env var (for Kafka)
            # - host: RABBITMQ_HOST/ACTIVEMQ_HOST/etc env var (for non-Kafka)
            # - port: RABBITMQ_PORT/ACTIVEMQ_PORT/etc env var (for non-Kafka)
            set_messaging_span_attributes(
                span,
                messaging_system=None,      # Will use MESSAGING_SYSTEM env var or "kafka"
                destination=None,           # Will use KAFKA_TOPIC/RABBITMQ_QUEUE/etc env var
                bootstrap_servers=None,     # Will use KAFKA_BOOTSTRAP_SERVERS env var
                chaos_activity="kafka_message_flood",
                chaos_action="message_flood",
                chaos_operation="message_flood",
                chaos_producer_id=1
            )
            # Or pass explicit values (takes precedence over env vars):
            set_messaging_span_attributes(
                span,
                messaging_system="kafka",
                destination="test-topic",
                bootstrap_servers="kafka:9092",
                chaos_activity="kafka_message_flood",
                chaos_action="message_flood"
            )
            # ... your messaging code here ...
    """
    # Get defaults from environment variables if not provided
    if not messaging_system:
        messaging_system = os.getenv("MESSAGING_SYSTEM", "kafka")

    if not destination:
        destination = (
            os.getenv("KAFKA_TOPIC")
            or os.getenv("RABBITMQ_QUEUE")
            or os.getenv("ACTIVEMQ_QUEUE")
            or os.getenv("MESSAGING_DESTINATION")
        )

    if not bootstrap_servers and messaging_system.lower() == "kafka":
        bootstrap_servers = os.getenv("KAFKA_BOOTSTRAP_SERVERS")

    if not host and not bootstrap_servers:
        # Try system-specific env vars
        host = (
            os.getenv("RABBITMQ_HOST")
            or os.getenv("ACTIVEMQ_HOST")
            or os.getenv("MESSAGING_HOST", "localhost")
        )

    if not port and not bootstrap_servers:
        port_str = (
            os.getenv("RABBITMQ_PORT")
            or os.getenv("ACTIVEMQ_PORT")
            or os.getenv("MESSAGING_PORT", "5672")
        )
        try:
            port = int(port_str)
        except (ValueError, TypeError):
            port = None

    # Normalize messaging_system
    normalized_messaging_system = MESSAGING_SYSTEM_MAP.get(
        messaging_system.lower(), messaging_system.lower()
    )

    # Set standard messaging attributes
    span.set_attribute("messaging.system", normalized_messaging_system)
    if destination:
        span.set_attribute("messaging.destination", destination)
    if destination_kind:
        span.set_attribute("messaging.destination_kind", destination_kind)
    elif destination:
        # Auto-detect destination kind based on system
        if normalized_messaging_system == "kafka":
            span.set_attribute("messaging.destination_kind", "topic")
        else:
            span.set_attribute("messaging.destination_kind", "queue")

    # Set network attributes (critical for service graph visibility)
    if bootstrap_servers:
        # Try to extract the first host from bootstrap_servers
        try:
            # bootstrap_servers can be "host1:port1,host2:port2"
            first_server = bootstrap_servers.split(",")[0]
            if ":" in first_server:
                bootstrap_host = first_server.split(":")[0]
                bootstrap_port = int(first_server.split(":")[1])
            else:
                bootstrap_host = first_server
                bootstrap_port = 9092

            span.set_attribute("network.peer.address", bootstrap_host)
            span.set_attribute("network.peer.port", bootstrap_port)
            # Set peer.service for service graph visibility (standard OTEL way)
            span.set_attribute("peer.service", bootstrap_host)
            # Also set service.name as span attribute for backward compatibility
            span.set_attribute("service.name", bootstrap_host)
        except Exception:
            span.set_attribute("messaging.kafka.bootstrap.servers", bootstrap_servers)
    elif host:
        span.set_attribute("network.peer.address", host)
        # Set peer.service for service graph visibility (standard OTEL way)
        span.set_attribute("peer.service", host)
        # Also set service.name as span attribute for backward compatibility
        span.set_attribute("service.name", host)
        if port:
            span.set_attribute("network.peer.port", port)

    # Set chaos-specific attributes
    span.set_attribute("chaos.system", normalized_messaging_system)
    if chaos_activity:
        span.set_attribute("chaos.activity", chaos_activity)
    if chaos_action:
        span.set_attribute("chaos.action", chaos_action)
    if chaos_operation:
        span.set_attribute("chaos.operation", chaos_operation)
    span.set_attribute("chaos.activity.type", "action")

    # Set additional attributes
    for key, value in additional_attributes.items():
        if value is not None:
            try:
                span.set_attribute(key, value)
            except Exception as e:
                logger.debug(f"Could not set attribute {key}: {e}")


def set_api_span_attributes(
    span: trace.Span,
    http_method: Optional[str] = None,
    http_url: Optional[str] = None,
    http_status_code: Optional[int] = None,
    host: Optional[str] = None,
    port: Optional[int] = None,
    chaos_activity: Optional[str] = None,
    chaos_action: Optional[str] = None,
    chaos_operation: Optional[str] = None,
    **additional_attributes,
) -> None:
    """
    Set standard API/HTTP span attributes on an existing span.

    This is a modular helper for HTTP/API operations and can be used
    with context managers like `tracer.start_as_current_span()`.

    Args:
        span: OpenTelemetry span (from tracer.start_as_current_span())
        http_method: HTTP method (e.g., "GET", "POST", "PUT")
        http_url: Full HTTP URL
        http_status_code: HTTP status code
        host: API host address
        port: API port
        chaos_activity: Chaos activity name
        chaos_action: Chaos action type
        chaos_operation: Chaos operation name
        **additional_attributes: Additional span attributes

    Example:
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
                chaos_activity="api_transaction_flow",
                chaos_action="transaction_flow"
            )
            # ... your API code here ...
    """
    # Set standard HTTP attributes
    if http_method:
        span.set_attribute("http.method", http_method)
    if http_url:
        span.set_attribute("http.url", http_url)
    if http_status_code:
        span.set_attribute("http.status_code", http_status_code)

    # Set network attributes (critical for service graph visibility)
    if host:
        span.set_attribute("network.peer.address", host)
    if port:
        span.set_attribute("network.peer.port", port)

    # Set chaos-specific attributes
    if chaos_activity:
        span.set_attribute("chaos.activity", chaos_activity)
    if chaos_action:
        span.set_attribute("chaos.action", chaos_action)
    if chaos_operation:
        span.set_attribute("chaos.operation", chaos_operation)
    if chaos_activity or chaos_action:
        span.set_attribute("chaos.activity.type", "action")

    # Set additional attributes
    for key, value in additional_attributes.items():
        if value is not None:
            try:
                span.set_attribute(key, value)
            except Exception as e:
                logger.debug(f"Could not set attribute {key}: {e}")


def instrument_db_span(
    span_name: str,
    db_system: str,
    db_name: Optional[str] = None,
    db_user: Optional[str] = None,
    db_host: Optional[str] = None,
    db_port: Optional[int] = None,
    **additional_attributes,
) -> trace.Span:
    """
    Create an instrumented span for database operations.

    Convenience function that sets all standard database attributes.

    Args:
        span_name: Name of the span
        db_system: Database system name (e.g., "postgresql", "mysql", "duckdb")
        db_name: Database name
        db_user: Database user
        db_host: Database host
        db_port: Database port
        **additional_attributes: Additional span attributes

    Returns:
        Instrumented span
    """
    attributes = {
        "db.name": db_name,
        "db.user": db_user,
        "net.peer.name": db_host,
        "net.peer.port": db_port,
        **additional_attributes,
    }

    # Remove None values
    attributes = {k: v for k, v in attributes.items() if v is not None}

    return create_instrumented_span(
        span_name, system_name=db_system, system_type="database", **attributes
    )


def instrument_messaging_span(
    span_name: str,
    messaging_system: str,
    destination: Optional[str] = None,
    destination_kind: Optional[str] = None,
    **additional_attributes,
) -> trace.Span:
    """
    Create an instrumented span for messaging operations.

    Convenience function that sets all standard messaging attributes.

    Args:
        span_name: Name of the span
        messaging_system: Messaging system name (e.g., "kafka", "rabbitmq")
        destination: Topic/queue name
        destination_kind: "topic" or "queue"
        **additional_attributes: Additional span attributes

    Returns:
        Instrumented span
    """
    attributes = {
        "messaging.destination": destination,
        "messaging.destination_kind": destination_kind,
        **additional_attributes,
    }

    # Remove None values
    attributes = {k: v for k, v in attributes.items() if v is not None}

    return create_instrumented_span(
        span_name, system_name=messaging_system, system_type="messaging", **attributes
    )


# ============================================================================
# KAFKA-SPECIFIC TRACING HELPERS
# ============================================================================
# High-level convenience functions for Kafka operations with automatic tracing.
# These ensure Kafka appears correctly in service graphs instead of "unknown".
# Uses the existing messaging span instrumentation helpers above.


def get_kafka_producer(bootstrap_servers: Optional[str] = None):
    """
    Create a Kafka producer with standard configuration.

    This is a convenience function that creates a KafkaProducer with
    standard JSON serialization. The producer should be used within
    traced operations (see trace_kafka_produce).

    Args:
        bootstrap_servers: Kafka bootstrap servers (defaults to KAFKA_BOOTSTRAP_SERVERS env var)

    Returns:
        KafkaProducer instance

    Example:
        from chaosotel.core.trace_core import get_kafka_producer, trace_kafka_produce

        # Use with trace_kafka_produce (recommended)
        trace_kafka_produce("my-topic", {"key": "value"})

        # Or create manually if needed
        producer = get_kafka_producer()
        producer.send("my-topic", {"key": "value"})
    """
    try:
        from kafka import KafkaProducer
    except ImportError:
        raise ImportError(
            "kafka-python is required for Kafka operations. "
            "Install with: pip install kafka-python"
        )

    if not bootstrap_servers:
        bootstrap_servers = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")

    return KafkaProducer(
        bootstrap_servers=bootstrap_servers.split(","),
        value_serializer=lambda v: json.dumps(v).encode("utf-8"),
    )


def trace_kafka_produce(
    topic: str,
    value: Dict[str, Any],
    bootstrap_servers: Optional[str] = None,
    additional_attributes: Optional[Dict[str, Any]] = None,
    **kwargs,
) -> bool:
    """
    Produce a message to Kafka with proper OpenTelemetry tracing.

    This ensures Kafka operations show up correctly in the service graph
    instead of appearing as "unknown". Automatically sets all required
    messaging attributes for service graph visibility.

    Args:
        topic: Kafka topic name
        value: Message value (dict that will be JSON serialized)
        bootstrap_servers: Kafka bootstrap servers (defaults to KAFKA_BOOTSTRAP_SERVERS env var)
        additional_attributes: Optional dict of additional span attributes (e.g., {"payment.id": 123})
        **kwargs: Additional span attributes as keyword arguments (alternative to additional_attributes)

    Returns:
        True if successful, False otherwise

    Example:
        from chaosotel.core.trace_core import trace_kafka_produce

        # Simple usage
        success = trace_kafka_produce(
            "payment-events",
            {"payment_id": 123, "amount": 100.0}
        )

        # With additional attributes (dict)
        trace_kafka_produce(
            "order-events",
            {"order_id": 456, "status": "PENDING"},
            additional_attributes={"order.id": 456, "user.id": 789}
        )

        # With additional attributes (kwargs)
        trace_kafka_produce(
            "purchases",
            {"transaction_id": 789},
            payment_id=123,
            order_id=456
        )
    """
    try:
        from kafka import KafkaProducer
    except ImportError:
        logger.error("kafka-python not installed - cannot produce Kafka messages")
        return False

    tracer = trace.get_tracer(__name__)
    span = None

    try:
        # Extract host from bootstrap_servers for network.peer.address
        if not bootstrap_servers:
            bootstrap_servers = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")

        # Get first bootstrap server for network.peer.address
        first_server = bootstrap_servers.split(",")[0].strip()
        if ":" in first_server:
            kafka_host, kafka_port = first_server.rsplit(":", 1)
        else:
            kafka_host = first_server
            kafka_port = "9092"

        # Merge additional attributes with kwargs
        all_attributes = {}
        if additional_attributes:
            all_attributes.update(additional_attributes)
        all_attributes.update(kwargs)

        # Create instrumented span using existing helper
        span = instrument_messaging_span(
            span_name=f"kafka.produce.{topic}",
            messaging_system="kafka",
            destination=topic,
            destination_kind="topic",
            messaging_operation="publish",
            messaging_kafka_topic=topic,
            network_peer_address=kafka_host,
            network_peer_port=int(kafka_port) if kafka_port.isdigit() else None,
            **all_attributes,
        )

        # Produce message
        producer = get_kafka_producer(bootstrap_servers)
        producer.send(topic, value)
        producer.flush()
        producer.close()

        span.set_status(Status(StatusCode.OK))
        logger.debug(f"Published message to Kafka topic '{topic}'")
        return True

    except Exception as e:
        logger.warning(f"Kafka publish failed for topic '{topic}': {e}")
        if span:
            span.set_status(Status(StatusCode.ERROR, str(e)))
            span.record_exception(e)
        return False
    finally:
        if span:
            try:
                span.end()
            except Exception:
                pass


def trace_kafka_consume(
    topic: str,
    consumer_group: Optional[str] = None,
    bootstrap_servers: Optional[str] = None,
    **additional_attributes,
):
    """
    Context manager for consuming Kafka messages with proper OpenTelemetry tracing.

    This ensures Kafka consumer operations show up correctly in the service graph.
    Automatically sets all required messaging attributes for service graph visibility.

    Args:
        topic: Kafka topic name
        consumer_group: Optional consumer group name
        bootstrap_servers: Kafka bootstrap servers (defaults to KAFKA_BOOTSTRAP_SERVERS env var)
        **additional_attributes: Additional span attributes

    Yields:
        Span object for adding custom attributes

    Example:
        from chaosotel.core.trace_core import trace_kafka_consume

        with trace_kafka_consume("purchases", "notification-service-group") as span:
            # Consume messages
            for message in consumer:
                span.set_attribute("message.id", message.value.get("id"))
                process_message(message)
    """
    try:
        from kafka import KafkaConsumer
    except ImportError:
        raise ImportError(
            "kafka-python is required for Kafka operations. "
            "Install with: pip install kafka-python"
        )

    tracer = trace.get_tracer(__name__)

    # Extract host from bootstrap_servers for network.peer.address
    if not bootstrap_servers:
        bootstrap_servers = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")

    first_server = bootstrap_servers.split(",")[0].strip()
    if ":" in first_server:
        kafka_host, kafka_port = first_server.rsplit(":", 1)
    else:
        kafka_host = first_server
        kafka_port = "9092"

    # Create instrumented span using existing helper
    # For consumers, we use destination (the topic we're consuming from)
    span = instrument_messaging_span(
        span_name=f"kafka.consume.{topic}",
        messaging_system="kafka",
        destination=topic,
        destination_kind="topic",
        messaging_operation="receive",
        messaging_kafka_topic=topic,
        network_peer_address=kafka_host,
        network_peer_port=int(kafka_port) if kafka_port.isdigit() else None,
        **additional_attributes,
    )

    # Set consumer-specific attributes
    span.set_attribute("messaging.source", topic)
    span.set_attribute("messaging.source_kind", "topic")
    if consumer_group:
        span.set_attribute("messaging.kafka.consumer.group", consumer_group)

    # Context manager
    class _KafkaConsumeContext:
        def __init__(self, span):
            self.span = span

        def __enter__(self):
            return self.span

        def __exit__(self, exc_type, exc_val, exc_tb):
            if exc_type:
                try:
                    self.span.record_exception(exc_val)
                except Exception:
                    pass
                self.span.set_status(
                    Status(
                        StatusCode.ERROR, str(exc_val) if exc_val else "Unknown error"
                    )
                )
            else:
                self.span.set_status(Status(StatusCode.OK))

            try:
                self.span.end()
            except Exception:
                pass

            return False  # Don't suppress exceptions

    return _KafkaConsumeContext(span)


class InstrumentedSpan:
    """
    Context manager for instrumented spans.

    Automatically handles span lifecycle: status setting and ending.

    Example:
        from chaosotel.core.trace_core import instrument_db_span, InstrumentedSpan

        with InstrumentedSpan(instrument_db_span(
            "query.execute",
            db_system="postgresql",
            db_name="mydb"
        )) as span:
            # Your code here
            # Span automatically gets OK status and ends
    """

    def __init__(self, span: trace.Span):
        """Initialize context manager with a span."""
        self.span = span

    def __enter__(self):
        """Enter context - return the span."""
        return self.span

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Exit context - set status and end span."""
        if exc_type:
            try:
                self.span.record_exception(exc_val)
            except Exception:
                pass
            self.span.set_status(
                StatusCode.ERROR, str(exc_val) if exc_val else "Unknown error"
            )
        else:
            self.span.set_status(StatusCode.OK)

        try:
            self.span.end()
        except Exception:
            pass


# ============================================================================
# TRACE CORE CLASS
# ============================================================================


class TraceCore:
    """
    Core tracing interface for Tempo/Jaeger.

    Provides unified API for:
    - Span creation and management
    - Attribute tracking
    - Event recording
    - Exception tracking
    - Status management
    """

    def __init__(self, tracer_provider: TracerProvider):
        """
        Initialize TraceCore.

        Args:
            tracer_provider: OpenTelemetry TracerProvider
        """
        self.tracer_provider = tracer_provider
        self.tracer = tracer_provider.get_tracer(__name__)

        logger.info("TraceCore initialized")

    # ========================================================================
    # SPAN CREATION & MANAGEMENT
    # ========================================================================

    def create_span(
        self, name: str, attributes: Optional[Dict[str, Any]] = None
    ) -> Any:
        """Create a new span."""
        try:
            span = self.tracer.start_span(name)

            if attributes:
                for key, value in attributes.items():
                    span.set_attribute(key, value)

            logger.debug(f"Created span: {name}")
            return span
        except Exception as e:
            logger.error(f"Error creating span: {e}")
            return None

    def start_span(self, name: str, attributes: Optional[Dict[str, Any]] = None) -> Any:
        """Start a span manually."""
        try:
            span = self.tracer.start_span(name)
            if attributes:
                for key, value in attributes.items():
                    span.set_attribute(key, value)
            return span
        except Exception as e:
            logger.error(f"Error starting span: {e}")
            return None

    # ========================================================================
    # ATTRIBUTE MANAGEMENT
    # ========================================================================

    def set_attribute(self, span: Any, key: str, value: Any) -> None:
        """Set attribute on span."""
        try:
            if span:
                span.set_attribute(key, value)
            logger.debug(f"Set attribute {key}={value}")
        except Exception as e:
            logger.error(f"Error setting attribute: {e}")

    def set_attributes(self, span: Any, attributes: Dict[str, Any]) -> None:
        """Set multiple attributes on span."""
        try:
            if span and attributes:
                for key, value in attributes.items():
                    span.set_attribute(key, value)
            logger.debug(f"Set {len(attributes or {})} attributes")
        except Exception as e:
            logger.error(f"Error setting attributes: {e}")

    # ========================================================================
    # EVENT RECORDING
    # ========================================================================

    def add_event(
        self, span: Any, name: str, attributes: Optional[Dict[str, Any]] = None
    ) -> None:
        """Add event to span."""
        try:
            if span:
                span.add_event(name, attributes=attributes)
            logger.debug(f"Added event: {name}")
        except Exception as e:
            logger.error(f"Error adding event: {e}")

    # ========================================================================
    # EXCEPTION TRACKING
    # ========================================================================

    def record_exception(
        self, span: Any, exception: Exception, escaped: bool = False
    ) -> None:
        """Record exception in span."""
        try:
            if span:
                span.record_exception(exception, escaped=escaped)
            logger.error(f"Recorded exception: {str(exception)}")
        except Exception as e:
            logger.error(f"Error recording exception: {e}")

    # ========================================================================
    # STATUS MANAGEMENT
    # ========================================================================

    def set_status_ok(self, span: Any) -> None:
        """Set span status to OK."""
        try:
            if span:
                span.set_status(Status(StatusCode.OK))
            logger.debug("Set span status to OK")
        except Exception as e:
            logger.error(f"Error setting status OK: {e}")

    def set_status_error(self, span: Any, description: Optional[str] = None) -> None:
        """Set span status to ERROR."""
        try:
            if span:
                span.set_status(Status(StatusCode.ERROR, description=description))
            logger.debug(f"Set span status to ERROR: {description}")
        except Exception as e:
            logger.error(f"Error setting status ERROR: {e}")

    def set_status_unset(self, span: Any) -> None:
        """Set span status to UNSET."""
        try:
            if span:
                span.set_status(Status(StatusCode.UNSET))
            logger.debug("Set span status to UNSET")
        except Exception as e:
            logger.error(f"Error setting status UNSET: {e}")

    # ========================================================================
    # SPAN ACCESSORS
    # ========================================================================

    def get_current_span(self) -> Any:
        """Get current active span."""
        try:
            from opentelemetry import trace

            return trace.get_current_span()
        except Exception as e:
            logger.error(f"Error getting current span: {e}")
            return None

    def get_span_context(self, span: Optional[Any] = None) -> Dict[str, Any]:
        """Get span context (trace_id, span_id)."""
        try:
            target_span = span or self.get_current_span()

            if target_span:
                context = target_span.get_span_context()
                return {
                    "trace_id": format(context.trace_id, "032x"),
                    "span_id": format(context.span_id, "016x"),
                    "is_valid": context.is_valid,
                    "is_recording": context.is_recording,
                }

            return {
                "trace_id": "00000000000000000000000000000000",
                "span_id": "0000000000000000",
                "is_valid": False,
                "is_recording": False,
            }
        except Exception as e:
            logger.error(f"Error getting span context: {e}")
            return {
                "trace_id": "00000000000000000000000000000000",
                "span_id": "0000000000000000",
                "is_valid": False,
                "is_recording": False,
            }

    # ========================================================================
    # CONTEXT MANAGERS
    # ========================================================================

    def span_context(self, name: str, attributes: Optional[Dict[str, Any]] = None):
        """Context manager for span creation."""
        try:
            span = self.create_span(name, attributes)
            return _SpanContextManager(span, self)
        except Exception as e:
            logger.error(f"Error creating span context: {e}")
            return _NullContextManager()

    # ========================================================================
    # SHUTDOWN
    # ========================================================================

    def shutdown(self) -> None:
        """Shutdown trace core."""
        try:
            if hasattr(self.tracer_provider, "shutdown"):
                self.tracer_provider.shutdown()
            logger.info("TraceCore shutdown complete")
        except Exception as e:
            logger.error(f"Error during TraceCore shutdown: {e}")


class _SpanContextManager:
    """Context manager for spans."""

    def __init__(self, span: Any, trace_core: TraceCore):
        self.span = span
        self.trace_core = trace_core

    def __enter__(self):
        return self.span

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type:
            self.trace_core.record_exception(self.span, exc_val)
            self.trace_core.set_status_error(self.span, str(exc_val))
        else:
            self.trace_core.set_status_ok(self.span)

        if self.span:
            self.span.end()


class _NullContextManager:
    """Null context manager for error cases."""

    def __enter__(self):
        return None

    def __exit__(self, exc_type, exc_val, exc_tb):
        pass
