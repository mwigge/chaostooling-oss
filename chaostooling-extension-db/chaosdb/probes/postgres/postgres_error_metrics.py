import logging
import os
from contextlib import nullcontext
from typing import Optional

import psycopg2
from chaosotel import flush, get_metrics_core, get_tracer
from opentelemetry.trace import StatusCode

logger = logging.getLogger("chaosdb.postgres.postgres_error_metrics")


def check_query_error_rate(
    host: Optional[str] = None,
    port: Optional[int] = None,
    database: Optional[str] = None,
    user: Optional[str] = None,
    password: Optional[str] = None,
) -> float:
    """
    Check the query error rate (rollback rate) in the PostgreSQL database.
    """
    if port is not None:
        port = int(port) if isinstance(port, str) else port

    host = host or os.getenv("POSTGRES_HOST", "postgres")
    port = port or int(os.getenv("POSTGRES_PORT", "5432"))
    database = database or os.getenv("POSTGRES_DB", "testdb")
    user = user or os.getenv("POSTGRES_USER", "postgres")
    password = password or os.getenv("POSTGRES_PASSWORD", "changeme")

    tracer = get_tracer()
    metrics = get_metrics_core()
    db_system = "postgresql"

    span_context = (
        tracer.start_as_current_span("probe.postgres.error_rate")
        if tracer
        else nullcontext()
    )

    with span_context as span:
        try:
            if span:
                span.set_attribute("db.system", db_system)
                span.set_attribute("db.name", database)
                span.set_attribute("chaos.activity", "postgresql_error_rate")

            conn = psycopg2.connect(
                host=host,
                port=port,
                database=database,
                user=user,
                password=password,
                connect_timeout=5,
            )
            cursor = conn.cursor()

            # Calculate rollback ratio: xact_rollback / (xact_commit + xact_rollback)
            cursor.execute(
                """
                SELECT
                    sum(xact_rollback),
                    sum(xact_commit)
                FROM pg_stat_database
                WHERE datname = %s;
                """,
                (database,),
            )
            row = cursor.fetchone()
            rollbacks = row[0] or 0
            commits = row[1] or 0
            total = rollbacks + commits

            error_rate = float(rollbacks) / float(total) if total > 0 else 0.0

            cursor.close()
            conn.close()

            metrics.record_db_gauge(
                "error_rate",
                error_rate,
                db_system=db_system,
                db_name=database,
            )

            logger.info(f"Query Error Rate: {error_rate}")
            flush()

            return error_rate

        except Exception as e:
            logger.error(f"Failed to check query error rate: {e}")
            if span:
                span.record_exception(e)
                span.set_status(StatusCode.ERROR, str(e))
            return 0.0
