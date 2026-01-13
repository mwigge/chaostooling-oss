"""PostgreSQL connectivity probe."""

import logging
import os
import time
from contextlib import nullcontext
from typing import Optional

import psycopg2
from chaosotel import flush, get_metric_tags, get_metrics_core, get_tracer
from opentelemetry._logs import get_logger_provider
from opentelemetry.sdk._logs import LoggingHandler
from opentelemetry.trace import StatusCode

DB_SYSTEM = os.getenv("DB_SYSTEM", "postgresql")


def probe_postgres_connectivity(
    host: Optional[str] = None,
    port: Optional[int] = None,
    database: Optional[str] = None,
    user: Optional[str] = None,
    password: Optional[str] = None,
) -> bool:
    """

    Probe PostgreSQL connectivity.



    Observability: Uses chaosotel (chaostooling-otel) as the central

    observability location. chaosotel must be initialized via chaosotel.control in

    the experiment configuration.

    """

    # Handle string input from Chaos Toolkit configuration

    if port is not None:
        port = int(port) if isinstance(port, str) else port

    host = host or os.getenv("POSTGRES_HOST", "localhost")

    port = port or int(os.getenv("POSTGRES_PORT", "5432"))

    database = database or os.getenv("POSTGRES_DB", "postgres")

    user = user or os.getenv("POSTGRES_USER", "postgres")

    password = password or os.getenv("POSTGRES_PASSWORD", "")

    # chaosotel is initialized via chaosotel.control - use directly

    tracer = get_tracer()

    metrics = get_metrics_core()

    # Setup OpenTelemetry logger via LoggingHandler

    logger_provider = get_logger_provider()

    if logger_provider:
        handler = LoggingHandler(level=logging.INFO, logger_provider=logger_provider)

        logger = logging.getLogger("chaosdb.postgres.connectivity")

        logger.addHandler(handler)

        logger.setLevel(logging.INFO)

    else:
        logger = logging.getLogger("chaosdb.postgres.connectivity")

    start = time.time()

    span_context = (
        tracer.start_as_current_span("probe.postgres.connectivity")
        if tracer
        else nullcontext()
    )

    with span_context as span:
        try:
            if span:
                span.set_attribute("db.system", DB_SYSTEM)

                span.set_attribute("db.name", database)

                span.set_attribute("db.user", user)

                span.set_attribute("network.peer.address", host)

                span.set_attribute("network.peer.port", port)
                span.set_attribute("service.name", host)

                span.set_attribute("db.operation", "probe")

                span.set_attribute("chaos.activity", "postgresql_connectivity_probe")

                span.set_attribute("chaos.activity.type", "probe")

                span.set_attribute("chaos.system", "postgresql")

                span.set_attribute("chaos.operation", "connectivity")

            conn = psycopg2.connect(
                host=host,
                port=port,
                database=database,
                user=user,
                password=password,
                connect_timeout=5,
            )

            conn.close()

            probe_time_ms = (time.time() - start) * 1000

            tags = get_metric_tags(
                db_name=database,
                db_system=DB_SYSTEM,
                db_operation="probe",
            )

            metrics.record_db_query_latency(
                probe_time_ms,
                db_system=DB_SYSTEM,
                db_name=database,
                db_operation="probe",
                tags=tags,
            )

            metrics.record_db_query_count(
                db_system=DB_SYSTEM,
                db_name=database,
                db_operation="probe",
                count=1,
                tags=tags,
            )

            if span:
                span.set_status(StatusCode.OK)

            logger.info(
                f"Postgres probe OK: {probe_time_ms:.2f}ms",
                extra={"probe_time_ms": probe_time_ms},
            )

            flush()

            return True
        except Exception as e:
            metrics.record_db_error(
                db_system=DB_SYSTEM,
                error_type=type(e).__name__,
                db_name=database,
            )
            if span:
                span.record_exception(e)
                span.set_status(StatusCode.ERROR, str(e))
            logger.error(f"Postgres probe failed: {str(e)}", extra={"error": str(e)})
            flush()
            return False
