"""PostgreSQL replication lag probe."""

import logging
import os
import time
from contextlib import nullcontext
from typing import Optional

import psycopg2
from chaosotel import flush, get_metric_tags, get_metrics_core, get_tracer
from opentelemetry._logs import get_logger_provider
from opentelemetry.sdk._logs import LoggingHandler
from opentelemetry.trace import StatusCode


def check_replication_lag(
    primary_host: Optional[str] = None,
    primary_port: Optional[int] = None,
    replica_host: Optional[str] = None,
    replica_port: Optional[int] = None,
    database: Optional[str] = None,
    user: Optional[str] = None,
    password: Optional[str] = None,
    max_lag_seconds: Optional[float] = None,
) -> dict:
    """
    Check replication lag between primary and replica.

    Observability: Uses chaosotel (chaostooling-otel) as the central
    observability location. chaosotel must be initialized via chaosotel.control in
    the experiment configuration.

    Args:
        primary_host: Primary hostname
        primary_port: Primary port
        replica_host: Replica hostname
        replica_port: Replica port
        database: Database name
        user: Database user
        password: Database password
        max_lag_seconds: Maximum acceptable lag in seconds (optional)

    Returns:
        Dict with lag information and status
    """
    # Handle string input
    if primary_port is not None:
        primary_port = (
            int(primary_port) if isinstance(primary_port, str) else primary_port
        )
    if replica_port is not None:
        replica_port = (
            int(replica_port) if isinstance(replica_port, str) else replica_port
        )
    if max_lag_seconds is not None:
        max_lag_seconds = (
            float(max_lag_seconds)
            if isinstance(max_lag_seconds, str)
            else max_lag_seconds
        )

    primary_host = primary_host or os.getenv(
        "POSTGRES_PRIMARY_HOST", "postgres-primary"
    )
    primary_port = primary_port or int(os.getenv("POSTGRES_PRIMARY_PORT", "5432"))
    replica_host = replica_host or os.getenv(
        "POSTGRES_REPLICA_HOST", "postgres-replica"
    )
    replica_port = replica_port or int(os.getenv("POSTGRES_REPLICA_PORT", "5432"))
    database = database or os.getenv("POSTGRES_DB", "testdb")
    user = user or os.getenv("POSTGRES_USER", "postgres")
    password = password or os.getenv("POSTGRES_PASSWORD", "postgres")

    # chaosotel is initialized via chaosotel.control - use directly
    tracer = get_tracer()
    # Setup OpenTelemetry logger via LoggingHandler
    logger_provider = get_logger_provider()
    if logger_provider:
        handler = LoggingHandler(level=logging.INFO, logger_provider=logger_provider)
        logger = logging.getLogger("chaosdb.postgres.postgres_replication_lag")
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
    else:
        logger = logging.getLogger("chaosdb.postgres.postgres_replication_lag")
    metrics = get_metrics_core()

    db_system = "postgresql"
    start = time.time()

    span_context = (
        tracer.start_as_current_span("probe.postgres.replication_lag")
        if tracer
        else nullcontext()
    )

    with span_context as span:
        try:
            if span:
                span.set_attribute("db.system", "postgresql")
                span.set_attribute("db.name", database)
                span.set_attribute("chaos.primary_host", primary_host)
                span.set_attribute("chaos.replica_host", replica_host)
                span.set_attribute("chaos.activity", "postgresql_replication_lag")
                span.set_attribute("chaos.activity.type", "probe")
                span.set_attribute("chaos.system", "postgresql")
                span.set_attribute("chaos.operation", "replication_lag")

            primary_conn = psycopg2.connect(
                host=primary_host,
                port=primary_port,
                database=database,
                user=user,
                password=password,
                connect_timeout=5,
            )
            primary_cursor = primary_conn.cursor()
            primary_cursor.execute("SELECT pg_current_wal_lsn();")
            primary_lsn = primary_cursor.fetchone()[0]
            primary_cursor.close()
            primary_conn.close()

            # Connect to replica and get replay LSN
            replica_conn = psycopg2.connect(
                host=replica_host,
                port=replica_port,
                database=database,
                user=user,
                password=password,
                connect_timeout=5,
            )
            replica_cursor = replica_conn.cursor()
            replica_cursor.execute("SELECT pg_last_wal_replay_lsn();")
            replica_lsn = replica_cursor.fetchone()[0]

            # Calculate lag in bytes
            replica_cursor.execute(
                "SELECT pg_wal_lsn_diff(%s, %s) as lag_bytes;",
                (primary_lsn, replica_lsn),
            )
            lag_bytes = replica_cursor.fetchone()[0]

            # Get replay timestamp for time-based lag
            replica_cursor.execute(
                "SELECT EXTRACT(EPOCH FROM (now() - pg_last_xact_replay_timestamp())) as lag_seconds;"
            )
            result = replica_cursor.fetchone()
            lag_seconds = result[0] if result[0] is not None else 0

            replica_cursor.close()
            replica_conn.close()

            # Determine status
            is_healthy = True
            if max_lag_seconds is not None and lag_seconds > max_lag_seconds:
                is_healthy = False

            probe_time_ms = (time.time() - start) * 1000

            tags = get_metric_tags(
                db_name=database,
                db_system="postgresql",
                primary_host=primary_host,
                replica_host=replica_host,
            )

            # Record lag as gauges
            metrics.record_db_gauge(
                "replication_lag_seconds",
                lag_seconds,
                db_system=db_system,
                db_name=database,
                unit="s",
                tags=tags,
            )
            metrics.record_db_gauge(
                "replication_lag_bytes",
                float(lag_bytes),
                db_system=db_system,
                db_name=database,
                unit="bytes",
                tags=tags,
            )

            {
                "primary_lsn": str(primary_lsn),
                "replica_lsn": str(replica_lsn),
                "lag_bytes": int(lag_bytes),
                "lag_seconds": float(lag_seconds),
                "is_healthy": is_healthy,
                "max_lag_seconds": max_lag_seconds,
                "probe_time_ms": probe_time_ms,
            }

            if span:
                span.set_attribute("chaos.lag_bytes", int(lag_bytes))
                span.set_attribute("chaos.lag_seconds", float(lag_seconds))
                span.set_attribute("chaos.is_healthy", is_healthy)
                span.set_status(StatusCode.OK)

            logger.info("Replication lag: %.2fs (%s bytes)", lag_seconds, lag_bytes)
            flush()

            # Return True for tolerance check
            return is_healthy
        except Exception as e:
            error_msg = str(e)
            # Handle DNS resolution errors gracefully (e.g., when container is stopped)
            if (
                "name resolution" in error_msg.lower()
                or "could not translate host name" in error_msg.lower()
            ):
                logger.warning(
                    "Replication lag check: DNS resolution failed for %s (container may be stopped): %s",
                    replica_host,
                    e,
                )
                metrics.record_db_error(
                    db_system=db_system,
                    error_type=type(e).__name__,
                    db_name=database,
                )
                if span:
                    span.record_exception(e)
                    span.set_status(StatusCode.ERROR, error_msg)
                flush()
                # Return False instead of raising - allows experiment to continue
                return False
            else:
                metrics.record_db_error(
                    db_system=db_system,
                    error_type=type(e).__name__,
                    db_name=database,
                )
                if span:
                    span.record_exception(e)
                    span.set_status(StatusCode.ERROR, error_msg)
                logger.error(
                    f"Replication lag check failed: {error_msg}",
                    extra={"error": error_msg},
                )
                flush()
                raise
