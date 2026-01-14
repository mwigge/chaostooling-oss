"""RabbitMQ slow consumer chaos action."""
import os
import threading
import time
from typing import Dict, Optional

import pika
from chaosotel import ( get_metric_tags
                       get_tracer)
from opentelemetry.trace import StatusCode

_active_threads = []
_stop_event = threading.Event()

def inject_slow_consumer(
    host: Optional[str] = None,
    port: Optional[int] = None,
    user: Optional[str] = None,
    password: Optional[str] = None,
    vhost: Optional[str] = None,
    queue: Optional[str] = None,
    num_consumers: int = 5,
    duration_seconds: int = 60,
    consume_delay_ms: int = 5000
) -> Dict:
    """Inject slow RabbitMQ consumers to create message backlog."""
    host = host or os.getenv("RABBITMQ_HOST", "localhost")
    port = port or int(os.getenv("RABBITMQ_PORT", "5672"))
    user = user or os.getenv("RABBITMQ_USER", "guest")
    password = password or os.getenv("RABBITMQ_PASSWORD", "guest")
    vhost = vhost or os.getenv("RABBITMQ_VHOST", "/")
    queue = queue or os.getenv("RABBITMQ_QUEUE", "chaos_test_queue")
    
    ensure_initialized()
    db_system = os.getenv("DB_SYSTEM", "rabbitmq")
    metrics = get_metrics_core()
    tracer = get_tracer()
    logger = get_logger()
    start_time = time.time()
    
    global _active_threads, _stop_event
    _stop_event.clear()
    _active_threads = []
    
    messages_consumed = 0
    errors = 0
    
    def slow_consumer_worker(consumer_id: int):
        nonlocal messages_consumed, errors
        conn = None
        channel = None
        try:
            with tracer.start_as_current_span(f"slow_consumer.worker.{consumer_id}") as span:
                from chaosotel.core.trace_core import set_messaging_span_attributes
                set_messaging_span_attributes(
                    span,
                    messaging_system="rabbitmq",
                    destination=queue,
                    host=host,
                    port=port,
                    chaos_activity="rabbitmq_slow_consumer",
                    chaos_action="slow_consumer",
                    chaos_operation="slow_consumer",
                    chaos_consumer_id=consumer_id
                )

                credentials = pika.PlainCredentials(user, password)
                params = pika.ConnectionParameters(host=host, port=port, virtual_host=vhost, credentials=credentials)
                conn = pika.BlockingConnection(params)
                channel = conn.channel()
                channel.queue_declare(queue=queue, durable=True)
                channel.basic_qos(prefetch_count=1)
                
                def callback(ch, method, properties, body):
                    nonlocal messages_consumed
                    try:
                        # Simulate slow processing
                        time.sleep(consume_delay_ms / 1000.0)
                        
                        messages_consumed += 1
                        tags = get_metric_tags(db_name=queue, db_system="rabbitmq", db_operation="slow_consume")
                        
                        
                        
                        ch.basic_ack(delivery_tag=method.delivery_tag)
                    except Exception:
                        ch.basic_nack(delivery_tag=method.delivery_tag, requeue=True)
                        raise
                
                channel.basic_consume(queue=queue, on_message_callback=callback)
                
                end_time = time.time() + duration_seconds
                while not _stop_event.is_set() and time.time() < end_time:
                    try:
                        conn.process_data_events(time_limit=1)
                    except Exception as e:
                        errors += 1
                        metrics.record_db_error(db_system=db_system, error_type=type(e).__name__)
                        logger.warning(f"Slow consumer {consumer_id} error: {e}")
                        span.set_status(StatusCode.ERROR, str(e))
                        time.sleep(0.1)
                
                span.set_status(StatusCode.OK)
        except Exception as e:
            errors += 1
            logger.error(f"Slow consumer worker {consumer_id} failed: {e}")
        finally:
            if channel:
                try:
                    channel.stop_consuming()
                    channel.close()
                except Exception:
                    pass
            if conn:
                try:
                    conn.close()
                except Exception:
                    pass
    
    try:
        with tracer.start_as_current_span("chaos.rabbitmq.slow_consumer") as span:
            from chaosotel.core.trace_core import set_messaging_span_attributes
            set_messaging_span_attributes(
                span,
                messaging_system="rabbitmq",
                destination=queue,
                host=host,
                port=port,
                chaos_activity="rabbitmq_slow_consumer",
                chaos_action="slow_consumer",
                chaos_operation="slow_consumer",
                chaos_num_consumers=num_consumers,
                chaos_duration_seconds=duration_seconds,
                chaos_consume_delay_ms=consume_delay_ms
            )
            
            logger.info(f"Starting RabbitMQ slow consumers with {num_consumers} consumers for {duration_seconds}s")
            
            for i in range(num_consumers):
                thread = threading.Thread(target=slow_consumer_worker, args=(i,), daemon=True)
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
                "messages_consumed": messages_consumed,
                "errors": errors,
                "consumers_used": num_consumers
            }
            
            span.set_attribute("chaos.messages_consumed", messages_consumed)
            span.set_attribute("chaos.errors", errors)
            span.set_status(StatusCode.OK)
            
            logger.info(f"RabbitMQ slow consumer completed: {result}")
            flush()
            return result
    except Exception as e:
        _stop_event.set()
        metrics.record_db_error(db_system=db_system, error_type=type(e).__name__)
        logger.error(f"RabbitMQ slow consumer failed: {e}")
        flush()
        raise

def stop_slow_consumer():
    global _stop_event, _active_threads
    _stop_event.set()
    for thread in _active_threads:
        thread.join(timeout=5)
    _active_threads = []

