"""MSSQL slow transaction chaos action."""
import os
import pyodbc
import time
import threading
from typing import Optional, Dict
from chaosotel import ensure_initialized, get_tracer, get_logger, flush, get_metrics_core
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
    table_name: str = "chaos_test_table"
) -> Dict:
    """Inject slow MSSQL transactions."""
    host = host or os.getenv("MSSQL_HOST", "localhost")
    port = port or int(os.getenv("MSSQL_PORT", "1433"))
    database = database or os.getenv("MSSQL_DB", "master")
    user = user or os.getenv("MSSQL_USER", "sa")
    password = password or os.getenv("MSSQL_PASSWORD", "")
    driver = driver or os.getenv("MSSQL_DRIVER", "ODBC Driver 18 for SQL Server")
    
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
    
    transactions_completed = 0
    total_transaction_time = 0
    errors = 0
    
    def slow_transaction_worker(thread_id: int):
        nonlocal transactions_completed, total_transaction_time, errors
        conn = None
        try:
            with tracer.start_as_current_span(f"slow_transaction.worker.{thread_id}") as span:
                span.set_attribute("db.system", "mssql")
                span.set_attribute("db.name", database)
                span.set_attribute("chaos.thread_id", thread_id)
                span.set_attribute("chaos.action", "slow_transactions")
                span.set_attribute("chaos.activity", "mssql_slow_transactions")
                span.set_attribute("chaos.activity.type", "action")
                span.set_attribute("chaos.system", "mssql")
                span.set_attribute("chaos.operation", "slow_transactions")
                span.set_attribute("chaos.activity", "mssql_slow_transactions")
                span.set_attribute("chaos.activity.type", "action")
                span.set_attribute("chaos.system", "mssql")
                span.set_attribute("chaos.operation", "slow_transactions")
                
                conn = pyodbc.connect(connection_string, timeout=5)
                conn.autocommit = False
                cursor = conn.cursor()
                
                cursor.execute(f"""
                    IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = '{table_name}')
                    CREATE TABLE {table_name} (
                        id INT PRIMARY KEY IDENTITY(1,1),
                        value INT,
                        updated_at DATETIME DEFAULT GETDATE()
                    )
                """)
                conn.commit()
                
                cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
                if cursor.fetchone()[0] == 0:
                    cursor.execute(f"INSERT INTO {table_name} (value) VALUES (1), (2), (3), (4), (5)")
                    conn.commit()
                
                end_time = time.time() + duration_seconds
                
                while not _stop_event.is_set() and time.time() < end_time:
                    try:
                        txn_start = time.time()
                        cursor.execute("BEGIN TRANSACTION")
                        cursor.execute(f"SELECT * FROM {table_name} WITH (UPDLOCK, ROWLOCK) WHERE id = 1")
                        cursor.fetchone()
                        time.sleep(transaction_delay_ms / 1000.0)
                        cursor.execute(f"UPDATE {table_name} SET value = value + 1, updated_at = GETDATE() WHERE id = 1")
                        conn.commit()
                        
                        txn_duration_ms = (time.time() - txn_start) * 1000
                        transactions_completed += 1
                        total_transaction_time += txn_duration_ms
                        
                        tags = get_metric_tags(db_name=database, db_system="mssql", db_operation="slow_transaction")
                        
                        
                        if txn_duration_ms > 1000 and metrics_module.slow_query_counter:
                            metrics_module.slow_query_counter.add(1, tags)
                        
                        span.set_status(StatusCode.OK)
                    except Exception as e:
                        errors += 1
                        metrics.record_db_error(db_system=db_system, error_type=type(e).__name__)
                        logger.warning(f"Slow transaction worker {thread_id} error: {e}")
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
        with tracer.start_as_current_span("chaos.mssql.slow_transactions") as span:
            span.set_attribute("db.system", "mssql")
            span.set_attribute("db.name", database)
            span.set_attribute("chaos.num_threads", num_threads)
            span.set_attribute("chaos.duration_seconds", duration_seconds)
            span.set_attribute("chaos.transaction_delay_ms", transaction_delay_ms)
            span.set_attribute("chaos.action", "slow_transactions")
            span.set_attribute("chaos.activity", "mssql_slow_transactions")
            span.set_attribute("chaos.activity.type", "action")
            span.set_attribute("chaos.system", "mssql")
            span.set_attribute("chaos.operation", "slow_transactions")
            
            logger.info(f"Starting MSSQL slow transactions with {num_threads} threads for {duration_seconds}s")
            
            for i in range(num_threads):
                thread = threading.Thread(target=slow_transaction_worker, args=(i,), daemon=True)
                thread.start()
                _active_threads.append(thread)
            
            time.sleep(duration_seconds)
            _stop_event.set()
            for thread in _active_threads:
                thread.join(timeout=10)
            
            duration_ms = (time.time() - start_time) * 1000
            avg_transaction_time = total_transaction_time / transactions_completed if transactions_completed > 0 else 0
            
            result = {
                "success": True,
                "duration_ms": duration_ms,
                "transactions_completed": transactions_completed,
                "average_transaction_time_ms": avg_transaction_time,
                "errors": errors,
                "threads_used": num_threads
            }
            
            span.set_attribute("chaos.transactions_completed", transactions_completed)
            span.set_attribute("chaos.average_transaction_time_ms", avg_transaction_time)
            span.set_status(StatusCode.OK)
            
            logger.info(f"MSSQL slow transactions completed: {result}")
            flush()
            return result
    except Exception as e:
        _stop_event.set()
        metrics.record_db_error(db_system=db_system, error_type=type(e).__name__)
        logger.error(f"MSSQL slow transactions failed: {e}")
        flush()
        raise

def stop_slow_transactions():
    global _stop_event, _active_threads
    _stop_event.set()
    for thread in _active_threads:
        thread.join(timeout=5)
    _active_threads = []

