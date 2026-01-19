"""
Traces Setup - Configure OpenTelemetry traces export to Tempo/Jaeger.

Initializes:
- TracerProvider
- OTLP/gRPC trace exporter
- Batch span processor
- Service name span processor (maps db.system/messaging.system to service.name)
- Resource attributes
"""

import logging
import os
from typing import Optional

from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import SpanProcessor, TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

logger = logging.getLogger("chaosotel.traces")


class ServiceNameSpanProcessor(SpanProcessor):
    """
    Automatically maps db.system and messaging.system to resource.service.name.

    This ensures databases and messaging systems appear in Grafana/Tempo service graphs.
    Works with both old approach (direct span.set_attribute) and new approach (helpers).
    """

    def __init__(self):
        """Initialize processor with system mappings."""
        # Try to import mappings from trace_core (where helpers are)
        try:
            from chaosotel.core.trace_core import DB_SYSTEM_MAP, MESSAGING_SYSTEM_MAP

            self.db_system_map = DB_SYSTEM_MAP
            self.messaging_system_map = MESSAGING_SYSTEM_MAP
            logger.debug("Using system mappings from trace_core")
        except ImportError:
            # Fallback if module not available
            self.db_system_map = {
                "postgresql": "postgresql",
                "postgres": "postgresql",
                "mysql": "mysql",
                "mariadb": "mysql",
                "mssql": "mssql",
                "sqlserver": "mssql",
                "mongodb": "mongodb",
                "mongo": "mongodb",
                "redis": "redis",
                "cassandra": "cassandra",
                "duckdb": "duckdb",
                "sqlite": "sqlite",
                "oracle": "oracle",
            }
            self.messaging_system_map = {
                "kafka": "kafka",
                "rabbitmq": "rabbitmq",
                "activemq": "activemq",
                "nats": "nats",
                "pulsar": "pulsar",
                "sqs": "sqs",
            }
            logger.debug("Using fallback system mappings")

    def on_start(self, span, parent_context):
        """Called when span starts - update resource early if we can detect the system."""
        # Try to update resource early based on span name or initial attributes
        # This is more reliable than updating in on_end
        try:
            if hasattr(span, "name"):
                span_name = span.name.lower()
                # Check if this looks like a database or messaging span
                if any(
                    db in span_name
                    for db in [
                        "postgres",
                        "mysql",
                        "mssql",
                        "mongodb",
                        "redis",
                        "cassandra",
                    ]
                ):
                    # Will be handled in on_end when attributes are set
                    pass
                elif any(msg in span_name for msg in ["kafka", "rabbitmq", "activemq"]):
                    # Will be handled in on_end when attributes are set
                    pass
        except Exception:
            pass  # Ignore errors in on_start

    def on_end(self, span):
        """Update resource service name based on span attributes."""
        if not hasattr(span, "attributes") or not span.attributes:
            return

        service_name = None

        # Industry standard: Prefer hostname/network peer address for service identification
        # This provides better service graph visibility (e.g., "postgres-primary-site-a" vs "test")
        network_peer = span.attributes.get(
            "network.peer.address"
        ) or span.attributes.get("net.peer.name")
        hostname = span.attributes.get("host.name")

        # Check for database system
        db_system = span.attributes.get("db.system")
        if db_system:
            db_system_str = str(db_system).lower()
            base_service_name = self.db_system_map.get(db_system_str, db_system_str)

            # Use hostname/network peer if available (industry standard), otherwise use system name
            if network_peer:
                # Extract hostname from network peer (remove port if present)
                peer_host = (
                    str(network_peer).split(":")[0]
                    if ":" in str(network_peer)
                    else str(network_peer)
                )
                service_name = peer_host
                logger.debug(
                    f"Mapped db.system={db_system} with network.peer.address={network_peer} to service.name={service_name}"
                )
            elif hostname:
                service_name = str(hostname)
                logger.debug(
                    f"Mapped db.system={db_system} with host.name={hostname} to service.name={service_name}"
                )
            else:
                service_name = base_service_name
                logger.debug(
                    f"Mapped db.system={db_system} to service.name={service_name} (no hostname available)"
                )

        # Check for messaging system
        if not service_name:
            messaging_system = span.attributes.get("messaging.system")
            if messaging_system:
                messaging_system_str = str(messaging_system).lower()
                base_service_name = self.messaging_system_map.get(
                    messaging_system_str, messaging_system_str
                )

                # Use hostname/network peer if available (industry standard)
                if network_peer:
                    peer_host = (
                        str(network_peer).split(":")[0]
                        if ":" in str(network_peer)
                        else str(network_peer)
                    )
                    service_name = peer_host
                    logger.debug(
                        f"Mapped messaging.system={messaging_system} with network.peer.address={network_peer} to service.name={service_name}"
                    )
                elif hostname:
                    service_name = str(hostname)
                    logger.debug(
                        f"Mapped messaging.system={messaging_system} with host.name={hostname} to service.name={service_name}"
                    )
                else:
                    service_name = base_service_name
                    logger.debug(
                        f"Mapped messaging.system={messaging_system} to service.name={service_name} (no hostname available)"
                    )

        # Update service name - CRITICAL for Tempo service graph visibility
        # We now use peer.service attribute which is the standard way to identify remote services.
        if service_name:
            try:
                # Set peer.service attribute (standard OTEL way)
                # Note: In on_end(), the span is a ReadableSpan, but we can still try to set attributes
                # if the SDK allows it, or better yet, this processor should have been on_start.
                # However, for backward compatibility with the existing design, we'll try to set it.
                if hasattr(span, "set_attribute"):
                    span.set_attribute("peer.service", service_name)
                    # Also set service.name for backward compatibility
                    span.set_attribute("service.name", service_name)
                    logger.debug(f"Set peer.service to {service_name} in on_end")
                else:
                    # If it's a ReadableSpan, we might not be able to set attributes.
                    # The best practice is to set these during span creation (which we now do in trace_core.py).
                    logger.debug(
                        "Could not set peer.service on read-only span in on_end"
                    )
            except Exception as e:
                logger.debug(f"Error setting peer.service in on_end: {e}")

    def shutdown(self):
        """Shutdown processor - no cleanup needed."""
        pass

    def force_flush(self, timeout_millis: int = 30000):
        """Force flush - no action needed."""
        pass


def setup_traces(
    service_name: str = "chaostoolkit",
    service_version: str = "1.0.0",
    service_namespace: Optional[str] = None,
    otel_endpoint: Optional[str] = None,
    enable_http_processor: bool = True,
) -> TracerProvider:
    """
    Setup OpenTelemetry traces export to Tempo/Jaeger via OTEL Collector.

    Args:
        service_name: Service name for resource
        service_version: Service version
        service_namespace: Service namespace (optional)
        otel_endpoint: OTEL Collector endpoint

    Returns:
        Configured TracerProvider
    """
    try:
        # Get OTEL endpoint from environment or use default
        # For gRPC, prefer OTEL_EXPORTER_OTLP_ENDPOINT (should be gRPC port 4317)
        # Fallback to OTEL_EXPORTER_OTLP_TRACES_ENDPOINT if set
        endpoint: str = (
            otel_endpoint
            or os.getenv(
                "OTEL_EXPORTER_OTLP_ENDPOINT",
                os.getenv(
                    "OTEL_EXPORTER_OTLP_TRACES_ENDPOINT",
                    "http://localhost:4317",
                )
                or "http://localhost:4317",
            )
            or "http://localhost:4317"
        )

        # For gRPC exporter, strip http:// or https:// scheme if present
        # gRPC endpoints should be just host:port
        if endpoint.startswith("http://"):
            endpoint = endpoint.replace("http://", "", 1)
        elif endpoint.startswith("https://"):
            endpoint = endpoint.replace("https://", "", 1)

        # Remove any path components (gRPC doesn't use paths)
        if "/" in endpoint:
            endpoint = endpoint.split("/")[0]

        logger.info(f"Setting up traces export to {endpoint} (gRPC)")

        # Create resource attributes
        resource_attrs = {
            "service.name": service_name,
            "service.version": service_version,
        }

        if service_namespace:
            resource_attrs["service.namespace"] = service_namespace

        # Add environment info
        # Use service_name as host.name fallback instead of "unknown" to avoid "unknown" in service graphs
        hostname = os.getenv("HOSTNAME") or service_name
        resource_attrs.update(
            {
                "deployment.environment": os.getenv("ENVIRONMENT", "development"),
                "host.name": hostname,
            }
        )

        resource = Resource.create(resource_attrs)

        # Create OTLP trace exporter (gRPC)
        # gRPC exporter uses insecure=True for non-TLS connections
        trace_exporter = OTLPSpanExporter(
            insecure=True,
            endpoint=endpoint,
        )

        # Create tracer provider
        tracer_provider = TracerProvider(resource=resource)

        # CRITICAL: Add service name processor BEFORE batch processor
        # This ensures resource.service.name is updated before spans are exported
        # The processor order matters - it must run before the batch processor
        service_name_processor = ServiceNameSpanProcessor()
        tracer_provider.add_span_processor(service_name_processor)
        logger.info(
            "✓ Service name span processor registered (→ service graph visibility)"
        )

        # Add HTTP span processor for extracting hostname from HTTP URLs
        if enable_http_processor:
            http_processor = HTTPSpanProcessor()
            tracer_provider.add_span_processor(http_processor)
            logger.info(
                "✓ HTTP span processor registered (→ HTTP service graph visibility)"
            )

        # Add batch processor for exporting traces (after service name processor)
        tracer_provider.add_span_processor(BatchSpanProcessor(trace_exporter))

        logger.info("✓ Traces provider configured (→ Tempo/Jaeger)")

        return tracer_provider

    except Exception as e:
        logger.error(f"Error setting up traces: {e}", exc_info=True)
        raise


class HTTPSpanProcessor(SpanProcessor):
    """Span processor to extract hostname from HTTP URLs and set peer.service for service graph visibility"""

    def on_start(self, span, parent_context):
        """Set peer.service from http.url during span creation"""
        if not hasattr(span, "attributes") or not span.attributes:
            return

        # Check if this is an HTTP span (has http.url but no peer.service)
        http_url = span.attributes.get("http.url") or span.attributes.get("url.full")
        if http_url and not span.attributes.get("peer.service"):
            try:
                from urllib.parse import urlparse

                parsed = urlparse(str(http_url))
                hostname = parsed.hostname
                port = parsed.port

                if hostname:
                    # Set peer.service for service graph visibility (standard OTEL way)
                    span.set_attribute("peer.service", hostname)
                    span.set_attribute("server.address", hostname)
                    span.set_attribute("network.peer.address", hostname)
                    if port:
                        span.set_attribute("server.port", port)
                        span.set_attribute("network.peer.port", port)
            except Exception:
                # Silently ignore parsing errors
                pass

    def on_end(self, span):
        """Also try to set in on_end in case http.url was set after on_start"""
        if not hasattr(span, "attributes") or not span.attributes:
            return

        # Check if this is an HTTP span (has http.url but no peer.service)
        http_url = span.attributes.get("http.url") or span.attributes.get("url.full")
        if http_url and not span.attributes.get("peer.service"):
            try:
                from urllib.parse import urlparse

                parsed = urlparse(str(http_url))
                hostname = parsed.hostname
                port = parsed.port

                if hostname:
                    # Try to set attributes (may fail if span is read-only)
                    try:
                        span.set_attribute("peer.service", hostname)
                        span.set_attribute("server.address", hostname)
                        span.set_attribute("network.peer.address", hostname)
                        if port:
                            span.set_attribute("server.port", port)
                            span.set_attribute("network.peer.port", port)
                    except (AttributeError, TypeError):
                        # Span might be read-only in on_end, that's okay
                        pass
            except Exception:
                # Silently ignore parsing errors
                pass

    def shutdown(self):
        pass

    def force_flush(self, timeout_millis=30000):
        pass


# ============================================================================
# INSTRUMENTATION CALLBACK HELPERS
# ============================================================================
# Callbacks to set peer.service on auto-instrumented spans for proper service graph visibility
# These are used with instrumentation libraries' request_hook/response_hook parameters
# ============================================================================


def create_db_span_callback(host_env_var: str = None, default_host: str = None):
    """
    Create a callback function to set peer.service on database spans.

    This ensures database services appear correctly in the Tempo service graph.

    Args:
        host_env_var: Environment variable name for the database host (e.g., "POSTGRES_HOST", "MYSQL_HOST")
        default_host: Default host value if env var is not set

    Returns:
        Callback function that can be used with Psycopg2Instrumentor, PyMySQLInstrumentor, etc.

    Example:
        from opentelemetry.instrumentation.psycopg2 import Psycopg2Instrumentor
        from chaosotel.traces import create_db_span_callback

        Psycopg2Instrumentor().instrument(
            skip_dep_check=True,
            request_hook=create_db_span_callback("POSTGRES_HOST", "postgres-primary-site-a")
        )
    """

    def db_span_callback(span, *args, **kwargs):
        """Callback to set peer.service on database spans

        Handles different callback signatures:
        - Psycopg2Instrumentor: (span, conn)
        - PyMySQLInstrumentor: (span, conn)
        - Other DB instrumentors may vary
        """
        try:
            # Try to extract host from connection (first arg after span)
            host = None
            conn = None

            # Get connection from args or kwargs
            if args and len(args) > 0:
                conn = args[0]
            elif "conn" in kwargs:
                conn = kwargs["conn"]
            elif "connection" in kwargs:
                conn = kwargs["connection"]

            # Try to extract host from connection object
            if conn:
                if hasattr(conn, "info") and hasattr(conn.info, "host"):
                    host = conn.info.host
                elif hasattr(conn, "host"):
                    host = conn.host
                elif hasattr(conn, "get_host"):
                    host = conn.get_host()
                elif hasattr(conn, "dns") and hasattr(conn.dns, "host"):
                    host = conn.dns.host

            # Fallback to environment variable or default
            if not host:
                if host_env_var:
                    host = os.getenv(host_env_var, default_host)
                else:
                    host = default_host

            if host:
                # Extract hostname (remove port if present)
                peer_host = str(host).split(":")[0] if ":" in str(host) else str(host)
                span.set_attribute("peer.service", peer_host)
                span.set_attribute("network.peer.address", peer_host)
        except Exception:
            # Silently ignore errors - span processor will handle fallback
            pass

    return db_span_callback


def create_redis_span_callback(
    host_env_var: str = "REDIS_HOST", default_host: str = "redis"
):
    """
    Create a callback function to set peer.service on Redis spans.

    Args:
        host_env_var: Environment variable name for Redis host
        default_host: Default host value if env var is not set

    Returns:
        Callback function that can be used with RedisInstrumentor
    """

    def redis_span_callback(span, *args, **kwargs):
        """Callback to set peer.service on Redis spans

        Handles different callback signatures:
        - RedisInstrumentor: (span, instance)
        """
        try:
            host = None
            instance = None

            # Get instance from args or kwargs
            if args and len(args) > 0:
                instance = args[0]
            elif "instance" in kwargs:
                instance = kwargs["instance"]
            elif "client" in kwargs:
                instance = kwargs["client"]

            # Try to extract host from Redis instance
            if instance:
                if hasattr(instance, "connection_pool") and hasattr(
                    instance.connection_pool, "connection_kwargs"
                ):
                    host = instance.connection_pool.connection_kwargs.get("host")
                elif hasattr(instance, "host"):
                    host = instance.host
                elif hasattr(instance, "connection_pool") and hasattr(
                    instance.connection_pool, "connection"
                ):
                    # Try to get from connection
                    conn = instance.connection_pool.connection
                    if hasattr(conn, "host"):
                        host = conn.host

            if not host:
                host = os.getenv(host_env_var, default_host)

            if host:
                peer_host = str(host).split(":")[0] if ":" in str(host) else str(host)
                span.set_attribute("peer.service", peer_host)
                span.set_attribute("network.peer.address", peer_host)
        except Exception:
            pass

    return redis_span_callback


def create_mongodb_span_callback(
    host_env_var: str = "MONGODB_HOST", default_host: str = "mongodb"
):
    """
    Create a callback function to set peer.service on MongoDB spans.

    Args:
        host_env_var: Environment variable name for MongoDB host
        default_host: Default host value if env var is not set

    Returns:
        Callback function that can be used with PymongoInstrumentor
    """

    def mongodb_span_callback(span, *args, **kwargs):
        """Callback to set peer.service on MongoDB spans

        Handles different callback signatures:
        - PymongoInstrumentor: (span, method_name, method_args, method_kwargs)
        """
        try:
            host = None
            method_args = None
            method_kwargs = None

            # Extract method_args and method_kwargs from args or kwargs
            if len(args) >= 3:
                method_args = args[1] if len(args) > 1 else None
                method_kwargs = args[2] if len(args) > 2 else None
            elif "method_args" in kwargs:
                method_args = kwargs["method_args"]
            if "method_kwargs" in kwargs:
                method_kwargs = kwargs["method_kwargs"]

            # Try to extract from client
            if method_kwargs and "client" in method_kwargs:
                client = method_kwargs["client"]
                if hasattr(client, "address") and client.address:
                    host = client.address[0]
            elif method_args and len(method_args) > 0:
                # First arg might be the collection/database which has client
                first_arg = method_args[0]
                if hasattr(first_arg, "database") and hasattr(
                    first_arg.database, "client"
                ):
                    client = first_arg.database.client
                    if hasattr(client, "address") and client.address:
                        host = client.address[0]
                elif hasattr(first_arg, "client"):
                    client = first_arg.client
                    if hasattr(client, "address") and client.address:
                        host = client.address[0]

            if not host:
                host = os.getenv(host_env_var, default_host)

            if host:
                peer_host = str(host).split(":")[0] if ":" in str(host) else str(host)
                span.set_attribute("peer.service", peer_host)
                span.set_attribute("network.peer.address", peer_host)
        except Exception:
            pass

    return mongodb_span_callback


def create_rabbitmq_span_callback(
    host_env_var: str = "RABBITMQ_HOST", default_host: str = "rabbitmq"
):
    """
    Create a callback function to set peer.service on RabbitMQ spans.

    Args:
        host_env_var: Environment variable name for RabbitMQ host
        default_host: Default host value if env var is not set

    Returns:
        Callback function that can be used with PikaInstrumentor
    """

    def rabbitmq_span_callback(span, *args, **kwargs):
        """Callback to set peer.service on RabbitMQ spans

        Handles different callback signatures:
        - PikaInstrumentor: (span, method_name, method_args, method_kwargs)
        """
        try:
            host = None
            method_args = None
            method_kwargs = None

            # Extract method_args and method_kwargs from args or kwargs
            if len(args) >= 3:
                method_args = args[1] if len(args) > 1 else None
                method_kwargs = args[2] if len(args) > 2 else None
            elif "method_args" in kwargs:
                method_args = kwargs["method_args"]
            if "method_kwargs" in kwargs:
                method_kwargs = kwargs["method_kwargs"]

            # Try to extract from connection parameters
            if method_kwargs and "connection" in method_kwargs:
                conn = method_kwargs["connection"]
                if hasattr(conn, "params") and hasattr(conn.params, "host"):
                    host = conn.params.host
            elif method_args and len(method_args) > 0:
                conn = method_args[0]
                if hasattr(conn, "params") and hasattr(conn.params, "host"):
                    host = conn.params.host
                elif hasattr(conn, "host"):
                    host = conn.host

            if not host:
                host = os.getenv(host_env_var, default_host)

            if host:
                peer_host = str(host).split(":")[0] if ":" in str(host) else str(host)
                span.set_attribute("peer.service", peer_host)
                span.set_attribute("network.peer.address", peer_host)
        except Exception:
            pass

    return rabbitmq_span_callback


def create_activemq_span_callback(
    host_env_var: str = "ACTIVEMQ_HOST", default_host: str = "activemq"
):
    """
    Create a callback function to set peer.service on ActiveMQ spans.

    Note: ActiveMQ uses STOMP protocol via stomp.py library, which doesn't have
    an official OpenTelemetry instrumentor. This callback is for manual instrumentation
    when using stomp.py with ActiveMQ.

    Args:
        host_env_var: Environment variable name for ActiveMQ host
        default_host: Default host value if env var is not set

    Returns:
        Callback function that can be used with manual instrumentation
    """

    def activemq_span_callback(span, *args, **kwargs):
        """Callback to set peer.service on ActiveMQ spans

        This is a placeholder for manual instrumentation.
        For ActiveMQ, use trace_activemq_send/trace_activemq_receive helpers instead.
        """
        try:
            host = os.getenv(host_env_var, default_host)
            if host:
                peer_host = str(host).split(":")[0] if ":" in str(host) else str(host)
                span.set_attribute("peer.service", peer_host)
                span.set_attribute("network.peer.address", peer_host)
        except Exception:
            pass

    return activemq_span_callback
