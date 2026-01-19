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
