"""Redis slow operations status probe."""

import logging
import os
import time
from contextlib import nullcontext
from typing import Optional

import redis
from chaosotel import flush, get_metric_tags, get_metrics_core, get_tracer
from opentelemetry._logs import get_logger_provider
from opentelemetry.sdk._logs import LoggingHandler
from opentelemetry.trace import StatusCode


def probe_slow_operations_status(
    host: Optional[str] = None,
    port: Optional[int] = None,
    password: Optional[str] = None,
) -> dict:
    """

    Probe to check Redis slow operations status.

    Observability: Uses chaosotel (chaostooling-otel) as the central observability location. chaosotel must be initialized via chaosotel.control in the experiment configuration.

    """

    host = host or os.getenv("REDIS_HOST", "localhost")

    port = port or int(os.getenv("REDIS_PORT", "6379"))

    password = password or os.getenv("REDIS_PASSWORD", None)

    # chaosotel is initialized via chaosotel.control - use directly

    tracer = get_tracer()

    # Setup OpenTelemetry logger via LoggingHandler

    logger_provider = get_logger_provider()

    if logger_provider:
        handler = LoggingHandler(level=logging.INFO, logger_provider=logger_provider)

        logger = logging.getLogger("chaosdb.redis.redis_slow_operations_status")

        logger.addHandler(handler)

        logger.setLevel(logging.INFO)

    else:
        logger = logging.getLogger("chaosdb.redis.redis_slow_operations_status")

    metrics = get_metrics_core()

    db_system = "redis"

    database = "redis"

    start = time.time()

    span_context = (
        tracer.start_as_current_span("probe.redis.slow_operations_status")
        if tracer
        else nullcontext()
    )

    with span_context as span:
        try:
            if span:
                span.set_attribute("db.system", db_system)

                span.set_attribute("db.name", database)

                span.set_attribute("chaos.activity", "redis_slow_operations_status")

                span.set_attribute("chaos.activity.type", "probe")

                span.set_attribute("chaos.system", "redis")

                span.set_attribute("chaos.operation", "slow_operations_status")

            r = redis.Redis(
                host=host, port=port, password=password, decode_responses=True
            )

            # Get slowlog

            slowlog = r.slowlog_get(128)  # Get last 128 slow log entries

            slow_operations_count = len(slowlog)

            slow_operations = []

            total_duration = 0

            for entry in slowlog:
                duration_ms = (
                    entry.get("duration", 0) / 1000
                )  # Convert microseconds to milliseconds

                slow_operations.append(
                    {
                        "duration_ms": duration_ms,
                        "command": entry.get("command", "unknown"),
                    }
                )

                total_duration += duration_ms

            avg_duration_ms = (
                total_duration / slow_operations_count
                if slow_operations_count > 0
                else 0
            )

            max_duration_ms = max(
                (op["duration_ms"] for op in slow_operations), default=0
            )

            r.close()

            probe_time_ms = (time.time() - start) * 1000

            tags = get_metric_tags(
                db_name=database,
                db_system=db_system,
                db_operation="probe_slow_operations",
            )

            metrics.record_db_query_latency(
                probe_time_ms,
                db_system=db_system,
                db_name=database,
                db_operation="probe_slow_operations",
                tags=tags,
            )

            metrics.record_db_query_count(
                db_system=db_system,
                db_name=database,
                db_operation="probe_slow_operations",
                count=1,
                tags=tags,
            )

            result = {
                "success": True,
                "slow_operations_count": slow_operations_count,
                "average_duration_ms": avg_duration_ms,
                "max_duration_ms": max_duration_ms,
                "probe_time_ms": probe_time_ms,
            }

            if span:
                span.set_attribute("chaos.slow_operations_count", slow_operations_count)

                span.set_attribute("chaos.average_duration_ms", avg_duration_ms)

                span.set_status(StatusCode.OK)

            logger.info(f"Redis slow operations probe: {result}")

            flush()

            return result

        except Exception as e:
            metrics.record_db_error(
                db_system=db_system,
                error_type=type(e).__name__,
                db_name=database,
            )

            if span:
                span.record_exception(e)
                span.set_status(StatusCode.ERROR, str(e))

            logger.error(
                f"Redis slow operations probe failed: {str(e)}", extra={"error": str(e)}
            )

            flush()

            return {"success": False, "error": str(e)}
