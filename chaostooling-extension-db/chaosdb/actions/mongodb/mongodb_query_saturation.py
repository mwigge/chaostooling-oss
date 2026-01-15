"""MongoDB query saturation chaos action."""

import logging
import os
import threading
import time
from typing import Optional

from chaosotel import (
    ensure_initialized,
    flush,
    get_metric_tags,
    get_metrics_core,
    get_tracer,
)
from opentelemetry.trace import StatusCode
from pymongo import MongoClient

_active_threads = []
_stop_event = threading.Event()


def inject_query_saturation(
    host: Optional[str] = None,
    port: Optional[int] = None,
    database: Optional[str] = None,
    collection: Optional[str] = None,
    user: Optional[str] = None,
    password: Optional[str] = None,
    authSource: Optional[str] = None,
    num_threads: int = 20,
    operations_per_thread: int = 1000,
    duration_seconds: int = 60,
    slow_operation_threshold_ms: int = 1000,
) -> dict:
    """
    Saturate MongoDB with a high volume of operations to test operation handling capacity.

    Args:
        host: MongoDB host
        port: MongoDB port
        database: Database name
        collection: Collection name
        user: Database user
        password: Database password
        authSource: Authentication source
        num_threads: Number of concurrent operation threads
        operations_per_thread: Target operations per thread
        duration_seconds: Maximum duration to run
        slow_operation_threshold_ms: Threshold for slow operation detection

    Returns:
        Dict with results including total operations, slow operations, timeouts, etc.
    """
    # Handle string input from Chaos Toolkit configuration
    if port is not None:
        port = int(port) if isinstance(port, str) else port
    num_threads = int(num_threads) if isinstance(num_threads, str) else num_threads
    operations_per_thread = (
        int(operations_per_thread)
        if isinstance(operations_per_thread, str)
        else operations_per_thread
    )
    duration_seconds = (
        int(duration_seconds) if isinstance(duration_seconds, str) else duration_seconds
    )
    slow_operation_threshold_ms = (
        int(slow_operation_threshold_ms)
        if isinstance(slow_operation_threshold_ms, str)
        else slow_operation_threshold_ms
    )

    host = host or os.getenv("MONGO_HOST", "localhost")
    port = port or int(os.getenv("MONGO_PORT", "27017"))
    database = database or os.getenv("MONGO_DB", "test")
    collection = collection or "chaos_test_collection"
    user = user or os.getenv("MONGO_USER")
    password = password or os.getenv("MONGO_PASSWORD")
    authSource = authSource or os.getenv("MONGO_AUTHSOURCE")

    ensure_initialized()
    db_system = os.getenv("DB_SYSTEM", "mongodb")
    metrics = get_metrics_core()
    tracer = get_tracer()
    logger = logging.getLogger("chaosdb.mongodb.query_saturation")
    start_time = time.time()

    global _active_threads, _stop_event
    _stop_event.clear()
    _active_threads = []

    uri = f"mongodb://{host}:{port}/"
    if user and password:
        uri = f"mongodb://{user}:{password}@{host}:{port}/"
        if authSource:
            uri += f"?authSource={authSource}"

    total_operations = 0
    slow_operations = 0
    timeouts = 0
    errors = 0

    def query_worker(thread_id: int):
        """Worker thread that executes operations."""
        nonlocal total_operations, slow_operations, timeouts, errors
        client = None
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
                    chaos_activity="mongodb_query_saturation",
                    chaos_action="query_saturation",
                    chaos_operation="query_saturation",
                    chaos_thread_id=thread_id,
                )

                client = MongoClient(uri, serverSelectionTimeoutMS=5000)
                db = client[database]
                coll = db[collection]

                # Ensure some test data
                try:
                    coll.insert_one({"_id": f"test_{thread_id}", "value": 0})
                except Exception:
                    pass  # Document may already exist

                operation_count = 0
                end_time = time.time() + duration_seconds

                while (
                    not _stop_event.is_set()
                    and time.time() < end_time
                    and operation_count < operations_per_thread
                ):
                    try:
                        op_start = time.time()

                        # Various operations
                        ops = [
                            lambda: coll.find_one({"_id": f"test_{thread_id}"}),
                            lambda: coll.count_documents({}),
                            lambda: list(coll.find({}).limit(10)),
                            lambda: coll.find({}).limit(1).next(),
                            lambda: db.command("ping"),
                            lambda: db.command("serverStatus"),
                        ]

                        op = ops[operation_count % len(ops)]
                        op()

                        op_duration_ms = (time.time() - op_start) * 1000
                        total_operations += 1
                        operation_count += 1

                        tags = get_metric_tags(
                            db_name=database,
                            db_system=db_system,
                            db_operation="saturation_query",
                        )
                        metrics.record_db_query_latency(
                            op_duration_ms,
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

                        if op_duration_ms > slow_operation_threshold_ms:
                            slow_operations += 1

                        time.sleep(0.01)
                    except Exception as e:
                        error_msg = str(e).lower()
                        if "timeout" in error_msg:
                            timeouts += 1
                        errors += 1
                        metrics.record_db_error(
                            db_system=db_system,
                            error_type=type(e).__name__,
                            db_name=database,
                        )
                        logger.warning(f"Query worker {thread_id} error: {e}")

                span.set_status(StatusCode.OK)
                span.set_attribute("chaos.operations_executed", operation_count)

        except Exception as e:
            errors += 1
            metrics.record_db_error(
                db_system=db_system,
                error_type=type(e).__name__,
                db_name=database,
            )
            logger.error(f"Query saturation worker {thread_id} failed: {e}")
        finally:
            if client:
                try:
                    client.close()
                except Exception:
                    pass

    try:
        with tracer.start_as_current_span("chaos.mongodb.query_saturation") as span:
            from chaosotel.core.trace_core import set_db_span_attributes

            set_db_span_attributes(
                span,
                db_system=db_system,
                db_name=database,
                host=host,
                port=port,
                chaos_activity="mongodb_query_saturation",
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
                "total_operations": total_operations,
                "slow_operations": slow_operations,
                "timeouts": timeouts,
                "errors": errors,
                "operations_per_second": (
                    total_operations / (duration_ms / 1000) if duration_ms > 0 else 0
                ),
                "threads_used": num_threads,
            }

            span.set_attribute("chaos.total_operations", total_operations)
            span.set_attribute("chaos.slow_operations", slow_operations)
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
