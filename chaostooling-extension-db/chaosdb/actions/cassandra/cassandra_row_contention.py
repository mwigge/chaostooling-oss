"""Cassandra row contention chaos action."""
import os
import time
import threading
from typing import Optional, Dict
from cassandra.cluster import Cluster
from cassandra.query import SimpleStatement
from chaosotel import ensure_initialized, get_tracer, get_logger, flush, get_metrics_core
from opentelemetry.trace import StatusCode

_active_threads = []
_stop_event = threading.Event()

def inject_row_contention(
    host: Optional[str] = None,
    port: Optional[int] = None,
    keyspace: Optional[str] = None,
    user: Optional[str] = None,
    password: Optional[str] = None,
    num_threads: int = 10,
    duration_seconds: int = 60,
    table_name: str = "chaos_test_table"
) -> Dict:
    """Inject Cassandra row contention by concurrent operations on same partition."""
    host = host or os.getenv("CASSANDRA_HOST", "localhost")
    port = port or int(os.getenv("CASSANDRA_PORT", "9042"))
    keyspace = keyspace or os.getenv("CASSANDRA_KEYSPACE", "system")
    user = user or os.getenv("CASSANDRA_USER")
    password = password or os.getenv("CASSANDRA_PASSWORD")
    
    ensure_initialized()
    metrics = get_metrics_core()
    tracer = get_tracer()
    logger = get_logger()
    start_time = time.time()
    
    global _active_threads, _stop_event
    _stop_event.clear()
    _active_threads = []
    
    operations_completed = 0
    read_timeouts = 0
    write_timeouts = 0
    errors = 0
    
    def contention_worker(thread_id: int):
        nonlocal operations_completed, read_timeouts, write_timeouts, errors
        cluster = None
        session = None
        try:
            with tracer.start_as_current_span(f"row_contention.worker.{thread_id}") as span:
                span.set_attribute("db.system", "cassandra")
                span.set_attribute("db.name", keyspace)
                span.set_attribute("chaos.thread_id", thread_id)
                span.set_attribute("chaos.action", "row_contention")
            span.set_attribute("chaos.activity", "cassandra_row_contention")
            span.set_attribute("chaos.activity.type", "action")
            span.set_attribute("chaos.system", "cassandra")
            span.set_attribute("chaos.operation", "row_contention")
                
                cluster = Cluster([host], port=port)
                if user and password:
                    cluster = Cluster([host], port=port, auth_provider=None)
                    # Note: cassandra-driver auth setup varies
                session = cluster.connect(keyspace)
                
                # Create table if needed
                session.execute(f"""
                    CREATE TABLE IF NOT EXISTS {table_name} (
                        id TEXT PRIMARY KEY,
                        value INT,
                        thread_id INT,
                        updated_at TIMESTAMP
                    )
                """)
                
                # Insert initial row
                session.execute(
                    SimpleStatement(f"INSERT INTO {table_name} (id, value, thread_id, updated_at) VALUES (?, ?, ?, ?) IF NOT EXISTS"),
                    ("contention_test", 0, thread_id, time.time())
                )
                
                while not _stop_event.is_set():
                    try:
                        op_start = time.time()
                        
                        # Read
                        result = session.execute(
                            SimpleStatement(f"SELECT * FROM {table_name} WHERE id = ?"),
                            ("contention_test",)
                        )
                        row = result.one()
                        
                        # Write
                        session.execute(
                            SimpleStatement(f"UPDATE {table_name} SET value = ?, thread_id = ?, updated_at = ? WHERE id = ?"),
                            ((row.value if row else 0) + 1, thread_id, time.time(), "contention_test")
                        )
                        
                        op_duration_ms = (time.time() - op_start) * 1000
                        operations_completed += 1
                        
                        tags = get_metric_tags(db_name=keyspace, db_system="cassandra", db_operation="contention")
                        
                        
                        
                        
                        span.set_status(StatusCode.OK)
                        time.sleep(0.1)
                    except Exception as e:
                        error_str = str(e).lower()
                        if "read timeout" in error_str:
                            read_timeouts += 1
                            )
                        elif "write timeout" in error_str:
                            write_timeouts += 1
                            )
                        errors += 1
                        metrics.record_db_error(db_system=db_system, error_type=type(e).__name__)
                        logger.warning(f"Row contention worker {thread_id} error: {e}")
                        span.set_status(StatusCode.ERROR, str(e))
                        time.sleep(0.1)
        except Exception as e:
            errors += 1
            logger.error(f"Row contention worker {thread_id} failed: {e}")
        finally:
            if session:
                try:
                    session.shutdown()
                except:
                    pass
            if cluster:
                try:
                    cluster.shutdown()
                except:
                    pass
    
    try:
        with tracer.start_as_current_span("chaos.cassandra.row_contention") as span:
            span.set_attribute("db.system", "cassandra")
            span.set_attribute("db.name", keyspace)
            span.set_attribute("chaos.num_threads", num_threads)
            span.set_attribute("chaos.duration_seconds", duration_seconds)
            span.set_attribute("chaos.action", "row_contention")
            span.set_attribute("chaos.activity", "cassandra_row_contention")
            span.set_attribute("chaos.activity.type", "action")
            span.set_attribute("chaos.system", "cassandra")
            span.set_attribute("chaos.operation", "row_contention")
            
            logger.info(f"Starting Cassandra row contention with {num_threads} threads for {duration_seconds}s")
            
            for i in range(num_threads):
                thread = threading.Thread(target=contention_worker, args=(i,), daemon=True)
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
                "operations_completed": operations_completed,
                "read_timeouts": read_timeouts,
                "write_timeouts": write_timeouts,
                "errors": errors,
                "threads_used": num_threads
            }
            
            span.set_attribute("chaos.operations_completed", operations_completed)
            span.set_attribute("chaos.read_timeouts", read_timeouts)
            span.set_attribute("chaos.write_timeouts", write_timeouts)
            span.set_status(StatusCode.OK)
            
            logger.info(f"Cassandra row contention completed: {result}")
            flush()
            return result
    except Exception as e:
        _stop_event.set()
        metrics.record_db_error(db_system=db_system, error_type=type(e).__name__)
        logger.error(f"Cassandra row contention failed: {e}")
        flush()
        raise

def stop_row_contention():
    global _stop_event, _active_threads
    _stop_event.set()
    for thread in _active_threads:
        thread.join(timeout=2)
    _active_threads = []

