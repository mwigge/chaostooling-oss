"""Kafka slow consumer status probe."""

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


def probe_slow_consumer_status(
    bootstrap_servers: Optional[str] = None,
    topic: Optional[str] = None,
    consumer_group: Optional[str] = None,
) -> dict:
    """

    Probe to check Kafka slow consumer status - measures consumer lag.



    Observability: Uses chaosotel (chaostooling-otel) as the central

    observability location. chaosotel must be initialized via chaosotel.control in

    the experiment configuration.

    """

    bootstrap_servers = bootstrap_servers or os.getenv(
        "KAFKA_BOOTSTRAP_SERVERS", "localhost:9092"
    )

    topic = topic or os.getenv("KAFKA_TOPIC", "chaos_test_topic")

    consumer_group = consumer_group or os.getenv(
        "KAFKA_CONSUMER_GROUP", "chaos_consumers"
    )

    # chaosotel is initialized via chaosotel.control - use directly

    tracer = get_tracer()

    # Setup OpenTelemetry logger via LoggingHandler

    logger_provider = get_logger_provider()

    if logger_provider:
        handler = LoggingHandler(level=logging.INFO, logger_provider=logger_provider)

        logger = logging.getLogger("chaosdb.kafka.kafka_slow_consumer_status")

        logger.addHandler(handler)

        logger.setLevel(logging.INFO)

    else:
        logger = logging.getLogger("chaosdb.kafka.kafka_slow_consumer_status")

    metrics = get_metrics_core()

    mq_system = "kafka"

    start = time.time()

    span_context = (
        tracer.start_as_current_span("probe.kafka.slow_consumer_status")
        if tracer
        else nullcontext()
    )

    with span_context as span:
        try:
            if span:
                span.set_attribute("messaging.system", "kafka")

                span.set_attribute("messaging.destination", topic)

                span.set_attribute("db.operation", "probe_slow_consumer")

                span.set_attribute("chaos.activity", "kafka_slow_consumer_status")

                span.set_attribute("chaos.activity.type", "probe")

                span.set_attribute("chaos.system", "kafka")

                span.set_attribute("chaos.operation", "slow_consumer_status")

            consumer = KafkaConsumer(
                topic,
                bootstrap_servers=bootstrap_servers,
                group_id=consumer_group,
                consumer_timeout_ms=1000,
                enable_auto_commit=False,
            )

            # Calculate consumer lag

            total_lag_messages = 0

            total_lag_seconds = 0

            partitions = consumer.assignment()

            if partitions:
                end_offsets = consumer.end_offsets(partitions)

                committed_offsets = {}

                for p in partitions:
                    committed = consumer.committed(p)

                    if committed:
                        committed_offsets[p] = committed

                for partition in partitions:
                    end_offset = end_offsets.get(partition, 0)

                    committed_offset = committed_offsets.get(partition, 0)

                    lag = end_offset - committed_offset

                    total_lag_messages += lag

                    # Estimate lag in seconds (rough)

                    if lag > 0:
                        total_lag_seconds += lag * 0.1  # Rough estimate

            consumer.close()

            probe_time_ms = (time.time() - start) * 1000

            tags = get_metric_tags(
                mq_system=mq_system,
                mq_destination=topic,
                mq_operation="probe",
                consumer_group=consumer_group,
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
                "total_lag_messages": total_lag_messages,
                "estimated_lag_seconds": total_lag_seconds,
                "probe_time_ms": probe_time_ms,
            }

            if span:
                span.set_attribute("chaos.total_lag_messages", total_lag_messages)

                span.set_attribute("chaos.estimated_lag_seconds", total_lag_seconds)

                span.set_status(StatusCode.OK)

            logger.info(f"Kafka slow consumer probe: {result}")

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

            logger.error(
                f"Kafka slow consumer probe failed: {str(e)}", extra={"error": str(e)}
            )

            flush()

            return {"success": False, "error": str(e)}
