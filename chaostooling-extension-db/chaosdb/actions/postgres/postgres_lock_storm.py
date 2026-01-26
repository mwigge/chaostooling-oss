"""PostgreSQL lock storm chaos action."""

import logging
import os
import threading
import time
from typing import Any, Dict, Optional

import psycopg2
from chaosotel import ensure_initialized, flush, get_metrics_core, get_tracer
from opentelemetry.trace import StatusCode

from chaosdb.common.constants import ConnectionDefaults, DatabaseDefaults
from chaosdb.common.validation import (
    validate_database_name,
    validate_host,
    validate_port,
)

_active_threads = []
_stop_event = threading.Event()


def inject_lock_storm(
    host: Optional[str] = None,
    port: Optional[int] = None,
    database: Optional[str] = None,
    user: Optional[str] = None,
    password: Optional[str] = None,
    num_threads: int = 10,
    duration_seconds: int = 60,
    table_name: str = "chaos_test_table",
) -> Dict[str, Any]:
    """
    Inject a database lock storm by creating multiple concurrent transactions
    that lock the same rows, causing contention.

    Args:
        host: PostgreSQL host
        port: PostgreSQL port
        database: Database name
        user: Database user
        password: Database password
        num_threads: Number of concurrent threads creating locks
        duration_seconds: How long to run the lock storm
        table_name: Table to use for lock contention

    Returns:
        Dict with results including locks created, deadlocks detected, etc.
    """
    # Handle string input from Chaos Toolkit configuration
    num_threads = int(num_threads) if isinstance(num_threads, str) else num_threads
    duration_seconds = (
        int(duration_seconds) if isinstance(duration_seconds, str) else duration_seconds
    )

    host = validate_host(
        host or os.getenv("POSTGRES_HOST"),
        DatabaseDefaults.POSTGRES_DEFAULT_HOST,
        "host",
    )
    port = validate_port(
        port or os.getenv("POSTGRES_PORT"),
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
    db_system = os.getenv("DB_SYSTEM", "postgresql")

    ensure_initialized()
    db_system = os.getenv("DB_SYSTEM", "postgresql")
    tracer = get_tracer()
    logger = logging.getLogger("chaosdb.postgres.lock_storm")
    metrics = get_metrics_core()
    start_time = time.time()

    # Prepare table once to ensure schema contains locked_by column
    _prepare_table(host, port, database, user, password, table_name, logger)

    global _active_threads, _stop_event
    _stop_event.clear()
    _active_threads = []

    locks_created = 0
    deadlocks_detected = 0
    errors = 0

    def lock_worker(thread_id: int) -> None:
        """Worker thread that creates and holds locks."""
        nonlocal locks_created, deadlocks_detected, errors
        conn = None
        try:
            with tracer.start_as_current_span(f"lock_storm.worker.{thread_id}") as span:
                from chaosotel.core.trace_core import set_db_span_attributes

                set_db_span_attributes(
                    span,
                    db_system=db_system,
                    db_name=database,
                    host=host,
                    port=port,
                    chaos_activity="postgresql_lock_storm",
                    chaos_action="lock_storm",
                    chaos_operation="lock_storm",
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
                conn.autocommit = False
                cursor = conn.cursor()

                primary_id = 1 if (thread_id % 2) == 0 else 2
                secondary_id = 2 if primary_id == 1 else 1

                # Continuously create locks with alternating order to force contention
                while not _stop_event.is_set():
                    try:
                        txn_start = time.time()
                        cursor.execute("BEGIN")

                        # Lock the first row
                        cursor.execute(
                            f"SELECT id FROM {table_name} WHERE id = %s FOR UPDATE",
                            (primary_id,),
                        )
                        cursor.fetchone()

                        metrics.record_db_gauge(
                            "lock_storm_threads",
                            1,
                            db_system=db_system,
                            db_name=database,
                        )

                        time.sleep(
                            0.2
                        )  # give other threads time to grab the opposite row

                        # Lock the second row (opposite order for half the threads)
                        cursor.execute(
                            f"SELECT id FROM {table_name} WHERE id = %s FOR UPDATE",
                            (secondary_id,),
                        )
                        cursor.fetchone()

                        locks_created += 1
                        # Record lock creation
                        metrics.record_db_lock(
                            db_system=db_system,
                            lock_type="row_lock",
                            db_name=database,
                        )

                        # Hold locks briefly to increase overlap
                        time.sleep(0.3)

                        try:
                            cursor.execute(
                                f"UPDATE {table_name} SET locked_by = %s WHERE id = %s",
                                (thread_id, primary_id),
                            )
                            cursor.execute(
                                f"UPDATE {table_name} SET locked_by = %s WHERE id = %s",
                                (thread_id, secondary_id),
                            )
                            conn.commit()
                        except psycopg2.extensions.TransactionRollbackError as e:
                            if "deadlock" in str(e).lower():
                                deadlocks_detected += 1
                                metrics.record_db_deadlock(
                                    db_system=db_system, db_name=database
                                )
                                logger.warning(
                                    f"Deadlock detected in thread {thread_id}: {e}"
                                )
                            conn.rollback()

                        txn_duration = (time.time() - txn_start) * 1000
                        metrics.record_db_query_latency(
                            txn_duration,
                            db_system=db_system,
                            db_name=database,
                            db_operation="lock_storm",
                        )

                        span.set_status(StatusCode.OK)
                    except Exception as e:
                        errors += 1
                        metrics.record_db_error(
                            db_system=db_system,
                            error_type=type(e).__name__,
                            db_name=database,
                        )
                        logger.error(f"Lock storm worker {thread_id} error: {e}")
                        span.set_status(StatusCode.ERROR, str(e))
                        if conn:
                            conn.rollback()
                        time.sleep(0.1)  # Brief pause before retry

        except Exception as e:
            errors += 1
            logger.error(f"Lock storm worker {thread_id} failed: {e}")
        finally:
            if conn:
                try:
                    conn.close()
                except Exception:
                    pass
            metrics.record_db_gauge(
                "lock_storm_threads", -1, db_system=db_system, db_name=database
            )

    try:
        with tracer.start_as_current_span("chaos.postgres.lock_storm") as span:
            from chaosotel.core.trace_core import set_db_span_attributes

            set_db_span_attributes(
                span,
                db_system="postgresql",
                db_name=database,
                host=host,
                port=port,
                chaos_activity="postgresql_lock_storm",
                chaos_action="lock_storm",
                chaos_operation="lock_storm",
                chaos_num_threads=num_threads,
                chaos_duration_seconds=duration_seconds,
            )

            logger.info(
                f"Starting lock storm with {num_threads} threads for {duration_seconds}s"
            )

            # Start worker threads
            for i in range(num_threads):
                thread = threading.Thread(target=lock_worker, args=(i,), daemon=True)
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
                "locks_created": locks_created,
                "deadlocks_detected": deadlocks_detected,
                "errors": errors,
                "threads_used": num_threads,
            }

            span.set_attribute("chaos.locks_created", locks_created)
            span.set_attribute("chaos.deadlocks_detected", deadlocks_detected)
            span.set_attribute("chaos.errors", errors)
            span.set_status(StatusCode.OK)

            logger.info(f"Lock storm completed: {result}")
            flush()
            return result

    except Exception as e:
        _stop_event.set()
        metrics.record_db_error(
            db_system=db_system, error_type=type(e).__name__, db_name=database
        )
        logger.error(f"Lock storm failed: {e}")
        flush()
        raise


def stop_lock_storm() -> None:
    """Stop any running lock storm."""
    global _stop_event, _active_threads
    _stop_event.set()
    for thread in _active_threads:
        thread.join(timeout=2)
    _active_threads = []


def _prepare_table(
    host: str,
    port: int,
    database: str,
    user: str,
    password: str,
    table_name: str,
    logger: logging.Logger,
) -> None:
    """
    Ensure table structure matches expectations (including locked_by column) before workers start.
    """
    conn = None
    try:
        conn = psycopg2.connect(
            host=host,
            port=port,
            database=database,
            user=user,
            password=password,
            connect_timeout=5,
        )
        conn.autocommit = True
        cursor = conn.cursor()
        cursor.execute(
            f"""
            CREATE TABLE IF NOT EXISTS {table_name} (
                id SERIAL PRIMARY KEY,
                value INTEGER,
                locked_by INTEGER
            )
        """
        )
        # Ensure locked_by column exists even if table was created by older schema
        cursor.execute(
            f"ALTER TABLE {table_name} ADD COLUMN IF NOT EXISTS locked_by INTEGER"
        )
        cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
        if cursor.fetchone()[0] < 2:
            cursor.execute(f"TRUNCATE TABLE {table_name} RESTART IDENTITY")
            cursor.execute(
                f"INSERT INTO {table_name} (value) VALUES (1), (2), (3), (4), (5)"
            )
        cursor.close()
    except Exception as exc:
        logger.warning(f"Failed to prepare table {table_name}: {exc}")
    finally:
        if conn:
            conn.close()
