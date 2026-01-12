"""PostgreSQL slow transactions status probe."""

import os

import logging

from contextlib import nullcontext

import psycopg2

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



def probe_slow_transactions_status(

    host: Optional[str] = None,

    port: Optional[int] = None,

    database: Optional[str] = None,

    user: Optional[str] = None,

    password: Optional[str] = None,

) -> Dict:

    """

    Probe to check slow transactions status - measures long-running transactions.

    

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

    # Setup OpenTelemetry logger via LoggingHandler

    logger_provider = get_logger_provider()

    if logger_provider:

        handler = LoggingHandler(level=logging.INFO, logger_provider=logger_provider)

        logger = logging.getLogger("chaosdb.postgres.postgres_slow_transactions_status")

        logger.addHandler(handler)

        logger.setLevel(logging.INFO)

    else:

        logger = logging.getLogger("chaosdb.postgres.postgres_slow_transactions_status")

    metrics = get_metrics_core()

    

    db_system = "postgresql"

    span = None

    start = time.time()

    

    span_context = (

        tracer.start_as_current_span("probe.postgres.slow_transactions_status")

        if tracer

        else nullcontext()

    )

    

    with span_context as span:



    

        try:





    

            if span:

                span.set_attribute("db.system", db_system)

                span.set_attribute("db.name", database)

                span.set_attribute("db.operation", "probe_slow_transactions")

                span.set_attribute("chaos.activity", "postgresql_slow_transactions_status")

                span.set_attribute("chaos.activity.type", "probe")

                span.set_attribute("chaos.system", "postgresql")

                span.set_attribute("chaos.operation", "slow_transactions_status")

            

            conn = psycopg2.connect(

                host=host, port=port, database=database,

                user=user, password=password, connect_timeout=5

            )

            cursor = conn.cursor()

            

            # Check for long-running transactions (> 1 second)

            cursor.execute("""

                SELECT count(*), 

                       COALESCE(AVG(EXTRACT(EPOCH FROM (NOW() - xact_start)) * 1000), 0) as avg_duration_ms,

                       COALESCE(MAX(EXTRACT(EPOCH FROM (NOW() - xact_start)) * 1000), 0) as max_duration_ms

                FROM pg_stat_activity 

                WHERE state = 'active' 

                  AND xact_start IS NOT NULL

                  AND datname = %s

                  AND EXTRACT(EPOCH FROM (NOW() - xact_start)) > 1

            """, (database,))

            result = cursor.fetchone()

            long_running_txns = result[0] if result else 0

            avg_duration_ms = result[1] if result else 0

            max_duration_ms = result[2] if result else 0

            

            # Check total active transactions

            cursor.execute("""

                SELECT count(*) 

                FROM pg_stat_activity 

                WHERE state = 'active' 

                  AND xact_start IS NOT NULL

                  AND datname = %s

            """, (database,))

            active_transactions = cursor.fetchone()[0]

            

            cursor.close()

            conn.close()

            

            probe_time_ms = (time.time() - start) * 1000

            

            tags = get_metric_tags(

            db_name=database,

            db_system=db_system,

                db_operation="probe_slow_transactions",

            )

            metrics.record_db_query_latency(

                probe_time_ms,

            db_system=db_system,

            db_name=database,

                db_operation="probe_slow_transactions",

                tags=tags,

            )

            metrics.record_db_query_count(

            db_system=db_system,

            db_name=database,

                db_operation="probe_slow_transactions",

                count=1,

                tags=tags,

            )

            

            result = {

                "success": True,

                "long_running_transactions": long_running_txns,

                "active_transactions": active_transactions,

                "average_transaction_duration_ms": avg_duration_ms,

                "max_transaction_duration_ms": max_duration_ms,

                "probe_time_ms": probe_time_ms

            }

            

            if span:

                span.set_attribute("chaos.long_running_transactions", long_running_txns)

                span.set_attribute("chaos.active_transactions", active_transactions)

                span.set_attribute("chaos.avg_transaction_duration_ms", float(avg_duration_ms) if avg_duration_ms is not None else 0.0)

                span.set_status(StatusCode.OK)

            

            logger.info(f"Postgres slow transactions probe: {result}")

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
            logger.error(f"Postgres slow transactions probe failed: {str(e)}", extra={"error": str(e)})

            flush()

            return {"success": False, "error": str(e)}
