"""Cassandra query saturation status probe."""

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


def probe_query_saturation_status(
    host: Optional[str] = None,
    port: Optional[int] = None,
    keyspace: Optional[str] = None,
    user: Optional[str] = None,
    password: Optional[str] = None,
) -> dict:
    """

    Probe to check Cassandra query saturation status.

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

        logger = logging.getLogger(
            "chaosdb.cassandra.cassandra_query_saturation_status"
        )

        logger.addHandler(handler)

        logger.setLevel(logging.INFO)

    else:
        logger = logging.getLogger(
            "chaosdb.cassandra.cassandra_query_saturation_status"
        )

    metrics = get_metrics_core()

    db_system = "cassandra"

    database = keyspace

    start = time.time()


    span_context = (
        tracer.start_as_current_span("probe.cassandra.query_saturation_status")
        if tracer
        else nullcontext()
    )

    with span_context as span:
        try:
            if span:
                span.set_attribute("db.system", db_system)

                span.set_attribute("db.name", database)

                span.set_attribute("db.operation", "probe_query_saturation")

                span.set_attribute(
                    "chaos.activity", "cassandra_query_saturation_status"
                )

                span.set_attribute("chaos.activity.type", "probe")

                span.set_attribute("chaos.system", "cassandra")

                span.set_attribute("chaos.operation", "query_saturation_status")

            cluster = Cluster([host], port=port)

            session = cluster.connect(keyspace)

            # Get native connections

            try:
                result = session.execute(
                    "SELECT native_transport_active FROM system.local"
                )

                native_connections = result.one()[0] if result else 0

            except Exception:
                native_connections = 0

            # Get client requests

            try:
                result = session.execute("SELECT client_requests FROM system.local")

                client_requests = result.one()[0] if result else 0

            except Exception:
                client_requests = 0

            session.shutdown()

            cluster.shutdown()

            probe_time_ms = (time.time() - start) * 1000

            tags = get_metric_tags(
                db_name=database,
                db_system=db_system,
                db_operation="probe_query_saturation",
            )

            metrics.record_db_query_latency(
                probe_time_ms,
                db_system=db_system,
                db_name=database,
                db_operation="probe_query_saturation",
                tags=tags,
            )

            metrics.record_db_query_count(
                db_system=db_system,
                db_name=database,
                db_operation="probe_query_saturation",
                count=1,
                tags=tags,
            )

            result = {
                "success": True,
                "native_connections": native_connections,
                "client_requests": client_requests,
                "probe_time_ms": probe_time_ms,
            }

            if span:
                span.set_attribute("chaos.native_connections", native_connections)

                span.set_attribute("chaos.client_requests", client_requests)

                span.set_status(StatusCode.OK)

            logger.info(f"Cassandra query saturation probe: {result}")

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
                f"Cassandra query saturation probe failed: {str(e)}",
                extra={"error": str(e)},
            )

            flush()

            return {"success": False, "error": str(e)}
