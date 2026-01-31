"""Cassandra slow operations chaos action."""

import os
import threading
import time
from typing import Optional

from cassandra.cluster import Cluster
from chaosotel import (
    ensure_initialized,
    flush,
    get_logger,
    get_metric_tags,
    get_metrics_core,
    get_tracer,
)
from opentelemetry.trace import StatusCode

_active_threads = []
_stop_event = threading.Event()


def inject_slow_operations(
    host: Optional[str] = None,
    port: Optional[int] = None,
    keyspace: Optional[str] = None,
    user: Optional[str] = None,
    password: Optional[str] = None,
    num_threads: int = 5,
    duration_seconds: int = 60,
    operation_delay_ms: int = 5000,
) -> dict:
    """Inject slow Cassandra operations."""
    host = host or os.getenv("CASSANDRA_HOST", "localhost")
    port = port or int(os.getenv("CASSANDRA_PORT", "9042"))
    keyspace = keyspace or os.getenv("CASSANDRA_KEYSPACE", "system")
    user = user or os.getenv("CASSANDRA_USER")
    password = password or os.getenv("CASSANDRA_PASSWORD")

    ensure_initialized()
    db_system = os.getenv("DB_SYSTEM", "cassandra")
    metrics = get_metrics_core()
    tracer = get_tracer()
    logger = get_logger()
    start_time = time.time()

    global _active_threads, _stop_event
    _stop_event.clear()
    _active_threads = []

    operations_completed = 0
    total_operation_time = 0
    errors = 0

    def slow_operation_worker(thread_id: int):
        nonlocal operations_completed, total_operation_time, errors
        cluster = None
        session = None
        try:
            with tracer.start_as_current_span(
                f"slow_operation.worker.{thread_id}"
            ) as span:
                from chaosotel.core.trace_core import set_db_span_attributes

                set_db_span_attributes(
                    span,
                    db_system="cassandra",
                    db_name=keyspace,
                    host=host,
                    port=port,
                    chaos_activity="cassandra_slow_operations",
                    chaos_action="slow_operations",
                    chaos_operation="slow_operations",
                    chaos_thread_id=thread_id,
                )

                cluster = Cluster([host], port=port)
                session = cluster.connect(keyspace)

                end_time = time.time() + duration_seconds

                while not _stop_event.is_set() and time.time() < end_time:
                    try:
                        op_start = time.time()

                        # Read
                        session.execute("SELECT release_version FROM system.local")

                        # Simulate slow work
                        time.sleep(operation_delay_ms / 1000.0)

                        # Another operation
                        session.execute("SELECT cluster_name FROM system.local")

                        op_duration_ms = (time.time() - op_start) * 1000
                        operations_completed += 1
                        total_operation_time += op_duration_ms

                        get_metric_tags(
                            db_name=keyspace,
                            db_system="cassandra",
                            db_operation="slow_operation",
                        )

                        span.set_status(StatusCode.OK)
                    except Exception as e:
                        errors += 1
                        metrics.record_db_error(
                            db_system=db_system, error_type=type(e).__name__
                        )
                        logger.warning(f"Slow operation worker {thread_id} error: {e}")
                        span.set_status(StatusCode.ERROR, str(e))
                        time.sleep(0.1)
        except Exception as e:
            errors += 1
            logger.error(f"Slow operation worker {thread_id} failed: {e}")
        finally:
            if session:
                try:
                    session.shutdown()
                except Exception:
                    pass
            if cluster:
                try:
                    cluster.shutdown()
                except Exception:
                    pass

    try:
        with tracer.start_as_current_span("chaos.cassandra.slow_operations") as span:
            span.set_attribute("db.system", "cassandra")
            span.set_attribute("db.name", keyspace)
            span.set_attribute("chaos.num_threads", num_threads)
            span.set_attribute("chaos.duration_seconds", duration_seconds)
            span.set_attribute("chaos.operation_delay_ms", operation_delay_ms)
            span.set_attribute("chaos.action", "slow_operations")
            span.set_attribute("chaos.activity", "cassandra_slow_operations")
            span.set_attribute("chaos.activity.type", "action")
            span.set_attribute("chaos.system", "cassandra")
            span.set_attribute("chaos.operation", "slow_operations")

            logger.info(
                f"Starting Cassandra slow operations with {num_threads} threads for {duration_seconds}s"
            )

            for i in range(num_threads):
                thread = threading.Thread(
                    target=slow_operation_worker, args=(i,), daemon=True
                )
                thread.start()
                _active_threads.append(thread)

            time.sleep(duration_seconds)
            _stop_event.set()
            for thread in _active_threads:
                thread.join(timeout=10)

            duration_ms = (time.time() - start_time) * 1000
            avg_operation_time = (
                total_operation_time / operations_completed
                if operations_completed > 0
                else 0
            )

            result = {
                "success": True,
                "duration_ms": duration_ms,
                "operations_completed": operations_completed,
                "average_operation_time_ms": avg_operation_time,
                "errors": errors,
                "threads_used": num_threads,
            }

            span.set_attribute("chaos.operations_completed", operations_completed)
            span.set_attribute("chaos.average_operation_time_ms", avg_operation_time)
            span.set_status(StatusCode.OK)

            logger.info(f"Cassandra slow operations completed: {result}")
            flush()
            return result
    except Exception as e:
        _stop_event.set()
        metrics.record_db_error(db_system=db_system, error_type=type(e).__name__)
        logger.error(f"Cassandra slow operations failed: {e}")
        flush()
        raise


def stop_slow_operations():
    global _stop_event, _active_threads
    _stop_event.set()
    for thread in _active_threads:
        thread.join(timeout=5)
    _active_threads = []
