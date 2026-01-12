"""RabbitMQ message flood chaos action."""
import os
import time
import threading
from typing import Optional, Dict
import pika
from chaosotel import ensure_initialized, get_tracer, get_logger, flush, get_metrics_core
from opentelemetry.trace import StatusCode

_active_threads = []
_stop_event = threading.Event()

def inject_message_flood(
    host: Optional[str] = None,
    port: Optional[int] = None,
    user: Optional[str] = None,
    password: Optional[str] = None,
    vhost: Optional[str] = None,
    queue: Optional[str] = None,
    num_producers: int = 10,
    messages_per_producer: int = 1000,
    duration_seconds: int = 60
) -> Dict:
    """Flood RabbitMQ queue with high volume of messages."""
    host = host or os.getenv("RABBITMQ_HOST", "localhost")
    port = port or int(os.getenv("RABBITMQ_PORT", "5672"))
    user = user or os.getenv("RABBITMQ_USER", "guest")
    password = password or os.getenv("RABBITMQ_PASSWORD", "guest")
    vhost = vhost or os.getenv("RABBITMQ_VHOST", "/")
    queue = queue or os.getenv("RABBITMQ_QUEUE", "chaos_test_queue")
    
    ensure_initialized()
    metrics = get_metrics_core()
    tracer = get_tracer()
    logger = get_logger()
    start_time = time.time()
    
    global _active_threads, _stop_event
    _stop_event.clear()
    _active_threads = []
    
    total_messages_sent = 0
    errors = 0
    
    def producer_worker(producer_id: int):
        nonlocal total_messages_sent, errors
        conn = None
        channel = None
        try:
            with tracer.start_as_current_span(f"message_flood.producer.{producer_id}") as span:
                span.set_attribute("messaging.system", "rabbitmq")
                span.set_attribute("messaging.destination", queue)
                span.set_attribute("chaos.producer_id", producer_id)
                span.set_attribute("chaos.action", "message_flood")
            span.set_attribute("chaos.activity", "rabbitmq_message_flood")
            span.set_attribute("chaos.activity.type", "action")
            span.set_attribute("chaos.system", "rabbitmq")
            span.set_attribute("chaos.operation", "message_flood")
                
                credentials = pika.PlainCredentials(user, password)
                params = pika.ConnectionParameters(host=host, port=port, virtual_host=vhost, credentials=credentials)
                conn = pika.BlockingConnection(params)
                channel = conn.channel()
                channel.queue_declare(queue=queue, durable=True)
                channel.confirm_delivery()
                
                message_count = 0
                end_time = time.time() + duration_seconds
                
                while not _stop_event.is_set() and time.time() < end_time and message_count < messages_per_producer:
                    try:
                        send_start = time.time()
                        
                        message = f"chaos_test_{producer_id}_{message_count}"
                        confirmed = channel.basic_publish(
                            exchange='',
                            routing_key=queue,
                            body=message,
                            properties=pika.BasicProperties(delivery_mode=2)
                        )
                        
                        send_duration_ms = (time.time() - send_start) * 1000
                        if confirmed:
                            total_messages_sent += 1
                            message_count += 1
                            
                            tags = get_metric_tags(db_name=queue, db_system="rabbitmq", db_operation="message_send")
                            
                            
                            
                        
                        span.set_status(StatusCode.OK)
                        time.sleep(0.01)
                    except Exception as e:
                        errors += 1
                        metrics.record_db_error(db_system=db_system, error_type=type(e).__name__)
                        logger.warning(f"Producer {producer_id} error: {e}")
        except Exception as e:
            errors += 1
            logger.error(f"Message flood producer {producer_id} failed: {e}")
        finally:
            if channel:
                try:
                    channel.close()
                except:
                    pass
            if conn:
                try:
                    conn.close()
                except:
                    pass
    
    try:
        with tracer.start_as_current_span("chaos.rabbitmq.message_flood") as span:
            span.set_attribute("messaging.system", "rabbitmq")
            span.set_attribute("messaging.destination", queue)
            span.set_attribute("chaos.num_producers", num_producers)
            span.set_attribute("chaos.duration_seconds", duration_seconds)
            span.set_attribute("chaos.action", "message_flood")
            span.set_attribute("chaos.activity", "rabbitmq_message_flood")
            span.set_attribute("chaos.activity.type", "action")
            span.set_attribute("chaos.system", "rabbitmq")
            span.set_attribute("chaos.operation", "message_flood")
            
            logger.info(f"Starting RabbitMQ message flood with {num_producers} producers for {duration_seconds}s")
            
            for i in range(num_producers):
                thread = threading.Thread(target=producer_worker, args=(i,), daemon=True)
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
            
            logger.info(f"RabbitMQ message flood completed: {result}")
            flush()
            return result
    except Exception as e:
        _stop_event.set()
        metrics.record_db_error(db_system=db_system, error_type=type(e).__name__)
        logger.error(f"RabbitMQ message flood failed: {e}")
        flush()
        raise

def stop_message_flood():
    global _stop_event, _active_threads
    _stop_event.set()
    for thread in _active_threads:
        thread.join(timeout=2)
    _active_threads = []

