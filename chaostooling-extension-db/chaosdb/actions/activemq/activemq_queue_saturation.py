"""ActiveMQ queue saturation chaos action."""

import os
import threading
import time
from typing import Dict, Optional

import stomp
from chaosotel import (
    ensure_initialized,
    flush,
    get_logger,
    get_metrics_core,
    get_tracer,
)
from opentelemetry.trace import StatusCode

_active_threads = []
_stop_event = threading.Event()


def inject_queue_saturation(
    host: Optional[str] = None,
    port: Optional[int] = None,
    user: Optional[str] = None,
    password: Optional[str] = None,
    queue: Optional[str] = None,
    num_producers: int = 20,
    messages_per_producer: int = 1000,
    duration_seconds: int = 60,
) -> Dict:
    """Saturate ActiveMQ queue with high message volume."""
    host = host or os.getenv("ACTIVEMQ_HOST", "localhost")
    port = port or int(os.getenv("ACTIVEMQ_PORT", "61613"))
    user = user or os.getenv("ACTIVEMQ_USER", "admin")
    password = password or os.getenv("ACTIVEMQ_PASSWORD", "admin")
    queue = queue or os.getenv("ACTIVEMQ_QUEUE", "chaos.saturation")

    ensure_initialized()
    db_system = os.getenv("DB_SYSTEM", "activemq")
    metrics = get_metrics_core()
    tracer = get_tracer()
    logger = get_logger()
    start_time = time.time()

    global _active_threads, _stop_event
    _stop_event.clear()
    _active_threads = []

    total_messages_sent = 0
    errors = 0

    def saturation_producer(producer_id: int):
        nonlocal total_messages_sent, errors, metrics
        conn = None
        try:
            with tracer.start_as_current_span(
                f"queue_saturation.producer.{producer_id}"
            ) as span:
                from chaosotel.core.trace_core import set_messaging_span_attributes

                set_messaging_span_attributes(
                    span,
                    messaging_system="activemq",
                    destination=queue,
                    host=host,
                    port=port,
                    chaos_activity="activemq_queue_saturation",
                    chaos_action="queue_saturation",
                    chaos_operation="queue_saturation",
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
                        message = f"chaos_sat_{producer_id}_{message_count}"
                        conn.send(destination=f"/queue/{queue}", body=message)

                        total_messages_sent += 1
                        message_count += 1

                        metrics.record_messaging_operation_count(
                            mq_system="activemq",
                            mq_destination=queue,
                            mq_operation="saturation_send",
                        )

                        span.set_status(StatusCode.OK)
                        time.sleep(0.01)
                    except Exception as e:
                        errors += 1
                        metrics.record_messaging_error(
                            mq_system="activemq",
                            error_type=type(e).__name__,
                            mq_destination=queue,
                            mq_operation="saturation_send",
                        )
                        logger.warning(f"Saturation producer {producer_id} error: {e}")
        except Exception as e:
            errors += 1
            logger.error(f"Queue saturation producer {producer_id} failed: {e}")
        finally:
            if conn:
                try:
                    conn.disconnect()
                except Exception:
                    pass

    try:
        with tracer.start_as_current_span("chaos.activemq.queue_saturation") as span:
            from chaosotel.core.trace_core import set_messaging_span_attributes

            set_messaging_span_attributes(
                span,
                messaging_system="activemq",
                destination=queue,
                host=host,
                port=port,
                chaos_activity="activemq_queue_saturation",
                chaos_action="queue_saturation",
                chaos_operation="queue_saturation",
                chaos_num_producers=num_producers,
                chaos_duration_seconds=duration_seconds,
            )

            logger.info(
                f"Starting ActiveMQ queue saturation with {num_producers} producers for {duration_seconds}s"
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
                "errors": errors,
                "messages_per_second": total_messages_sent / (duration_ms / 1000)
                if duration_ms > 0
                else 0,
                "producers_used": num_producers,
            }

            span.set_attribute("chaos.total_messages_sent", total_messages_sent)
            span.set_attribute("chaos.errors", errors)
            span.set_status(StatusCode.OK)

            logger.info(f"ActiveMQ queue saturation completed: {result}")
            flush()
            return result
    except Exception as e:
        _stop_event.set()
        metrics = get_metrics_core()
        metrics.record_db_error(db_system=db_system, error_type=type(e).__name__)
        logger.error(f"ActiveMQ queue saturation failed: {e}")
        flush()
        raise


def stop_queue_saturation():
    global _stop_event, _active_threads
    _stop_event.set()
    for thread in _active_threads:
        thread.join(timeout=2)
    _active_threads = []
