"""RabbitMQ connectivity probe."""

import logging
import os
import time
from contextlib import nullcontext
from typing import Optional

import pika
from chaosotel import flush, get_metric_tags, get_metrics_core, get_tracer
from opentelemetry._logs import get_logger_provider
from opentelemetry.sdk._logs import LoggingHandler
from opentelemetry.trace import StatusCode


def probe_rabbitmq_connectivity(
    host: Optional[str] = None,
    port: Optional[int] = None,
    user: Optional[str] = None,
    password: Optional[str] = None,
    vhost: Optional[str] = None,
) -> bool:
    """
    Probe RabbitMQ connectivity by establishing a connection.

    Observability: Uses chaosotel (chaostooling-otel) as the central
    observability location. chaosotel must be initialized via chaosotel.control in
    the experiment configuration.
    """
    host = host or os.getenv("RABBITMQ_HOST", "localhost")
    port = port or int(os.getenv("RABBITMQ_PORT", "5672"))
    user = user or os.getenv("RABBITMQ_USER", "guest")
    password = password or os.getenv("RABBITMQ_PASSWORD", "guest")
    vhost = vhost or os.getenv("RABBITMQ_VHOST", "/")

    # chaosotel is initialized via chaosotel.control - use directly
    tracer = get_tracer()
    # Setup OpenTelemetry logger via LoggingHandler
    logger_provider = get_logger_provider()
    if logger_provider:
        handler = LoggingHandler(level=logging.INFO, logger_provider=logger_provider)
        logger = logging.getLogger("chaosdb.rabbitmq.rabbitmq_connectivity")
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
    else:
        logger = logging.getLogger("chaosdb.rabbitmq.rabbitmq_connectivity")
    metrics = get_metrics_core()

    mq_system = "rabbitmq"
    start = time.time()

    span_context = (
        tracer.start_as_current_span("probe.rabbitmq.connectivity")
        if tracer
        else nullcontext()
    )

    with span_context as span:
        try:
            if span:
                # Use span helper for consistent attribute setting and resource updates
                from chaosotel.core.trace_core import set_messaging_span_attributes

                set_messaging_span_attributes(
                    span,
                    messaging_system="rabbitmq",
                    destination=vhost,
                    host=host,
                    port=port,
                    chaos_activity="rabbitmq_connectivity_probe",
                    chaos_action="connectivity_probe",
                    chaos_operation="probe",
                )

            credentials = pika.PlainCredentials(user, password)
            params = pika.ConnectionParameters(
                host=host, port=port, virtual_host=vhost, credentials=credentials
            )
            conn = pika.BlockingConnection(params)
            conn.close()

            probe_time_ms = (time.time() - start) * 1000

            tags = get_metric_tags(
                mq_system=mq_system,
                mq_vhost=vhost,
                mq_operation="probe",
            )
            metrics.record_messaging_operation_count(
                mq_system=mq_system,
                count=1,
                tags=tags,
            )

            if span:
                span.set_status(StatusCode.OK)
            logger.info(
                f"RabbitMQ probe OK: {probe_time_ms:.2f}ms",
                extra={"probe_time_ms": probe_time_ms},
            )
            flush()
            return True
        except Exception as e:
            metrics.record_messaging_error(
                mq_system=mq_system,
                error_type=type(e).__name__,
            )
            if span:
                span.record_exception(e)
                span.set_status(StatusCode.ERROR, str(e))
            logger.error(f"RabbitMQ probe failed: {str(e)}", extra={"error": str(e)})
        flush()
        return False
