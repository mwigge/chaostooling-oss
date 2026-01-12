"""RabbitMQ consumer rebalancing storm chaos action."""
import os
import time
import threading
import pika
from typing import Optional, Dict
from chaosotel import ensure_initialized, get_tracer, get_logger, flush, get_metrics_core
from opentelemetry.trace import StatusCode

_active_consumers = []
_stop_event = threading.Event()

def inject_rebalancing_storm(
    host: Optional[str] = None,
    port: Optional[int] = None,
    user: Optional[str] = None,
    password: Optional[str] = None,
    vhost: Optional[str] = None,
    queue: Optional[str] = None,
    num_consumers: int = 10,
    rebalance_interval_seconds: int = 5,
    duration_seconds: int = 60
) -> Dict:
    """
    Inject consumer rebalancing storm by rapidly adding/removing consumers.
    Forces frequent rebalancing to test system stability.
    """
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
    
    global _active_consumers, _stop_event
    _stop_event.clear()
    _active_consumers = []
    
    rebalances_triggered = 0
    errors = 0
    
    def consumer_worker(consumer_id: int):
        nonlocal rebalances_triggered, errors
        conn = None
        channel = None
        try:
            with tracer.start_as_current_span(f"rebalancing_storm.consumer.{consumer_id}") as span:
                span.set_attribute("messaging.system", "rabbitmq")
                span.set_attribute("messaging.destination", queue)
                span.set_attribute("chaos.consumer_id", consumer_id)
                span.set_attribute("chaos.action", "rebalancing_storm")
            span.set_attribute("chaos.activity", "rabbitmq_rebalancing_storm")
            span.set_attribute("chaos.activity.type", "action")
            span.set_attribute("chaos.system", "rabbitmq")
            span.set_attribute("chaos.operation", "rebalancing_storm")
                
                end_time = time.time() + duration_seconds
                
                while not _stop_event.is_set() and time.time() < end_time:
                    try:
                        credentials = pika.PlainCredentials(user, password)
                        params = pika.ConnectionParameters(host=host, port=port, virtual_host=vhost, credentials=credentials)
                        conn = pika.BlockingConnection(params)
                        channel = conn.channel()
                        channel.queue_declare(queue=queue, durable=True)
                        
                        _active_consumers.append((conn, channel))
                        rebalances_triggered += 1
                        
                        # Consume briefly
                        method, properties, body = channel.basic_get(queue=queue, auto_ack=True)
                        
                        # Close connection to trigger rebalance
                        channel.close()
                        conn.close()
                        conn = None
                        channel = None
                        _active_consumers = [c for c in _active_consumers if c[0] != conn]
                        
                        time.sleep(rebalance_interval_seconds)
                        
                        span.set_status(StatusCode.OK)
                        
                    except Exception as e:
                        errors += 1
                        metrics.record_db_error(db_system=db_system, error_type=type(e).__name__)
                        logger.warning(f"Rebalancing consumer {consumer_id} error: {e}")
                        span.set_status(StatusCode.ERROR, str(e))
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
                        time.sleep(0.5)
                        
        except Exception as e:
            errors += 1
            logger.error(f"Rebalancing consumer worker {consumer_id} failed: {e}")
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
        with tracer.start_as_current_span("chaos.rabbitmq.rebalancing_storm") as span:
            span.set_attribute("messaging.system", "rabbitmq")
            span.set_attribute("messaging.destination", queue)
            span.set_attribute("chaos.num_consumers", num_consumers)
            span.set_attribute("chaos.rebalance_interval_seconds", rebalance_interval_seconds)
            span.set_attribute("chaos.duration_seconds", duration_seconds)
            span.set_attribute("chaos.action", "rebalancing_storm")
            span.set_attribute("chaos.activity", "rabbitmq_rebalancing_storm")
            span.set_attribute("chaos.activity.type", "action")
            span.set_attribute("chaos.system", "rabbitmq")
            span.set_attribute("chaos.operation", "rebalancing_storm")
            
            logger.info(f"Starting RabbitMQ rebalancing storm with {num_consumers} consumers for {duration_seconds}s")
            
            threads = []
            for i in range(num_consumers):
                thread = threading.Thread(target=consumer_worker, args=(i,), daemon=True)
                thread.start()
                threads.append(thread)
                time.sleep(0.5)
            
            time.sleep(duration_seconds)
            _stop_event.set()
            for thread in threads:
                thread.join(timeout=10)
            
            for conn, channel in _active_consumers:
                try:
                    channel.close()
                    conn.close()
                except:
                    pass
            
            duration_ms = (time.time() - start_time) * 1000
            
            result = {
                "success": True,
                "duration_ms": duration_ms,
                "rebalances_triggered": rebalances_triggered,
                "errors": errors,
                "consumers_used": num_consumers
            }
            
            span.set_attribute("chaos.rebalances_triggered", rebalances_triggered)
            span.set_status(StatusCode.OK)
            
            logger.info(f"RabbitMQ rebalancing storm completed: {result}")
            flush()
            return result
    except Exception as e:
        _stop_event.set()
        metrics.record_db_error(db_system=db_system, error_type=type(e).__name__)
        logger.error(f"RabbitMQ rebalancing storm failed: {e}")
        flush()
        raise

def stop_rebalancing_storm():
    global _stop_event, _active_consumers
    _stop_event.set()
    for conn, channel in _active_consumers:
        try:
            channel.close()
            conn.close()
        except:
            pass
    _active_consumers = []

