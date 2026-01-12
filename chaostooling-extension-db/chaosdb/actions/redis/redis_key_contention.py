"""Redis key contention chaos action."""
import os
import time
import threading
from typing import Optional, Dict
import redis
from chaosotel import ensure_initialized, get_tracer, get_logger, flush, get_metrics_core
from opentelemetry.trace import StatusCode

_active_threads = []
_stop_event = threading.Event()

def inject_key_contention(
    host: Optional[str] = None,
    port: Optional[int] = None,
    password: Optional[str] = None,
    num_threads: int = 10,
    duration_seconds: int = 60,
    key_name: str = "chaos:contention:test"
) -> Dict:
    """Inject Redis key contention by concurrent operations on same key."""
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
    errors = 0
    
    def contention_worker(thread_id: int):
        nonlocal operations_completed, errors
        r = None
        try:
            with tracer.start_as_current_span(f"key_contention.worker.{thread_id}") as span:
                span.set_attribute("db.system", "redis")
                span.set_attribute("chaos.thread_id", thread_id)
                span.set_attribute("chaos.action", "key_contention")
            span.set_attribute("chaos.activity", "redis_key_contention")
            span.set_attribute("chaos.activity.type", "action")
            span.set_attribute("chaos.system", "redis")
            span.set_attribute("chaos.operation", "key_contention")
                
                r = redis.Redis(host=host, port=port, password=password, decode_responses=True)
                
                # Initialize key
                r.set(key_name, 0)
                
                while not _stop_event.is_set():
                    try:
                        cmd_start = time.time()
                        
                        # Concurrent operations on same key
                        pipe = r.pipeline()
                        pipe.incr(key_name)
                        pipe.get(key_name)
                        pipe.set(f"{key_name}:thread_{thread_id}", thread_id)
                        results = pipe.execute()
                        
                        cmd_duration_ms = (time.time() - cmd_start) * 1000
                        operations_completed += 1
                        
                        tags = get_metric_tags(db_name="redis", db_system="redis", db_operation="contention")
                        
                        
                        
                        if cmd_duration_ms > 1000:
                            
                        
                        span.set_status(StatusCode.OK)
                        time.sleep(0.1)
                    except Exception as e:
                        errors += 1
                        metrics.record_db_error(db_system=db_system, error_type=type(e).__name__)
                        logger.warning(f"Key contention worker {thread_id} error: {e}")
                        span.set_status(StatusCode.ERROR, str(e))
                        time.sleep(0.1)
        except Exception as e:
            errors += 1
            logger.error(f"Key contention worker {thread_id} failed: {e}")
        finally:
            if r:
                try:
                    r.close()
                except:
                    pass
    
    try:
        with tracer.start_as_current_span("chaos.redis.key_contention") as span:
            span.set_attribute("db.system", "redis")
            span.set_attribute("chaos.num_threads", num_threads)
            span.set_attribute("chaos.duration_seconds", duration_seconds)
            span.set_attribute("chaos.action", "key_contention")
            span.set_attribute("chaos.activity", "redis_key_contention")
            span.set_attribute("chaos.activity.type", "action")
            span.set_attribute("chaos.system", "redis")
            span.set_attribute("chaos.operation", "key_contention")
            
            logger.info(f"Starting Redis key contention with {num_threads} threads for {duration_seconds}s")
            
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
                "errors": errors,
                "threads_used": num_threads
            }
            
            span.set_attribute("chaos.operations_completed", operations_completed)
            span.set_attribute("chaos.errors", errors)
            span.set_status(StatusCode.OK)
            
            logger.info(f"Redis key contention completed: {result}")
            flush()
            return result
    except Exception as e:
        _stop_event.set()
        metrics.record_db_error(db_system=db_system, error_type=type(e).__name__)
        logger.error(f"Redis key contention failed: {e}")
        flush()
        raise

def stop_key_contention():
    global _stop_event, _active_threads
    _stop_event.set()
    for thread in _active_threads:
        thread.join(timeout=2)
    _active_threads = []

