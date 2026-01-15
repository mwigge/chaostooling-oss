import os
import time
from typing import Optional

import pyodbc  # pip install pyodbc -- requires system ODBC driver for MSSQL
from chaosotel import (ensure_initialized, flush, get_logger, get_metric_tags,
                       get_metrics_core, get_tracer)
from opentelemetry.trace import StatusCode

# Requires: pyodbc, and the system ODBC driver for SQL Server (ODBC Driver 17 or 18 for SQL Server)
# See MS docs: https://docs.microsoft.com/en-us/sql/connect/odbc/linux-mac/installing-the-microsoft-odbc-driver-for-sql-server


def test_mssql_connection(
    host: Optional[str] = None,
    port: Optional[int] = None,
    database: Optional[str] = None,
    user: Optional[str] = None,
    password: Optional[str] = None,
    driver: Optional[str] = None,
) -> dict:
    host = host or os.getenv("MSSQL_HOST", "localhost")
    port = port or int(os.getenv("MSSQL_PORT", "1433"))
    database = database or os.getenv("MSSQL_DB", "master")
    user = user or os.getenv("MSSQL_USER", "sa")
    password = password or os.getenv("MSSQL_PASSWORD", "yourStrong(!)Password")
    driver = driver or os.getenv("MSSQL_DRIVER", "FreeTDS")
    ensure_initialized()
    db_system = os.getenv("DB_SYSTEM", "mssql")
    metrics = get_metrics_core()
    tracer = get_tracer()
    logger = get_logger()
    start = time.time()
    connection_string = (
        f"DRIVER={{{driver}}};SERVER={host},{port};DATABASE={database};UID={user};PWD={password};"
        "Encrypt=no"
    )
    try:
        with tracer.start_as_current_span("test.mssql.connection") as span:
            span.set_attribute("db.system", "mssql")
            span.set_attribute("db.name", database)
            span.set_attribute("network.peer.address", host)
            span.set_attribute("network.peer.port", port)
            span.set_attribute("db.operation", "connect")
            span.set_attribute("chaos.activity", "mssql_connectivity")
            span.set_attribute("chaos.activity.type", "action")
            span.set_attribute("chaos.system", "mssql")
            span.set_attribute("chaos.operation", "connectivity")
            conn = pyodbc.connect(connection_string, timeout=5)
            cursor = conn.cursor()
            cursor.execute("SELECT 1")
            cursor.fetchone()
            cursor.close()
            conn.close()
            connection_time_ms = (time.time() - start) * 1000
            tags = get_metric_tags(
                db_name=database, db_system="mssql", db_operation="connectivity_test"
            )
            metrics.record_db_query_latency(
                connection_time_ms,
                db_system="mssql",
                db_name=database,
                db_operation="connectivity_test",
                tags=tags,
            )
            metrics.record_db_query_count(
                db_system=db_system, db_name=database, count=1
            )
            span.set_status(StatusCode.OK)
            logger.info(
                f"MSSQL connection OK: {connection_time_ms:.2f}ms",
                extra={"connection_time_ms": connection_time_ms},
            )
            flush()
            return dict(
                success=True,
                connection_time_ms=connection_time_ms,
                database=database,
                host=host,
            )
    except Exception as e:
        span.set_status(StatusCode.ERROR, str(e))
        metrics.record_db_error(
            db_system=db_system,
            error_type=type(e).__name__,
            db_name=database,
        )
        logger.error(f"MSSQL connection failed: {e}", extra={"error": str(e)})
        flush()
        raise
