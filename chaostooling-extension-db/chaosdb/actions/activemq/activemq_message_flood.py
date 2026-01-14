"""ActiveMQ message flood chaos action."""

import logging
import os
import threading
import time
from typing import Dict, Optional

import stomp
from chaosotel import (
    ensure_initialized,
    flush,
    get_metric_tags,
    get_metrics_core,
    get_tracer,
)
from opentelemetry._logs import get_logger_provider
from opentelemetry.sdk._logs import LoggingHandler
from opentelemetry.trace import StatusCode

_active_threads = []
_stop_event = threading.Event()


def inject_message_flood(
    host: Optional[str] = None,
    port: Optional[int] = None,
    user: Optional[str] = None,
    password: Optional[str] = None,
    queue: Optional[str] = None,
    num_producers: int = 10,
    messages_per_producer: int = 1000,
    duration_seconds: int = 60,
) -> Dict:
    """Flood ActiveMQ queue with high volume of messages."""
    host = host or os.getenv("ACTIVEMQ_HOST", "localhost")
    port = port or int(os.getenv("ACTIVEMQ_PORT", "61613"))
    user = user or os.getenv("ACTIVEMQ_USER", "admin")
    password = password or os.getenv("ACTIVEMQ_PASSWORD", "admin")
    queue = queue or os.getenv("ACTIVEMQ_QUEUE", "chaos.test")

    ensure_initialized()
    mq_system = "activemq"
    metrics = get_metrics_core()
    tracer = get_tracer()

    # Setup OpenTelemetry logger via LoggingHandler (OpenTelemetry standard)
    logger_provider = get_logger_provider()
    if logger_provider:
        handler = LoggingHandler(level=logging.INFO, logger_provider=logger_provider)
        logger = logging.getLogger("chaosdb.activemq.message_flood")
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
    else:
        logger = logging.getLogger("chaosdb.activemq.message_flood")

    start_time = time.time()

    global _active_threads, _stop_event
    _stop_event.clear()
    _active_threads = []

    total_messages_sent = 0
    errors = 0

    def producer_worker(producer_id: int):
        nonlocal total_messages_sent, errors, metrics
        conn = None
        try:
            with tracer.start_as_current_span(
                f"message_flood.producer.{producer_id}"
            ) as span:
                from chaosotel.core.trace_core import set_messaging_span_attributes

                set_messaging_span_attributes(
                    span,
                    messaging_system="activemq",
                    destination=queue,
                    host=host,
                    port=port,
                    chaos_activity="activemq_message_flood",
                    chaos_action="message_flood",
                    chaos_operation="message_flood",
                    chaos_producer_id=producer_id,
                )

                conn = stomp.Connection([(host, port)])
                conn.connect(user, password, wait=True)

                message_count = 0
                end_time = time.time() + duration_seconds

                while (
                    not _stop_event.is_set()
                    and time.time() < end_time
                    and message_count < messages_per_producer
                ):
                    try:
                        send_start = time.time()

                        message = f"chaos_test_{producer_id}_{message_count}"
                        conn.send(destination=f"/queue/{queue}", body=message)

                        send_duration_ms = (time.time() - send_start) * 1000
                        total_messages_sent += 1
                        message_count += 1

                        tags = get_metric_tags(
                            mq_system=mq_system,
                            mq_destination=queue,
                            mq_operation="message_send",
                        )
                        metrics.record_messaging_operation_count(
                            mq_system=mq_system,
                            mq_destination=queue,
                            mq_operation="message_send",
                            tags=tags,
                        )
                        metrics.record_messaging_operation_latency(
                            duration_ms=send_duration_ms,
                            mq_system=mq_system,
                            mq_destination=queue,
                            mq_operation="message_send",
                            tags=tags,
                        )

                        span.set_status(StatusCode.OK)
                        time.sleep(0.01)
                    except Exception as e:
                        errors += 1
                        metrics.record_messaging_error(
                            mq_system=mq_system,
                            error_type=type(e).__name__,
                            mq_destination=queue,
                            mq_operation="message_send",
                        )
                        logger.warning(
                            f"Producer {producer_id} error: {e}",
                            exc_info=True,
                        )
        except Exception as e:
            errors += 1
            logger.error(
                f"Message flood producer {producer_id} failed: {e}",
                exc_info=True,
            )
        finally:
            if conn:
                try:
                    conn.disconnect()
                except Exception:
                    pass

    try:
        with tracer.start_as_current_span("chaos.activemq.message_flood") as span:
            from chaosotel.core.trace_core import set_messaging_span_attributes

            set_messaging_span_attributes(
                span,
                messaging_system="activemq",
                destination=queue,
                host=host,
                port=port,
                chaos_activity="activemq_message_flood",
                chaos_action="message_flood",
                chaos_operation="message_flood",
                chaos_num_producers=num_producers,
                chaos_duration_seconds=duration_seconds,
            )
            span.set_attribute("chaos.system", "activemq")
            span.set_attribute("chaos.operation", "message_flood")

            logger.info(
                f"Starting ActiveMQ message flood with {num_producers} producers for {duration_seconds}s"
            )

            for i in range(num_producers):
                thread = threading.Thread(
                    target=producer_worker, args=(i,), daemon=True
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
                "errors": errors,
                "messages_per_second": total_messages_sent / (duration_ms / 1000)
                if duration_ms > 0
                else 0,
                "producers_used": num_producers,
            }

            span.set_attribute("chaos.total_messages_sent", total_messages_sent)
            span.set_attribute("chaos.errors", errors)
            span.set_status(StatusCode.OK)

            logger.info(f"ActiveMQ message flood completed: {result}")
            flush()
            return result
    except Exception as e:
        _stop_event.set()
        metrics.record_messaging_error(
            mq_system=mq_system,
            error_type=type(e).__name__,
            mq_destination=queue,
            mq_operation="message_flood",
        )
        logger.error(
            f"ActiveMQ message flood failed: {e}",
            exc_info=True,
        )
        flush()
        raise


def stop_message_flood():
    global _stop_event, _active_threads
    _stop_event.set()
    for thread in _active_threads:
        thread.join(timeout=2)
    _active_threads = []
