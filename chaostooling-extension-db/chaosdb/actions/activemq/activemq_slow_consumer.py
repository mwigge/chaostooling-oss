"""ActiveMQ slow consumer chaos action."""
import os
import threading
import time
from typing import Dict, Optional

import stomp
from chaosotel import (ensure_initialized, flush, get_logger, get_metric_tags,
                       get_metrics_core, get_tracer)
from opentelemetry.trace import StatusCode

_active_threads = []
_stop_event = threading.Event()

class SlowConsumerListener(stomp.ConnectionListener):
    def __init__(self, consumer_id, consume_delay_ms, tracer, logger, host, port, queue):
        self.consumer_id = consumer_id
        self.consume_delay_ms = consume_delay_ms
        self.tracer = tracer
        self.logger = logger
        self.host = host
        self.port = port
        self.queue = queue
        self.messages_consumed = 0
        self.errors = 0
    
    def on_message(self, frame):
        with self.tracer.start_as_current_span(f"slow_consumer.message.{self.consumer_id}") as span:
            from chaosotel.core.trace_core import set_messaging_span_attributes
            set_messaging_span_attributes(
                span,
                messaging_system="activemq",
                destination=self.queue,
                host=self.host,
                port=self.port,
                chaos_activity="activemq_slow_consumer",
                chaos_action="slow_consumer",
                chaos_operation="slow_consumer",
                chaos_consumer_id=self.consumer_id
            )
            
            try:
                # Simulate slow processing
                time.sleep(self.consume_delay_ms / 1000.0)
                
                self.messages_consumed += 1
                
                # Record metrics
                metrics = get_metrics_core()
                tags = get_metric_tags(db_system="activemq", db_operation="slow_consume")
                metrics.record_messaging_operation_count(
                    count=1,
                    mq_system="activemq",
                    mq_destination=self.queue,
                    tags=tags,
                )
                
                
                
                span.set_status(StatusCode.OK)
            except Exception as e:
                self.errors += 1
                span.set_status(StatusCode.ERROR, str(e))
                self.logger.error(f"Slow consumer {self.consumer_id} message processing error: {e}")

def inject_slow_consumer(
    host: Optional[str] = None,
    port: Optional[int] = None,
    user: Optional[str] = None,
    password: Optional[str] = None,
    queue: Optional[str] = None,
    num_consumers: int = 5,
    duration_seconds: int = 60,
    consume_delay_ms: int = 5000
) -> Dict:
    """Inject slow ActiveMQ consumers to create message backlog."""
    host = host or os.getenv("ACTIVEMQ_HOST", "localhost")
    port = port or int(os.getenv("ACTIVEMQ_PORT", "61613"))
    user = user or os.getenv("ACTIVEMQ_USER", "admin")
    password = password or os.getenv("ACTIVEMQ_PASSWORD", "admin")
    queue = queue or os.getenv("ACTIVEMQ_QUEUE", "chaos.test")
    
    ensure_initialized()
    db_system = os.getenv("DB_SYSTEM", "activemq")
    metrics = get_metrics_core()
    tracer = get_tracer()
    logger = get_logger()
    start_time = time.time()
    
    global _active_threads, _stop_event
    _stop_event.clear()
    _active_threads = []
    
    total_messages_consumed = 0
    errors = 0
    
    def slow_consumer_worker(consumer_id: int):
        nonlocal total_messages_consumed, errors
        conn = None
        try:
            with tracer.start_as_current_span(f"slow_consumer.worker.{consumer_id}") as span:
                from chaosotel.core.trace_core import set_messaging_span_attributes
                set_messaging_span_attributes(
                    span,
                    messaging_system="activemq",
                    destination=queue,
                    host=host,
                    port=port,
                    chaos_activity="activemq_slow_consumer",
                    chaos_action="slow_consumer",
                    chaos_operation="slow_consumer",
                    chaos_consumer_id=consumer_id
                )

                conn = stomp.Connection([(host, port)])
                listener = SlowConsumerListener(consumer_id, consume_delay_ms, tracer, logger, host, port, queue)
                conn.set_listener('', listener)
                conn.connect(user, password, wait=True)
                conn.subscribe(destination=f"/queue/{queue}", id=consumer_id, ack='client')
                
                end_time = time.time() + duration_seconds
                while not _stop_event.is_set() and time.time() < end_time:
                    try:
                        time.sleep(1)
                    except Exception as e:
                        errors += 1
                        metrics.record_db_error(db_system=db_system, error_type=type(e).__name__)
                        logger.warning(f"Slow consumer {consumer_id} error: {e}")
                        span.set_status(StatusCode.ERROR, str(e))
                        time.sleep(0.1)
                
                total_messages_consumed += listener.messages_consumed
                errors += listener.errors
                
                span.set_status(StatusCode.OK)
        except Exception as e:
            errors += 1
            logger.error(f"Slow consumer worker {consumer_id} failed: {e}")
        finally:
            if conn:
                try:
                    conn.disconnect()
                except Exception:
                    pass
    
    try:
        with tracer.start_as_current_span("chaos.activemq.slow_consumer") as span:
            from chaosotel.core.trace_core import set_messaging_span_attributes
            set_messaging_span_attributes(
                span,
                messaging_system="activemq",
                destination=queue,
                host=host,
                port=port,
                chaos_activity="activemq_slow_consumer",
                chaos_action="slow_consumer",
                chaos_operation="slow_consumer",
                chaos_num_consumers=num_consumers,
                chaos_duration_seconds=duration_seconds,
                chaos_consume_delay_ms=consume_delay_ms
            )
            
            logger.info(f"Starting ActiveMQ slow consumers with {num_consumers} consumers for {duration_seconds}s")
            
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
                "messages_consumed": total_messages_consumed,
                "errors": errors,
                "consumers_used": num_consumers
            }
            
            span.set_attribute("chaos.messages_consumed", total_messages_consumed)
            span.set_attribute("chaos.errors", errors)
            span.set_status(StatusCode.OK)
            
            logger.info(f"ActiveMQ slow consumer completed: {result}")
            flush()
            return result
    except Exception as e:
        _stop_event.set()
        metrics.record_db_error(db_system=db_system, error_type=type(e).__name__)
        logger.error(f"ActiveMQ slow consumer failed: {e}")
        flush()
        raise

def stop_slow_consumer():
    global _stop_event, _active_threads
    _stop_event.set()
    for thread in _active_threads:
        thread.join(timeout=5)
    _active_threads = []

