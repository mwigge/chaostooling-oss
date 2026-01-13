"""Kafka topic saturation status probe."""

import logging
import os
import time
from contextlib import nullcontext
from typing import Optional

from chaosotel import flush, get_metric_tags, get_metrics_core, get_tracer
from kafka import KafkaConsumer
from opentelemetry._logs import get_logger_provider
from opentelemetry.sdk._logs import LoggingHandler
from opentelemetry.trace import StatusCode


def probe_topic_saturation_status(
    bootstrap_servers: Optional[str] = None,
    topic: Optional[str] = None,
) -> dict:
    """

    Probe to check Kafka topic saturation status.



    Observability: Uses chaosotel (chaostooling-otel) as the central

    observability location. chaosotel must be initialized via chaosotel.control in

    the experiment configuration.

    """

    bootstrap_servers = bootstrap_servers or os.getenv(
        "KAFKA_BOOTSTRAP_SERVERS", "localhost:9092"
    )

    topic = topic or os.getenv("KAFKA_TOPIC", "chaos_saturation_topic")

    # chaosotel is initialized via chaosotel.control - use directly

    tracer = get_tracer()

    # Setup OpenTelemetry logger via LoggingHandler

    logger_provider = get_logger_provider()

    if logger_provider:
        handler = LoggingHandler(level=logging.INFO, logger_provider=logger_provider)

        logger = logging.getLogger("chaosdb.kafka.kafka_topic_saturation_status")

        logger.addHandler(handler)

        logger.setLevel(logging.INFO)

    else:
        logger = logging.getLogger("chaosdb.kafka.kafka_topic_saturation_status")

    metrics = get_metrics_core()

    mq_system = "kafka"

    start = time.time()

    span = None

    span_context = (
        tracer.start_as_current_span("probe.kafka.topic_saturation_status")
        if tracer
        else nullcontext()
    )

    with span_context as span:
        try:
            if span:
                span.set_attribute("messaging.system", "kafka")

                span.set_attribute("messaging.destination", topic)

                span.set_attribute("db.operation", "probe_topic_saturation")

                span.set_attribute("chaos.activity", "kafka_topic_saturation_status")

                span.set_attribute("chaos.activity.type", "probe")

                span.set_attribute("chaos.system", "kafka")

                span.set_attribute("chaos.operation", "topic_saturation_status")

            consumer = KafkaConsumer(
                topic,
                bootstrap_servers=bootstrap_servers,
                consumer_timeout_ms=1000,
                enable_auto_commit=False,
            )

            # Get partition info

            partitions = consumer.partitions_for_topic(topic)

            partition_count = len(partitions) if partitions else 0

            # Get end offsets

            if partitions:
                end_offsets = consumer.end_offsets([p for p in partitions])

                total_messages = sum(end_offsets.values()) if end_offsets else 0

            else:
                total_messages = 0

            consumer.close()

            probe_time_ms = (time.time() - start) * 1000

            tags = get_metric_tags(
                mq_system=mq_system,
                mq_destination=topic,
                mq_operation="probe",
            )

            metrics.record_messaging_operation_count(
                mq_system=mq_system,
                mq_destination=topic,
                mq_operation="probe",
                tags=tags,
            )

            metrics.record_messaging_operation_latency(
                duration_ms=probe_time_ms,
                mq_system=mq_system,
                mq_destination=topic,
                mq_operation="probe",
                tags=tags,
            )

            result = {
                "success": True,
                "partition_count": partition_count,
                "total_messages": total_messages,
                "probe_time_ms": probe_time_ms,
            }

            if span:
                span.set_attribute("chaos.partition_count", partition_count)

                span.set_attribute("chaos.total_messages", total_messages)

                span.set_status(StatusCode.OK)

            logger.info(f"Kafka topic saturation probe: {result}")

            flush()

            return result

        except Exception as e:
            metrics.record_messaging_error(
                mq_system=mq_system,
                error_type=type(e).__name__,
                mq_destination=topic,
                mq_operation="probe",
            )

        if span:
            span.record_exception(e)

            span.set_status(StatusCode.ERROR, str(e))

            span.record_exception(e)

        logger.error(
            f"Kafka topic saturation probe failed: {str(e)}", extra={"error": str(e)}
        )

        flush()

        return {"success": False, "error": str(e)}
