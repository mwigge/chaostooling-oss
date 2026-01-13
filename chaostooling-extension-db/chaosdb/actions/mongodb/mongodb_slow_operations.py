"""MongoDB slow operations chaos action."""

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


def inject_slow_operations(
    host: Optional[str] = None,
    port: Optional[int] = None,
    database: Optional[str] = None,
    collection: Optional[str] = None,
    user: Optional[str] = None,
    password: Optional[str] = None,
    authSource: Optional[str] = None,
    num_threads: int = 5,
    duration_seconds: int = 60,
    operation_delay_ms: int = 5000,
) -> dict:
    """
    Inject slow operations by creating long-running operations that hold resources.

    Args:
        host: MongoDB host
        port: MongoDB port
        database: Database name
        collection: Collection name
        user: Database user
        password: Database password
        authSource: Authentication source
        num_threads: Number of concurrent slow operations
        duration_seconds: How long to run slow operations
        operation_delay_ms: Delay inside each operation in milliseconds

    Returns:
        Dict with results including operations created, average duration, etc.
    """
    # Handle string input from Chaos Toolkit configuration
    if port is not None:
        port = int(port) if isinstance(port, str) else port
    num_threads = int(num_threads) if isinstance(num_threads, str) else num_threads
    duration_seconds = (
        int(duration_seconds) if isinstance(duration_seconds, str) else duration_seconds
    )
    operation_delay_ms = (
        int(operation_delay_ms)
        if isinstance(operation_delay_ms, str)
        else operation_delay_ms
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
    logger = logging.getLogger("chaosdb.mongodb.slow_operations")
    start_time = time.time()

    uri = f"mongodb://{host}:{port}/"
    if user and password:
        uri = f"mongodb://{user}:{password}@{host}:{port}/"
        if authSource:
            uri += f"?authSource={authSource}"

    global _active_threads, _stop_event
    _stop_event.clear()
    _active_threads = []

    operations_completed = 0
    total_operation_time = 0
    errors = 0

    def slow_operation_worker(thread_id: int):
        """Worker thread that creates slow operations."""
        nonlocal operations_completed, total_operation_time, errors
        client = None
        try:
            with tracer.start_as_current_span(
                f"slow_operation.worker.{thread_id}"
            ) as span:
                from chaosotel.core.trace_core import set_db_span_attributes
                set_db_span_attributes(
                    span,
                    db_system=db_system,
                    db_name=database,
                    host=host,
                    port=port,
                    chaos_activity="mongodb_slow_operations",
                    chaos_action="slow_operations",
                    chaos_operation="slow_operations",
                    chaos_thread_id=thread_id
                )

                client = MongoClient(uri, serverSelectionTimeoutMS=5000)
                db = client[database]
                coll = db[collection]

                # Ensure test document exists
                try:
                    coll.update_one(
                        {"_id": f"slow_test_{thread_id}"},
                        {"$set": {"value": 0}},
                        upsert=True,
                    )
                except Exception:
                    pass

                end_time = time.time() + duration_seconds

                while not _stop_event.is_set() and time.time() < end_time:
                    try:
                        op_start = time.time()

                        # Start a long-running operation
                        coll.find_one({"_id": f"slow_test_{thread_id}"})

                        # Simulate slow work
                        time.sleep(operation_delay_ms / 1000.0)

                        # Update
                        coll.update_one(
                            {"_id": f"slow_test_{thread_id}"},
                            {"$inc": {"value": 1}, "$set": {"updated_at": time.time()}},
                        )

                        op_duration_ms = (time.time() - op_start) * 1000
                        operations_completed += 1
                        total_operation_time += op_duration_ms

                        tags = get_metric_tags(
                            db_name=database,
                            db_system=db_system,
                            db_operation="slow_operation",
                        )
                        metrics.record_db_query_latency(
                            op_duration_ms,
                            db_system=db_system,
                            db_name=database,
                            db_operation="slow_operation",
                            tags=tags,
                        )
                        metrics.record_db_query_count(
                            db_system=db_system,
                            db_name=database,
                            db_operation="slow_operation",
                            count=1,
                            tags=tags,
                        )

                        # Mark as slow operation if exceeds threshold
                        if op_duration_ms > operation_delay_ms:
                            span.set_attribute("chaos.slow_operation_detected", True)

                        span.set_status(StatusCode.OK)
                    except Exception as e:
                        errors += 1
                        metrics.record_db_error(
                            db_system=db_system,
                            error_type=type(e).__name__,
                            db_name=database,
                        )
                        logger.warning(f"Slow operation worker {thread_id} error: {e}")
                        span.set_status(StatusCode.ERROR, str(e))
                        time.sleep(0.1)
        except Exception as e:
            errors += 1
            logger.error(f"Slow operation worker {thread_id} failed: {e}")
        finally:
            if client:
                try:
                    client.close()
                except:
                    pass

    try:
        with tracer.start_as_current_span("chaos.mongodb.slow_operations") as span:
            span.set_attribute("db.system", db_system)
            span.set_attribute("db.name", database)
            span.set_attribute("chaos.num_threads", num_threads)
            span.set_attribute("chaos.duration_seconds", duration_seconds)
            span.set_attribute("chaos.operation_delay_ms", operation_delay_ms)
            span.set_attribute("chaos.action", "slow_operations")
            span.set_attribute("chaos.activity", "mongodb_slow_operations")
            span.set_attribute("chaos.activity.type", "action")
            span.set_attribute("chaos.system", "mongodb")
            span.set_attribute("chaos.operation", "slow_operations")

            logger.info(
                f"Starting slow operations with {num_threads} threads for {duration_seconds}s"
            )

            # Start worker threads
            for i in range(num_threads):
                thread = threading.Thread(
                    target=slow_operation_worker, args=(i,), daemon=True
                )
                thread.start()
                _active_threads.append(thread)

            # Wait for duration
            time.sleep(duration_seconds)

            # Stop all threads
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

            logger.info(f"Slow operations completed: {result}")
            flush()
            return result

    except Exception as e:
        _stop_event.set()
        metrics.record_db_error(
            db_system=db_system,
            error_type=type(e).__name__,
            db_name=database,
        )
        logger.error(f"Slow operations failed: {e}")
        flush()
        raise


def stop_slow_operations():
    """Stop any running slow operations."""
    global _stop_event, _active_threads
    _stop_event.set()
    for thread in _active_threads:
        thread.join(timeout=5)
    _active_threads = []
