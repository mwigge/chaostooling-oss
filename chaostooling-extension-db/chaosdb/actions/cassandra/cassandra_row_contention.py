"""Cassandra row contention chaos action."""
import logging
import os
import threading
import time
from typing import Dict, Optional

from cassandra.cluster import Cluster
from cassandra.query import SimpleStatement
from chaosotel import (ensure_initialized, flush, get_metric_tags, get_metrics_core,
                       get_tracer)
from opentelemetry._logs import get_logger_provider
from opentelemetry.sdk._logs import LoggingHandler
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
    db_system = "cassandra"
    metrics = get_metrics_core()
    tracer = get_tracer()
    
    # Setup OpenTelemetry logger via LoggingHandler (OpenTelemetry standard)
    logger_provider = get_logger_provider()
    if logger_provider:
        handler = LoggingHandler(level=logging.INFO, logger_provider=logger_provider)
        logger = logging.getLogger("chaosdb.cassandra.row_contention")
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
    else:
        logger = logging.getLogger("chaosdb.cassandra.row_contention")
    
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
                from chaosotel.core.trace_core import set_db_span_attributes
                set_db_span_attributes(
                    span,
                    db_system="cassandra",
                    db_name=keyspace,
                    host=host,
                    port=port,
                    chaos_activity="cassandra_row_contention",
                    chaos_action="row_contention",
                    chaos_operation="row_contention",
                    chaos_thread_id=thread_id
                )

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
                        metrics = get_metrics_core()
                        metrics.record_db_query_latency(
                            op_duration_ms,
                            db_system="cassandra",
                            db_name=keyspace,
                            db_operation="contention",
                            tags=tags,
                        )
                        
                        span.set_status(StatusCode.OK)
                        time.sleep(0.1)
                    except Exception as e:
                        error_str = str(e).lower()
                        if "read timeout" in error_str:
                            read_timeouts += 1
                        elif "write timeout" in error_str:
                            write_timeouts += 1
                        errors += 1
                        metrics.record_db_error(db_system=db_system, error_type=type(e).__name__)
                        logger.warning(
                            f"Row contention worker {thread_id} error: {e}",
                            exc_info=True,
                        )
                        span.set_status(StatusCode.ERROR, str(e))
                        time.sleep(0.1)
        except Exception as e:
            errors += 1
            logger.error(
                f"Row contention worker {thread_id} failed: {e}",
                exc_info=True,
            )
        finally:
            if session:
                try:
                    session.shutdown()
                except Exception:
                    pass
            if cluster:
                try:
                    cluster.shutdown()
                except Exception:
                    pass
    
    try:
        with tracer.start_as_current_span("chaos.cassandra.row_contention") as span:
            span.set_attribute("db.system", "cassandra")
            span.set_attribute("db.name", keyspace)
            span.set_attribute("network.peer.address", host)
            span.set_attribute("network.peer.port", port)
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
        logger.error(
            f"Cassandra row contention failed: {e}",
            exc_info=True,
        )
        flush()
        raise

def stop_row_contention():
    global _stop_event, _active_threads
    _stop_event.set()
    for thread in _active_threads:
        thread.join(timeout=2)
    _active_threads = []

