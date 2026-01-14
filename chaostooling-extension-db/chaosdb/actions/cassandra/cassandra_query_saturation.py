"""Cassandra query saturation chaos action."""
import os
import threading
import time
from typing import Dict, Optional

from cassandra.cluster import Cluster
from chaosotel import ( get_metric_tags
                       get_tracer)
from opentelemetry.trace import StatusCode

_active_threads = []
_stop_event = threading.Event()

def inject_query_saturation(
    host: Optional[str] = None,
    port: Optional[int] = None,
    keyspace: Optional[str] = None,
    user: Optional[str] = None,
    password: Optional[str] = None,
    num_threads: int = 20,
    queries_per_thread: int = 1000,
    duration_seconds: int = 60
) -> Dict:
    """Saturate Cassandra with high volume of queries."""
    host = host or os.getenv("CASSANDRA_HOST", "localhost")
    port = port or int(os.getenv("CASSANDRA_PORT", "9042"))
    keyspace = keyspace or os.getenv("CASSANDRA_KEYSPACE", "system")
    user = user or os.getenv("CASSANDRA_USER")
    password = password or os.getenv("CASSANDRA_PASSWORD")
    
    ensure_initialized()
    db_system = os.getenv("DB_SYSTEM", "cassandra")
    metrics = get_metrics_core()
    tracer = get_tracer()
    logger = get_logger()
    start_time = time.time()
    
    global _active_threads, _stop_event
    _stop_event.clear()
    _active_threads = []
    
    total_queries = 0
    read_timeouts = 0
    write_timeouts = 0
    errors = 0
    
    def query_worker(thread_id: int):
        nonlocal total_queries, read_timeouts, write_timeouts, errors
        cluster = None
        session = None
        try:
            with tracer.start_as_current_span(f"query_saturation.worker.{thread_id}") as span:
                from chaosotel.core.trace_core import set_db_span_attributes
                set_db_span_attributes(
                    span,
                    db_system="cassandra",
                    db_name=keyspace,
                    host=host,
                    port=port,
                    chaos_activity="cassandra_query_saturation",
                    chaos_action="query_saturation",
                    chaos_operation="query_saturation",
                    chaos_thread_id=thread_id
                )

                cluster = Cluster([host], port=port)
                session = cluster.connect(keyspace)
                
                query_count = 0
                end_time = time.time() + duration_seconds
                
                while not _stop_event.is_set() and time.time() < end_time and query_count < queries_per_thread:
                    try:
                        query_start = time.time()
                        
                        # Various queries
                        queries = [
                            lambda: session.execute("SELECT release_version FROM system.local"),
                            lambda: session.execute("SELECT cluster_name FROM system.local"),
                            lambda: session.execute("SELECT * FROM system.local LIMIT 1"),
                            lambda: session.execute("SELECT COUNT(*) FROM system.local"),
                        ]
                        
                        query = queries[query_count % len(queries)]
                        query()
                        
                        query_duration_ms = (time.time() - query_start) * 1000
                        total_queries += 1
                        query_count += 1
                        
                        tags = get_metric_tags(db_name=keyspace, db_system="cassandra", db_operation="saturation_query")
                        
                        
                        
                        time.sleep(0.01)
                    except Exception as e:
                        error_str = str(e).lower()
                        if "read timeout" in error_str:
                            read_timeouts += 1
                        elif "write timeout" in error_str:
                            write_timeouts += 1
                        errors += 1
                        metrics.record_db_error(db_system=db_system, error_type=type(e).__name__)
                        logger.warning(f"Query worker {thread_id} error: {e}")
                
                span.set_status(StatusCode.OK)
        except Exception as e:
            errors += 1
            logger.error(f"Query saturation worker {thread_id} failed: {e}")
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
        with tracer.start_as_current_span("chaos.cassandra.query_saturation") as span:
            span.set_attribute("db.system", "cassandra")
            span.set_attribute("db.name", keyspace)
            span.set_attribute("chaos.num_threads", num_threads)
            span.set_attribute("chaos.duration_seconds", duration_seconds)
            span.set_attribute("chaos.action", "query_saturation")
            span.set_attribute("chaos.activity", "cassandra_query_saturation")
            span.set_attribute("chaos.activity.type", "action")
            span.set_attribute("chaos.system", "cassandra")
            span.set_attribute("chaos.operation", "query_saturation")
            
            logger.info(f"Starting Cassandra query saturation with {num_threads} threads for {duration_seconds}s")
            
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
                "read_timeouts": read_timeouts,
                "write_timeouts": write_timeouts,
                "errors": errors,
                "queries_per_second": total_queries / (duration_ms / 1000) if duration_ms > 0 else 0,
                "threads_used": num_threads
            }
            
            span.set_attribute("chaos.total_queries", total_queries)
            span.set_attribute("chaos.read_timeouts", read_timeouts)
            span.set_attribute("chaos.write_timeouts", write_timeouts)
            span.set_status(StatusCode.OK)
            
            logger.info(f"Cassandra query saturation completed: {result}")
            flush()
            return result
    except Exception as e:
        _stop_event.set()
        metrics.record_db_error(db_system=db_system, error_type=type(e).__name__)
        logger.error(f"Cassandra query saturation failed: {e}")
        flush()
        raise

def stop_query_saturation():
    global _stop_event, _active_threads
    _stop_event.set()
    for thread in _active_threads:
        thread.join(timeout=2)
    _active_threads = []

