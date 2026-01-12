"""
Metrics Setup - Configure OpenTelemetry metrics export via OTLP to OTEL Collector.

Initializes:
- MeterProvider
- OTLP HTTP metrics exporter
- PeriodicExportingMetricReader
- Resource attributes
"""

import logging
import os
from typing import Optional

from opentelemetry.exporter.otlp.proto.http.metric_exporter import (
    OTLPMetricExporter,
)
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.sdk.resources import Resource

logger = logging.getLogger("chaosotel.metrics")


def setup_metrics(
    service_name: str = "chaostoolkit",
    service_version: str = "1.0.0",
    service_namespace: Optional[str] = None,
    otel_endpoint: Optional[str] = None,
) -> MeterProvider:
    """
    Setup OpenTelemetry metrics export via OTLP HTTP to OTEL Collector.

    Args:
        service_name: Service name for resource
        service_version: Service version
        service_namespace: Service namespace (optional)
        otel_endpoint: OTEL Collector endpoint (optional, uses env var if not provided)

    Returns:
        Configured MeterProvider
    """
    try:
        # Get OTEL endpoint from environment or use default
        # Prefer OTEL_EXPORTER_OTLP_METRICS_ENDPOINT, fallback to OTEL_EXPORTER_OTLP_ENDPOINT
        endpoint: str = (
            otel_endpoint
            or os.getenv(
                "OTEL_EXPORTER_OTLP_METRICS_ENDPOINT",
                os.getenv(
                    "OTEL_EXPORTER_OTLP_ENDPOINT",
                    "http://localhost:4318/v1/metrics",
                )
                or "http://localhost:4318/v1/metrics",
            )
            or "http://localhost:4318/v1/metrics"
        )

        # Ensure endpoint has /v1/metrics path if not present
        if not endpoint.endswith("/v1/metrics"):
            if endpoint.endswith("/"):
                endpoint = endpoint + "v1/metrics"
            else:
                endpoint = endpoint + "/v1/metrics"

        logger.info(f"Setting up metrics export to {endpoint}")

        # Create OTLP HTTP metrics exporter
        # For HTTP exporters, TLS is determined by endpoint scheme (http:// vs https://)
        metric_exporter = OTLPMetricExporter(
            endpoint=endpoint,
        )

        # Create periodic metric reader (exports every 5 seconds by default)
        export_interval_ms = int(
            os.getenv("OTEL_METRIC_EXPORT_INTERVAL", "5000")
        )
        metric_reader = PeriodicExportingMetricReader(
            exporter=metric_exporter,
            export_interval_millis=export_interval_ms,
        )

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

        # Create meter provider with OTLP exporter
        meter_provider = MeterProvider(
            metric_readers=[metric_reader],
            resource=resource,
        )

        logger.info(
            f"✓ Metrics provider configured (→ OTEL Collector at {endpoint})"
        )

        return meter_provider

    except Exception as e:
        logger.error(f"Error setting up metrics: {e}", exc_info=True)
        raise
