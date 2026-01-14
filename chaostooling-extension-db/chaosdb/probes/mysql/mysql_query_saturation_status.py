"""MySQL query saturation status probe."""

import logging
import os
import time
from contextlib import nullcontext
from typing import Optional

import mysql.connector
from chaosotel import flush, get_metric_tags, get_metrics_core, get_tracer
from opentelemetry._logs import get_logger_provider
from opentelemetry.sdk._logs import LoggingHandler
from opentelemetry.trace import StatusCode


def probe_query_saturation_status(
    host: Optional[str] = None,
    port: Optional[int] = None,
    database: Optional[str] = None,
    user: Optional[str] = None,
    password: Optional[str] = None,
) -> dict:
    """
    Probe to check query saturation status - measures active query load.

    Returns:
        Dict with query metrics. Observability via `chaosotel` is best-effort –
        if not initialized, probe still runs but tracing/metrics are skipped.
    """
    # Handle string input from Chaos Toolkit configuration
    if port is not None:
        port = int(port) if isinstance(port, str) else port

    host = host or os.getenv("MYSQL_HOST", "localhost")
    port = port or int(os.getenv("MYSQL_PORT", "3306"))
    database = database or os.getenv("MYSQL_DB", "testdb")
    user = user or os.getenv("MYSQL_USER", "root")
    password = password or os.getenv("MYSQL_PASSWORD", "")

    # chaosotel is initialized via chaosotel.control - use directly
    tracer = get_tracer()
    # Setup OpenTelemetry logger via LoggingHandler
    logger_provider = get_logger_provider()
    if logger_provider:
        handler = LoggingHandler(level=logging.INFO, logger_provider=logger_provider)
        logger = logging.getLogger("chaosdb.mysql.mysql_query_saturation_status")
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
    else:
        logger = logging.getLogger("chaosdb.mysql.mysql_query_saturation_status")
    metrics = get_metrics_core()

    db_system = os.getenv("DB_SYSTEM", "mysql")
    start = time.time()

    span_context = (
        tracer.start_as_current_span("probe.mysql.query_saturation_status")
        if tracer
        else nullcontext()
    )

    with span_context as span:
        try:
            if span:
                span.set_attribute("db.system", db_system)
                span.set_attribute("db.name", database)
                span.set_attribute("db.operation", "probe_query_saturation")
                span.set_attribute("chaos.activity", "mysql_query_saturation_status")
                span.set_attribute("chaos.activity.type", "probe")
                span.set_attribute("chaos.system", "mysql")
                span.set_attribute("chaos.operation", "query_saturation_status")

            conn = mysql.connector.connect(
                host=host,
                port=port,
                database=database,
                user=user,
                password=password,
                connect_timeout=5,
            )
            cursor = conn.cursor()

            # Check active queries
            cursor.execute(
                """
                SELECT COUNT(*)
                FROM information_schema.PROCESSLIST
                WHERE DB = %s AND COMMAND != 'Sleep'
            """,
                (database,),
            )
            active_queries = cursor.fetchone()[0]

            # Check total connections
            cursor.execute("SHOW STATUS LIKE 'Threads_connected'")
            total_connections = int(cursor.fetchone()[1])

            # Check max connections
            cursor.execute("SHOW VARIABLES LIKE 'max_connections'")
            max_connections = int(cursor.fetchone()[1])

            connection_utilization = (
                (total_connections / max_connections * 100)
                if max_connections > 0
                else 0
            )

            cursor.close()
            conn.close()

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
                "active_queries": active_queries,
                "total_connections": total_connections,
                "max_connections": max_connections,
                "connection_utilization_percent": connection_utilization,
                "probe_time_ms": probe_time_ms,
            }

            if span:
                span.set_attribute("chaos.active_queries", active_queries)
                span.set_attribute("chaos.total_connections", total_connections)
                span.set_attribute(
                    "chaos.connection_utilization_percent", connection_utilization
                )
                span.set_status(StatusCode.OK)

            logger.info(f"MySQL query saturation probe: {result}")
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
                f"MySQL query saturation probe failed: {str(e)}",
                extra={"error": str(e)},
            )
            flush()
            raise
