"""MSSQL transaction deadlock injection chaos action."""
import os
import threading
import time
from typing import Dict, Optional

import pyodbc
from chaosotel import (ensure_initialized, flush, get_logger, get_tracer), get_metric_tags
from opentelemetry.trace import StatusCode

_active_threads = []
_stop_event = threading.Event()

def inject_deadlock(
    host: Optional[str] = None,
    port: Optional[int] = None,
    database: Optional[str] = None,
    user: Optional[str] = None,
    password: Optional[str] = None,
    driver: Optional[str] = None,
    num_threads: int = 10,
    duration_seconds: int = 60,
    table_name: str = "chaos_deadlock_table"
) -> Dict:
    """
    Inject transaction deadlocks by creating circular dependency deadlocks.
    Creates transactions that lock resources in opposite order, causing circular waits.
    """
    host = host or os.getenv("MSSQL_HOST", "localhost")
    port = port or int(os.getenv("MSSQL_PORT", "1433"))
    database = database or os.getenv("MSSQL_DB", "master")
    user = user or os.getenv("MSSQL_USER", "sa")
    password = password or os.getenv("MSSQL_PASSWORD", "")
    driver = driver or os.getenv("MSSQL_DRIVER", "FreeTDS")
    
    ensure_initialized()
    tracer = get_tracer()
    logger = get_logger()
    start_time = time.time()
    
    global _active_threads, _stop_event
    _stop_event.clear()
    _active_threads = []
    
    deadlocks_created = 0
    transactions_rolled_back = 0
    errors = 0
    
    connection_string = f"DRIVER={{{driver}}};SERVER={host},{port};DATABASE={database};UID={user};PWD={password};Encrypt=no"
    
    def deadlock_worker(thread_id: int):
        """Worker thread that creates deadlocks."""
        nonlocal deadlocks_created, transactions_rolled_back, errors
        conn = None
        try:
            with tracer.start_as_current_span(f"deadlock_injection.worker.{thread_id}") as span:
                from chaosotel.core.trace_core import set_db_span_attributes
                set_db_span_attributes(
                    span,
                    db_system="mssql",
                    db_name=database,
                    host=host,
                    port=port,
                    chaos_activity="mssql_deadlock_injection",
                    chaos_action="deadlock_injection",
                    chaos_operation="deadlock_injection",
                    chaos_thread_id=thread_id
                )
                
                conn = pyodbc.connect(connection_string, timeout=5)
                conn.autocommit = False
                cursor = conn.cursor()
                
                # Create test table if it doesn't exist
                cursor.execute(f"""
                    IF NOT EXISTS (SELECT * FROM sys.objects WHERE object_id = OBJECT_ID(N'[dbo].[{table_name}]') AND type in (N'U'))
                    CREATE TABLE [dbo].[{table_name}] (
                        id INT IDENTITY(1,1) PRIMARY KEY,
                        value INT,
                        data NVARCHAR(255)
                    )
                """)
                conn.commit()
                
                # Insert test data if needed
                cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
                if cursor.fetchone()[0] < 5:
                    cursor.execute(f"INSERT INTO {table_name} (value, data) VALUES (1, 'data1'), (2, 'data2'), (3, 'data3'), (4, 'data4'), (5, 'data5')")
                    conn.commit()
                
                end_time = time.time() + duration_seconds
                
                while not _stop_event.is_set() and time.time() < end_time:
                    try:
                        txn_start = time.time()
                        
                        # Create circular dependency
                        first_id = (thread_id % 2) + 1
                        second_id = ((thread_id + 1) % 2) + 1
                        
                        cursor.execute("BEGIN TRANSACTION")
                        
                        # Lock first resource
                        cursor.execute(f"SELECT * FROM {table_name} WITH (UPDLOCK, ROWLOCK) WHERE id = ?", first_id)
                        cursor.fetchone()
                        
                        time.sleep(0.1)
                        
                        # Try to lock second resource
                        cursor.execute(f"SELECT * FROM {table_name} WITH (UPDLOCK, ROWLOCK) WHERE id = ?", second_id)
                        cursor.fetchone()
                        
                        cursor.execute(f"UPDATE {table_name} SET value = value + 1 WHERE id = ?", first_id)
                        cursor.execute(f"UPDATE {table_name} SET value = value + 1 WHERE id = ?", second_id)
                        
                        conn.commit()
                        
                        txn_duration_ms = (time.time() - txn_start) * 1000
                        tags = get_metric_tags(db_name=database, db_system="mssql", db_operation="deadlock_txn")
                        
                        metrics.record_db_query_count(db_system=db_system, db_name=database, count=1)
                        
                        span.set_status(StatusCode.OK)
                        time.sleep(0.2)
                        
                    except pyodbc.Error as e:
                        error_str = str(e).lower()
                        if "deadlock" in error_str or "1205" in error_str:
                            deadlocks_created += 1
                            transactions_rolled_back += 1
                            
                            tags = get_metric_tags(db_name=database, db_system="mssql", db_operation="deadlock")
                            
                            
                            logger.debug(f"Deadlock detected in thread {thread_id}: {e}")
                            span.set_attribute("chaos.deadlock_detected", True)
                            span.set_status(StatusCode.OK)
                        else:
                            errors += 1
                            metrics.record_db_error(db_system=db_system, error_type=type(e).__name__)
                            logger.warning(f"Transaction rollback in thread {thread_id}: {e}")
                            span.set_status(StatusCode.ERROR, str(e))
                        
                        try:
                            conn.rollback()
                        except Exception:
                            pass
                        time.sleep(0.1)
                        
                    except Exception as e:
                        errors += 1
                        metrics.record_db_error(db_system=db_system, error_type=type(e).__name__)
                        logger.warning(f"Error in deadlock worker {thread_id}: {e}")
                        span.set_status(StatusCode.ERROR, str(e))
                        try:
                            conn.rollback()
                        except Exception:
                            pass
                        time.sleep(0.1)
                        
        except Exception as e:
            errors += 1
            logger.error(f"Deadlock worker {thread_id} failed: {e}")
        finally:
            if conn:
                try:
                    conn.close()
                except Exception:
                    pass
    
    try:
        with tracer.start_as_current_span("chaos.mssql.deadlock_injection") as span:
            span.set_attribute("db.system", "mssql")
            span.set_attribute("db.name", database)
            span.set_attribute("chaos.num_threads", num_threads)
            span.set_attribute("chaos.duration_seconds", duration_seconds)
            span.set_attribute("chaos.action", "deadlock_injection")
            span.set_attribute("chaos.activity", "mssql_deadlock_injection")
            span.set_attribute("chaos.activity.type", "action")
            span.set_attribute("chaos.system", "mssql")
            span.set_attribute("chaos.operation", "deadlock_injection")
            
            logger.info(f"Starting MSSQL deadlock injection with {num_threads} threads for {duration_seconds}s")
            
            for i in range(num_threads):
                thread = threading.Thread(target=deadlock_worker, args=(i,), daemon=True)
                thread.start()
                _active_threads.append(thread)
            
            time.sleep(duration_seconds)
            _stop_event.set()
            for thread in _active_threads:
                thread.join(timeout=10)
            
            duration_ms = (time.time() - start_time) * 1000
            
            result = {
                "success": True,
                "duration_ms": duration_ms,
                "deadlocks_created": deadlocks_created,
                "transactions_rolled_back": transactions_rolled_back,
                "errors": errors,
                "threads_used": num_threads
            }
            
            span.set_attribute("chaos.deadlocks_created", deadlocks_created)
            span.set_attribute("chaos.transactions_rolled_back", transactions_rolled_back)
            span.set_status(StatusCode.OK)
            
            logger.info(f"MSSQL deadlock injection completed: {result}")
            flush()
            return result
    except Exception as e:
        _stop_event.set()
        metrics.record_db_error(db_system=db_system, error_type=type(e).__name__)
        logger.error(f"MSSQL deadlock injection failed: {e}")
        flush()
        raise

def stop_deadlock():
    """Stop deadlock injection."""
    global _stop_event, _active_threads
    _stop_event.set()
    for thread in _active_threads:
        thread.join(timeout=5)
    _active_threads = []

