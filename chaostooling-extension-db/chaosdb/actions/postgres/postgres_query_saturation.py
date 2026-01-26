"""PostgreSQL query saturation chaos action."""

import logging
import os
import threading
import time
from typing import Optional

import psycopg2
from chaosotel import (
    ensure_initialized,
    flush,
    get_metric_tags,
    get_metrics_core,
    get_tracer,
)
from opentelemetry.trace import StatusCode

from chaosdb.common.constants import ConnectionDefaults, DatabaseDefaults
from chaosdb.common.validation import (
    validate_database_name,
    validate_host,
    validate_port,
)

_active_threads = []
_stop_event = threading.Event()


def inject_query_saturation(
    host: Optional[str] = None,
    port: Optional[int] = None,
    database: Optional[str] = None,
    user: Optional[str] = None,
    password: Optional[str] = None,
    num_threads: int = 20,
    queries_per_thread: int = 1000,
    duration_seconds: int = 60,
    slow_query_threshold_ms: int = 1000,
) -> Dict[str, Any]:
    """
    Saturate the database with a high volume of queries to test query handling capacity.

    Args:
        host: PostgreSQL host
        port: PostgreSQL port
        database: Database name
        user: Database user
        password: Database password
        num_threads: Number of concurrent query threads
        queries_per_thread: Target queries per thread
        duration_seconds: Maximum duration to run
        slow_query_threshold_ms: Threshold for slow query detection

    Returns:
        Dict with results including total queries, slow queries, timeouts, etc.
    """
    # Handle string input from Chaos Toolkit configuration
    num_threads = int(num_threads) if isinstance(num_threads, str) else num_threads
    queries_per_thread = (
        int(queries_per_thread)
        if isinstance(queries_per_thread, str)
        else queries_per_thread
    )
    duration_seconds = (
        int(duration_seconds) if isinstance(duration_seconds, str) else duration_seconds
    )
    slow_query_threshold_ms = (
        int(slow_query_threshold_ms)
        if isinstance(slow_query_threshold_ms, str)
        else slow_query_threshold_ms
    )

    # Support both POSTGRES_HOST and POSTGRES_PRIMARY_HOST for e2e tests
    host_env = host or os.getenv("POSTGRES_PRIMARY_HOST") or os.getenv("POSTGRES_HOST")
    host = validate_host(
        host_env,
        DatabaseDefaults.POSTGRES_DEFAULT_HOST,
        "host",
    )
    port_env = port or os.getenv("POSTGRES_PRIMARY_PORT") or os.getenv("POSTGRES_PORT")
    port = validate_port(
        port_env,
        DatabaseDefaults.POSTGRES_PORT,
        "port",
    )
    database = validate_database_name(
        database or os.getenv("POSTGRES_DB"),
        DatabaseDefaults.POSTGRES_DEFAULT_DB,
        "database",
    )
    user = user or os.getenv("POSTGRES_USER", DatabaseDefaults.POSTGRES_DEFAULT_USER)
    password = password or os.getenv("POSTGRES_PASSWORD", "")

    ensure_initialized()
    db_system = os.getenv("DB_SYSTEM", "postgresql")
    metrics = get_metrics_core()
    tracer = get_tracer()
    logger = logging.getLogger("chaosdb.postgres.query_saturation")
    start_time = time.time()

    global _active_threads, _stop_event
    _stop_event.clear()
    _active_threads = []

    total_queries = 0
    slow_queries = 0
    timeouts = 0
    errors = 0

    def query_worker(thread_id: int) -> None:
        """Worker thread that executes queries."""
        nonlocal total_queries, slow_queries, timeouts, errors
        conn = None
        try:
            with tracer.start_as_current_span(
                f"query_saturation.worker.{thread_id}"
            ) as span:
                from chaosotel.core.trace_core import set_db_span_attributes

                set_db_span_attributes(
                    span,
                    db_system="postgresql",
                    db_name=database,
                    host=host,
                    port=port,
                    chaos_activity="postgresql_query_saturation",
                    chaos_action="query_saturation",
                    chaos_operation="query_saturation",
                    chaos_thread_id=thread_id,
                )

                conn = psycopg2.connect(
                    host=host,
                    port=port,
                    database=database,
                    user=user,
                    password=password,
                    connect_timeout=ConnectionDefaults.CONNECT_TIMEOUT,
                )
                cursor = conn.cursor()

                query_count = 0
                end_time = time.time() + duration_seconds

                while (
                    not _stop_event.is_set()
                    and time.time() < end_time
                    and query_count < queries_per_thread
                ):
                    try:
                        query_start = time.time()

                        # Execute various query types to saturate the system
                        queries = [
                            "SELECT 1",
                            "SELECT NOW()",
                            "SELECT version()",
                            "SELECT pg_database_size(current_database())",
                            "SELECT count(*) FROM pg_stat_activity",
                            "SELECT * FROM pg_stat_database LIMIT 1",
                        ]

                        query = queries[query_count % len(queries)]
                        cursor.execute(query)
                        cursor.fetchall()

                        query_duration_ms = (time.time() - query_start) * 1000
                        total_queries += 1
                        query_count += 1

                        tags = get_metric_tags(
                            db_name=database,
                            db_system=db_system,
                            db_operation="saturation_query",
                        )
                        metrics.record_db_query_latency(
                            query_duration_ms,
                            db_system=db_system,
                            db_name=database,
                            db_operation="saturation_query",
                            tags=tags,
                        )
                        metrics.record_db_query_count(
                            db_system=db_system,
                            db_name=database,
                            db_operation="saturation_query",
                            count=1,
                            tags=tags,
                        )

                        if query_duration_ms > slow_query_threshold_ms:
                            slow_queries += 1
                            # Record slow query metric
                            metrics.record_db_slow_query_count(
                                db_system=db_system,
                                threshold_ms=float(slow_query_threshold_ms),
                                db_name=database,
                                tags=tags,
                            )

                        # Brief pause to avoid overwhelming
                        time.sleep(0.01)

                    except psycopg2.extensions.QueryCanceledError:
                        timeouts += 1
                        metrics.record_db_query_timeout(
                            db_system=db_system,
                            db_name=database,
                            count=1,
                        )
                        errors += 1
                    except Exception as e:
                        errors += 1
                        metrics.record_db_error(
                            db_system=db_system,
                            error_type=type(e).__name__,
                            db_name=database,
                        )
                        logger.warning(f"Query worker {thread_id} error: {e}")

                span.set_status(StatusCode.OK)
                span.set_attribute("chaos.queries_executed", query_count)

        except psycopg2.OperationalError as e:
            errors += 1
            # Track connection failures specifically
            str(e)

            metrics.record_db_error(
                db_system=db_system,
                error_type=type(e).__name__,
                db_name=database,
            )

            logger.error(f"Query saturation worker {thread_id} failed: {e}")
        except Exception as e:
            errors += 1
            metrics.record_db_error(
                db_system=db_system,
                error_type=type(e).__name__,
                db_name=database,
            )
            logger.error(f"Query saturation worker {thread_id} failed: {e}")
        finally:
            if conn:
                try:
                    conn.close()
                except Exception:
                    pass

    try:
        with tracer.start_as_current_span("chaos.postgres.query_saturation") as span:
            from chaosotel.core.trace_core import set_db_span_attributes

            set_db_span_attributes(
                span,
                db_system="postgresql",
                db_name=database,
                host=host,
                port=port,
                chaos_activity="postgresql_query_saturation",
                chaos_action="query_saturation",
                chaos_operation="query_saturation",
                chaos_num_threads=num_threads,
                chaos_duration_seconds=duration_seconds,
            )

            logger.info(
                f"Starting query saturation with {num_threads} threads for {duration_seconds}s"
            )

            # Start worker threads
            for i in range(num_threads):
                thread = threading.Thread(target=query_worker, args=(i,), daemon=True)
                thread.start()
                _active_threads.append(thread)

            # Wait for duration or until threads complete
            for thread in _active_threads:
                thread.join(timeout=duration_seconds + 5)

            _stop_event.set()
            duration_ms = (time.time() - start_time) * 1000

            result = {
                "success": True,
                "duration_ms": duration_ms,
                "total_queries": total_queries,
                "slow_queries": slow_queries,
                "timeouts": timeouts,
                "errors": errors,
                "queries_per_second": (
                    total_queries / (duration_ms / 1000) if duration_ms > 0 else 0
                ),
                "threads_used": num_threads,
            }

            span.set_attribute("chaos.total_queries", total_queries)
            span.set_attribute("chaos.slow_queries", slow_queries)
            span.set_attribute("chaos.timeouts", timeouts)
            span.set_attribute("chaos.errors", errors)
            span.set_status(StatusCode.OK)

            logger.info(f"Query saturation completed: {result}")
            flush()
            return result

    except Exception as e:
        _stop_event.set()
        metrics.record_db_error(
            db_system=db_system,
            error_type=type(e).__name__,
            db_name=database,
        )
        logger.error(f"Query saturation failed: {e}")
        flush()
        raise


def stop_query_saturation() -> None:
    """Stop any running query saturation."""
    global _stop_event, _active_threads
    _stop_event.set()
    for thread in _active_threads:
        thread.join(timeout=2)
    _active_threads = []
