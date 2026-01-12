"""MSSQL query saturation status probe."""

import os

import logging

from contextlib import nullcontext

import pyodbc

import time

from typing import Optional, Dict

from chaosotel import get_tracer, get_metrics_core, get_metric_tags, flush

from opentelemetry.sdk._logs import LoggingHandler

from opentelemetry._logs import get_logger_provider

import logging

from opentelemetry.trace import StatusCode



def probe_query_saturation_status(

    host: Optional[str] = None,

    port: Optional[int] = None,

    database: Optional[str] = None,

    user: Optional[str] = None,

    password: Optional[str] = None,

    driver: Optional[str] = None,

) -> Dict:

    """

    Probe to check MSSQL query saturation status.

    

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

        logger = logging.getLogger("chaosdb.mssql.mssql_query_saturation_status")

        logger.addHandler(handler)

        logger.setLevel(logging.INFO)

    else:

        logger = logging.getLogger("chaosdb.mssql.mssql_query_saturation_status")

    metrics = get_metrics_core()

    

    db_system = "mssql"

    start = time.time()

    span = None

    

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

            tracer.start_as_current_span("probe.mssql.query_saturation_status")

            if tracer

            else nullcontext()

        )

        

    with span_context as span:

        try:





        

            if span:

                span.set_attribute("db.system", db_system)

                span.set_attribute("db.name", database)

                span.set_attribute("db.operation", "probe_query_saturation")

                span.set_attribute("chaos.activity", "mssql_query_saturation_status")

                span.set_attribute("chaos.activity.type", "probe")

                span.set_attribute("chaos.system", "mssql")

                span.set_attribute("chaos.operation", "query_saturation_status")

            

            conn = pyodbc.connect(connection_string, timeout=5)

            cursor = conn.cursor()

            

            # Check active queries

            cursor.execute("""

                SELECT COUNT(*) 

                FROM sys.dm_exec_requests 

                WHERE database_id = DB_ID(?) AND status = 'running'

            """, database)

            active_queries = cursor.fetchone()[0]

            

            # Check total connections

            cursor.execute("""

                SELECT COUNT(*) 

                FROM sys.dm_exec_connections 

                WHERE database_id = DB_ID(?)

            """, database)

            total_connections = cursor.fetchone()[0]

            

            # Get max connections

            cursor.execute("SELECT @@MAX_CONNECTIONS")

            max_connections = int(cursor.fetchone()[0])

            

            connection_utilization = (total_connections / max_connections * 100) if max_connections > 0 else 0

            

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

                "probe_time_ms": probe_time_ms

            }

            

            if span:

                span.set_attribute("chaos.active_queries", active_queries)

                span.set_attribute("chaos.total_connections", total_connections)

                span.set_attribute("chaos.connection_utilization_percent", connection_utilization)

                span.set_status(StatusCode.OK)

            

            logger.info(f"MSSQL query saturation probe: {result}")

            flush()

            return result

        except Exception as e:
            db_system=db_system,

            error_type=type(e).__name__,

            db_name=database,

        )

        if span:

            span.record_exception(e)

            span.set_status(StatusCode.ERROR, str(e))

        logger.error(f"MSSQL query saturation probe failed: {str(e)}", extra={"error": str(e)})

        flush()

        return {"success": False, "error": str(e)}
