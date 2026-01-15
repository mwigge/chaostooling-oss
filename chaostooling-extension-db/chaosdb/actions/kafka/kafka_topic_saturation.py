"""Kafka topic saturation chaos action."""

import logging
import os
import threading
import time
from typing import Optional

from chaosotel import (
    ensure_initialized,
    flush,
    get_metric_tags,
    get_metrics_core,
    get_tracer,
)
from kafka import KafkaProducer
from opentelemetry.trace import StatusCode

_active_threads = []
_stop_event = threading.Event()


def inject_topic_saturation(
    bootstrap_servers: Optional[str] = None,
    topic: Optional[str] = None,
    num_producers: int = 20,
    messages_per_producer: int = 1000,
    duration_seconds: int = 60,
    message_size_bytes: int = 1024,
) -> dict:
    """Saturate Kafka topic with high message volume."""
    # Handle string input from Chaos Toolkit configuration
    num_producers = (
        int(num_producers) if isinstance(num_producers, str) else num_producers
    )
    messages_per_producer = (
        int(messages_per_producer)
        if isinstance(messages_per_producer, str)
        else messages_per_producer
    )
    duration_seconds = (
        int(duration_seconds) if isinstance(duration_seconds, str) else duration_seconds
    )
    message_size_bytes = (
        int(message_size_bytes)
        if isinstance(message_size_bytes, str)
        else message_size_bytes
    )

    bootstrap_servers = bootstrap_servers or os.getenv(
        "KAFKA_BOOTSTRAP_SERVERS", "localhost:9092"
    )
    topic = topic or os.getenv("KAFKA_TOPIC", "chaos_saturation_topic")

    ensure_initialized()
    mq_system = os.getenv("MQ_SYSTEM", "kafka")
    metrics = get_metrics_core()
    tracer = get_tracer()
    logger = logging.getLogger("chaosdb.kafka.topic_saturation")
    start_time = time.time()

    global _active_threads, _stop_event
    _stop_event.clear()
    _active_threads = []

    total_messages_sent = 0
    total_bytes_sent = 0
    errors = 0

    def saturation_producer(producer_id: int):
        nonlocal total_messages_sent, total_bytes_sent, errors, metrics
        producer = None
        try:
            with tracer.start_as_current_span(
                f"topic_saturation.producer.{producer_id}"
            ) as span:
                from chaosotel.core.trace_core import set_messaging_span_attributes

                # Extract host/port from bootstrap_servers for network attributes
                bootstrap_host = (
                    bootstrap_servers.split(",")[0].split(":")[0]
                    if bootstrap_servers
                    else None
                )
                bootstrap_port = (
                    int(bootstrap_servers.split(",")[0].split(":")[1])
                    if bootstrap_servers and ":" in bootstrap_servers.split(",")[0]
                    else None
                )
                set_messaging_span_attributes(
                    span,
                    messaging_system=mq_system,
                    destination=topic,
                    bootstrap_servers=bootstrap_servers,
                    host=bootstrap_host,
                    port=bootstrap_port,
                    chaos_activity="kafka_topic_saturation",
                    chaos_action="topic_saturation",
                    chaos_operation="topic_saturation",
                    chaos_producer_id=producer_id,
                )

                producer = KafkaProducer(bootstrap_servers=bootstrap_servers)

                message_count = 0
                end_time = time.time() + duration_seconds

                while (
                    not _stop_event.is_set()
                    and time.time() < end_time
                    and message_count < messages_per_producer
                ):
                    try:
                        message = (
                            f"chaos_sat_{producer_id}_{message_count}_"
                            + "x" * message_size_bytes
                        ).encode()
                        future = producer.send(topic, message)
                        future.get(timeout=10)

                        total_messages_sent += 1
                        total_bytes_sent += len(message)
                        message_count += 1

                        tags = get_metric_tags(
                            mq_system=mq_system,
                            mq_destination=topic,
                            mq_operation="saturation_send",
                        )

                        metrics.record_messaging_operation_count(
                            mq_system=mq_system,
                            mq_destination=topic,
                            mq_operation="saturation_send",
                            tags=tags,
                        )

                        span.set_status(StatusCode.OK)
                        time.sleep(0.01)
                    except Exception as e:
                        errors += 1
                        metrics.record_messaging_error(
                            mq_system=mq_system,
                            error_type=type(e).__name__,
                            mq_destination=topic,
                            mq_operation="saturation_send",
                        )
                        logger.warning(f"Saturation producer {producer_id} error: {e}")
                        span.set_status(StatusCode.ERROR, str(e))
        except Exception as e:
            errors += 1
            logger.error(f"Topic saturation producer {producer_id} failed: {e}")
        finally:
            if producer:
                try:
                    producer.close()
                except Exception:
                    pass

    try:
        with tracer.start_as_current_span("chaos.kafka.topic_saturation") as span:
            from chaosotel.core.trace_core import set_messaging_span_attributes

            # Extract host/port from bootstrap_servers for network attributes
            bootstrap_host = (
                bootstrap_servers.split(",")[0].split(":")[0]
                if bootstrap_servers
                else "kafka"
            )
            bootstrap_port = (
                int(bootstrap_servers.split(",")[0].split(":")[1])
                if bootstrap_servers and ":" in bootstrap_servers.split(",")[0]
                else 9092
            )
            set_messaging_span_attributes(
                span,
                messaging_system=mq_system,
                destination=topic,
                bootstrap_servers=bootstrap_servers,
                host=bootstrap_host,
                port=bootstrap_port,
                chaos_activity="kafka_topic_saturation",
                chaos_action="topic_saturation",
                chaos_operation="topic_saturation",
                chaos_num_producers=num_producers,
                chaos_duration_seconds=duration_seconds,
            )

            logger.info(
                f"Starting Kafka topic saturation with {num_producers} producers for {duration_seconds}s"
            )

            for i in range(num_producers):
                thread = threading.Thread(
                    target=saturation_producer, args=(i,), daemon=True
                )
                thread.start()
                _active_threads.append(thread)

            for thread in _active_threads:
                thread.join(timeout=duration_seconds + 5)

            _stop_event.set()
            duration_ms = (time.time() - start_time) * 1000

            result = {
                "success": True,
                "duration_ms": duration_ms,
                "total_messages_sent": total_messages_sent,
                "total_bytes_sent": total_bytes_sent,
                "errors": errors,
                "messages_per_second": (
                    total_messages_sent / (duration_ms / 1000) if duration_ms > 0 else 0
                ),
                "bytes_per_second": (
                    total_bytes_sent / (duration_ms / 1000) if duration_ms > 0 else 0
                ),
                "producers_used": num_producers,
            }

            span.set_attribute("chaos.total_messages_sent", total_messages_sent)
            span.set_attribute("chaos.total_bytes_sent", total_bytes_sent)
            span.set_status(StatusCode.OK)

            logger.info(f"Kafka topic saturation completed: {result}")
            flush()
            return result
    except Exception as e:
        _stop_event.set()
        metrics = get_metrics_core()
        metrics.record_messaging_error(
            mq_system=mq_system,
            error_type=type(e).__name__,
            mq_destination=topic,
            mq_operation="topic_saturation",
        )
        logger.error(f"Kafka topic saturation failed: {e}")
        flush()
        raise


def stop_topic_saturation():
    global _stop_event, _active_threads
    _stop_event.set()
    for thread in _active_threads:
        thread.join(timeout=2)
    _active_threads = []
