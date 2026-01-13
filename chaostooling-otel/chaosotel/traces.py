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

from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import (
    OTLPSpanExporter,
)
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider, SpanProcessor
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
                "postgresql": "postgresql", "postgres": "postgresql",
                "mysql": "mysql", "mariadb": "mysql",
                "mssql": "mssql", "sqlserver": "mssql",
                "mongodb": "mongodb", "mongo": "mongodb",
                "redis": "redis", "cassandra": "cassandra",
                "duckdb": "duckdb", "sqlite": "sqlite", "oracle": "oracle",
            }
            self.messaging_system_map = {
                "kafka": "kafka", "rabbitmq": "rabbitmq", "activemq": "activemq",
                "nats": "nats", "pulsar": "pulsar", "sqs": "sqs",
            }
            logger.debug("Using fallback system mappings")
    
    def on_start(self, span, parent_context):
        """Called when span starts - no action needed."""
        pass
    
    def on_end(self, span):
        """Update resource service name based on span attributes."""
        if not hasattr(span, 'attributes') or not span.attributes:
            return
        
        service_name = None
        
        # Industry standard: Prefer hostname/network peer address for service identification
        # This provides better service graph visibility (e.g., "postgres-primary-site-a" vs "test")
        network_peer = span.attributes.get("network.peer.address") or span.attributes.get("net.peer.name")
        hostname = span.attributes.get("host.name")
        
        # Check for database system
        db_system = span.attributes.get("db.system")
        if db_system:
            db_system_str = str(db_system).lower()
            base_service_name = self.db_system_map.get(db_system_str, db_system_str)
            
            # Use hostname/network peer if available (industry standard), otherwise use system name
            if network_peer:
                # Extract hostname from network peer (remove port if present)
                peer_host = str(network_peer).split(':')[0] if ':' in str(network_peer) else str(network_peer)
                service_name = peer_host
                logger.debug(f"Mapped db.system={db_system} with network.peer.address={network_peer} to service.name={service_name}")
            elif hostname:
                service_name = str(hostname)
                logger.debug(f"Mapped db.system={db_system} with host.name={hostname} to service.name={service_name}")
            else:
                service_name = base_service_name
                logger.debug(f"Mapped db.system={db_system} to service.name={service_name} (no hostname available)")
        
        # Check for messaging system
        if not service_name:
            messaging_system = span.attributes.get("messaging.system")
            if messaging_system:
                messaging_system_str = str(messaging_system).lower()
                base_service_name = self.messaging_system_map.get(messaging_system_str, messaging_system_str)
                
                # Use hostname/network peer if available (industry standard)
                if network_peer:
                    peer_host = str(network_peer).split(':')[0] if ':' in str(network_peer) else str(network_peer)
                    service_name = peer_host
                    logger.debug(f"Mapped messaging.system={messaging_system} with network.peer.address={network_peer} to service.name={service_name}")
                elif hostname:
                    service_name = str(hostname)
                    logger.debug(f"Mapped messaging.system={messaging_system} with host.name={hostname} to service.name={service_name}")
                else:
                    service_name = base_service_name
                    logger.debug(f"Mapped messaging.system={messaging_system} to service.name={service_name} (no hostname available)")
        
        # Update service name - set as span attribute (Grafana/Tempo service graphs use this)
        if service_name:
            try:
                # Set service.name as span attribute (required for service graph visibility)
                span.set_attribute("service.name", service_name)
                logger.debug(f"Set span attribute service.name={service_name}")
                
                # Also try to update resource if possible
                if hasattr(span, 'resource') and span.resource:
                    current_attrs = dict(span.resource.attributes)
                    current_service_name = current_attrs.get("service.name", "")
                    if current_service_name != service_name:
                        current_attrs["service.name"] = service_name
                        new_resource = Resource.create(current_attrs)
                        
                        if hasattr(span, '_resource'):
                            span._resource = new_resource
                        elif hasattr(span, 'resource'):
                            span.resource = new_resource
                        
                        logger.debug(f"Updated span resource.service.name to {service_name}")
            except Exception as e:
                logger.debug(f"Could not update service name: {e}")
    
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
        resource_attrs.update(
            {
                "deployment.environment": os.getenv(
                    "ENVIRONMENT", "development"
                ),
                "host.name": os.getenv("HOSTNAME", "unknown"),
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

        # Add batch processor for exporting traces
        tracer_provider.add_span_processor(BatchSpanProcessor(trace_exporter))
        
        # Add service name processor for automatic service graph visibility
        # This maps db.system and messaging.system to resource.service.name
        tracer_provider.add_span_processor(ServiceNameSpanProcessor())
        logger.info("✓ Service name span processor registered (→ service graph visibility)")

        logger.info("✓ Traces provider configured (→ Tempo/Jaeger)")

        return tracer_provider

    except Exception as e:
        logger.error(f"Error setting up traces: {e}", exc_info=True)
        raise
