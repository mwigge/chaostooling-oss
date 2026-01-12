"""MSSQL query saturation chaos action."""
import os
import pyodbc
import time
import threading
from typing import Optional, Dict
from chaosotel import ensure_initialized, get_tracer, get_logger, flush, get_metrics_core
from opentelemetry.trace import StatusCode

_active_threads = []
_stop_event = threading.Event()

def inject_query_saturation(
    metrics = get_metrics_core()
    host: Optional[str] = None,
    port: Optional[int] = None,
    database: Optional[str] = None,
    user: Optional[str] = None,
    password: Optional[str] = None,
    driver: Optional[str] = None,
    num_threads: int = 20,
    queries_per_thread: int = 1000,
    duration_seconds: int = 60,
    slow_query_threshold_ms: int = 1000
) -> Dict:
    """Saturate MSSQL with a high volume of queries."""
    host = host or os.getenv("MSSQL_HOST", "localhost")
    port = port or int(os.getenv("MSSQL_PORT", "1433"))
    database = database or os.getenv("MSSQL_DB", "master")
    user = user or os.getenv("MSSQL_USER", "sa")
    password = password or os.getenv("MSSQL_PASSWORD", "")
    driver = driver or os.getenv("MSSQL_DRIVER", "ODBC Driver 18 for SQL Server")
    
    ensure_initialized()
    tracer = get_tracer()
    logger = get_logger()
    start_time = time.time()
    
    global _active_threads, _stop_event
    _stop_event.clear()
    _active_threads = []
    
    connection_string = f"DRIVER={{{driver}}};SERVER={host},{port};DATABASE={database};UID={user};PWD={password};Encrypt=no"
    
    total_queries = 0
    slow_queries = 0
    timeouts = 0
    errors = 0
    
    def query_worker(thread_id: int):
        nonlocal total_queries, slow_queries, timeouts, errors
        conn = None
        try:
            with tracer.start_as_current_span(f"query_saturation.worker.{thread_id}") as span:
                span.set_attribute("db.system", "mssql")
                span.set_attribute("db.name", database)
                span.set_attribute("chaos.thread_id", thread_id)
                span.set_attribute("chaos.action", "query_saturation")
                span.set_attribute("chaos.activity", "mssql_query_saturation")
                span.set_attribute("chaos.activity.type", "action")
                span.set_attribute("chaos.system", "mssql")
                span.set_attribute("chaos.operation", "query_saturation")
                span.set_attribute("chaos.activity", "mssql_query_saturation")
                span.set_attribute("chaos.activity.type", "action")
                span.set_attribute("chaos.system", "mssql")
                span.set_attribute("chaos.operation", "query_saturation")
                
                conn = pyodbc.connect(connection_string, timeout=5)
                cursor = conn.cursor()
                
                query_count = 0
                end_time = time.time() + duration_seconds
                
                queries = [
                    "SELECT 1",
                    "SELECT GETDATE()",
                    "SELECT @@VERSION",
                    "SELECT DB_NAME()",
                    "SELECT @@SPID",
                    "SELECT COUNT(*) FROM sys.tables"
                ]
                
                while not _stop_event.is_set() and time.time() < end_time and query_count < queries_per_thread:
                    try:
                        query_start = time.time()
                        query = queries[query_count % len(queries)]
                        cursor.execute(query)
                        cursor.fetchall()
                        
                        query_duration_ms = (time.time() - query_start) * 1000
                        total_queries += 1
                        query_count += 1
                        
                        tags = get_metric_tags(db_name=database, db_system="mssql", db_operation="saturation_query")
                        metrics.record_db_query_latency(query_duration_ms / 1000.0, db_system=db_system, db_name=database)
                        metrics.record_db_query_count(db_system=db_system, db_name=database, count=1)
                        
                        if query_duration_ms > slow_query_threshold_ms:
                            slow_queries += 1
                        
                        
                        time.sleep(0.01)
                    except pyodbc.Error as e:
                        if "timeout" in str(e).lower():
                            timeouts += 1
                            )
                        errors += 1
                    except Exception as e:
                        errors += 1
                        metrics.record_db_error(db_system=db_system, error_type=type(e).__name__)
                        logger.warning(f"Query worker {thread_id} error: {e}")
                
                span.set_status(StatusCode.OK)
        except Exception as e:
            errors += 1
            logger.error(f"Query saturation worker {thread_id} failed: {e}")
        finally:
            if conn:
                try:
                    conn.close()
                except:
                    pass
    
    try:
        with tracer.start_as_current_span("chaos.mssql.query_saturation") as span:
            span.set_attribute("db.system", "mssql")
            span.set_attribute("db.name", database)
            span.set_attribute("chaos.num_threads", num_threads)
            span.set_attribute("chaos.duration_seconds", duration_seconds)
            span.set_attribute("chaos.action", "query_saturation")
            span.set_attribute("chaos.activity", "mssql_query_saturation")
            span.set_attribute("chaos.activity.type", "action")
            span.set_attribute("chaos.system", "mssql")
            span.set_attribute("chaos.operation", "query_saturation")
            
            logger.info(f"Starting MSSQL query saturation with {num_threads} threads for {duration_seconds}s")
            
            for i in range(num_threads):
                thread = threading.Thread(target=query_worker, args=(i,), daemon=True)
                thread.start()
                _active_threads.append(thread)
            
            for thread in _active_threads:
                thread.join(timeout=duration_seconds + 5)
            
            _stop_event.set()
            duration_ms = (time.time() - start_time) * 1000
            
            result = {
                "success": True,
                "duration_ms": duration_ms,
                "total_queries": total_queries,
                "slow_queries": slow_queries,
                "timeouts": timeouts,
                "errors": errors,
                "queries_per_second": total_queries / (duration_ms / 1000) if duration_ms > 0 else 0,
                "threads_used": num_threads
            }
            
            span.set_attribute("chaos.total_queries", total_queries)
            span.set_attribute("chaos.slow_queries", slow_queries)
            span.set_attribute("chaos.timeouts", timeouts)
            span.set_status(StatusCode.OK)
            
            logger.info(f"MSSQL query saturation completed: {result}")
            flush()
            return result
    except Exception as e:
        _stop_event.set()
        metrics.record_db_error(db_system=db_system, error_type=type(e).__name__)
        logger.error(f"MSSQL query saturation failed: {e}")
        flush()
        raise

def stop_query_saturation():
    global _stop_event, _active_threads
    _stop_event.set()
    for thread in _active_threads:
        thread.join(timeout=2)
    _active_threads = []

