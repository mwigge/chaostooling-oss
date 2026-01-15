import os
import time

import pika
from chaosotel import (ensure_initialized, flush, get_logger, get_metric_tags,
                       get_metrics_core, get_tracer)
from opentelemetry.trace import StatusCode


def test_rabbitmq_connection(
    host=None, port=None, user=None, password=None, vhost=None
) -> dict:
    """
    Test RabbitMQ connection by establishing and closing a connection.

    Records metrics:
    - rabbitmq_confirm_latency_histogram: Connection latency
    - operation_counter: Successful operations
    - error_counter: On failure
    """
    host = host or os.getenv("RABBITMQ_HOST", "localhost")
    port = port or int(os.getenv("RABBITMQ_PORT", "5672"))
    user = user or os.getenv("RABBITMQ_USER", "guest")
    password = password or os.getenv("RABBITMQ_PASSWORD", "guest")
    vhost = vhost or os.getenv("RABBITMQ_VHOST", "/")
    ensure_initialized()
    db_system = os.getenv("DB_SYSTEM", "rabbitmq")
    metrics = get_metrics_core()
    tracer = get_tracer()
    logger = get_logger()
    start = time.time()
    try:
        with tracer.start_as_current_span("test.rabbitmq.connection") as span:
            span.set_attribute("messaging.system", "rabbitmq")
            span.set_attribute("network.peer.address", host)
            span.set_attribute("network.peer.port", port)
            span.set_attribute("chaos.activity", "rabbitmq_connectivity")
            span.set_attribute("chaos.activity.type", "action")
            span.set_attribute("chaos.system", "rabbitmq")
            span.set_attribute("chaos.operation", "connectivity")
            credentials = pika.PlainCredentials(user, password)
            params = pika.ConnectionParameters(
                host=host, port=port, virtual_host=vhost, credentials=credentials
            )
            conn = pika.BlockingConnection(params)
            conn.close()
            connection_time_ms = (time.time() - start) * 1000

            # Record metrics
            mq_system = "rabbitmq"
            tags = get_metric_tags(
                mq_system=mq_system, mq_vhost=vhost, mq_operation="connection_test"
            )
            metrics.record_messaging_operation_count(
                mq_system=mq_system, count=1, tags=tags
            )

            span.set_status(StatusCode.OK)
            logger.info(
                f"RabbitMQ connection OK: {connection_time_ms:.2f}ms",
                extra={"connection_time_ms": connection_time_ms},
            )
            flush()
            return dict(success=True, connection_time_ms=connection_time_ms, host=host)
    except Exception as e:
        mq_system = "rabbitmq"
        db_system = os.getenv("DB_SYSTEM", "rabbitmq")
        metrics = get_metrics_core()
        metrics.record_db_error(db_system=db_system, error_type=type(e).__name__)
        span.set_status(StatusCode.ERROR, str(e))
        logger.error(f"RabbitMQ connection failed: {e}", extra={"error": str(e)})
        flush()
        raise
