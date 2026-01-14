import os
import time
from typing import Optional

import redis
from chaosotel import (ensure_initialized, flush, get_logger, get_metric_tags, get_metrics_core, get_tracer)
from opentelemetry.trace import StatusCode


def test_redis_connection(
    host: Optional[str] = None,
    port: Optional[int] = None,
    password: Optional[str] = None,
) -> dict:
    host = host or os.getenv("REDIS_HOST", "localhost")
    port = port or int(os.getenv("REDIS_PORT", "6379"))
    password = password or os.getenv("REDIS_PASSWORD", None)

    # FIX: Don't pass redis details to ensure_initialized! Only service-level config.
    ensure_initialized()
    db_system = os.getenv("DB_SYSTEM", "redis")
    metrics = get_metrics_core()

    tracer = get_tracer()
    logger = get_logger()
    start = time.time()
    try:
        with tracer.start_as_current_span("test.redis.connection") as span:
            # Proper span attributes for OTEL tracing
            span.set_attribute("db.system", db_system)
            span.set_attribute("db.name", "redis")
            span.set_attribute("network.peer.address", host)  # Use OTEL convention
            span.set_attribute("network.peer.port", port)  # Use OTEL convention
            span.set_attribute("db.operation", "connect")
            span.set_attribute("chaos.activity", "redis_connectivity")
            span.set_attribute("chaos.activity.type", "action")
            span.set_attribute("chaos.system", "redis")
            span.set_attribute("chaos.operation", "connectivity")

            r = redis.Redis(host=host, port=port, password=password)
            query_start = time.time()
            r.ping()
            query_time_ms = (time.time() - query_start) * 1000
            connection_time_ms = (time.time() - start) * 1000
            tags = get_metric_tags(
                db_name="redis", db_system=db_system, db_operation="connect"
            )
            metrics.record_db_query_latency(
                query_time_ms,
                db_system=db_system,
                db_name="redis",
                db_operation="connect",
                tags=tags,
            )
            metrics.record_db_query_count(
                db_system=db_system,
                db_name="redis",
                db_operation="connect",
                count=1,
                tags=tags,
            )
            span.set_status(StatusCode.OK)
            logger.info(
                f"Redis connection OK: {connection_time_ms:.2f}ms",
                extra={"connection_time_ms": connection_time_ms},
            )
            flush()
            return {
                "success": True,
                "connection_time_ms": connection_time_ms,
                "query_time_ms": query_time_ms,
                "database": "redis",
                "host": host,
            }
    except Exception as e:
        metrics.record_db_error(
            db_system=db_system, error_type=type(e).__name__, db_name="redis"
        )
        span.set_status(StatusCode.ERROR, str(e))
        logger.error(f"Redis connection failed: {e}", extra={"error": str(e)})
        flush()
        raise
