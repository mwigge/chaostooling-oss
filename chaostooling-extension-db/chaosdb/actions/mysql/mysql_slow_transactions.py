"""MySQL slow transaction chaos action."""

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


def _prepare_table(
    host: str,
    port: int,
    database: str,
    user: str,
    password: str,
    table_name: str,
    logger,
):
    """Prepare test table if it doesn't exist."""
    try:
        conn = mysql.connector.connect(
            host=host,
            port=port,
            database=database,
            user=user,
            password=password,
            connect_timeout=5,
        )
        cursor = conn.cursor()

        cursor.execute(
            f"""
            CREATE TABLE IF NOT EXISTS {table_name} (
                id INT AUTO_INCREMENT PRIMARY KEY,
                value INT,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
            )
        """
        )
        conn.commit()

        # Initialize with test data if empty
        cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
        if cursor.fetchone()[0] == 0:
            cursor.execute(
                f"INSERT INTO {table_name} (value) VALUES (1), (2), (3), (4), (5)"
            )
            conn.commit()
            logger.info(f"Initialized {table_name} with test data")

        cursor.close()
        conn.close()
    except Exception as e:
        logger.warning(f"Failed to prepare table {table_name}: {e}")


def inject_slow_transactions(
    host: Optional[str] = None,
    port: Optional[int] = None,
    database: Optional[str] = None,
    user: Optional[str] = None,
    password: Optional[str] = None,
    num_threads: int = 5,
    duration_seconds: int = 60,
    transaction_delay_ms: int = 5000,
    table_name: str = "chaos_test_table",
) -> dict:
    """
    Inject slow transactions by creating long-running transactions that hold locks.

    Args:
        host: MySQL host
        port: MySQL port
        database: Database name
        user: Database user
        password: Database password
        num_threads: Number of concurrent slow transactions
        duration_seconds: How long to run slow transactions
        transaction_delay_ms: Delay inside each transaction in milliseconds
        table_name: Table to use for transactions

    Returns:
        Dict with results including transactions created, average duration, etc.
    """
    # Handle string input from Chaos Toolkit configuration
    if port is not None:
        port = int(port) if isinstance(port, str) else port
    num_threads = int(num_threads) if isinstance(num_threads, str) else num_threads
    duration_seconds = (
        int(duration_seconds) if isinstance(duration_seconds, str) else duration_seconds
    )
    transaction_delay_ms = (
        int(transaction_delay_ms)
        if isinstance(transaction_delay_ms, str)
        else transaction_delay_ms
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
    logger = logging.getLogger("chaosdb.mysql.slow_transactions")
    start_time = time.time()

    # Run table setup once to avoid concurrent DDL conflicts
    _prepare_table(host, port, database, user, password, table_name, logger)

    global _active_threads, _stop_event
    _stop_event.clear()
    _active_threads = []

    transactions_completed = 0
    total_transaction_time = 0
    errors = 0

    def slow_transaction_worker(thread_id: int):
        """Worker thread that creates slow transactions."""
        nonlocal transactions_completed, total_transaction_time, errors
        conn = None
        try:
            with tracer.start_as_current_span(
                f"slow_transaction.worker.{thread_id}"
            ) as span:
                from chaosotel.core.trace_core import set_db_span_attributes
                set_db_span_attributes(
                    span,
                    db_system=db_system,
                    db_name=database,
                    host=host,
                    port=port,
                    chaos_activity="mysql_slow_transactions",
                    chaos_action="slow_transactions",
                    chaos_operation="slow_transactions",
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
                conn.autocommit = False
                cursor = conn.cursor()

                end_time = time.time() + duration_seconds

                while not _stop_event.is_set() and time.time() < end_time:
                    try:
                        txn_start = time.time()

                        # Start a long-running transaction
                        cursor.execute("START TRANSACTION")

                        # Lock a row
                        cursor.execute(
                            f"SELECT * FROM {table_name} WHERE id = 1 FOR UPDATE"
                        )
                        cursor.fetchone()

                        # Simulate slow work inside transaction
                        time.sleep(transaction_delay_ms / 1000.0)

                        # Update the row
                        cursor.execute(
                            f"UPDATE {table_name} SET value = value + 1, updated_at = NOW() WHERE id = 1"
                        )

                        # Commit the transaction
                        conn.commit()

                        txn_duration_ms = (time.time() - txn_start) * 1000
                        transactions_completed += 1
                        total_transaction_time += txn_duration_ms

                        tags = get_metric_tags(
                            db_name=database,
                            db_system=db_system,
                            db_operation="slow_transaction",
                        )
                        metrics.record_db_query_latency(
                            txn_duration_ms,
                            db_system=db_system,
                            db_name=database,
                            db_operation="slow_transaction",
                            tags=tags,
                        )
                        metrics.record_db_query_count(
                            db_system=db_system,
                            db_name=database,
                            db_operation="slow_transaction",
                            count=1,
                            tags=tags,
                        )

                        # Mark as slow transaction if exceeds threshold
                        if txn_duration_ms > transaction_delay_ms:
                            span.set_attribute("chaos.slow_transaction_detected", True)

                        span.set_status(StatusCode.OK)

                    except Exception as e:
                        errors += 1
                        metrics.record_db_error(
                            db_system=db_system,
                            error_type=type(e).__name__,
                            db_name=database,
                        )
                        logger.warning(
                            f"Slow transaction worker {thread_id} error: {e}"
                        )
                        if conn:
                            try:
                                conn.rollback()
                            except:
                                pass
                        time.sleep(0.1)

        except Exception as e:
            errors += 1
            logger.error(f"Slow transaction worker {thread_id} failed: {e}")
        finally:
            if conn:
                try:
                    conn.close()
                except:
                    pass

    try:
        with tracer.start_as_current_span("chaos.mysql.slow_transactions") as span:
            span.set_attribute("db.system", db_system)
            span.set_attribute("db.name", database)
            span.set_attribute("network.peer.address", host)
            span.set_attribute("network.peer.port", port)
            span.set_attribute("chaos.num_threads", num_threads)
            span.set_attribute("chaos.duration_seconds", duration_seconds)
            span.set_attribute("chaos.transaction_delay_ms", transaction_delay_ms)
            span.set_attribute("chaos.action", "slow_transactions")
            span.set_attribute("chaos.activity", "mysql_slow_transactions")
            span.set_attribute("chaos.activity.type", "action")
            span.set_attribute("chaos.system", "mysql")
            span.set_attribute("chaos.operation", "slow_transactions")

            logger.info(
                f"Starting slow transactions with {num_threads} threads for {duration_seconds}s"
            )

            # Start worker threads
            for i in range(num_threads):
                thread = threading.Thread(
                    target=slow_transaction_worker, args=(i,), daemon=True
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
            avg_transaction_time = (
                total_transaction_time / transactions_completed
                if transactions_completed > 0
                else 0
            )

            result = {
                "success": True,
                "duration_ms": duration_ms,
                "transactions_completed": transactions_completed,
                "average_transaction_time_ms": avg_transaction_time,
                "errors": errors,
                "threads_used": num_threads,
            }

            span.set_attribute("chaos.transactions_completed", transactions_completed)
            span.set_attribute(
                "chaos.average_transaction_time_ms", avg_transaction_time
            )
            span.set_status(StatusCode.OK)

            logger.info(f"Slow transactions completed: {result}")
            flush()
            return result

    except Exception as e:
        _stop_event.set()
        metrics.record_db_error(
            db_system=db_system,
            error_type=type(e).__name__,
            db_name=database,
        )
        logger.error(f"Slow transactions failed: {e}")
        flush()
        raise


def stop_slow_transactions():
    """Stop any running slow transactions."""
    global _stop_event, _active_threads
    _stop_event.set()
    for thread in _active_threads:
        thread.join(timeout=5)
    _active_threads = []
