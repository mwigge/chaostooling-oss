"""MSSQL connectivity probe."""

import logging
import os
import time
from contextlib import nullcontext
from typing import Optional

import pyodbc
from chaosotel import flush, get_metric_tags, get_metrics_core, get_tracer
from opentelemetry._logs import get_logger_provider
from opentelemetry.sdk._logs import LoggingHandler
from opentelemetry.trace import StatusCode

# Requires: pyodbc, and the system ODBC driver for SQL Server


def probe_mssql_connectivity(
    host: Optional[str] = None,
    port: Optional[int] = None,
    database: Optional[str] = None,
    user: Optional[str] = None,
    password: Optional[str] = None,
    driver: Optional[str] = None,
) -> bool:
    """

    Probe MSSQL connectivity.



    Observability: Uses chaosotel (chaostooling-otel) as the central

    observability location. chaosotel must be initialized via chaosotel.control in

    the experiment configuration.

    """

    host = host or os.getenv("MSSQL_HOST", "localhost")

    port = port or int(os.getenv("MSSQL_PORT", "1433"))

    database = database or os.getenv("MSSQL_DB", "master")

    user = user or os.getenv("MSSQL_USER", "sa")

    password = password or os.getenv("MSSQL_PASSWORD", "Password123!")

    driver = driver or os.getenv("MSSQL_DRIVER", "FreeTDS")

    # chaosotel is initialized via chaosotel.control - use directly

    tracer = get_tracer()

    # Setup OpenTelemetry logger via LoggingHandler

    logger_provider = get_logger_provider()

    if logger_provider:
        handler = LoggingHandler(level=logging.INFO, logger_provider=logger_provider)

        logger = logging.getLogger("chaosdb.mssql.mssql_connectivity")

        logger.addHandler(handler)

        logger.setLevel(logging.INFO)

    else:
        logger = logging.getLogger("chaosdb.mssql.mssql_connectivity")

    metrics = get_metrics_core()

    db_system = "mssql"

    start = time.time()

    # Build connection string
    # FreeTDS uses different format than Microsoft ODBC Driver
    if driver == "FreeTDS":
        connection_string = (
            f"DRIVER={{{driver}}};"
            f"SERVER={host};"
            f"PORT={port};"
            f"DATABASE={database};"
            f"UID={user};"
            f"PWD={password};"
            "TDS_Version=7.4;"
        )
    else:
        connection_string = (
            f"DRIVER={{{driver}}};"
            f"SERVER={host},{port};"
            f"DATABASE={database};"
            f"UID={user};"
            f"PWD={password};"
            "TrustServerCertificate=yes;"
        )

    span_context = (
        tracer.start_as_current_span("probe.mssql.connectivity")
        if tracer
        else nullcontext()
    )

    with span_context as span:
        try:
            if span:
                span.set_attribute("db.system", db_system)

                span.set_attribute("db.name", database)

                span.set_attribute("network.peer.address", host)

                span.set_attribute("network.peer.port", port)
                span.set_attribute("service.name", host)

                span.set_attribute("db.operation", "probe")

                span.set_attribute("chaos.activity", "mssql_connectivity_probe")

                span.set_attribute("chaos.activity.type", "probe")

                span.set_attribute("chaos.system", "mssql")

                span.set_attribute("chaos.operation", "connectivity")

            conn = pyodbc.connect(connection_string, timeout=5)

            cursor = conn.cursor()

            cursor.execute("SELECT 1")

            cursor.fetchone()

            cursor.close()

            conn.close()

            probe_time_ms = (time.time() - start) * 1000

            tags = get_metric_tags(
                db_name=database,
                db_system=db_system,
                db_operation="probe",
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
                f"MSSQL probe OK: {probe_time_ms:.2f}ms",
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

            logger.error(f"MSSQL probe failed: {str(e)}", extra={"error": str(e)})

        flush()

        return False
