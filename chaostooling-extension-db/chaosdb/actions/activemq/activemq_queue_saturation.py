"""ActiveMQ queue saturation chaos action."""
import os
import time
import threading
from typing import Optional, Dict
import stomp
from chaosotel import ensure_initialized, get_tracer, get_logger, flush, get_metrics_core
from opentelemetry.trace import StatusCode

_active_threads = []
_stop_event = threading.Event()

def inject_queue_saturation(
    host: Optional[str] = None,
    port: Optional[int] = None,
    user: Optional[str] = None,
    password: Optional[str] = None,
    queue: Optional[str] = None,
    num_producers: int = 20,
    messages_per_producer: int = 1000,
    duration_seconds: int = 60
) -> Dict:
    """Saturate ActiveMQ queue with high message volume."""
    host = host or os.getenv("ACTIVEMQ_HOST", "localhost")
    port = port or int(os.getenv("ACTIVEMQ_PORT", "61613"))
    user = user or os.getenv("ACTIVEMQ_USER", "admin")
    password = password or os.getenv("ACTIVEMQ_PASSWORD", "admin")
    queue = queue or os.getenv("ACTIVEMQ_QUEUE", "chaos.saturation")
    
    ensure_initialized()
    db_system = os.getenv("DB_SYSTEM", "activemq")
    tracer = get_tracer()
    logger = get_logger()
    start_time = time.time()
    
    global _active_threads, _stop_event
    _stop_event.clear()
    _active_threads = []
    
    total_messages_sent = 0
    errors = 0
    
    def saturation_producer(producer_id: int):
        nonlocal total_messages_sent, errors
        conn = None
        try:
            with tracer.start_as_current_span(f"queue_saturation.producer.{producer_id}") as span:
                span.set_attribute("messaging.system", "activemq")
                span.set_attribute("messaging.destination", queue)
                span.set_attribute("chaos.producer_id", producer_id)
                span.set_attribute("chaos.action", "queue_saturation")
            span.set_attribute("chaos.activity", "activemq_queue_saturation")
            span.set_attribute("chaos.activity.type", "action")
            span.set_attribute("chaos.system", "activemq")
            span.set_attribute("chaos.operation", "queue_saturation")
                
                conn = stomp.Connection([(host, port)])
                conn.connect(user, password, wait=True)
                
                message_count = 0
                end_time = time.time() + duration_seconds
                
                while not _stop_event.is_set() and time.time() < end_time and message_count < messages_per_producer:
                    try:
                        message = f"chaos_sat_{producer_id}_{message_count}"
                        conn.send(destination=f"/queue/{queue}", body=message)
                        
                        total_messages_sent += 1
                        message_count += 1
                        
                        tags = get_metric_tags(db_name=queue, db_system="activemq", db_operation="saturation_send")
                        if metrics_module.activemq_messages_enqueued_counter:
                            metrics_module.activemq_messages_enqueued_counter.add(1, tags)
                        if metrics_module.activemq_queue_size_gauge:
                            metrics_module.activemq_queue_size_gauge.add(1, tags)
                        
                        span.set_status(StatusCode.OK)
                        time.sleep(0.01)
                    except Exception as e:
                        errors += 1
                        metrics = get_metrics_core()
            metrics.record_db_error(db_system=db_system, error_type=type(e).__name__)
                        logger.warning(f"Saturation producer {producer_id} error: {e}")
        except Exception as e:
            errors += 1
            logger.error(f"Queue saturation producer {producer_id} failed: {e}")
        finally:
            if conn:
                try:
                    conn.disconnect()
                except:
                    pass
    
    try:
        with tracer.start_as_current_span("chaos.activemq.queue_saturation") as span:
            span.set_attribute("messaging.system", "activemq")
            span.set_attribute("messaging.destination", queue)
            span.set_attribute("chaos.num_producers", num_producers)
            span.set_attribute("chaos.duration_seconds", duration_seconds)
            span.set_attribute("chaos.action", "queue_saturation")
            span.set_attribute("chaos.activity", "activemq_queue_saturation")
            span.set_attribute("chaos.activity.type", "action")
            span.set_attribute("chaos.system", "activemq")
            span.set_attribute("chaos.operation", "queue_saturation")
            
            logger.info(f"Starting ActiveMQ queue saturation with {num_producers} producers for {duration_seconds}s")
            
            for i in range(num_producers):
                thread = threading.Thread(target=saturation_producer, args=(i,), daemon=True)
                thread.start()
                _active_threads.append(thread)
            
            for thread in _active_threads:
                thread.join(timeout=duration_seconds + 5)
            
            _stop_event.set()
            duration_ms = (time.time() - start_time) * 1000
            
            result = {
                "success": True,
                "duration_ms": duration_ms,
                "total_messages_sent": total_messages_sent,
                "errors": errors,
                "messages_per_second": total_messages_sent / (duration_ms / 1000) if duration_ms > 0 else 0,
                "producers_used": num_producers
            }
            
            span.set_attribute("chaos.total_messages_sent", total_messages_sent)
            span.set_attribute("chaos.errors", errors)
            span.set_status(StatusCode.OK)
            
            logger.info(f"ActiveMQ queue saturation completed: {result}")
            flush()
            return result
    except Exception as e:
        _stop_event.set()
        metrics = get_metrics_core()
            metrics.record_db_error(db_system=db_system, error_type=type(e).__name__)
        logger.error(f"ActiveMQ queue saturation failed: {e}")
        flush()
        raise

def stop_queue_saturation():
    global _stop_event, _active_threads
    _stop_event.set()
    for thread in _active_threads:
        thread.join(timeout=2)
    _active_threads = []

