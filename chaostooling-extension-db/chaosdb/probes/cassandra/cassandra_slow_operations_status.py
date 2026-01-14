"""Cassandra slow operations status probe."""

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


def probe_slow_operations_status(
    host: Optional[str] = None,
    port: Optional[int] = None,
    keyspace: Optional[str] = None,
    user: Optional[str] = None,
    password: Optional[str] = None,
) -> dict:
    """

    Probe to check Cassandra slow operations status.

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

        logger = logging.getLogger("chaosdb.cassandra.cassandra_slow_operations_status")

        logger.addHandler(handler)

        logger.setLevel(logging.INFO)

    else:
        logger = logging.getLogger("chaosdb.cassandra.cassandra_slow_operations_status")

    metrics = get_metrics_core()

    db_system = "cassandra"

    database = keyspace

    start = time.time()

    span_context = (
        tracer.start_as_current_span("probe.cassandra.slow_operations_status")
        if tracer
        else nullcontext()
    )

    with span_context as span:
        try:
            if span:
                span.set_attribute("db.system", db_system)

                span.set_attribute("db.name", database)

                span.set_attribute("db.operation", "probe_slow_operations")

                span.set_attribute("chaos.activity", "cassandra_slow_operations_status")

                span.set_attribute("chaos.activity.type", "probe")

                span.set_attribute("chaos.system", "cassandra")

                span.set_attribute("chaos.operation", "slow_operations_status")

            cluster = Cluster([host], port=port)

            session = cluster.connect(keyspace)

            # Check for read/write timeouts (indicates slow operations)

            read_timeouts = 0

            write_timeouts = 0

            # Get average read/write latencies from system tables

            try:
                result = session.execute(
                    "SELECT read_latency, write_latency FROM system.local"
                )

                row = result.one()

                read_latency_ms = row[0] if row and row[0] else 0

                write_latency_ms = row[1] if row and row[1] else 0

            except Exception:
                read_latency_ms = 0

                write_latency_ms = 0

            session.shutdown()

            cluster.shutdown()

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
                "read_timeouts": read_timeouts,
                "write_timeouts": write_timeouts,
                "average_read_latency_ms": read_latency_ms,
                "average_write_latency_ms": write_latency_ms,
                "probe_time_ms": probe_time_ms,
            }

            if span:
                span.set_attribute("chaos.read_timeouts", read_timeouts)

                span.set_attribute("chaos.write_timeouts", write_timeouts)

                span.set_status(StatusCode.OK)

            logger.info(f"Cassandra slow operations probe: {result}")

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
                f"Cassandra slow operations probe failed: {str(e)}",
                extra={"error": str(e)},
            )

            flush()

            return {"success": False, "error": str(e)}
