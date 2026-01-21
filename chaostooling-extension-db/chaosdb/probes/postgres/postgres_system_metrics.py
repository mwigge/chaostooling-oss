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
    retries: int = 5,
    delay: int = 2,
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
        retries: Number of retries on failure (default: 5)
        delay: Delay in seconds between retries (default: 2)

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
    try:
        tracer = get_tracer()
    except Exception:
        tracer = None

    # Setup OpenTelemetry logger via LoggingHandler
    logger_provider = get_logger_provider()
    if logger_provider:
        handler = LoggingHandler(level=logging.INFO, logger_provider=logger_provider)
        logger = logging.getLogger("chaosdb.postgres.postgres_system_metrics")
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
    else:
        logger = logging.getLogger("chaosdb.postgres.postgres_system_metrics")

    try:
        metrics = get_metrics_core()
    except Exception:
        metrics = None

    db_system = "postgresql"
    start = time.time()

    span_context = (
        tracer.start_as_current_span("probe.postgres.system_metrics")
        if tracer
        else nullcontext()
    )

    with span_context as span:
        for i in range(retries):
            try:
                if span:
                    # Use span helper for consistent attribute setting and resource updates
                    # This ensures the database appears in Tempo service graph
                    from chaosotel.core.trace_core import set_db_span_attributes

                    set_db_span_attributes(
                        span,
                        db_system=db_system,
                        db_name=database,
                        db_user=user,
                        host=host,
                        port=port,
                        db_operation="system_metrics",
                        chaos_activity="postgresql_system_metrics",
                        chaos_action="system_metrics",
                        chaos_operation="system_metrics",
                    )

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
                try:
                    cursor.execute("SELECT count(*) FROM pg_ls_waldir();")
                    wal_count = cursor.fetchone()[0]
                    metrics_collected["wal_files"] = wal_count
                    metrics.record_db_gauge(
                        "wal_files",
                        float(wal_count),
                        db_system=db_system,
                        db_name=database,
                    )
                except Exception:
                    pass

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
                    pass

                # 8. Temp Files & Bytes
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

                # 9. Dead Tuples
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

                # 10. Total Transactions
                cursor.execute(
                    """
                    SELECT sum(xact_commit) + sum(xact_rollback)
                    FROM pg_stat_database
                    WHERE datname = %s;
                    """,
                    (database,),
                )
                row = cursor.fetchone()
                if row:
                    total_transactions = row[0] or 0
                    metrics_collected["total_transactions"] = total_transactions
                    metrics.record_db_gauge(
                        "transaction_total",
                        float(total_transactions),
                        db_system=db_system,
                        db_name=database,
                    )

                cursor.close()
                conn.close()

                probe_time_ms = (time.time() - start) * 1000

                # Ensure the dictionary is not empty so tolerance: true passes
                metrics_collected["status"] = "success"
                metrics_collected["probe_time_ms"] = probe_time_ms

                if span:
                    span.set_status(StatusCode.OK)

                logger.info(
                    f"Postgres system metrics collected: {len(metrics_collected)} items"
                )
                logger.debug(f"Metrics: {metrics_collected}")

                flush()

                # Return metrics dict for tolerance check
                return metrics_collected

            except BaseException as e:
                logger.warning(
                    f"Postgres system metrics probe failed (attempt {i + 1}/{retries}): {str(e)}",
                    extra={"error": str(e)},
                )
                if i < retries - 1:
                    time.sleep(delay)
                else:
                    metrics.record_db_error(
                        db_system=db_system,
                        error_type=type(e).__name__,
                        db_name=database,
                    )
                    if span:
                        span.record_exception(e)
                        span.set_status(StatusCode.ERROR, str(e))
                    logger.error(
                        f"Postgres system metrics probe failed after {retries} retries: {str(e)}",
                        extra={"error": str(e)},
                    )

                    flush()

                    raise
    return {}
