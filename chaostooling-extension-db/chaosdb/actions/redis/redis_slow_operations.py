"""Redis slow operations chaos action."""
import os
import time
import threading
from typing import Optional, Dict
import redis
from chaosotel import ensure_initialized, get_tracer, get_logger, flush, get_metrics_core
from opentelemetry.trace import StatusCode

_active_threads = []
_stop_event = threading.Event()

def inject_slow_operations(
    host: Optional[str] = None,
    port: Optional[int] = None,
    password: Optional[str] = None,
    num_threads: int = 5,
    duration_seconds: int = 60,
    operation_delay_ms: int = 5000
) -> Dict:
    """Inject slow Redis operations."""
    host = host or os.getenv("REDIS_HOST", "localhost")
    port = port or int(os.getenv("REDIS_PORT", "6379"))
    password = password or os.getenv("REDIS_PASSWORD", None)
    
    ensure_initialized()
    metrics = get_metrics_core()
    tracer = get_tracer()
    logger = get_logger()
    start_time = time.time()
    
    global _active_threads, _stop_event
    _stop_event.clear()
    _active_threads = []
    
    operations_completed = 0
    total_operation_time = 0
    errors = 0
    
    def slow_operation_worker(thread_id: int):
        nonlocal operations_completed, total_operation_time, errors
        r = None
        try:
            with tracer.start_as_current_span(f"slow_operation.worker.{thread_id}") as span:
                span.set_attribute("db.system", "redis")
                span.set_attribute("chaos.thread_id", thread_id)
                span.set_attribute("chaos.action", "slow_operations")
            span.set_attribute("chaos.activity", "redis_slow_operations")
            span.set_attribute("chaos.activity.type", "action")
            span.set_attribute("chaos.system", "redis")
            span.set_attribute("chaos.operation", "slow_operations")
                
                r = redis.Redis(host=host, port=port, password=password, decode_responses=True)
                
                key = f"chaos:slow:{thread_id}"
                r.set(key, 0)
                
                end_time = time.time() + duration_seconds
                
                while not _stop_event.is_set() and time.time() < end_time:
                    try:
                        op_start = time.time()
                        
                        # Get value
                        r.get(key)
                        
                        # Simulate slow work
                        time.sleep(operation_delay_ms / 1000.0)
                        
                        # Update
                        r.incr(key)
                        r.set(f"{key}:updated", time.time())
                        
                        op_duration_ms = (time.time() - op_start) * 1000
                        operations_completed += 1
                        total_operation_time += op_duration_ms
                        
                        tags = get_metric_tags(db_name="redis", db_system="redis", db_operation="slow_operation")
                        
                        
                        
                        if op_duration_ms > 1000:
                            
                        
                        span.set_status(StatusCode.OK)
                    except Exception as e:
                        errors += 1
                        metrics.record_db_error(db_system=db_system, error_type=type(e).__name__)
                        logger.warning(f"Slow operation worker {thread_id} error: {e}")
                        span.set_status(StatusCode.ERROR, str(e))
                        time.sleep(0.1)
        except Exception as e:
            errors += 1
            logger.error(f"Slow operation worker {thread_id} failed: {e}")
        finally:
            if r:
                try:
                    r.close()
                except:
                    pass
    
    try:
        with tracer.start_as_current_span("chaos.redis.slow_operations") as span:
            span.set_attribute("db.system", "redis")
            span.set_attribute("chaos.num_threads", num_threads)
            span.set_attribute("chaos.duration_seconds", duration_seconds)
            span.set_attribute("chaos.operation_delay_ms", operation_delay_ms)
            span.set_attribute("chaos.action", "slow_operations")
            span.set_attribute("chaos.activity", "redis_slow_operations")
            span.set_attribute("chaos.activity.type", "action")
            span.set_attribute("chaos.system", "redis")
            span.set_attribute("chaos.operation", "slow_operations")
            
            logger.info(f"Starting Redis slow operations with {num_threads} threads for {duration_seconds}s")
            
            for i in range(num_threads):
                thread = threading.Thread(target=slow_operation_worker, args=(i,), daemon=True)
                thread.start()
                _active_threads.append(thread)
            
            time.sleep(duration_seconds)
            _stop_event.set()
            for thread in _active_threads:
                thread.join(timeout=10)
            
            duration_ms = (time.time() - start_time) * 1000
            avg_operation_time = total_operation_time / operations_completed if operations_completed > 0 else 0
            
            result = {
                "success": True,
                "duration_ms": duration_ms,
                "operations_completed": operations_completed,
                "average_operation_time_ms": avg_operation_time,
                "errors": errors,
                "threads_used": num_threads
            }
            
            span.set_attribute("chaos.operations_completed", operations_completed)
            span.set_attribute("chaos.average_operation_time_ms", avg_operation_time)
            span.set_status(StatusCode.OK)
            
            logger.info(f"Redis slow operations completed: {result}")
            flush()
            return result
    except Exception as e:
        _stop_event.set()
        metrics.record_db_error(db_system=db_system, error_type=type(e).__name__)
        logger.error(f"Redis slow operations failed: {e}")
        flush()
        raise

def stop_slow_operations():
    global _stop_event, _active_threads
    _stop_event.set()
    for thread in _active_threads:
        thread.join(timeout=5)
    _active_threads = []

