"""MSSQL slow transaction chaos action."""

import logging
import os
import threading
import time
from typing import Optional

import pyodbc
from chaosotel import (ensure_initialized, flush, get_metric_tags, get_metrics_core, get_tracer)
from opentelemetry._logs import get_logger_provider
from opentelemetry.sdk._logs import LoggingHandler
from opentelemetry.trace import StatusCode

_active_threads = []
_stop_event = threading.Event()


def inject_slow_transactions(
    host: Optional[str] = None,
    port: Optional[int] = None,
    database: Optional[str] = None,
    user: Optional[str] = None,
    password: Optional[str] = None,
    driver: Optional[str] = None,
    num_threads: int = 5,
    duration_seconds: int = 60,
    transaction_delay_ms: int = 5000,
    table_name: str = "chaos_test_table",
) -> dict:
    """Inject slow MSSQL transactions."""
    host = host or os.getenv("MSSQL_HOST", "localhost")
    port = port or int(os.getenv("MSSQL_PORT", "1433"))
    database = database or os.getenv("MSSQL_DB", "master")
    user = user or os.getenv("MSSQL_USER", "sa")
    password = password or os.getenv("MSSQL_PASSWORD", "")
    driver = driver or os.getenv("MSSQL_DRIVER", "FreeTDS")

    ensure_initialized()
    db_system = os.getenv("DB_SYSTEM", "mssql")
    metrics = get_metrics_core()
    tracer = get_tracer()
    
    # Setup OpenTelemetry logger via LoggingHandler (OpenTelemetry standard)
    logger_provider = get_logger_provider()
    if logger_provider:
        handler = LoggingHandler(level=logging.INFO, logger_provider=logger_provider)
        logger = logging.getLogger("chaosdb.mssql.slow_transactions")
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
    else:
        logger = logging.getLogger("chaosdb.mssql.slow_transactions")
    
    start_time = time.time()

    global _active_threads, _stop_event
    _stop_event.clear()
    _active_threads = []

    connection_string = f"DRIVER={{{driver}}};SERVER={host},{port};DATABASE={database};UID={user};PWD={password};Encrypt=no"

    transactions_completed = 0
    total_transaction_time = 0
    errors = 0

    def slow_transaction_worker(thread_id: int):
        nonlocal transactions_completed, total_transaction_time, errors
        conn = None
        try:
            with tracer.start_as_current_span(
                f"slow_transaction.worker.{thread_id}"
            ) as span:
                from chaosotel.core.trace_core import set_db_span_attributes
                set_db_span_attributes(
                    span,
                    db_system="mssql",
                    db_name=database,
                    host=host,
                    port=port,
                    chaos_activity="mssql_slow_transactions",
                    chaos_action="slow_transactions",
                    chaos_operation="slow_transactions",
                    chaos_thread_id=thread_id
                )

                conn = pyodbc.connect(connection_string, timeout=5)
                conn.autocommit = False
                cursor = conn.cursor()

                cursor.execute(
                    f"""
                    IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = '{table_name}')
                    CREATE TABLE {table_name} (
                        id INT PRIMARY KEY IDENTITY(1,1),
                        value INT,
                        updated_at DATETIME DEFAULT GETDATE()
                    )
                """
                )
                conn.commit()

                cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
                if cursor.fetchone()[0] == 0:
                    cursor.execute(
                        f"INSERT INTO {table_name} (value) VALUES (1), (2), (3), (4), (5)"
                    )
                    conn.commit()

                end_time = time.time() + duration_seconds

                while not _stop_event.is_set() and time.time() < end_time:
                    try:
                        txn_start = time.time()
                        cursor.execute("BEGIN TRANSACTION")
                        cursor.execute(
                            f"SELECT * FROM {table_name} WITH (UPDLOCK, ROWLOCK) WHERE id = 1"
                        )
                        cursor.fetchone()
                        time.sleep(transaction_delay_ms / 1000.0)
                        cursor.execute(
                            f"UPDATE {table_name} SET value = value + 1, updated_at = GETDATE() WHERE id = 1"
                        )
                        conn.commit()

                        txn_duration_ms = (time.time() - txn_start) * 1000
                        transactions_completed += 1
                        total_transaction_time += txn_duration_ms

                        tags = get_metric_tags(
                            db_name=database,
                            db_system="mssql",
                            db_operation="slow_transaction",
                        )

                        # Record slow query if exceeds threshold (using transaction_delay_ms as threshold)
                        if txn_duration_ms > transaction_delay_ms:
                            metrics.record_db_slow_query_count(
                                db_system=db_system,
                                threshold_ms=transaction_delay_ms,
                                db_name=database,
                                tags=tags,
                            )

                        span.set_status(StatusCode.OK)
                    except Exception as e:
                        errors += 1
                        metrics.record_db_error(
                            db_system=db_system, error_type=type(e).__name__
                        )
                        logger.warning(
                            f"Slow transaction worker {thread_id} error: {e}",
                            exc_info=True,
                        )
                        if conn:
                            try:
                                conn.rollback()
                            except Exception:
                                pass
                        time.sleep(0.1)
        except Exception as e:
            errors += 1
            logger.error(
                f"Slow transaction worker {thread_id} failed: {e}",
                exc_info=True,
            )
        finally:
            if conn:
                try:
                    conn.close()
                except Exception:
                    pass

    try:
        with tracer.start_as_current_span("chaos.mssql.slow_transactions") as span:
            from chaosotel.core.trace_core import set_db_span_attributes
            set_db_span_attributes(
                span,
                db_system="mssql",
                db_name=database,
                host=host,
                port=port,
                chaos_activity="mssql_slow_transactions",
                chaos_action="slow_transactions",
                chaos_operation="slow_transactions",
                chaos_num_threads=num_threads,
                chaos_duration_seconds=duration_seconds,
                chaos_transaction_delay_ms=transaction_delay_ms
            )
            span.set_attribute("chaos.operation", "slow_transactions")

            logger.info(
                f"Starting MSSQL slow transactions with {num_threads} threads for {duration_seconds}s"
            )

            for i in range(num_threads):
                thread = threading.Thread(
                    target=slow_transaction_worker, args=(i,), daemon=True
                )
                thread.start()
                _active_threads.append(thread)

            time.sleep(duration_seconds)
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

            logger.info(f"MSSQL slow transactions completed: {result}")
            flush()
            return result
    except Exception as e:
        _stop_event.set()
        metrics.record_db_error(db_system=db_system, error_type=type(e).__name__)
        logger.error(
            f"MSSQL slow transactions failed: {e}",
            exc_info=True,
        )
        flush()
        raise


def stop_slow_transactions():
    global _stop_event, _active_threads
    _stop_event.set()
    for thread in _active_threads:
        thread.join(timeout=5)
    _active_threads = []
