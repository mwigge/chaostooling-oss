"""ActiveMQ slow consumer status probe."""

import logging
import os
import time
from contextlib import nullcontext
from typing import Optional

import stomp
from chaosotel import flush, get_metric_tags, get_metrics_core, get_tracer
from opentelemetry._logs import get_logger_provider
from opentelemetry.sdk._logs import LoggingHandler
from opentelemetry.trace import StatusCode


def probe_slow_consumer_status(
    host: Optional[str] = None,
    port: Optional[int] = None,
    user: Optional[str] = None,
    password: Optional[str] = None,
    queue: Optional[str] = None,
) -> dict:
    """

    Probe to check ActiveMQ slow consumer status.



    Observability: Uses chaosotel (chaostooling-otel) as the central

    observability location. chaosotel must be initialized via chaosotel.control in

    the experiment configuration.

    """

    host = host or os.getenv("ACTIVEMQ_HOST", "localhost")

    port = port or int(os.getenv("ACTIVEMQ_PORT", "61613"))

    user = user or os.getenv("ACTIVEMQ_USER", "admin")

    password = password or os.getenv("ACTIVEMQ_PASSWORD", "admin")

    queue = queue or os.getenv("ACTIVEMQ_QUEUE", "chaos.test")

    # chaosotel is initialized via chaosotel.control - use directly

    tracer = get_tracer()

    # Setup OpenTelemetry logger via LoggingHandler

    logger_provider = get_logger_provider()

    if logger_provider:
        handler = LoggingHandler(level=logging.INFO, logger_provider=logger_provider)

        logger = logging.getLogger("chaosdb.activemq.activemq_slow_consumer_status")

        logger.addHandler(handler)

        logger.setLevel(logging.INFO)

    else:
        logger = logging.getLogger("chaosdb.activemq.activemq_slow_consumer_status")

    metrics = get_metrics_core()

    mq_system = "activemq"

    start = time.time()

    span_context = (
        tracer.start_as_current_span("probe.activemq.slow_consumer_status")
        if tracer
        else nullcontext()
    )

    with span_context as span:
        try:
            if span:
                span.set_attribute("messaging.system", "activemq")

                span.set_attribute("messaging.destination", queue)

                span.set_attribute("db.operation", "probe_slow_consumer")

                span.set_attribute("chaos.activity", "activemq_slow_consumer_status")

                span.set_attribute("chaos.activity.type", "probe")

                span.set_attribute("chaos.system", "activemq")

                span.set_attribute("chaos.operation", "slow_consumer_status")

            conn = stomp.Connection([(host, port)])

            conn.connect(user, password, wait=True)

            conn.send(destination=f"/queue/{queue}", body="probe")

            conn.disconnect()

            probe_time_ms = (time.time() - start) * 1000

            tags = get_metric_tags(
                mq_system=mq_system,
                mq_destination=queue,
                mq_operation="probe",
            )

            metrics.record_messaging_dispatch_latency(
                probe_time_ms,
                mq_system=mq_system,
                tags=tags,
            )

            metrics.record_messaging_operation_count(
                mq_system=mq_system,
                count=1,
                tags=tags,
            )

            result = {"success": True, "probe_time_ms": probe_time_ms}

            if span:
                span.set_status(StatusCode.OK)

            logger.info(f"ActiveMQ slow consumer probe: {result}")

            flush()

            return result

        except Exception as e:
            metrics.record_messaging_error(
                mq_system=mq_system,
                error_type=type(e).__name__,
            )

            if span:
                span.record_exception(e)
                span.set_status(StatusCode.ERROR, str(e))

            logger.error(
                f"ActiveMQ slow consumer probe failed: {str(e)}",
                extra={"error": str(e)},
            )

            flush()

            return {"success": False, "error": str(e)}
