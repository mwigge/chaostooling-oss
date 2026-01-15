"""MSSQL connection pool exhaustion status probe."""

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


def probe_pool_exhaustion_status(
    host: Optional[str] = None,
    port: Optional[int] = None,
    database: Optional[str] = None,
    user: Optional[str] = None,
    password: Optional[str] = None,
    driver: Optional[str] = None,
) -> dict:
    """

    Probe to check MSSQL connection pool exhaustion status.



    Observability: Uses chaosotel (chaostooling-otel) as the central

    observability location. chaosotel must be initialized via chaosotel.control in

    the experiment configuration.

    """

    host = host or os.getenv("MSSQL_HOST", "localhost")

    port = port or int(os.getenv("MSSQL_PORT", "1433"))

    database = database or os.getenv("MSSQL_DB", "master")

    user = user or os.getenv("MSSQL_USER", "sa")

    password = password or os.getenv("MSSQL_PASSWORD", "")

    driver = driver or os.getenv("MSSQL_DRIVER", "ODBC Driver 18 for SQL Server")

    # chaosotel is initialized via chaosotel.control - use directly

    tracer = get_tracer()

    # Setup OpenTelemetry logger via LoggingHandler

    logger_provider = get_logger_provider()

    if logger_provider:
        handler = LoggingHandler(level=logging.INFO, logger_provider=logger_provider)

        logger = logging.getLogger("chaosdb.mssql.mssql_pool_exhaustion_status")

        logger.addHandler(handler)

        logger.setLevel(logging.INFO)

    else:
        logger = logging.getLogger("chaosdb.mssql.mssql_pool_exhaustion_status")

    metrics = get_metrics_core()

    db_system = "mssql"

    start = time.time()

    # Build connection string

    connection_string = (
        f"DRIVER={{{driver}}};"
        f"SERVER={host},{port};"
        f"DATABASE={database};"
        f"UID={user};"
        f"PWD={password};"
        "TrustServerCertificate=yes;"
    )

    span_context = (
        tracer.start_as_current_span("probe.mssql.pool_exhaustion_status")
        if tracer
        else nullcontext()
    )

    with span_context as span:
        try:
            if span:
                span.set_attribute("db.system", db_system)

                span.set_attribute("db.name", database)

                span.set_attribute("db.operation", "probe_pool_exhaustion")

                span.set_attribute("chaos.activity", "mssql_pool_exhaustion_status")

                span.set_attribute("chaos.activity.type", "probe")

                span.set_attribute("chaos.system", "mssql")

                span.set_attribute("chaos.operation", "pool_exhaustion_status")

            conn = pyodbc.connect(connection_string, timeout=5)

            cursor = conn.cursor()

            # Get max connections

            cursor.execute("SELECT @@MAX_CONNECTIONS")

            max_connections = int(cursor.fetchone()[0])

            # Get current connections

            cursor.execute(
                """

                SELECT COUNT(*)

                FROM sys.dm_exec_connections

                WHERE database_id = DB_ID(?)

            """,
                database,
            )

            current_connections = cursor.fetchone()[0]

            # Get active connections

            cursor.execute(
                """

                SELECT COUNT(*)

                FROM sys.dm_exec_requests

                WHERE database_id = DB_ID(?) AND status = 'running'

            """,
                database,
            )

            active_connections = cursor.fetchone()[0]

            idle_connections = current_connections - active_connections

            connection_utilization = (
                (current_connections / max_connections * 100)
                if max_connections > 0
                else 0
            )

            cursor.close()

            conn.close()

            probe_time_ms = (time.time() - start) * 1000

            tags = get_metric_tags(
                db_name=database,
                db_system=db_system,
                db_operation="probe_pool_exhaustion",
            )

            metrics.record_db_query_latency(
                probe_time_ms,
                db_system=db_system,
                db_name=database,
                db_operation="probe_pool_exhaustion",
                tags=tags,
            )

            metrics.record_db_query_count(
                db_system=db_system,
                db_name=database,
                db_operation="probe_pool_exhaustion",
                count=1,
                tags=tags,
            )

            # Record connection pool utilization metric
            metrics.record_db_connection_pool_utilization(
                db_system=db_system,
                utilization_percent=connection_utilization,
                db_name=database,
                tags=tags,
            )

            result = {
                "success": True,
                "current_connections": current_connections,
                "active_connections": active_connections,
                "idle_connections": idle_connections,
                "max_connections": max_connections,
                "connection_utilization_percent": connection_utilization,
                "available_connections": max_connections - current_connections,
                "probe_time_ms": probe_time_ms,
            }

            if span:
                span.set_attribute("chaos.current_connections", current_connections)

                span.set_attribute("chaos.active_connections", active_connections)

                span.set_attribute(
                    "chaos.connection_utilization_percent", connection_utilization
                )

                span.set_status(StatusCode.OK)

            logger.info(f"MSSQL pool exhaustion probe: {result}")

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
                f"MSSQL pool exhaustion probe failed: {str(e)}", extra={"error": str(e)}
            )

            flush()

            return {"success": False, "error": str(e)}
