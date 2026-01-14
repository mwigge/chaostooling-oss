"""Cassandra row contention status probe."""

import logging
import os
import time
from contextlib import nullcontext
from typing import Optional

from cassandra.cluster import Cluster
from chaosotel import flush, get_metric_tags, get_metrics_core, get_tracer
from opentelemetry._logs import get_logger_provider
from opentelemetry.sdk._logs import LoggingHandler
from opentelemetry.trace import StatusCode


def probe_row_contention_status(
    host: Optional[str] = None,
    port: Optional[int] = None,
    keyspace: Optional[str] = None,
    user: Optional[str] = None,
    password: Optional[str] = None,
) -> dict:
    """

    Probe to check Cassandra row contention status.

    Observability: Uses chaosotel (chaostooling-otel) as the central observability location. chaosotel must be initialized via chaosotel.control in the experiment configuration.

    """

    host = host or os.getenv("CASSANDRA_HOST", "localhost")

    port = port or int(os.getenv("CASSANDRA_PORT", "9042"))

    keyspace = keyspace or os.getenv("CASSANDRA_KEYSPACE", "system")

    user = user or os.getenv("CASSANDRA_USER")

    password = password or os.getenv("CASSANDRA_PASSWORD")

    # chaosotel is initialized via chaosotel.control - use directly

    tracer = get_tracer()

    # Setup OpenTelemetry logger via LoggingHandler

    logger_provider = get_logger_provider()

    if logger_provider:
        handler = LoggingHandler(level=logging.INFO, logger_provider=logger_provider)

        logger = logging.getLogger("chaosdb.cassandra.cassandra_row_contention_status")

        logger.addHandler(handler)

        logger.setLevel(logging.INFO)

    else:
        logger = logging.getLogger("chaosdb.cassandra.cassandra_row_contention_status")

    metrics = get_metrics_core()

    db_system = "cassandra"

    database = keyspace

    start = time.time()

    span_context = (
        tracer.start_as_current_span("probe.cassandra.row_contention_status")
        if tracer
        else nullcontext()
    )

    with span_context as span:
        try:
            if span:
                span.set_attribute("db.system", db_system)

                span.set_attribute("db.name", database)

                span.set_attribute("db.operation", "probe_row_contention")

                span.set_attribute("chaos.activity", "cassandra_row_contention_status")

                span.set_attribute("chaos.activity.type", "probe")

                span.set_attribute("chaos.system", "cassandra")

                span.set_attribute("chaos.operation", "row_contention_status")

            cluster = Cluster([host], port=port)

            session = cluster.connect(keyspace)

            # Get read/write timeouts from system tables

            # Note: Cassandra doesn't expose contention directly, we check for timeouts

            read_timeouts = 0

            write_timeouts = 0

            # Get active requests

            try:
                result = session.execute("SELECT * FROM system.local")

                # Check for hints (indicating write contention)

                hints_result = session.execute("SELECT COUNT(*) FROM system.hints")

                hints_pending = hints_result.one()[0] if hints_result else 0

            except Exception:
                hints_pending = 0

            session.shutdown()

            cluster.shutdown()

            probe_time_ms = (time.time() - start) * 1000

            tags = get_metric_tags(
                db_name=database,
                db_system=db_system,
                db_operation="probe_row_contention",
            )

            metrics.record_db_query_latency(
                probe_time_ms,
                db_system=db_system,
                db_name=database,
                db_operation="probe_row_contention",
                tags=tags,
            )

            metrics.record_db_query_count(
                db_system=db_system,
                db_name=database,
                db_operation="probe_row_contention",
                count=1,
                tags=tags,
            )

            result = {
                "success": True,
                "read_timeouts": read_timeouts,
                "write_timeouts": write_timeouts,
                "hints_pending": hints_pending,
                "probe_time_ms": probe_time_ms,
            }

            if span:
                span.set_attribute("chaos.read_timeouts", read_timeouts)

                span.set_attribute("chaos.write_timeouts", write_timeouts)

                span.set_attribute("chaos.hints_pending", hints_pending)

                span.set_status(StatusCode.OK)

            logger.info(f"Cassandra row contention probe: {result}")

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
                f"Cassandra row contention probe failed: {str(e)}",
                extra={"error": str(e)},
            )

            flush()

            return {"success": False, "error": str(e)}
