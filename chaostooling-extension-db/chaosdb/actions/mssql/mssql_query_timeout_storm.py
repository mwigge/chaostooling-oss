"""MSSQL query timeout storm chaos action."""
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

def inject_query_timeout_storm(
    host: Optional[str] = None,
    port: Optional[int] = None,
    database: Optional[str] = None,
    user: Optional[str] = None,
    password: Optional[str] = None,
    driver: Optional[str] = None,
    num_threads: int = 20,
    duration_seconds: int = 60,
    timeout_seconds: int = 1
) -> Dict:
    """
    Inject query timeout storm by executing many queries with very short timeouts.
    Tests system behavior when many operations timeout simultaneously.
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
    
    total_queries = 0
    timeouts = 0
    errors = 0
    
    connection_string = f"DRIVER={{{driver}}};SERVER={host},{port};DATABASE={database};UID={user};PWD={password};Encrypt=no"
    
    def timeout_worker(thread_id: int):
        """Worker thread that executes queries with timeouts."""
        nonlocal total_queries, timeouts, errors
        conn = None
        try:
            with tracer.start_as_current_span(f"query_timeout_storm.worker.{thread_id}") as span:
                span.set_attribute("db.system", "mssql")
                span.set_attribute("db.name", database)
                span.set_attribute("chaos.thread_id", thread_id)
                span.set_attribute("chaos.action", "query_timeout_storm")
                span.set_attribute("chaos.timeout_seconds", timeout_seconds)
                span.set_attribute("chaos.activity", "mssql_query_timeout_storm")
                span.set_attribute("chaos.activity.type", "action")
                span.set_attribute("chaos.system", "mssql")
                span.set_attribute("chaos.operation", "query_timeout_storm")
                span.set_attribute("chaos.activity", "mssql_query_timeout_storm")
                span.set_attribute("chaos.activity.type", "action")
                span.set_attribute("chaos.system", "mssql")
                span.set_attribute("chaos.operation", "query_timeout_storm")
                
                conn = pyodbc.connect(connection_string, timeout=timeout_seconds)
                cursor = conn.cursor()
                
                end_time = time.time() + duration_seconds
                
                while not _stop_event.is_set() and time.time() < end_time:
                    try:
                        query_start = time.time()
                        
                        # Execute a query that might timeout
                        try:
                            cursor.execute("WAITFOR DELAY '00:00:02'")
                            cursor.fetchone()
                            total_queries += 1
                        except pyodbc.Error as e:
                            error_str = str(e).lower()
                            if "timeout" in error_str or "timed out" in error_str:
                                timeouts += 1
                                total_queries += 1
                                
                                tags = get_metric_tags(db_name=database, db_system="mssql", db_operation="timeout")
                                
                                
                                logger.debug(f"Query timeout in thread {thread_id}")
                                span.set_attribute("chaos.timeout_detected", True)
                            else:
                                raise
                        
                        query_duration_ms = (time.time() - query_start) * 1000
                        tags = get_metric_tags(db_name=database, db_system="mssql", db_operation="query")
                        metrics.record_db_query_latency(query_duration_ms / 1000.0, db_system=db_system, db_name=database)
                        metrics.record_db_query_count(db_system=db_system, db_name=database, count=1)
                        
                        span.set_status(StatusCode.OK)
                        time.sleep(0.1)
                        
                    except Exception as e:
                        errors += 1
                        metrics.record_db_error(db_system=db_system, error_type=type(e).__name__)
                        logger.warning(f"Error in timeout worker {thread_id}: {e}")
                        span.set_status(StatusCode.ERROR, str(e))
                        time.sleep(0.1)
                        
        except Exception as e:
            errors += 1
            logger.error(f"Timeout worker {thread_id} failed: {e}")
        finally:
            if conn:
                try:
                    conn.close()
                except:
                    pass
    
    try:
        with tracer.start_as_current_span("chaos.mssql.query_timeout_storm") as span:
            span.set_attribute("db.system", "mssql")
            span.set_attribute("db.name", database)
            span.set_attribute("chaos.num_threads", num_threads)
            span.set_attribute("chaos.duration_seconds", duration_seconds)
            span.set_attribute("chaos.timeout_seconds", timeout_seconds)
            span.set_attribute("chaos.action", "query_timeout_storm")
            
            logger.info(f"Starting MSSQL query timeout storm with {num_threads} threads for {duration_seconds}s")
            
            for i in range(num_threads):
                thread = threading.Thread(target=timeout_worker, args=(i,), daemon=True)
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
                "total_queries": total_queries,
                "timeouts": timeouts,
                "errors": errors,
                "timeout_rate": timeouts / total_queries if total_queries > 0 else 0,
                "threads_used": num_threads
            }
            
            span.set_attribute("chaos.total_queries", total_queries)
            span.set_attribute("chaos.timeouts", timeouts)
            span.set_attribute("chaos.timeout_rate", result["timeout_rate"])
            span.set_status(StatusCode.OK)
            
            logger.info(f"MSSQL query timeout storm completed: {result}")
            flush()
            return result
    except Exception as e:
        _stop_event.set()
        metrics.record_db_error(db_system=db_system, error_type=type(e).__name__)
        logger.error(f"MSSQL query timeout storm failed: {e}")
        flush()
        raise

def stop_query_timeout_storm():
    """Stop query timeout storm."""
    global _stop_event, _active_threads
    _stop_event.set()
    for thread in _active_threads:
        thread.join(timeout=5)
    _active_threads = []

