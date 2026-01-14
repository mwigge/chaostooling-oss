"""MSSQL lock storm chaos action."""
import os
import threading
import time
from typing import Dict, Optional

import pyodbc
from chaosotel import (ensure_initialized, flush, get_logger, get_metrics_core,
                       get_tracer)
from opentelemetry.trace import StatusCode

_active_threads = []
_stop_event = threading.Event()

def inject_lock_storm(
    host: Optional[str] = None,
    port: Optional[int] = None,
    database: Optional[str] = None,
    user: Optional[str] = None,
    password: Optional[str] = None,
    driver: Optional[str] = None,
    num_threads: int = 10,
    duration_seconds: int = 60,
    table_name: str = "chaos_test_table"
) -> Dict:
    """Inject MSSQL lock storm."""
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
    logger = get_logger()
    start_time = time.time()
    
    global _active_threads, _stop_event
    _stop_event.clear()
    _active_threads = []
    
    connection_string = f"DRIVER={{{driver}}};SERVER={host},{port};DATABASE={database};UID={user};PWD={password};Encrypt=no"
    
    locks_created = 0
    deadlocks_detected = 0
    errors = 0
    
    def lock_worker(thread_id: int):
        nonlocal locks_created, deadlocks_detected, errors
        conn = None
        try:
            with tracer.start_as_current_span(f"lock_storm.worker.{thread_id}") as span:
                from chaosotel.core.trace_core import set_db_span_attributes
                set_db_span_attributes(
                    span,
                    db_system="mssql",
                    db_name=database,
                    host=host,
                    port=port,
                    chaos_activity="mssql_lock_storm",
                    chaos_action="lock_storm",
                    chaos_operation="lock_storm",
                    chaos_thread_id=thread_id
                )
                
                conn = pyodbc.connect(connection_string, timeout=5)
                conn.autocommit = False
                cursor = conn.cursor()
                
                cursor.execute(f"""
                    IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = '{table_name}')
                    CREATE TABLE {table_name} (
                        id INT PRIMARY KEY IDENTITY(1,1),
                        value INT,
                        locked_by INT
                    )
                """)
                conn.commit()
                
                cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
                if cursor.fetchone()[0] == 0:
                    cursor.execute(f"INSERT INTO {table_name} (value) VALUES (1), (2), (3), (4), (5)")
                    conn.commit()
                
                while not _stop_event.is_set():
                    try:
                        txn_start = time.time()
                        cursor.execute("BEGIN TRANSACTION")
                        cursor.execute(f"SELECT * FROM {table_name} WITH (UPDLOCK, ROWLOCK) WHERE id = 1")
                        cursor.fetchone()

                        locks_created += 1
                        # Record lock creation
                        metrics.record_db_lock(
                            db_system=db_system,
                            lock_type="row_lock",
                            db_name=database,
                        )

                        time.sleep(0.5)
                        
                        try:
                            cursor.execute(f"UPDATE {table_name} SET locked_by = ? WHERE id = 1", thread_id)
                            conn.commit()
                        except pyodbc.Error as e:
                            if "deadlock" in str(e).lower() or "1205" in str(e):
                                deadlocks_detected += 1
                                metrics.record_db_deadlock(
                                    db_system=db_system,
                                    db_name=database,
                                )
                                logger.warning(f"Deadlock detected in thread {thread_id}: {e}")
                            conn.rollback()

                        txn_duration = (time.time() - txn_start) * 1000

                        span.set_status(StatusCode.OK)
                    except Exception as e:
                        errors += 1
                        metrics.record_db_error(db_system=db_system, error_type=type(e).__name__)
                        logger.error(f"Lock storm worker {thread_id} error: {e}")
                        if conn:
                            conn.rollback()
                        time.sleep(0.1)
        except Exception as e:
            errors += 1
            logger.error(f"Lock storm worker {thread_id} failed: {e}")
        finally:
            if conn:
                try:
                    conn.close()
                except Exception:
                    pass

    try:
        with tracer.start_as_current_span("chaos.mssql.lock_storm") as span:
            from chaosotel.core.trace_core import set_db_span_attributes
            set_db_span_attributes(
                span,
                db_system="mssql",
                db_name=database,
                host=host,
                port=port,
                chaos_activity="mssql_lock_storm",
                chaos_action="lock_storm",
                chaos_operation="lock_storm",
                chaos_num_threads=num_threads,
                chaos_duration_seconds=duration_seconds
            )
            
            logger.info(f"Starting MSSQL lock storm with {num_threads} threads for {duration_seconds}s")
            
            for i in range(num_threads):
                thread = threading.Thread(target=lock_worker, args=(i,), daemon=True)
                thread.start()
                _active_threads.append(thread)
            
            time.sleep(duration_seconds)
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
                "threads_used": num_threads
            }
            
            span.set_attribute("chaos.locks_created", locks_created)
            span.set_attribute("chaos.deadlocks_detected", deadlocks_detected)
            span.set_status(StatusCode.OK)
            
            logger.info(f"MSSQL lock storm completed: {result}")
            flush()
            return result
    except Exception as e:
        _stop_event.set()
        metrics.record_db_error(db_system=db_system, error_type=type(e).__name__)
        logger.error(f"MSSQL lock storm failed: {e}")
        flush()
        raise

def stop_lock_storm():
    global _stop_event, _active_threads
    _stop_event.set()
    for thread in _active_threads:
        thread.join(timeout=2)
    _active_threads = []

