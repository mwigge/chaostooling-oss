"""
Traces Setup - Configure OpenTelemetry traces export to Tempo/Jaeger.

Initializes:
- TracerProvider
- OTLP/gRPC trace exporter
- Batch span processor
- Resource attributes
"""

import logging
import os
from typing import Optional

from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import (
    OTLPSpanExporter,
)
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

logger = logging.getLogger("chaosotel.traces")


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

        # Add batch processor
        tracer_provider.add_span_processor(BatchSpanProcessor(trace_exporter))

        logger.info("✓ Traces provider configured (→ Tempo/Jaeger)")

        return tracer_provider

    except Exception as e:
        logger.error(f"Error setting up traces: {e}", exc_info=True)
        raise
