"""MySQL query saturation chaos action."""

import logging
import os
import threading
import time
from typing import Optional

import mysql.connector
from chaosotel import (
    ensure_initialized,
    flush,
    get_metric_tags,
    get_metrics_core,
    get_tracer,
)
from opentelemetry.trace import StatusCode

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
) -> dict:
    """
    Saturate the database with a high volume of queries to test query handling capacity.

    Args:
        host: MySQL host
        port: MySQL port
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
    if port is not None:
        port = int(port) if isinstance(port, str) else port
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

    host = host or os.getenv("MYSQL_HOST", "localhost")
    port = port or int(os.getenv("MYSQL_PORT", "3306"))
    database = database or os.getenv("MYSQL_DB", "testdb")
    user = user or os.getenv("MYSQL_USER", "root")
    password = password or os.getenv("MYSQL_PASSWORD", "")

    ensure_initialized()
    db_system = os.getenv("DB_SYSTEM", "mysql")
    metrics = get_metrics_core()
    tracer = get_tracer()
    logger = logging.getLogger("chaosdb.mysql.query_saturation")
    start_time = time.time()

    global _active_threads, _stop_event
    _stop_event.clear()
    _active_threads = []

    total_queries = 0
    slow_queries = 0
    timeouts = 0
    errors = 0

    def query_worker(thread_id: int):
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
                    db_system=db_system,
                    db_name=database,
                    host=host,
                    port=port,
                    chaos_activity="mysql_query_saturation",
                    chaos_action="query_saturation",
                    chaos_operation="query_saturation",
                    chaos_thread_id=thread_id
                )

                conn = mysql.connector.connect(
                    host=host,
                    port=port,
                    database=database,
                    user=user,
                    password=password,
                    connect_timeout=5,
                )
                cursor = conn.cursor()

                query_count = 0
                end_time = time.time() + duration_seconds

                # Execute various query types to saturate the system
                queries = [
                    "SELECT 1",
                    "SELECT NOW()",
                    "SELECT VERSION()",
                    "SELECT DATABASE()",
                    "SELECT CONNECTION_ID()",
                    "SHOW STATUS",
                ]

                while (
                    not _stop_event.is_set()
                    and time.time() < end_time
                    and query_count < queries_per_thread
                ):
                    try:
                        query_start = time.time()

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

                        # Brief pause to avoid overwhelming
                        time.sleep(0.01)

                    except mysql.connector.errors.DatabaseError as e:
                        error_msg = str(e).lower()
                        if "timeout" in error_msg or "deadlock" in error_msg:
                            timeouts += 1
                        errors += 1
                        metrics.record_db_error(
                            db_system=db_system,
                            error_type=type(e).__name__,
                            db_name=database,
                        )
                        logger.warning(f"Query worker {thread_id} error: {e}")
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

        except mysql.connector.errors.OperationalError as e:
            errors += 1
            # Track connection failures specifically
            error_msg = str(e)

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
                except:
                    pass

    try:
        with tracer.start_as_current_span("chaos.mysql.query_saturation") as span:
            from chaosotel.core.trace_core import set_db_span_attributes
            set_db_span_attributes(
                span,
                db_system=db_system,
                db_name=database,
                host=host,
                port=port,
                chaos_activity="mysql_query_saturation",
                chaos_action="query_saturation",
                chaos_operation="query_saturation",
                chaos_num_threads=num_threads,
                chaos_duration_seconds=duration_seconds
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


def stop_query_saturation():
    """Stop any running query saturation."""
    global _stop_event, _active_threads
    _stop_event.set()
    for thread in _active_threads:
        thread.join(timeout=2)
    _active_threads = []
