"""MongoDB document contention chaos action."""

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
from pymongo.errors import OperationFailure

_active_threads = []
_stop_event = threading.Event()


def inject_document_contention(
    host: Optional[str] = None,
    port: Optional[int] = None,
    database: Optional[str] = None,
    collection: Optional[str] = None,
    user: Optional[str] = None,
    password: Optional[str] = None,
    authSource: Optional[str] = None,
    num_threads: int = 10,
    duration_seconds: int = 60,
) -> dict:
    """
    Inject document contention by creating concurrent updates to the same document.

    Args:
        host: MongoDB host
        port: MongoDB port
        database: Database name
        collection: Collection name
        user: Database user
        password: Database password
        authSource: Authentication source
        num_threads: Number of concurrent threads updating the same document
        duration_seconds: How long to run the contention scenario

    Returns:
        Dict with results including operations completed, write errors, etc.
    """
    # Handle string input from Chaos Toolkit configuration
    if port is not None:
        port = int(port) if isinstance(port, str) else port
    num_threads = int(num_threads) if isinstance(num_threads, str) else num_threads
    duration_seconds = (
        int(duration_seconds) if isinstance(duration_seconds, str) else duration_seconds
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
    logger = logging.getLogger("chaosdb.mongodb.document_contention")
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
    write_errors = 0
    errors = 0

    def contention_worker(thread_id: int):
        """Worker thread that creates contention by updating the same document."""
        nonlocal operations_completed, write_errors, errors
        client = None
        try:
            with tracer.start_as_current_span(
                f"document_contention.worker.{thread_id}"
            ) as span:
                span.set_attribute("db.system", db_system)
                span.set_attribute("db.name", database)
                span.set_attribute("chaos.thread_id", thread_id)
                span.set_attribute("chaos.action", "document_contention")
                span.set_attribute("chaos.activity", "mongodb_document_contention")
                span.set_attribute("chaos.activity.type", "action")
                span.set_attribute("chaos.system", "mongodb")
                span.set_attribute("chaos.operation", "document_contention")

                client = MongoClient(uri, serverSelectionTimeoutMS=5000)
                db = client[database]
                coll = db[collection]

                # Ensure test document exists
                try:
                    coll.update_one(
                        {"_id": "contention_test"},
                        {"$set": {"value": 0, "thread_id": thread_id}},
                        upsert=True,
                    )
                except Exception:
                    pass

                end_time = time.time() + duration_seconds

                while not _stop_event.is_set() and time.time() < end_time:
                    try:
                        op_start = time.time()

                        # Concurrent updates to same document
                        result = coll.update_one(
                            {"_id": "contention_test"},
                            {
                                "$inc": {"value": 1},
                                "$set": {
                                    "last_thread": thread_id,
                                    "updated_at": time.time(),
                                },
                            },
                            upsert=False,
                        )

                        op_duration_ms = (time.time() - op_start) * 1000
                        operations_completed += 1

                        tags = get_metric_tags(
                            db_name=database,
                            db_system=db_system,
                            db_operation="contention_update",
                        )
                        metrics.record_db_query_latency(
                            op_duration_ms,
                            db_system=db_system,
                            db_name=database,
                            db_operation="contention_update",
                            tags=tags,
                        )
                        metrics.record_db_query_count(
                            db_system=db_system,
                            db_name=database,
                            db_operation="contention_update",
                            count=1,
                            tags=tags,
                        )

                        if not result.acknowledged:
                            write_errors += 1

                        span.set_status(StatusCode.OK)
                        time.sleep(0.1)
                    except OperationFailure as e:
                        write_errors += 1
                        errors += 1
                        metrics.record_db_error(
                            db_system=db_system,
                            error_type="OperationFailure",
                            db_name=database,
                        )
                        logger.warning(
                            f"Document contention worker {thread_id} error: {e}"
                        )
                    except Exception as e:
                        errors += 1
                        metrics.record_db_error(
                            db_system=db_system,
                            error_type=type(e).__name__,
                            db_name=database,
                        )
                        logger.error(
                            f"Document contention worker {thread_id} error: {e}"
                        )
                        span.set_status(StatusCode.ERROR, str(e))
                        time.sleep(0.1)
        except Exception as e:
            errors += 1
            logger.error(f"Document contention worker {thread_id} failed: {e}")
        finally:
            if client:
                try:
                    client.close()
                except:
                    pass

    try:
        with tracer.start_as_current_span("chaos.mongodb.document_contention") as span:
            span.set_attribute("db.system", db_system)
            span.set_attribute("db.name", database)
            span.set_attribute("chaos.num_threads", num_threads)
            span.set_attribute("chaos.duration_seconds", duration_seconds)
            span.set_attribute("chaos.action", "document_contention")
            span.set_attribute("chaos.activity", "mongodb_document_contention")
            span.set_attribute("chaos.activity.type", "action")
            span.set_attribute("chaos.system", "mongodb")
            span.set_attribute("chaos.operation", "document_contention")

            logger.info(
                f"Starting document contention with {num_threads} threads for {duration_seconds}s"
            )

            # Start worker threads
            for i in range(num_threads):
                thread = threading.Thread(
                    target=contention_worker, args=(i,), daemon=True
                )
                thread.start()
                _active_threads.append(thread)

            # Wait for duration
            time.sleep(duration_seconds)

            # Stop all threads
            _stop_event.set()
            for thread in _active_threads:
                thread.join(timeout=5)

            duration_ms = (time.time() - start_time) * 1000

            result = {
                "success": True,
                "duration_ms": duration_ms,
                "operations_completed": operations_completed,
                "write_errors": write_errors,
                "errors": errors,
                "threads_used": num_threads,
            }

            span.set_attribute("chaos.operations_completed", operations_completed)
            span.set_attribute("chaos.write_errors", write_errors)
            span.set_status(StatusCode.OK)

            logger.info(f"Document contention completed: {result}")
            flush()
            return result

    except Exception as e:
        _stop_event.set()
        metrics.record_db_error(
            db_system=db_system,
            error_type=type(e).__name__,
            db_name=database,
        )
        logger.error(f"Document contention failed: {e}")
        flush()
        raise


def stop_document_contention():
    """Stop any running document contention."""
    global _stop_event, _active_threads
    _stop_event.set()
    for thread in _active_threads:
        thread.join(timeout=2)
    _active_threads = []
