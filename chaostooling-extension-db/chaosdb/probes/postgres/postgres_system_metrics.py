"""PostgreSQL system metrics probe."""

import logging
import os
import time
from contextlib import nullcontext
from typing import Optional

import psycopg2
from chaosotel import flush, get_metrics_core, get_tracer
from opentelemetry._logs import get_logger_provider
from opentelemetry.sdk._logs import LoggingHandler
from opentelemetry.trace import StatusCode


def collect_postgres_system_metrics(
    host: Optional[str] = None,
    port: Optional[int] = None,
    database: Optional[str] = None,
    user: Optional[str] = None,
    password: Optional[str] = None,
) -> dict:
    """

    Collect advanced PostgreSQL system metrics (Cache, WAL, Temp Files, Scans, etc.).



    Observability: Uses chaosotel (chaostooling-otel) as the central

    observability location. chaosotel must be initialized via chaosotel.control in

    the experiment configuration.



    Args:

        host: PostgreSQL host

        port: PostgreSQL port

        database: Database name

        user: Database user

        password: Database password



    Returns:

        Dict with collected metrics

    """

    # Handle string input from Chaos Toolkit configuration

    if port is not None:
        port = int(port) if isinstance(port, str) else port

    host = host or os.getenv("POSTGRES_HOST", "postgres")

    port = port or int(os.getenv("POSTGRES_PORT", "5432"))

    database = database or os.getenv("POSTGRES_DB", "testdb")

    user = user or os.getenv("POSTGRES_USER", "postgres")

    password = password or os.getenv("POSTGRES_PASSWORD", "postgres")

    # chaosotel is initialized via chaosotel.control - use directly

    tracer = get_tracer()

    # Setup OpenTelemetry logger via LoggingHandler

    logger_provider = get_logger_provider()

    if logger_provider:
        handler = LoggingHandler(level=logging.INFO, logger_provider=logger_provider)

        logger = logging.getLogger("chaosdb.postgres.postgres_system_metrics")

        logger.addHandler(handler)

        logger.setLevel(logging.INFO)

    else:
        logger = logging.getLogger("chaosdb.postgres.postgres_system_metrics")

    metrics = get_metrics_core()

    db_system = "postgresql"

    start = time.time()

    span = None

    span_context = (
        tracer.start_as_current_span("probe.postgres.system_metrics")
        if tracer
        else nullcontext()
    )

    with span_context as span:
        try:
            if span:
                span.set_attribute("db.system", db_system)

                span.set_attribute("db.name", database)

                span.set_attribute("chaos.activity", "postgresql_system_metrics")

                span.set_attribute("chaos.activity.type", "probe")

                span.set_attribute("chaos.system", "postgresql")

                span.set_attribute("chaos.operation", "system_metrics")

            conn = psycopg2.connect(
                host=host,
                port=port,
                database=database,
                user=user,
                password=password,
                connect_timeout=5,
            )

            cursor = conn.cursor()

            metrics_collected = {}

            # 1. Cache Hit Ratio (with division by zero protection)

            cursor.execute(
                """

                SELECT

                    COALESCE(

                        sum(heap_blks_hit)::float / NULLIF(sum(heap_blks_hit) + sum(heap_blks_read), 0),

                        0

                    ) as ratio

                FROM pg_statio_user_tables;

            """
            )

            row = cursor.fetchone()

            if row and row[0] is not None:
                ratio = float(row[0])

                metrics_collected["cache_hit_ratio"] = ratio

                metrics.record_db_gauge(
                    "cache_hit_ratio",
                    ratio,
                    db_system=db_system,
                    db_name=database,
                )

            # 2. Count WAL files

            cursor.execute("SELECT count(*) FROM pg_ls_waldir();")

            wal_count = cursor.fetchone()[0]

            metrics_collected["wal_files"] = wal_count

            metrics.record_db_gauge(
                "wal_files",
                float(wal_count),
                db_system=db_system,
                db_name=database,
            )

            # 3. Active Sessions

            cursor.execute(
                "SELECT count(*) FROM pg_stat_activity WHERE state = 'active';"
            )

            active_sessions = cursor.fetchone()[0]

            metrics_collected["active_sessions"] = active_sessions

            metrics.record_db_gauge(
                "active_sessions",
                float(active_sessions),
                db_system=db_system,
                db_name=database,
            )

            # 4. Total Sessions

            cursor.execute("SELECT count(*) FROM pg_stat_activity;")

            total_sessions = cursor.fetchone()[0]

            metrics_collected["total_sessions"] = total_sessions

            metrics.record_db_gauge(
                "total_sessions",
                float(total_sessions),
                db_system=db_system,
                db_name=database,
            )

            # 5. Active Transactions

            cursor.execute(
                "SELECT count(*) FROM pg_stat_activity WHERE state IN ('active', 'idle in transaction');"
            )

            active_transactions = cursor.fetchone()[0]

            metrics_collected["active_transactions"] = active_transactions

            metrics.record_db_gauge(
                "active_transactions",
                float(active_transactions),
                db_system=db_system,
                db_name=database,
            )

            # 6. Connection Pool Usage (max_connections)

            cursor.execute(
                "SELECT setting::int FROM pg_settings WHERE name = 'max_connections';"
            )

            max_connections = cursor.fetchone()[0]

            pool_usage_ratio = (
                float(total_sessions) / float(max_connections)
                if max_connections > 0
                else 0
            )

            metrics_collected["max_connections"] = max_connections

            metrics_collected["pool_usage_ratio"] = pool_usage_ratio

            metrics.record_db_gauge(
                "pool_usage_ratio",
                pool_usage_ratio,
                db_system=db_system,
                db_name=database,
            )

            # 7. Replication Lag (if replica)

            try:
                cursor.execute(
                    "SELECT EXTRACT(EPOCH FROM (now() - pg_last_xact_replay_timestamp())) as lag_seconds;"
                )

                result = cursor.fetchone()

                if result and result[0] is not None:
                    lag_seconds = float(result[0])

                    metrics_collected["replication_lag_seconds"] = lag_seconds

                    metrics.record_db_gauge(
                        "replication_lag_seconds",
                        lag_seconds,
                        db_system=db_system,
                        db_name=database,
                        unit="s",
                    )

            except Exception:
                # Not a replica or function not available

                pass

            # 8. Temp Files & Bytes (Current snapshot from pg_stat_database)

            # Note: pg_stat_database returns cumulative totals.

            # We collect them for logging but do not export as OTel Gauges to avoid monotonic growth issues.

            cursor.execute(
                """

                SELECT sum(temp_files), sum(temp_bytes)

                FROM pg_stat_database WHERE datname = %s;

            """,
                (database,),
            )

            row = cursor.fetchone()

            if row:
                temp_files = row[0] or 0

                temp_bytes = row[1] or 0

                metrics_collected["temp_files"] = temp_files

                metrics_collected["temp_bytes"] = temp_bytes

            # 9. Dead Tuples (Current state)

            cursor.execute(
                """

                SELECT sum(n_dead_tup) FROM pg_stat_user_tables;

            """
            )

            dead_tuples = cursor.fetchone()[0] or 0

            metrics_collected["dead_tuples"] = dead_tuples

            metrics.record_db_gauge(
                "dead_tuples",
                float(dead_tuples),
                db_system=db_system,
                db_name=database,
            )

            cursor.close()

            conn.close()

            probe_time_ms = (time.time() - start) * 1000

            metrics_collected["probe_time_ms"] = probe_time_ms

            if span:
                span.set_status(StatusCode.OK)

            logger.info(f"Postgres system metrics: {metrics_collected}")

            flush()

            # Return True for tolerance check (metrics are already recorded to OTEL)

            return True

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
                f"Postgres system metrics probe failed: {str(e)}",
                extra={"error": str(e)},
            )

            flush()

            raise
