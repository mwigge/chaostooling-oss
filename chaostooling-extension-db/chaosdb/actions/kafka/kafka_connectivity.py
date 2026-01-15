import logging
import os
import time
from typing import Optional

from chaosotel import (ensure_initialized, flush, get_metric_tags,
                       get_metrics_core, get_tracer)
from kafka import KafkaProducer
from opentelemetry.trace import StatusCode


def test_kafka_connection(
    bootstrap_servers: Optional[str] = None,
    topic: Optional[str] = None,
) -> dict:
    """
    Test Kafka connection by sending a test message.

    Records metrics:
    - messaging.operation.count: Operation count
    - messaging.operation.latency: Connection latency
    """
    bootstrap_servers = bootstrap_servers or os.getenv(
        "KAFKA_BOOTSTRAP_SERVERS", "localhost:9092"
    )
    topic = topic or os.getenv("KAFKA_TOPIC", "test")
    ensure_initialized()
    mq_system = os.getenv("MQ_SYSTEM", "kafka")
    tracer = get_tracer()
    logger = logging.getLogger("chaosdb.kafka.connectivity")
    metrics = get_metrics_core()
    start = time.time()
    with tracer.start_as_current_span("test.kafka.connection") as span:
        try:
            span.set_attribute("messaging.system", mq_system)
            span.set_attribute("messaging.destination", topic)
            span.set_attribute("network.peer.address", bootstrap_servers)
            span.set_attribute("chaos.activity", "kafka_connectivity")
            span.set_attribute("chaos.activity.type", "action")
            span.set_attribute("chaos.system", "kafka")
            span.set_attribute("chaos.operation", "connectivity")
            producer = KafkaProducer(bootstrap_servers=bootstrap_servers)
            # Send a dummy message (won't be consumed)
            producer.send(topic, b"chaos-connectivity-test")
            producer.flush()
            producer.close()
            connection_time_ms = (time.time() - start) * 1000

            # Record metrics
            tags = get_metric_tags(
                mq_system=mq_system,
                mq_destination=topic,
                mq_operation="connection_test",
            )

            metrics.record_messaging_operation_count(
                mq_system=mq_system,
                mq_destination=topic,
                mq_operation="connection_test",
                tags=tags,
            )

            metrics.record_messaging_operation_latency(
                duration_ms=connection_time_ms,
                mq_system=mq_system,
                mq_destination=topic,
                mq_operation="connection_test",
                tags=tags,
            )

            span.set_status(StatusCode.OK)
            logger.info(
                f"Kafka connection OK: {connection_time_ms:.2f}ms",
                extra={"connection_time_ms": connection_time_ms},
            )
            flush()
            return dict(
                success=True,
                connection_time_ms=connection_time_ms,
                bootstrap_servers=bootstrap_servers,
                topic=topic,
            )
        except Exception as e:
            metrics.record_messaging_error(
                mq_system=mq_system,
                error_type=type(e).__name__,
                mq_destination=topic,
                mq_operation="connection_test",
                tags=get_metric_tags(
                    mq_system=mq_system,
                    mq_destination=topic,
                    mq_operation="connection_test",
                ),
            )
            span.set_status(StatusCode.ERROR, str(e))
            span.record_exception(e)
            logger.error("Kafka connection failed: %s", e, extra={"error": str(e)})
            flush()
            raise
