"""PostgreSQL query saturation status probe."""

import os

import logging

from contextlib import nullcontext

import time

from typing import Optional, Dict

import psycopg2

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

) -> Dict:

    """

    Probe to check PostgreSQL query saturation status.

    

    Observability: Uses chaosotel (chaostooling-otel) as the central

    observability location. chaosotel must be initialized via chaosotel.control in

    the experiment configuration.

    """

    # Handle string input from Chaos Toolkit configuration

    if port is not None:

        port = int(port) if isinstance(port, str) else port

    

    host = host or os.getenv("POSTGRES_HOST", "postgres")

    port = port or int(os.getenv("POSTGRES_PORT", "5432"))

    database = database or os.getenv("POSTGRES_DB", "postgres")

    user = user or os.getenv("POSTGRES_USER", "postgres")

    password = password or os.getenv("POSTGRES_PASSWORD", "")

    

    # chaosotel is initialized via chaosotel.control - use directly

    tracer = get_tracer()

    # Setup OpenTelemetry logger via LoggingHandler

    logger_provider = get_logger_provider()

    if logger_provider:

        handler = LoggingHandler(level=logging.INFO, logger_provider=logger_provider)

        logger = logging.getLogger("chaosdb.postgres.postgres_query_saturation_status")

        logger.addHandler(handler)

        logger.setLevel(logging.INFO)

    else:

        logger = logging.getLogger("chaosdb.postgres.postgres_query_saturation_status")

    metrics = get_metrics_core()

    

    db_system = "postgresql"

    start = time.time()

    

    span_context = (

        tracer.start_as_current_span("probe.postgres.query_saturation_status")

        if tracer

        else nullcontext()

    )

    

    with span_context as span:

        try:

            if span:

                span.set_attribute("db.system", db_system)

                span.set_attribute("db.name", database)

                span.set_attribute("db.operation", "probe_query_saturation")

                span.set_attribute("chaos.activity", "postgresql_query_saturation_status")

                span.set_attribute("chaos.activity.type", "probe")

                span.set_attribute("chaos.system", "postgresql")

                span.set_attribute("chaos.operation", "query_saturation_status")

            

            conn = psycopg2.connect(

                host=host, port=port, database=database,

                user=user, password=password, connect_timeout=5

            )

            cursor = conn.cursor()

            

            # Get active queries

            cursor.execute("""

                SELECT COUNT(*) 

                FROM pg_stat_activity 

                WHERE state = 'active' AND query NOT LIKE '%pg_stat_activity%'

            """)

            active_queries = cursor.fetchone()[0]

            

            # Get waiting queries

            cursor.execute("""

                SELECT COUNT(*) 

                FROM pg_stat_activity 

                WHERE wait_event_type IS NOT NULL

            """)

            waiting_queries = cursor.fetchone()[0]

            

            # Get total connections

            cursor.execute("SELECT COUNT(*) FROM pg_stat_activity")

            total_connections = cursor.fetchone()[0]

            

            # Get max connections

            cursor.execute("SHOW max_connections")

            max_connections = int(cursor.fetchone()[0])

            

            connection_utilization = (total_connections / max_connections * 100) if max_connections > 0 else 0

            

            cursor.close()

            conn.close()

            

            probe_time_ms = (time.time() - start) * 1000

            

            # Record metrics via MetricsCore

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

                "waiting_queries": waiting_queries,

                "total_connections": total_connections,

                "max_connections": max_connections,

                "connection_utilization_percent": connection_utilization,

                "probe_time_ms": probe_time_ms

            }

            

            if span:

                span.set_attribute("chaos.active_queries", active_queries)

                span.set_attribute("chaos.waiting_queries", waiting_queries)

                span.set_attribute("chaos.connection_utilization_percent", connection_utilization)

                span.set_status(StatusCode.OK)

            

            logger.info(f"PostgreSQL query saturation probe: {result}")

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
            logger.error(f"PostgreSQL query saturation probe failed: {str(e)}", extra={"error": str(e)})

            flush()

            raise
