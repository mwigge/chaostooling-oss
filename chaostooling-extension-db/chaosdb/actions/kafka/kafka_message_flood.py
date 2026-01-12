"""Kafka message flood chaos action."""
import logging
import os
import time
import threading
from typing import Optional, Dict
from kafka import KafkaProducer, KafkaConsumer
from chaosotel import (
    ensure_initialized,
    get_tracer,
    flush,
    get_metrics_core,
    get_metric_tags,
)
from opentelemetry.trace import StatusCode

_active_threads = []
_stop_event = threading.Event()

def inject_message_flood(
    bootstrap_servers: Optional[str] = None,
    topic: Optional[str] = None,
    num_producers: int = 10,
    messages_per_producer: int = 1000,
    duration_seconds: int = 60
) -> Dict:
    """Flood Kafka topic with high volume of messages."""
    bootstrap_servers = bootstrap_servers or os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
    topic = topic or os.getenv("KAFKA_TOPIC", "chaos_test_topic")
    
    ensure_initialized()
    mq_system = os.getenv("MQ_SYSTEM", "kafka")
    tracer = get_tracer()
    logger = logging.getLogger("chaosdb.kafka.message_flood")
    start_time = time.time()
    
    global _active_threads, _stop_event
    _stop_event.clear()
    _active_threads = []
    
    total_messages_sent = 0
    errors = 0
    
    def producer_worker(producer_id: int):
        nonlocal total_messages_sent, errors
        producer = None
        try:
            with tracer.start_as_current_span(
                f"message_flood.producer.{producer_id}"
            ) as span:
                span.set_attribute("messaging.system", mq_system)
                span.set_attribute("messaging.destination", topic)
                span.set_attribute("chaos.producer_id", producer_id)
                span.set_attribute("chaos.action", "message_flood")
                span.set_attribute("chaos.activity", "kafka_message_flood")
                span.set_attribute("chaos.activity.type", "action")
                span.set_attribute("chaos.system", "kafka")
                span.set_attribute("chaos.operation", "message_flood")

                producer = KafkaProducer(bootstrap_servers=bootstrap_servers)
                
                message_count = 0
                end_time = time.time() + duration_seconds
                
                while not _stop_event.is_set() and time.time() < end_time and message_count < messages_per_producer:
                    try:
                        send_start = time.time()
                        
                        message = f"chaos_test_{producer_id}_{message_count}".encode()
                        future = producer.send(topic, message)
                        future.get(timeout=10)  # Wait for send confirmation
                        
                        send_duration_ms = (time.time() - send_start) * 1000
                        total_messages_sent += 1
                        message_count += 1
                        
                        tags = get_metric_tags(
                            mq_system=mq_system,
                            mq_destination=topic,
                            mq_operation="message_send",
                        )

                        metrics.record_messaging_operation_count(
                            mq_system=mq_system,
                            mq_destination=topic,
                            mq_operation="message_send",
                            tags=tags,
                        )
                        
                        metrics.record_messaging_operation_latency(
                            duration_ms=send_duration_ms,
                            mq_system=mq_system,
                            mq_destination=topic,
                            mq_operation="message_send",
                            tags=tags,
                        )

                        span.set_status(StatusCode.OK)
                        time.sleep(0.01)
                    except Exception as e:
                        errors += 1
                        metrics.record_messaging_error(
                            mq_system=mq_system,
                            error_type=type(e).__name__,
                            mq_destination=topic,
                            mq_operation="message_send",
                        )
                        logger.warning(f"Producer {producer_id} error: {e}")
                        span.set_status(StatusCode.ERROR, str(e))
                
                span.set_status(StatusCode.OK)
        except Exception as e:
            errors += 1
            logger.error(f"Message flood producer {producer_id} failed: {e}")
        finally:
            if producer:
                try:
                    producer.close()
                except:
                    pass
    
    try:
        with tracer.start_as_current_span("chaos.kafka.message_flood") as span:
            span.set_attribute("messaging.system", mq_system)
            span.set_attribute("messaging.destination", topic)
            span.set_attribute("chaos.num_producers", num_producers)
            span.set_attribute("chaos.duration_seconds", duration_seconds)
            span.set_attribute("chaos.action", "message_flood")
            span.set_attribute("chaos.activity", "kafka_message_flood")
            span.set_attribute("chaos.activity.type", "action")
            span.set_attribute("chaos.system", "kafka")
            span.set_attribute("chaos.operation", "message_flood")
            
            logger.info(f"Starting Kafka message flood with {num_producers} producers for {duration_seconds}s")
            
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
            
            logger.info(f"Kafka message flood completed: {result}")
            flush()
            return result
    except Exception as e:
        _stop_event.set()
        metrics.record_db_error(
            db_system=mq_system, error_type=type(e).__name__, db_name=topic
        )
        logger.error(f"Kafka message flood failed: {e}")
        flush()
        raise

def stop_message_flood():
    global _stop_event, _active_threads
    _stop_event.set()
    for thread in _active_threads:
        thread.join(timeout=2)
    _active_threads = []

