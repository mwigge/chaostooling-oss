"""MySQL lock storm status probe."""

import os

import logging

from contextlib import nullcontext

import mysql.connector

import time

from typing import Optional, Dict

from chaosotel import (

    flush,

    get_metrics_core,

    get_metric_tags,

    get_tracer,

)

from opentelemetry.sdk._logs import LoggingHandler

from opentelemetry._logs import get_logger_provider

from opentelemetry.trace import StatusCode



def probe_lock_storm_status(

    host: Optional[str] = None,

    port: Optional[int] = None,

    database: Optional[str] = None,

    user: Optional[str] = None,

    password: Optional[str] = None,

) -> Dict:

    """

    Probe to check lock storm status - measures lock contention and deadlocks.

    Observability: Uses chaosotel (chaostooling-otel) as the central observability location. chaosotel must be initialized via chaosotel.control in the experiment configuration.

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

        logger = logging.getLogger("chaosdb.mysql.mysql_lock_storm_status")

        logger.addHandler(handler)

        logger.setLevel(logging.INFO)

    else:

        logger = logging.getLogger("chaosdb.mysql.mysql_lock_storm_status")

    metrics = get_metrics_core()

    

    db_system = "mysql"

    start = time.time()

    span = None

    

    span_context = (

        tracer.start_as_current_span("probe.mysql.lock_storm_status")

        if tracer

        else nullcontext()

    )

    

    with span_context as span:

        try:

            if span:

                span.set_attribute("db.system", db_system)

                span.set_attribute("db.name", database)

                span.set_attribute("db.operation", "probe_lock_storm")

                span.set_attribute("chaos.activity", "mysql_lock_storm_status")

                span.set_attribute("chaos.activity.type", "probe")

                span.set_attribute("chaos.system", "mysql")

                span.set_attribute("chaos.operation", "lock_storm_status")

            

            conn = mysql.connector.connect(

                host=host, port=port, database=database,

                user=user, password=password, connect_timeout=5

            )

            cursor = conn.cursor()

            

            # Note: MySQL 8.0+ uses performance_schema.data_locks instead of information_schema.INNODB_LOCKS

            # Check for waiting locks (MySQL 8.0+)

            try:

                cursor.execute("""

                    SELECT COUNT(*) 

                    FROM performance_schema.data_lock_waits

                """)

                waiting_locks = cursor.fetchone()[0]

            except mysql.connector.errors.ProgrammingError:

                # Fallback for older MySQL versions

                waiting_locks = 0

            

            # Check for granted locks (MySQL 8.0+)

            try:

                cursor.execute("""

                    SELECT COUNT(DISTINCT object_schema, object_name, index_name)

                    FROM performance_schema.data_locks

                """)

                granted_locks = cursor.fetchone()[0]

            except mysql.connector.errors.ProgrammingError:

                # Fallback for older MySQL versions

                granted_locks = 0

            

            # Check for deadlocks

            cursor.execute("SHOW STATUS LIKE 'Innodb_deadlocks'")

            deadlock_result = cursor.fetchone()

            deadlocks = int(deadlock_result[1]) if deadlock_result else 0

            

            cursor.close()

            conn.close()

            

            probe_time_ms = (time.time() - start) * 1000

            

            tags = get_metric_tags(

                db_name=database,

                db_system=db_system,

                db_operation="probe_lock_storm",

            )

            metrics.record_db_query_latency(

                probe_time_ms,

                db_system=db_system,

                db_name=database,

                db_operation="probe_lock_storm",

                tags=tags,

            )

            metrics.record_db_query_count(

                db_system=db_system,

                db_name=database,

                db_operation="probe_lock_storm",

                count=1,

                tags=tags,

            )

            

            result = {

                "success": True,

                "waiting_locks": waiting_locks,

                "granted_locks": granted_locks,

                "deadlocks": deadlocks,

                "probe_time_ms": probe_time_ms

            }

            

            if span:

                span.set_attribute("chaos.waiting_locks", waiting_locks)

                span.set_attribute("chaos.granted_locks", granted_locks)

                span.set_attribute("chaos.deadlocks", deadlocks)

                span.set_status(StatusCode.OK)

            

            logger.info(f"MySQL lock storm probe: {result}")

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

            logger.error(f"MySQL lock storm probe failed: {str(e)}", extra={"error": str(e)})

            flush()

            return {"success": False, "error": str(e)}
