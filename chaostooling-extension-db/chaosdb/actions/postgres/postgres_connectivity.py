import logging
import os
import time
from typing import Any, Dict, Optional

import psycopg2
from chaosotel import (
    ensure_initialized,
    flush,
    get_logger,
    get_logger_provider,
    get_metric_tags,
    get_metrics_core,
    get_tracer,
)
from opentelemetry.sdk._logs import LoggingHandler
from opentelemetry.trace import StatusCode

from chaosdb.common.connection import create_postgres_connection


def test_postgres_connection(
    host: Optional[str] = None,
    port: Optional[int] = None,
    database: Optional[str] = None,
    user: Optional[str] = None,
    password: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Simple connectivity check against PostgreSQL with chaosotel tracing/metrics.
    """
    from chaosdb.common.constants import DatabaseDefaults

    host = host or os.getenv("POSTGRES_HOST", DatabaseDefaults.POSTGRES_DEFAULT_HOST)
    port = port or int(os.getenv("POSTGRES_PORT", str(DatabaseDefaults.POSTGRES_PORT)))
    database = database or os.getenv(
        "POSTGRES_DB", DatabaseDefaults.POSTGRES_DEFAULT_DB
    )
    user = user or os.getenv("POSTGRES_USER", DatabaseDefaults.POSTGRES_DEFAULT_USER)
    password = password or os.getenv("POSTGRES_PASSWORD", "")

    ensure_initialized()
    db_system = os.getenv("DB_SYSTEM", "postgresql")
    metrics = get_metrics_core()

    # Setup OpenTelemetry logger via LoggingHandler
    logger_provider = get_logger_provider()
    if logger_provider:
        handler = LoggingHandler(level=logging.INFO, logger_provider=logger_provider)
        logger = logging.getLogger("chaosdb.postgres.test_postgres_connection")
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
    else:
        logger = logging.getLogger("chaosdb.postgres.test_postgres_connection")
    tracer = get_tracer()
    logger = get_logger()
    start = time.time()
    span = None

    try:
        with tracer.start_as_current_span("test.postgres.connection") as span:
            span.set_attribute("db.system", db_system)
            span.set_attribute("db.name", database)
            span.set_attribute("db.user", user)
            span.set_attribute("network.peer.address", host)
            span.set_attribute("network.peer.port", port)
            span.set_attribute("db.operation", "connect")
            span.set_attribute("chaos.activity", "postgresql_connectivity")
            span.set_attribute("chaos.activity.type", "action")
            span.set_attribute("chaos.system", "postgresql")
            span.set_attribute("chaos.operation", "connectivity")

            conn = create_postgres_connection(
                host=host,
                port=port,
                database=database,
                user=user,
                password=password,
            )
            cursor = conn.cursor()
            query_start = time.time()
            cursor.execute("SELECT 1")
            cursor.fetchone()
            query_time_ms = (time.time() - query_start) * 1000
            cursor.close()
            conn.close()

            connection_time_ms = (time.time() - start) * 1000
            tags = get_metric_tags(
                db_name=database,
                db_system=db_system,
                db_operation="connect",
            )
            metrics.record_db_query_latency(
                query_time_ms,
                db_system=db_system,
                db_name=database,
                db_operation="connect",
                tags=tags,
            )
            metrics.record_db_query_count(
                db_system=db_system,
                db_name=database,
                db_operation="connect",
                count=1,
                tags=tags,
            )

            span.set_status(StatusCode.OK)
            logger.info(
                f"Postgres connection OK: {connection_time_ms:.2f}ms",
                extra={"connection_time_ms": connection_time_ms},
            )
            flush()
            return {
                "success": True,
                "connection_time_ms": connection_time_ms,
                "query_time_ms": query_time_ms,
                "database": database,
                "host": host,
            }
    except psycopg2.OperationalError as e:
        logger.error(f"PostgreSQL connection failed: {e}")
        if metrics:
            metrics.record_db_error(
                db_system=db_system,
                error_type=type(e).__name__,
                db_name=database,
            )
        if span:
            span.set_status(StatusCode.ERROR, str(e))
        flush()
        return {"success": False, "error": f"Connection error: {e}"}
    except psycopg2.Error as e:
        logger.error(f"PostgreSQL database error: {e}")
        if metrics:
            metrics.record_db_error(
                db_system=db_system,
                error_type=type(e).__name__,
                db_name=database,
            )
        if span:
            span.set_status(StatusCode.ERROR, str(e))
        flush()
        return {"success": False, "error": f"Database error: {e}"}
    except Exception as e:
        logger.error(
            f"Unexpected error testing PostgreSQL connection: {e}", exc_info=True
        )
        if metrics:
            metrics.record_db_error(
                db_system=db_system,
                error_type=type(e).__name__,
                db_name=database,
            )
        if span:
            span.set_status(StatusCode.ERROR, str(e))
        flush()
        return {"success": False, "error": f"Unexpected error: {e}"}
