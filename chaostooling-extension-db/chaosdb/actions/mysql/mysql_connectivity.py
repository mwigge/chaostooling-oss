import os
import time
from typing import Any, Optional

from chaosdb.common.connection import create_mysql_connection
from chaosdb.common.constants import DatabaseDefaults
from chaosotel import (
    ensure_initialized,
    flush,
    get_logger,
    get_metric_tags,
    get_metrics_core,
    get_tracer,
)
from opentelemetry.trace import StatusCode


def test_mysql_connection(
    host: Optional[str] = None,
    port: Optional[int] = None,
    database: Optional[str] = None,
    user: Optional[str] = None,
    password: Optional[str] = None,
) -> dict[str, Any]:
    """
    Simple connectivity check against MySQL with chaosotel tracing/metrics.
    """
    # Use constants for defaults
    host = host or os.getenv("MYSQL_HOST", DatabaseDefaults.MYSQL_DEFAULT_HOST)
    port = port or int(os.getenv("MYSQL_PORT", str(DatabaseDefaults.MYSQL_PORT)))
    database = database or os.getenv("MYSQL_DB", DatabaseDefaults.MYSQL_DEFAULT_DB)
    user = user or os.getenv("MYSQL_USER", DatabaseDefaults.MYSQL_DEFAULT_USER)
    password = password or os.getenv("MYSQL_PASSWORD", "")

    ensure_initialized()
    db_system = os.getenv("DB_SYSTEM", "mysql")
    metrics = get_metrics_core()
    tracer = get_tracer()
    logger = get_logger()
    start = time.time()
    span = None

    try:
        with tracer.start_as_current_span("test.mysql.connection") as span:
            span.set_attribute("db.system", db_system)
            span.set_attribute("db.name", database)
            span.set_attribute("db.user", user)
            span.set_attribute("network.peer.address", host)
            span.set_attribute("network.peer.port", port)
            span.set_attribute("db.operation", "connect")
            span.set_attribute("chaos.activity", "mysql_connectivity")
            span.set_attribute("chaos.activity.type", "action")
            span.set_attribute("chaos.system", "mysql")
            span.set_attribute("chaos.operation", "connectivity")

            conn = create_mysql_connection(
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
                f"MySQL connection OK: {connection_time_ms:.2f}ms",
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
    except Exception as e:
        metrics.record_db_error(
            db_system=db_system,
            error_type=type(e).__name__,
            db_name=database,
        )
        if span:
            span.set_status(StatusCode.ERROR, str(e))
        logger.error(
            f"MySQL connection failed: {e}",
            extra={"error": str(e)},
        )
        flush()
        raise
