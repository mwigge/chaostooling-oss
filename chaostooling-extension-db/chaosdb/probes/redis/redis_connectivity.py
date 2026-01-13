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


def probe_redis_connectivity(
    host: Optional[str] = None,
    port: Optional[int] = None,
    password: Optional[str] = None,
) -> bool:
    """

    Probe Redis connectivity. Observability: Uses chaosotel (chaostooling-otel) as the central observability location. chaosotel must be initialized via chaosotel.control in the experiment configuration.

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

        logger = logging.getLogger("chaosdb.redis.redis_connectivity")

        logger.addHandler(handler)

        logger.setLevel(logging.INFO)

    else:
        logger = logging.getLogger("chaosdb.redis.redis_connectivity")

    metrics = get_metrics_core()

    db_system = "redis"

    database = "redis"

    start = time.time()

    span = None

    span_context = (
        tracer.start_as_current_span("probe.redis.connectivity")
        if tracer
        else nullcontext()
    )

    with span_context as span:
        try:
            if span:
                # Use span helper for consistent attribute setting and resource updates
                from chaosotel.core.trace_core import set_db_span_attributes
                set_db_span_attributes(
                    span,
                    db_system=db_system,
                    db_name=database,
                    host=host,
                    port=port,
                    db_operation="probe",
                    chaos_activity="redis_connectivity_probe",
                    chaos_action="connectivity_probe",
                    chaos_operation="probe",
                )

            r = redis.Redis(host=host, port=port, password=password)

            r.ping()

            probe_time_ms = (time.time() - start) * 1000

            tags = get_metric_tags(
                db_name=database, db_system=db_system, db_operation="probe"
            )

            metrics.record_db_query_latency(
                probe_time_ms,
                db_system=db_system,
                db_name=database,
                db_operation="probe",
                tags=tags,
            )

            metrics.record_db_query_count(
                db_system=db_system,
                db_name=database,
                db_operation="probe",
                count=1,
                tags=tags,
            )

            if span:
                span.set_status(StatusCode.OK)

            logger.info(
                f"Redis probe OK: {probe_time_ms:.2f}ms",
                extra={"probe_time_ms": probe_time_ms},
            )

            flush()

            return True

        except Exception as e:
            metrics.record_db_error(
                db_system=db_system,
                error_type=type(e).__name__,
                db_name=database,
            )

            if span:
                span.record_exception(e)

                span.set_status(StatusCode.ERROR, str(e))

            logger.error(f"Redis probe failed: {str(e)}", extra={"error": str(e)})

            flush()

            return False
