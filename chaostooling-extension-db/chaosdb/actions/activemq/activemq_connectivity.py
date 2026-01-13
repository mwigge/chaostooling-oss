import os
import time

import stomp  # pip install stomp.py
from chaosotel import (
    ensure_initialized,
    flush,
    get_logger,
    get_metrics_core,
    get_tracer,
)
from opentelemetry.trace import StatusCode

# Requires: stomp.py for Python; ActiveMQ server must have STOMP support enabled (default).


def test_activemq_connection(
    host=None, port=None, user=None, password=None, queue=None
) -> dict:
    """
    Test ActiveMQ connection by sending a test message via STOMP.

    Records metrics:
    - activemq_dispatch_latency_histogram: Connection latency
    - operation_counter: Successful operations
    - error_counter: On failure
    """
    host = host or os.getenv("ACTIVEMQ_HOST", "localhost")
    port = port or int(os.getenv("ACTIVEMQ_PORT", "61613"))
    user = user or os.getenv("ACTIVEMQ_USER", "admin")
    password = password or os.getenv("ACTIVEMQ_PASSWORD", "admin")
    queue = queue or os.getenv("ACTIVEMQ_QUEUE", "chaos.test")
    mq_system = os.getenv("MQ_SYSTEM", "activemq")
    ensure_initialized()
    tracer = get_tracer()
    logger = get_logger()
    start = time.time()
    try:
        with tracer.start_as_current_span("test.activemq.connection") as span:
            span.set_attribute("messaging.system", mq_system)
            span.set_attribute("messaging.destination", queue)
            span.set_attribute("network.peer.address", host)
            span.set_attribute("network.peer.port", port)
            span.set_attribute("chaos.activity", "activemq_connectivity")
            span.set_attribute("chaos.activity.type", "action")
            span.set_attribute("chaos.system", "activemq")
            span.set_attribute("chaos.operation", "connectivity")
            conn = stomp.Connection([(host, port)])
            conn.connect(user, password, wait=True)
            conn.send(destination=f"/queue/{queue}", body="chaos-connectivity-test")
            conn.disconnect()
            connection_time_ms = (time.time() - start) * 1000

            # Record metrics
            metrics = get_metrics_core()
            metrics.record_messaging_dispatch_latency(
                connection_time_ms / 1000.0,
                mq_system=mq_system,
                mq_destination=queue,
                mq_operation="connection_test",
            )
            metrics.record_messaging_operation_count(
                mq_system=mq_system,
                mq_destination=queue,
                count=1,
                mq_operation="connection_test",
            )

            span.set_status(StatusCode.OK)
            logger.info(
                f"ActiveMQ connection OK: {connection_time_ms:.2f}ms",
                extra={"connection_time_ms": connection_time_ms},
            )
            flush()
            return dict(
                success=True,
                connection_time_ms=connection_time_ms,
                host=host,
                queue=queue,
            )
    except Exception as e:
        mq_system = os.getenv("MQ_SYSTEM", "activemq")
        metrics = get_metrics_core()
        metrics.record_messaging_operation_count(
            mq_system=mq_system,
            count=1,
            mq_operation="connection_test",
            error_type=type(e).__name__,
        )
        span.set_status(StatusCode.ERROR, str(e))
        logger.error(f"ActiveMQ connection failed: {e}", extra={"error": str(e)})
        flush()
        raise
