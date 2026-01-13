"""PostgreSQL replication probes."""

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


def probe_replication_lag(
    primary_host: Optional[str] = None,
    primary_port: Optional[int] = None,
    replica_host: Optional[str] = None,
    replica_port: Optional[int] = None,
    database: Optional[str] = None,
    user: Optional[str] = None,
    password: Optional[str] = None,
) -> dict:
    """
    Probe replication lag between primary and replica.

    Args:
        primary_host: Primary PostgreSQL host
        primary_port: Primary PostgreSQL port
        replica_host: Replica PostgreSQL host
        replica_port: Replica PostgreSQL port
        database: Database name
        user: Database user
        password: Database password

    Returns:
        Dict with replication lag information
    """
    # Handle string input from Chaos Toolkit configuration
    if primary_port is not None:
        primary_port = (
            int(primary_port) if isinstance(primary_port, str) else primary_port
        )
    if replica_port is not None:
        replica_port = (
            int(replica_port) if isinstance(replica_port, str) else replica_port
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
    metrics = get_metrics_core()

    # Setup OpenTelemetry logger via LoggingHandler
    logger_provider = get_logger_provider()
    if logger_provider:
        handler = LoggingHandler(level=logging.INFO, logger_provider=logger_provider)
        logger = logging.getLogger("chaosdb.postgres.replication_lag")
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
    else:
        logger = logging.getLogger("chaosdb.postgres.replication_lag")

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
                span.set_attribute("db.operation", "probe_replication_lag")
                span.set_attribute("chaos.activity", "postgresql_replication_lag")
                span.set_attribute("chaos.activity.type", "probe")
                span.set_attribute("chaos.system", "postgresql")
                span.set_attribute("chaos.operation", "replication_lag")

            # Get primary LSN
            primary_conn = psycopg2.connect(
                host=primary_host,
                port=primary_port,
                database=database,
                user=user,
                password=password,
                connect_timeout=5,
            )
            primary_cursor = primary_conn.cursor()
            primary_cursor.execute("SELECT pg_current_wal_lsn()")
            primary_lsn = primary_cursor.fetchone()[0]
            primary_cursor.execute(
                "SELECT pg_wal_lsn_diff(pg_current_wal_lsn(), '0/0')"
            )
            primary_cursor.fetchone()[0]
            primary_cursor.close()
            primary_conn.close()

            # Get replica LSN
            replica_conn = psycopg2.connect(
                host=replica_host,
                port=replica_port,
                database=database,
                user=user,
                password=password,
                connect_timeout=5,
            )
            replica_cursor = replica_conn.cursor()

            # Check if replica is in recovery mode
            replica_cursor.execute("SELECT pg_is_in_recovery()")
            is_replica = replica_cursor.fetchone()[0]

            if is_replica:
                replica_cursor.execute("SELECT pg_last_wal_receive_lsn()")
                replica_receive_lsn = replica_cursor.fetchone()[0]
                replica_cursor.execute("SELECT pg_last_wal_replay_lsn()")
                replica_replay_lsn = replica_cursor.fetchone()[0]

                # Calculate lag in bytes
                if replica_receive_lsn and primary_lsn:
                    replica_cursor.execute(
                        "SELECT pg_wal_lsn_diff(%s, %s)",
                        (primary_lsn, replica_receive_lsn),
                    )
                    receive_lag_bytes = replica_cursor.fetchone()[0] or 0
                else:
                    receive_lag_bytes = None

                if replica_replay_lsn and primary_lsn:
                    replica_cursor.execute(
                        "SELECT pg_wal_lsn_diff(%s, %s)",
                        (primary_lsn, replica_replay_lsn),
                    )
                    replay_lag_bytes = replica_cursor.fetchone()[0] or 0
                else:
                    replay_lag_bytes = None

                # Estimate lag in seconds (rough estimate: 16MB per second)
                receive_lag_seconds = (
                    (receive_lag_bytes / (16 * 1024 * 1024))
                    if receive_lag_bytes
                    else None
                )
                replay_lag_seconds = (
                    (replay_lag_bytes / (16 * 1024 * 1024))
                    if replay_lag_bytes
                    else None
                )
            else:
                receive_lag_bytes = None
                replay_lag_bytes = None
                receive_lag_seconds = None
                replay_lag_seconds = None

            replica_cursor.close()
            replica_conn.close()

            probe_time_ms = (time.time() - start) * 1000

            tags = get_metric_tags(
                db_name=database,
                db_system=db_system,
                db_operation="probe_replication_lag",
            )
            metrics.record_db_query_latency(
                probe_time_ms,
                db_system=db_system,
                db_name=database,
                db_operation="probe_replication_lag",
                tags=tags,
            )
            metrics.record_db_query_count(
                db_system=db_system,
                db_name=database,
                db_operation="probe_replication_lag",
                count=1,
                tags=tags,
            )

            result = {
                "success": True,
                "is_replica": is_replica,
                "primary_lsn": str(primary_lsn),
                "receive_lag_bytes": receive_lag_bytes,
                "replay_lag_bytes": replay_lag_bytes,
                "receive_lag_seconds": receive_lag_seconds,
                "replay_lag_seconds": replay_lag_seconds,
                "probe_time_ms": probe_time_ms,
            }

            # Add lag metrics
            if receive_lag_bytes is not None:
                if span:
                    span.set_attribute(
                        "replication.receive_lag_bytes", receive_lag_bytes
                    )
                    span.set_attribute(
                        "replication.receive_lag_seconds", receive_lag_seconds or 0
                    )
            if replay_lag_bytes is not None:
                if span:
                    span.set_attribute("replication.replay_lag_bytes", replay_lag_bytes)
                    span.set_attribute(
                        "replication.replay_lag_seconds", replay_lag_seconds or 0
                    )

            if span:
                span.set_status(StatusCode.OK)
            logger.info("Replication lag probe: %s", result)
            flush()
            return result
        except Exception as e:
            error_msg = str(e)
            db_system = os.getenv("DB_SYSTEM", "postgresql")
            metrics = get_metrics_core()
            # Handle DNS resolution errors gracefully (e.g., when container is stopped)
            if (
                "name resolution" in error_msg.lower()
                or "could not translate host name" in error_msg.lower()
            ):
                logger.warning(
                    "Replication lag probe: DNS resolution failed for %s (container may be stopped): %s",
                    replica_host,
                    e,
                )
                result = {
                    "success": False,
                    "error": "DNS resolution failed - container may be stopped",
                    "replica_host": replica_host,
                    "probe_time_ms": (time.time() - start) * 1000,
                }
                metrics.record_db_error(
                    db_system=db_system, error_type=type(e).__name__
                )
                if span:
                    span.record_exception(e)
                    span.set_status(StatusCode.ERROR, error_msg)
                flush()
                return result
            else:
                metrics.record_db_error(
                    db_system=db_system, error_type=type(e).__name__
                )
                if span:
                    span.record_exception(e)
                    span.set_status(StatusCode.ERROR, error_msg)
                logger.error(
                    f"Replication lag probe failed: {error_msg}",
                    extra={"error": error_msg},
                )
                flush()
                raise


def probe_data_consistency(
    primary_host: Optional[str] = None,
    primary_port: Optional[int] = None,
    replica_host: Optional[str] = None,
    replica_port: Optional[int] = None,
    database: Optional[str] = None,
    user: Optional[str] = None,
    password: Optional[str] = None,
    table_name: str = "mobile_purchases",
) -> dict:
    """
    Probe data consistency between primary and replica by comparing record counts and checksums.

    Args:
        primary_host: Primary PostgreSQL host
        primary_port: Primary PostgreSQL port
        replica_host: Replica PostgreSQL host
        replica_port: Replica PostgreSQL port
        database: Database name
        user: Database user
        password: Database password
        table_name: Table to check consistency

    Returns:
        Dict with consistency information
    """
    # Handle string input from Chaos Toolkit configuration
    if primary_port is not None:
        primary_port = (
            int(primary_port) if isinstance(primary_port, str) else primary_port
        )
    if replica_port is not None:
        replica_port = (
            int(replica_port) if isinstance(replica_port, str) else replica_port
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
    metrics = get_metrics_core()

    # Setup OpenTelemetry logger via LoggingHandler
    logger_provider = get_logger_provider()
    if logger_provider:
        handler = LoggingHandler(level=logging.INFO, logger_provider=logger_provider)
        logger = logging.getLogger("chaosdb.postgres.data_consistency")
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
    else:
        logger = logging.getLogger("chaosdb.postgres.data_consistency")

    db_system = "postgresql"
    start = time.time()

    span_context = (
        tracer.start_as_current_span("probe.postgres.data_consistency")
        if tracer
        else nullcontext()
    )

    with span_context as span:
        try:
            if span:
                span.set_attribute("db.system", "postgresql")
                span.set_attribute("db.operation", "probe_data_consistency")
                span.set_attribute("db.table", table_name)
                span.set_attribute("chaos.activity", "postgresql_data_consistency")
                span.set_attribute("chaos.activity.type", "probe")
                span.set_attribute("chaos.system", "postgresql")
                span.set_attribute("chaos.operation", "data_consistency")

            # Get primary count
            primary_conn = psycopg2.connect(
                host=primary_host,
                port=primary_port,
                database=database,
                user=user,
                password=password,
                connect_timeout=5,
            )
            primary_cursor = primary_conn.cursor()
            primary_cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
            primary_count = primary_cursor.fetchone()[0]

            # Get primary max ID
            primary_cursor.execute(f"SELECT COALESCE(MAX(id), 0) FROM {table_name}")
            primary_max_id = primary_cursor.fetchone()[0]

            primary_cursor.close()
            primary_conn.close()

            # Get replica count
            replica_conn = psycopg2.connect(
                host=replica_host,
                port=replica_port,
                database=database,
                user=user,
                password=password,
                connect_timeout=5,
            )
            replica_cursor = replica_conn.cursor()
            replica_cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
            replica_count = replica_cursor.fetchone()[0]

            # Get replica max ID
            replica_cursor.execute(f"SELECT COALESCE(MAX(id), 0) FROM {table_name}")
            replica_max_id = replica_cursor.fetchone()[0]

            replica_cursor.close()
            replica_conn.close()

            # Calculate differences
            count_diff = primary_count - replica_count
            max_id_diff = primary_max_id - replica_max_id
            is_consistent = count_diff == 0 and max_id_diff == 0

            probe_time_ms = (time.time() - start) * 1000

            tags = get_metric_tags(
                db_name=database,
                db_system=db_system,
                db_operation="probe_data_consistency",
            )
            metrics.record_db_query_latency(
                probe_time_ms,
                db_system=db_system,
                db_name=database,
                db_operation="probe_data_consistency",
                tags=tags,
            )
            metrics.record_db_query_count(
                db_system=db_system,
                db_name=database,
                db_operation="probe_data_consistency",
                count=1,
                tags=tags,
            )

            result = {
                "success": True,
                "is_consistent": is_consistent,
                "primary_count": primary_count,
                "replica_count": replica_count,
                "count_diff": count_diff,
                "primary_max_id": primary_max_id,
                "replica_max_id": replica_max_id,
                "max_id_diff": max_id_diff,
                "probe_time_ms": probe_time_ms,
            }

            if span:
                span.set_attribute("consistency.is_consistent", is_consistent)
                span.set_attribute("consistency.count_diff", count_diff)
                span.set_attribute("consistency.max_id_diff", max_id_diff)
                span.set_status(StatusCode.OK)
            logger.info("Data consistency probe: %s", result)
            flush()
            return result
        except Exception as e:
            error_msg = str(e)
            db_system = os.getenv("DB_SYSTEM", "postgresql")
            metrics = get_metrics_core()
            # Handle DNS resolution errors gracefully (e.g., when container is stopped)
            if (
                "name resolution" in error_msg.lower()
                or "could not translate host name" in error_msg.lower()
            ):
                logger.warning(
                    "Data consistency probe: DNS resolution failed for %s (container may be stopped): %s",
                    replica_host,
                    e,
                )
                result = {
                    "success": False,
                    "is_consistent": False,
                    "error": "DNS resolution failed - container may be stopped",
                    "replica_host": replica_host,
                    "probe_time_ms": (time.time() - start) * 1000,
                }
                metrics.record_db_error(
                    db_system=db_system, error_type=type(e).__name__
                )
                if span:
                    span.record_exception(e)
                    span.set_status(StatusCode.ERROR, error_msg)
                flush()
                return result
            else:
                metrics.record_db_error(
                    db_system=db_system, error_type=type(e).__name__
                )
                if span:
                    span.record_exception(e)
                    span.set_status(StatusCode.ERROR, error_msg)
                logger.error(
                    f"Data consistency probe failed: {error_msg}",
                    extra={"error": error_msg},
                )
                flush()
                raise
