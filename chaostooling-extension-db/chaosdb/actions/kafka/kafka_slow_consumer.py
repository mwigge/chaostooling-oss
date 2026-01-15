"""Kafka slow consumer chaos action."""

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
from kafka import KafkaConsumer
from opentelemetry.trace import StatusCode

_active_threads = []
_stop_event = threading.Event()


def inject_slow_consumer(
    bootstrap_servers: Optional[str] = None,
    topic: Optional[str] = None,
    consumer_group: Optional[str] = None,
    num_consumers: int = 5,
    duration_seconds: int = 60,
    consume_delay_ms: int = 5000,
) -> dict:
    """Inject slow Kafka consumers to create consumer lag."""
    # Handle string input from Chaos Toolkit configuration
    num_consumers = int(num_consumers) if isinstance(num_consumers, str) else num_consumers
    duration_seconds = (
        int(duration_seconds) if isinstance(duration_seconds, str) else duration_seconds
    )
    consume_delay_ms = (
        int(consume_delay_ms) if isinstance(consume_delay_ms, str) else consume_delay_ms
    )
    
    bootstrap_servers = bootstrap_servers or os.getenv(
        "KAFKA_BOOTSTRAP_SERVERS", "localhost:9092"
    )
    topic = topic or os.getenv("KAFKA_TOPIC", "chaos_test_topic")
    consumer_group = consumer_group or os.getenv(
        "KAFKA_CONSUMER_GROUP", "chaos_slow_consumers"
    )

    ensure_initialized()
    mq_system = os.getenv("MQ_SYSTEM", "kafka")
    metrics = get_metrics_core()
    tracer = get_tracer()
    logger = logging.getLogger("chaosdb.kafka.slow_consumer")
    start_time = time.time()

    global _active_threads, _stop_event
    _stop_event.clear()
    _active_threads = []

    messages_consumed = 0
    errors = 0

    def slow_consumer_worker(consumer_id: int):
        nonlocal messages_consumed, errors, metrics
        consumer = None
        try:
            with tracer.start_as_current_span(
                f"slow_consumer.worker.{consumer_id}"
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
                    chaos_activity="kafka_slow_consumer",
                    chaos_action="slow_consumer",
                    chaos_operation="slow_consumer",
                    chaos_consumer_id=consumer_id,
                )

                consumer = KafkaConsumer(
                    topic,
                    bootstrap_servers=bootstrap_servers,
                    group_id=f"{consumer_group}_{consumer_id}",
                    auto_offset_reset="earliest",
                    enable_auto_commit=False,
                )

                end_time = time.time() + duration_seconds

                while not _stop_event.is_set() and time.time() < end_time:
                    try:
                        fetch_start = time.time()

                        # Fetch messages
                        message_pack = consumer.poll(timeout_ms=1000)

                        if message_pack:
                            for topic_partition, messages in message_pack.items():
                                for message in messages:
                                    # Simulate slow processing
                                    time.sleep(consume_delay_ms / 1000.0)

                                    fetch_duration_ms = (
                                        time.time() - fetch_start
                                    ) * 1000
                                    messages_consumed += 1

                                    tags = get_metric_tags(
                                        mq_system=mq_system,
                                        mq_destination=topic,
                                        mq_operation="slow_consume",
                                    )

                                    metrics.record_messaging_operation_count(
                                        mq_system=mq_system,
                                        mq_destination=topic,
                                        mq_operation="slow_consume",
                                        tags=tags,
                                    )

                                    metrics.record_messaging_operation_latency(
                                        duration_ms=fetch_duration_ms,
                                        mq_system=mq_system,
                                        mq_destination=topic,
                                        mq_operation="slow_consume",
                                        tags=tags,
                                    )

                                    # Check lag
                                    partition = consumer.assignment()
                                    if partition:
                                        for p in partition:
                                            committed = consumer.committed(p)
                                            if committed:
                                                end_offsets = consumer.end_offsets([p])
                                                end_offsets[p] - committed

                                    consumer.commit()

                        span.set_status(StatusCode.OK)
                    except Exception as e:
                        errors += 1
                        metrics.record_messaging_error(
                            mq_system=mq_system,
                            error_type=type(e).__name__,
                            mq_destination=topic,
                            mq_operation="slow_consume",
                        )
                        # CommitFailedError is expected during memory stress - log as warning
                        from kafka.errors import CommitFailedError

                        if isinstance(e, CommitFailedError):
                            logger.warning(
                                f"Slow consumer {consumer_id} commit failed (expected during stress): {e}",
                                exc_info=False,
                            )
                        else:
                            logger.warning(
                                f"Slow consumer {consumer_id} error: {e}",
                                exc_info=True,
                            )
                        span.set_status(StatusCode.ERROR, str(e))
                        time.sleep(0.1)
        except Exception as e:
            errors += 1
            logger.error(
                f"Slow consumer worker {consumer_id} failed: {e}",
                exc_info=True,
            )
        finally:
            if consumer:
                try:
                    consumer.close()
                except Exception:
                    pass

    try:
        with tracer.start_as_current_span("chaos.kafka.slow_consumer") as span:
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
                chaos_activity="kafka_slow_consumer",
                chaos_action="slow_consumer",
                chaos_operation="slow_consumer",
                chaos_num_consumers=num_consumers,
                chaos_duration_seconds=duration_seconds,
                chaos_consume_delay_ms=consume_delay_ms,
            )

            logger.info(
                f"Starting Kafka slow consumers with {num_consumers} consumers for {duration_seconds}s"
            )

            for i in range(num_consumers):
                thread = threading.Thread(
                    target=slow_consumer_worker, args=(i,), daemon=True
                )
                thread.start()
                _active_threads.append(thread)

            time.sleep(duration_seconds)
            _stop_event.set()
            for thread in _active_threads:
                thread.join(timeout=10)

            duration_ms = (time.time() - start_time) * 1000

            result = {
                "success": True,
                "duration_ms": duration_ms,
                "messages_consumed": messages_consumed,
                "errors": errors,
                "consumers_used": num_consumers,
            }

            span.set_attribute("chaos.messages_consumed", messages_consumed)
            span.set_attribute("chaos.errors", errors)
            span.set_status(StatusCode.OK)

            logger.info(f"Kafka slow consumer completed: {result}")
            flush()
            return result
    except Exception as e:
        _stop_event.set()
        metrics = get_metrics_core()
        metrics.record_messaging_error(
            mq_system=mq_system,
            error_type=type(e).__name__,
            mq_destination=topic,
            mq_operation="slow_consumer",
        )
        logger.error(
            f"Kafka slow consumer failed: {e}",
            exc_info=True,
        )
        flush()
        raise


def stop_slow_consumer():
    global _stop_event, _active_threads
    _stop_event.set()
    for thread in _active_threads:
        thread.join(timeout=5)
    _active_threads = []
