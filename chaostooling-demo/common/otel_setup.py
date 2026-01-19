"""
Common OpenTelemetry setup for all services

Includes:
- OTEL provider setup
- Span processors for service graph visibility
- Kafka tracing helpers (re-exported from chaosotel.core.trace_core)
"""

import os

from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider, SpanProcessor
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.resources import Resource
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter

# Kafka tracing helpers are available from chaosotel.core.trace_core
# Services can import directly:
#   from chaosotel.core.trace_core import trace_kafka_produce, trace_kafka_consume


class ServiceNameSpanProcessor(SpanProcessor):
    """Span processor to set service names for database and messaging spans

    Prioritizes hostname/network peer address over database/messaging system name
    to ensure proper service graph visibility (e.g., "postgres-primary-site-a" vs "test").
    """

    def on_start(self, span, parent_context):
        """Set peer.service during span creation when span is still writable"""
        if not hasattr(span, "attributes") or not span.attributes:
            return

        # Check if peer.service is already set (don't override)
        if span.attributes.get("peer.service"):
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
            # Use hostname/network peer if available (industry standard), otherwise use system name
            # NEVER use db.name as service identifier - it's just the database name (e.g., "test", "testdb")
            if network_peer:
                # Extract hostname from network peer (remove port if present)
                peer_host = (
                    str(network_peer).split(":")[0]
                    if ":" in str(network_peer)
                    else str(network_peer)
                )
                service_name = peer_host
            elif hostname:
                service_name = str(hostname)
            else:
                # Fallback to system name only if no hostname available
                db_system_str = str(db_system).lower()
                service_name = db_system_str

        # Check for messaging system
        if not service_name:
            messaging_system = span.attributes.get("messaging.system")
            if messaging_system:
                # Use hostname/network peer if available (industry standard)
                if network_peer:
                    peer_host = (
                        str(network_peer).split(":")[0]
                        if ":" in str(network_peer)
                        else str(network_peer)
                    )
                    service_name = peer_host
                elif hostname:
                    service_name = str(hostname)
                else:
                    # Fallback to system name only if no hostname available
                    messaging_system_str = str(messaging_system).lower()
                    service_name = messaging_system_str

        # Set peer.service attribute (standard OTEL way for service graph visibility)
        # This is what Tempo uses to identify services in the service graph
        if service_name:
            try:
                span.set_attribute("peer.service", service_name)
                # Also set service.name as span attribute for backward compatibility
                span.set_attribute("service.name", service_name)
            except Exception:
                # Silently ignore errors
                pass

    def on_end(self, span):
        """Fallback: Try to set peer.service in on_end if not set in on_start"""
        if not hasattr(span, "attributes") or not span.attributes:
            return

        # If peer.service is already set, we're done
        if span.attributes.get("peer.service"):
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
            # Use hostname/network peer if available (industry standard), otherwise use system name
            # NEVER use db.name as service identifier - it's just the database name (e.g., "test", "testdb")
            if network_peer:
                # Extract hostname from network peer (remove port if present)
                peer_host = (
                    str(network_peer).split(":")[0]
                    if ":" in str(network_peer)
                    else str(network_peer)
                )
                service_name = peer_host
            elif hostname:
                service_name = str(hostname)
            else:
                # Fallback to system name only if no hostname available
                db_system_str = str(db_system).lower()
                service_name = db_system_str

        # Check for messaging system
        if not service_name:
            messaging_system = span.attributes.get("messaging.system")
            if messaging_system:
                # Use hostname/network peer if available (industry standard)
                if network_peer:
                    peer_host = (
                        str(network_peer).split(":")[0]
                        if ":" in str(network_peer)
                        else str(network_peer)
                    )
                    service_name = peer_host
                elif hostname:
                    service_name = str(hostname)
                else:
                    # Fallback to system name only if no hostname available
                    messaging_system_str = str(messaging_system).lower()
                    service_name = messaging_system_str

        # Set peer.service attribute (standard OTEL way for service graph visibility)
        # This is what Tempo uses to identify services in the service graph
        if service_name:
            try:
                if hasattr(span, "set_attribute"):
                    span.set_attribute("peer.service", service_name)
                    # Also set service.name as span attribute for backward compatibility
                    span.set_attribute("service.name", service_name)
            except Exception:
                # Span might be read-only in on_end, that's okay
                pass

    def shutdown(self):
        pass

    def force_flush(self, timeout_millis=30000):
        pass


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


def setup_otel(service_name: str):
    """Setup OpenTelemetry with proper service name and span processor"""
    resource = Resource.create(
        {
            "service.name": service_name,
            "service.version": "1.0.0",
        }
    )
    tracer_provider = TracerProvider(resource=resource)
    otlp_exporter = OTLPSpanExporter(
        endpoint=os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://otel-collector:4317"),
        insecure=True,
    )
    # Add span processors (order matters - HTTP processor before batch processor)
    tracer_provider.add_span_processor(ServiceNameSpanProcessor())
    tracer_provider.add_span_processor(
        HTTPSpanProcessor()
    )  # Extract hostname from HTTP URLs
    tracer_provider.add_span_processor(BatchSpanProcessor(otlp_exporter))
    trace.set_tracer_provider(tracer_provider)
    return tracer_provider


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
        from otel_setup import create_db_span_callback

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


# ============================================================================
# KAFKA TRACING HELPERS
# ============================================================================
# Re-exported from chaosotel.core.trace_core for convenience
# All Kafka tracing logic lives in trace_core.py (modular, reusable, production-ready)
#
# Services can import from here:
#   from otel_setup import trace_kafka_produce
#
# Or directly from trace_core:
#   from chaosotel.core.trace_core import trace_kafka_produce
#
# Both use the same production-ready implementation from chaosotel
# ============================================================================
