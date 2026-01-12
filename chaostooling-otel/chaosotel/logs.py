"""
LogCore Setup - Configure OpenTelemetry logs export to Loki via OTEL Collector.

Initializes:
- LoggerProvider
- OTLP HTTP log exporter
- Batch log processor
- Resource attributes
"""

import logging
import os
from typing import Any, Optional

from opentelemetry.exporter.otlp.proto.http._log_exporter import OTLPLogExporter
from opentelemetry.sdk._logs import LoggerProvider
from opentelemetry.sdk._logs.export import BatchLogRecordProcessor
from opentelemetry.sdk.resources import Resource

logger = logging.getLogger("chaosotel.logs")


def setup_logs(
    service_name: str = "chaostoolkit",
    service_version: str = "1.0.0",
    service_namespace: Optional[str] = None,
    otel_endpoint: Optional[str] = None,
) -> LoggerProvider:
    """
    Setup OpenTelemetry logs export to Loki via OTEL Collector using OTLP HTTP.

    Args:
        service_name: Service name for resource
        service_version: Service version
        service_namespace: Service namespace (optional)
        otel_endpoint: OTEL Collector endpoint (optional, uses env var if not provided)

    Returns:
        Configured LoggerProvider
    """
    try:
        # Get OTEL endpoint from environment or use default
        # Prefer OTEL_EXPORTER_OTLP_LOGS_ENDPOINT, fallback to OTEL_EXPORTER_OTLP_ENDPOINT
        endpoint: str = (
            otel_endpoint
            or os.getenv(
                "OTEL_EXPORTER_OTLP_LOGS_ENDPOINT",
                os.getenv(
                    "OTEL_EXPORTER_OTLP_ENDPOINT",
                    "http://localhost:4318/v1/logs",
                )
                or "http://localhost:4318/v1/logs",
            )
            or "http://localhost:4318/v1/logs"
        )

        # Ensure endpoint has /v1/logs path if not present
        if not endpoint.endswith("/v1/logs"):
            if endpoint.endswith("/"):
                endpoint = endpoint + "v1/logs"
            else:
                endpoint = endpoint + "/v1/logs"

        logger.info(f"Setting up logs export to {endpoint}")

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

        # Create OTLP HTTP log exporter
        # For HTTP exporters, TLS is determined by endpoint scheme (http:// vs https://)
        log_exporter = OTLPLogExporter(
            endpoint=endpoint,
        )

        # Create logger provider
        logger_provider = LoggerProvider(resource=resource)

        # Add batch processor
        logger_provider.add_log_record_processor(
            BatchLogRecordProcessor(log_exporter)
        )

        logger.info(
            f"✓ Logs provider configured (→ OTEL Collector at {endpoint})"
        )

        return logger_provider

    except Exception as e:
        logger.error(f"Error setting up logs: {e}", exc_info=True)
        raise


def get_logger(name: str = "chaosotel") -> Any:
    """
    Get logger instance.

    Args:
        name: Logger name

    Returns:
        Logger instance
    """
    return logging.getLogger(name)
