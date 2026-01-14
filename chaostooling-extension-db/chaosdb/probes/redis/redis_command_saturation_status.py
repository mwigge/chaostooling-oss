"""Redis command saturation status probe."""

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


def probe_command_saturation_status(
    host: Optional[str] = None,
    port: Optional[int] = None,
    password: Optional[str] = None,
) -> dict:
    """

    Probe to check Redis command saturation status.

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

        logger = logging.getLogger("chaosdb.redis.redis_command_saturation_status")

        logger.addHandler(handler)

        logger.setLevel(logging.INFO)

    else:
        logger = logging.getLogger("chaosdb.redis.redis_command_saturation_status")

    metrics = get_metrics_core()

    db_system = "redis"

    database = "redis"

    start = time.time()

    span_context = (
        tracer.start_as_current_span("probe.redis.command_saturation_status")
        if tracer
        else nullcontext()
    )

    with span_context as span:
        try:
            if span:
                span.set_attribute("db.system", db_system)

                span.set_attribute("db.name", database)

                span.set_attribute("chaos.activity", "redis_command_saturation_status")

                span.set_attribute("chaos.activity.type", "probe")

                span.set_attribute("chaos.system", "redis")

                span.set_attribute("chaos.operation", "command_saturation_status")

            r = redis.Redis(
                host=host, port=port, password=password, decode_responses=True
            )

            # Get stats

            info = r.info()

            stats = r.info("stats")

            # Get total commands processed

            total_commands = stats.get("total_commands_processed", 0)

            # Get commands per second

            commands_per_sec = stats.get("instantaneous_ops_per_sec", 0)

            # Get connected clients

            connected_clients = info.get("connected_clients", 0)

            # Get rejected connections

            rejected_connections = info.get("rejected_connections", 0)

            r.close()

            probe_time_ms = (time.time() - start) * 1000

            tags = get_metric_tags(
                db_name=database,
                db_system=db_system,
                db_operation="probe_command_saturation",
            )

            metrics.record_db_query_latency(
                probe_time_ms,
                db_system=db_system,
                db_name=database,
                db_operation="probe_command_saturation",
                tags=tags,
            )

            metrics.record_db_query_count(
                db_system=db_system,
                db_name=database,
                db_operation="probe_command_saturation",
                count=1,
                tags=tags,
            )

            result = {
                "success": True,
                "total_commands_processed": total_commands,
                "commands_per_second": commands_per_sec,
                "connected_clients": connected_clients,
                "rejected_connections": rejected_connections,
                "probe_time_ms": probe_time_ms,
            }

            if span:
                span.set_attribute("chaos.total_commands_processed", total_commands)

                span.set_attribute("chaos.commands_per_second", commands_per_sec)

                span.set_status(StatusCode.OK)

            logger.info(f"Redis command saturation probe: {result}")

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
                f"Redis command saturation probe failed: {str(e)}",
                extra={"error": str(e)},
            )

            flush()

            return {"success": False, "error": str(e)}
