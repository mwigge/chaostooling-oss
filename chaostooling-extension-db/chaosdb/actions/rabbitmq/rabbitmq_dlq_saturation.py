"""RabbitMQ dead letter queue saturation chaos action."""

import os
import threading
import time
from typing import Optional

import pika
from chaosotel import (
    ensure_initialized,
    flush,
    get_logger,
    get_metric_tags,
    get_metrics_core,
    get_tracer,
)
from opentelemetry.trace import StatusCode

_active_threads = []
_stop_event = threading.Event()


def inject_dlq_saturation(
    host: Optional[str] = None,
    port: Optional[int] = None,
    user: Optional[str] = None,
    password: Optional[str] = None,
    vhost: Optional[str] = None,
    queue: Optional[str] = None,
    dlq_queue: Optional[str] = None,
    num_producers: int = 10,
    messages_per_producer: int = 1000,
    duration_seconds: int = 60,
) -> dict:
    """
    Saturate dead letter queue by sending messages that will be rejected.
    Tests system behavior when error queues are full.
    """
    host = host or os.getenv("RABBITMQ_HOST", "localhost")
    port = port or int(os.getenv("RABBITMQ_PORT", "5672"))
    user = user or os.getenv("RABBITMQ_USER", "guest")
    password = password or os.getenv("RABBITMQ_PASSWORD", "guest")
    vhost = vhost or os.getenv("RABBITMQ_VHOST", "/")
    queue = queue or os.getenv("RABBITMQ_QUEUE", "chaos_test_queue")
    dlq_queue = dlq_queue or os.getenv("RABBITMQ_DLQ_QUEUE", f"{queue}_dlq")

    ensure_initialized()
    db_system = os.getenv("DB_SYSTEM", "rabbitmq")
    metrics = get_metrics_core()
    tracer = get_tracer()
    logger = get_logger()
    start_time = time.time()

    global _active_threads, _stop_event
    _stop_event.clear()
    _active_threads = []

    total_messages_sent = 0
    errors = 0

    def dlq_producer(producer_id: int):
        nonlocal total_messages_sent, errors
        conn = None
        channel = None
        try:
            with tracer.start_as_current_span(
                f"dlq_saturation.producer.{producer_id}"
            ) as span:
                from chaosotel.core.trace_core import set_messaging_span_attributes

                set_messaging_span_attributes(
                    span,
                    messaging_system="rabbitmq",
                    destination=dlq_queue,
                    host=host,
                    port=port,
                    chaos_activity="rabbitmq_dlq_saturation",
                    chaos_action="dlq_saturation",
                    chaos_operation="dlq_saturation",
                    chaos_producer_id=producer_id,
                )

                credentials = pika.PlainCredentials(user, password)
                params = pika.ConnectionParameters(
                    host=host, port=port, virtual_host=vhost, credentials=credentials
                )
                conn = pika.BlockingConnection(params)
                channel = conn.channel()
                channel.queue_declare(queue=dlq_queue, durable=True)

                message_count = 0
                end_time = time.time() + duration_seconds

                while (
                    not _stop_event.is_set()
                    and time.time() < end_time
                    and message_count < messages_per_producer
                ):
                    try:
                        message = f"chaos_dlq_{producer_id}_{message_count}"
                        channel.basic_publish(
                            exchange="",
                            routing_key=dlq_queue,
                            body=message,
                            properties=pika.BasicProperties(delivery_mode=2),
                        )

                        total_messages_sent += 1
                        message_count += 1

                        get_metric_tags(
                            db_name=dlq_queue,
                            db_system="rabbitmq",
                            db_operation="dlq_send",
                        )

                        span.set_status(StatusCode.OK)
                        time.sleep(0.01)
                    except Exception as e:
                        errors += 1
                        metrics.record_db_error(
                            db_system=db_system, error_type=type(e).__name__
                        )
                        logger.warning(f"DLQ producer {producer_id} error: {e}")
        except Exception as e:
            errors += 1
            logger.error(f"DLQ saturation producer {producer_id} failed: {e}")
        finally:
            if channel:
                try:
                    channel.close()
                except Exception:
                    pass
            if conn:
                try:
                    conn.close()
                except Exception:
                    pass

    try:
        with tracer.start_as_current_span("chaos.rabbitmq.dlq_saturation") as span:
            from chaosotel.core.trace_core import set_messaging_span_attributes

            set_messaging_span_attributes(
                span,
                messaging_system="rabbitmq",
                destination=dlq_queue,
                host=host,
                port=port,
                chaos_activity="rabbitmq_dlq_saturation",
                chaos_action="dlq_saturation",
                chaos_operation="dlq_saturation",
                chaos_num_producers=num_producers,
                chaos_duration_seconds=duration_seconds,
            )

            logger.info(
                f"Starting RabbitMQ DLQ saturation with {num_producers} producers for {duration_seconds}s"
            )

            for i in range(num_producers):
                thread = threading.Thread(target=dlq_producer, args=(i,), daemon=True)
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
                "messages_per_second": (
                    total_messages_sent / (duration_ms / 1000) if duration_ms > 0 else 0
                ),
                "producers_used": num_producers,
            }

            span.set_attribute("chaos.total_messages_sent", total_messages_sent)
            span.set_status(StatusCode.OK)

            logger.info(f"RabbitMQ DLQ saturation completed: {result}")
            flush()
            return result
    except Exception as e:
        _stop_event.set()
        metrics.record_db_error(db_system=db_system, error_type=type(e).__name__)
        logger.error(f"RabbitMQ DLQ saturation failed: {e}")
        flush()
        raise


def stop_dlq_saturation():
    global _stop_event, _active_threads
    _stop_event.set()
    for thread in _active_threads:
        thread.join(timeout=2)
    _active_threads = []
