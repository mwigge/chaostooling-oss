"""RabbitMQ message flood status probe."""

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


def probe_message_flood_status(
    host: Optional[str] = None,
    port: Optional[int] = None,
    user: Optional[str] = None,
    password: Optional[str] = None,
    vhost: Optional[str] = None,
    queue: Optional[str] = None,
) -> dict:
    """

    Probe to check RabbitMQ message flood status.



    Observability: Uses chaosotel (chaostooling-otel) as the central

    observability location. chaosotel must be initialized via chaosotel.control in

    the experiment configuration.

    """

    host = host or os.getenv("RABBITMQ_HOST", "localhost")

    port = port or int(os.getenv("RABBITMQ_PORT", "5672"))

    user = user or os.getenv("RABBITMQ_USER", "guest")

    password = password or os.getenv("RABBITMQ_PASSWORD", "guest")

    vhost = vhost or os.getenv("RABBITMQ_VHOST", "/")

    queue = queue or os.getenv("RABBITMQ_QUEUE", "chaos_test_queue")

    # chaosotel is initialized via chaosotel.control - use directly

    tracer = get_tracer()

    # Setup OpenTelemetry logger via LoggingHandler

    logger_provider = get_logger_provider()

    if logger_provider:
        handler = LoggingHandler(level=logging.INFO, logger_provider=logger_provider)

        logger = logging.getLogger("chaosdb.rabbitmq.rabbitmq_message_flood_status")

        logger.addHandler(handler)

        logger.setLevel(logging.INFO)

    else:
        logger = logging.getLogger("chaosdb.rabbitmq.rabbitmq_message_flood_status")

    metrics = get_metrics_core()

    mq_system = "rabbitmq"

    start = time.time()


    span_context = (
        tracer.start_as_current_span("probe.rabbitmq.message_flood_status")
        if tracer
        else nullcontext()
    )

    with span_context as span:
        try:
            if span:
                span.set_attribute("messaging.system", "rabbitmq")

                span.set_attribute("messaging.destination", queue)

                span.set_attribute("db.operation", "probe_message_flood")

                span.set_attribute("chaos.activity", "rabbitmq_message_flood_status")

                span.set_attribute("chaos.activity.type", "probe")

                span.set_attribute("chaos.system", "rabbitmq")

                span.set_attribute("chaos.operation", "message_flood_status")

            credentials = pika.PlainCredentials(user, password)

            params = pika.ConnectionParameters(
                host=host, port=port, virtual_host=vhost, credentials=credentials
            )

            conn = pika.BlockingConnection(params)

            channel = conn.channel()

            # Get queue info

            queue_info = channel.queue_declare(queue=queue, passive=True)

            queue_depth = queue_info.method.message_count

            consumers = queue_info.method.consumer_count

            channel.close()

            conn.close()

            probe_time_ms = (time.time() - start) * 1000

            tags = get_metric_tags(
                mq_system=mq_system,
                mq_destination=queue,
                mq_operation="probe",
            )

            metrics.record_messaging_operation_count(
                mq_system=mq_system,
                count=1,
                tags=tags,
            )

            result = {
                "success": True,
                "queue_depth": queue_depth,
                "consumers": consumers,
                "probe_time_ms": probe_time_ms,
            }

            if span:
                span.set_attribute("chaos.queue_depth", queue_depth)

                span.set_attribute("chaos.consumers", consumers)

                span.set_status(StatusCode.OK)

            logger.info(f"RabbitMQ message flood probe: {result}")

            flush()

            return result

        except Exception as e:
            mq_system = "rabbitmq"
            metrics = get_metrics_core()
            metrics.record_messaging_error(
                mq_system=mq_system,
                error_type=type(e).__name__,
            )

            if span:
                span.record_exception(e)
                span.set_status(StatusCode.ERROR, str(e))

            logger.error(
                f"RabbitMQ message flood probe failed: {e}", extra={"error": str(e)}
            )

            flush()

            return {"success": False, "error": str(e)}
