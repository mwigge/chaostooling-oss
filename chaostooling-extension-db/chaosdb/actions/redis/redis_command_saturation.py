"""Redis command saturation chaos action."""
import os
import time
import threading
from typing import Optional, Dict
import redis
from chaosotel import ensure_initialized, get_tracer, get_logger, flush, get_metrics_core
from opentelemetry.trace import StatusCode

_active_threads = []
_stop_event = threading.Event()

def inject_command_saturation(
    host: Optional[str] = None,
    port: Optional[int] = None,
    password: Optional[str] = None,
    num_threads: int = 20,
    commands_per_thread: int = 1000,
    duration_seconds: int = 60,
    slow_command_threshold_ms: int = 1000
) -> Dict:
    """Saturate Redis with high volume of commands."""
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
    
    total_commands = 0
    slow_commands = 0
    errors = 0
    
    def command_worker(thread_id: int):
        nonlocal total_commands, slow_commands, errors
        r = None
        try:
            with tracer.start_as_current_span(f"command_saturation.worker.{thread_id}") as span:
                span.set_attribute("db.system", "redis")
                span.set_attribute("chaos.thread_id", thread_id)
                span.set_attribute("chaos.action", "command_saturation")
            span.set_attribute("chaos.activity", "redis_command_saturation")
            span.set_attribute("chaos.activity.type", "action")
            span.set_attribute("chaos.system", "redis")
            span.set_attribute("chaos.operation", "command_saturation")
                
                r = redis.Redis(host=host, port=port, password=password, decode_responses=True)
                
                command_count = 0
                end_time = time.time() + duration_seconds
                
                while not _stop_event.is_set() and time.time() < end_time and command_count < commands_per_thread:
                    try:
                        cmd_start = time.time()
                        
                        # Various Redis commands
                        key = f"chaos:sat:{thread_id}:{command_count}"
                        r.set(key, command_count)
                        r.get(key)
                        r.incr(f"chaos:counter:{thread_id}")
                        r.ping()
                        r.info("memory")
                        r.dbsize()
                        
                        cmd_duration_ms = (time.time() - cmd_start) * 1000
                        total_commands += 1
                        command_count += 1
                        
                        tags = get_metric_tags(db_name="redis", db_system="redis", db_operation="saturation_command")
                        
                        
                        
                        if cmd_duration_ms > slow_command_threshold_ms:
                            slow_commands += 1
                            
                        
                        time.sleep(0.01)
                    except Exception as e:
                        errors += 1
                        metrics.record_db_error(db_system=db_system, error_type=type(e).__name__)
                        logger.warning(f"Command worker {thread_id} error: {e}")
                
                span.set_status(StatusCode.OK)
        except Exception as e:
            errors += 1
            logger.error(f"Command saturation worker {thread_id} failed: {e}")
        finally:
            if r:
                try:
                    r.close()
                except:
                    pass
    
    try:
        with tracer.start_as_current_span("chaos.redis.command_saturation") as span:
            span.set_attribute("db.system", "redis")
            span.set_attribute("chaos.num_threads", num_threads)
            span.set_attribute("chaos.duration_seconds", duration_seconds)
            span.set_attribute("chaos.action", "command_saturation")
            span.set_attribute("chaos.activity", "redis_command_saturation")
            span.set_attribute("chaos.activity.type", "action")
            span.set_attribute("chaos.system", "redis")
            span.set_attribute("chaos.operation", "command_saturation")
            
            logger.info(f"Starting Redis command saturation with {num_threads} threads for {duration_seconds}s")
            
            for i in range(num_threads):
                thread = threading.Thread(target=command_worker, args=(i,), daemon=True)
                thread.start()
                _active_threads.append(thread)
            
            for thread in _active_threads:
                thread.join(timeout=duration_seconds + 5)
            
            _stop_event.set()
            duration_ms = (time.time() - start_time) * 1000
            
            result = {
                "success": True,
                "duration_ms": duration_ms,
                "total_commands": total_commands,
                "slow_commands": slow_commands,
                "errors": errors,
                "commands_per_second": total_commands / (duration_ms / 1000) if duration_ms > 0 else 0,
                "threads_used": num_threads
            }
            
            span.set_attribute("chaos.total_commands", total_commands)
            span.set_attribute("chaos.slow_commands", slow_commands)
            span.set_status(StatusCode.OK)
            
            logger.info(f"Redis command saturation completed: {result}")
            flush()
            return result
    except Exception as e:
        _stop_event.set()
        metrics.record_db_error(db_system=db_system, error_type=type(e).__name__)
        logger.error(f"Redis command saturation failed: {e}")
        flush()
        raise

def stop_command_saturation():
    global _stop_event, _active_threads
    _stop_event.set()
    for thread in _active_threads:
        thread.join(timeout=2)
    _active_threads = []

