"""Kafka consumer group rebalancing storm chaos action."""
import logging
import os
import threading
import time
from typing import Dict, Optional

from chaosotel import (ensure_initialized, flush, get_metrics_core, get_tracer)
from kafka import KafkaConsumer
from opentelemetry.trace import StatusCode

_active_consumers = []
_stop_event = threading.Event()

def inject_rebalancing_storm(
    bootstrap_servers: Optional[str] = None,
    topic: Optional[str] = None,
    consumer_group: Optional[str] = None,
    num_consumers: int = 10,
    rebalance_interval_seconds: int = 5,
    duration_seconds: int = 60
) -> Dict:
    """
    Inject consumer group rebalancing storm by rapidly adding/removing consumers.
    Forces frequent rebalancing to test system stability during rebalancing.
    """
    bootstrap_servers = bootstrap_servers or os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
    topic = topic or os.getenv("KAFKA_TOPIC", "chaos_test_topic")
    consumer_group = consumer_group or os.getenv("KAFKA_CONSUMER_GROUP", "chaos_rebalancing_group")
    
    ensure_initialized()
    mq_system = os.getenv("MQ_SYSTEM", "kafka")
    metrics = get_metrics_core()
    tracer = get_tracer()
    logger = logging.getLogger("chaosdb.kafka.rebalancing_storm")
    start_time = time.time()
    
    global _active_consumers, _stop_event
    _stop_event.clear()
    _active_consumers = []
    
    rebalances_triggered = 0
    errors = 0
    
    def consumer_worker(consumer_id: int):
        """Consumer worker that joins and leaves the group rapidly."""
        nonlocal rebalances_triggered, errors, metrics
        consumer = None
        try:
            with tracer.start_as_current_span(f"rebalancing_storm.consumer.{consumer_id}") as span:
                from chaosotel.core.trace_core import set_messaging_span_attributes
                # Extract host/port from bootstrap_servers for network attributes
                bootstrap_host = bootstrap_servers.split(',')[0].split(':')[0] if bootstrap_servers else None
                bootstrap_port = int(bootstrap_servers.split(',')[0].split(':')[1]) if bootstrap_servers and ':' in bootstrap_servers.split(',')[0] else None
                set_messaging_span_attributes(
                    span,
                    messaging_system="kafka",
                    destination=topic,
                    bootstrap_servers=bootstrap_servers,
                    host=bootstrap_host,
                    port=bootstrap_port,
                    chaos_activity="kafka_rebalancing_storm",
                    chaos_action="rebalancing_storm",
                    chaos_operation="rebalancing_storm",
                    chaos_consumer_id=consumer_id
                )

                end_time = time.time() + duration_seconds
                
                while not _stop_event.is_set() and time.time() < end_time:
                    try:
                        # Create consumer and join group
                        consumer = KafkaConsumer(
                            topic,
                            bootstrap_servers=bootstrap_servers,
                            group_id=consumer_group,
                            auto_offset_reset='earliest',
                            enable_auto_commit=False,
                            consumer_timeout_ms=1000
                        )
                        
                        _active_consumers.append(consumer)
                        rebalances_triggered += 1
                        
                        # Consume for a short time
                        consumer.poll(timeout_ms=500)
                        
                        # Leave group by closing consumer
                        consumer.close()
                        consumer = None
                        _active_consumers.remove(consumer) if consumer in _active_consumers else None
                        
                        # Wait before rejoining
                        time.sleep(rebalance_interval_seconds)
                        
                        span.set_status(StatusCode.OK)
                        
                    except Exception as e:
                        errors += 1
                        metrics.record_messaging_error(
                            mq_system=mq_system,
                            error_type=type(e).__name__,
                            mq_destination=topic,
                            mq_operation="rebalancing_storm",
                        )
                        logger.warning(f"Rebalancing consumer {consumer_id} error: {e}")
                        span.set_status(StatusCode.ERROR, str(e))
                        if consumer:
                            try:
                                consumer.close()
                            except Exception:
                                pass
                        time.sleep(0.5)
                        
        except Exception as e:
            errors += 1
            logger.error(f"Rebalancing consumer worker {consumer_id} failed: {e}")
        finally:
            if consumer:
                try:
                    consumer.close()
                except Exception:
                    pass
    
    try:
        with tracer.start_as_current_span("chaos.kafka.rebalancing_storm") as span:
            from chaosotel.core.trace_core import set_messaging_span_attributes
            # Extract host/port from bootstrap_servers for network attributes
            bootstrap_host = bootstrap_servers.split(',')[0].split(':')[0] if bootstrap_servers else "kafka"
            bootstrap_port = int(bootstrap_servers.split(',')[0].split(':')[1]) if bootstrap_servers and ':' in bootstrap_servers.split(',')[0] else 9092
            set_messaging_span_attributes(
                span,
                messaging_system="kafka",
                destination=topic,
                bootstrap_servers=bootstrap_servers,
                host=bootstrap_host,
                port=bootstrap_port,
                chaos_activity="kafka_rebalancing_storm",
                chaos_action="rebalancing_storm",
                chaos_operation="rebalancing_storm",
                chaos_num_consumers=num_consumers,
                chaos_rebalance_interval_seconds=rebalance_interval_seconds,
                chaos_duration_seconds=duration_seconds
            )
            
            logger.info(f"Starting Kafka rebalancing storm with {num_consumers} consumers for {duration_seconds}s")
            
            threads = []
            for i in range(num_consumers):
                thread = threading.Thread(target=consumer_worker, args=(i,), daemon=True)
                thread.start()
                threads.append(thread)
                time.sleep(0.5)  # Stagger consumer starts
            
            time.sleep(duration_seconds)
            _stop_event.set()
            for thread in threads:
                thread.join(timeout=10)
            
            # Clean up any remaining consumers
            for consumer in _active_consumers:
                try:
                    consumer.close()
                except Exception:
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
            span.set_attribute("chaos.errors", errors)
            span.set_status(StatusCode.OK)
            
            logger.info(f"Kafka rebalancing storm completed: {result}")
            flush()
            return result
    except Exception as e:
        _stop_event.set()
        metrics = get_metrics_core()
        metrics.record_messaging_error(
            mq_system=mq_system,
            error_type=type(e).__name__,
            mq_destination=topic,
            mq_operation="rebalancing_storm",
        )
        logger.error(f"Kafka rebalancing storm failed: {e}")
        flush()
        raise

def stop_rebalancing_storm():
    """Stop rebalancing storm."""
    global _stop_event, _active_consumers
    _stop_event.set()
    for consumer in _active_consumers:
        try:
            consumer.close()
        except Exception:
            pass
    _active_consumers = []

