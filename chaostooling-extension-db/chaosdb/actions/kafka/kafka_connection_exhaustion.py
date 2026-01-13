"""Kafka connection exhaustion chaos action."""

import logging
import os
import threading
import time
from typing import Optional

from chaosotel import ensure_initialized, flush, get_metrics_core, get_tracer
from kafka import KafkaProducer
from opentelemetry.trace import StatusCode

_active_connections = []
_stop_event = threading.Event()


def inject_connection_exhaustion(
    bootstrap_servers: Optional[str] = None,
    topic: Optional[str] = None,
    num_connections: int = 100,
    hold_duration_seconds: int = 60,
    leak_connections: bool = False,
) -> dict:
    """Exhaust Kafka connection pool."""
    bootstrap_servers = bootstrap_servers or os.getenv(
        "KAFKA_BOOTSTRAP_SERVERS", "localhost:9092"
    )
    topic = topic or os.getenv("KAFKA_TOPIC", "chaos_test_topic")

    ensure_initialized()
    mq_system = os.getenv("MQ_SYSTEM", "kafka")
    tracer = get_tracer()
    logger = logging.getLogger("chaosdb.kafka.connection_exhaustion")
    start_time = time.time()

    global _active_connections, _stop_event
    _stop_event.clear()
    _active_connections = []

    connections_created = 0
    connections_failed = 0
    errors = 0

    def create_and_hold_connection(conn_id: int):
        nonlocal connections_created, connections_failed, errors
        producer = None
        try:
            with tracer.start_as_current_span(
                f"connection_exhaustion.connection.{conn_id}"
            ) as span:
                from chaosotel.core.trace_core import set_messaging_span_attributes
                # Extract host/port from bootstrap_servers for network attributes
                bootstrap_host = bootstrap_servers.split(',')[0].split(':')[0] if bootstrap_servers else None
                bootstrap_port = int(bootstrap_servers.split(',')[0].split(':')[1]) if bootstrap_servers and ':' in bootstrap_servers.split(',')[0] else None
                set_messaging_span_attributes(
                    span,
                    messaging_system=mq_system,
                    destination=topic,
                    bootstrap_servers=bootstrap_servers,
                    host=bootstrap_host,
                    port=bootstrap_port,
                    chaos_activity="kafka_connection_exhaustion",
                    chaos_action="connection_exhaustion",
                    chaos_operation="connection_exhaustion",
                    chaos_connection_id=conn_id
                )

                try:
                    producer = KafkaProducer(bootstrap_servers=bootstrap_servers)
                    producer.send(topic, b"ping").get(timeout=5)

                    connections_created += 1
                    _active_connections.append(producer)

                    end_time = time.time() + hold_duration_seconds
                    while not _stop_event.is_set() and time.time() < end_time:
                        try:
                            producer.send(topic, b"keepalive").get(timeout=5)
                            time.sleep(1)
                        except Exception as e:
                            logger.warning(
                                f"Connection {conn_id} error during hold: {e}"
                            )
                            break

                    span.set_status(StatusCode.OK)
                except Exception as e:
                    connections_failed += 1
                    metrics.record_messaging_error(
                        mq_system=mq_system,
                        error_type=type(e).__name__,
                        mq_destination=topic,
                        mq_operation="connection_exhaustion",
                    )
                    logger.warning(f"Failed to create connection {conn_id}: {e}")
                    span.set_status(StatusCode.ERROR, str(e))
        except Exception as e:
            errors += 1
            logger.error(f"Connection {conn_id} failed: {e}")
        finally:
            if producer and not leak_connections:
                try:
                    producer.close()
                except:
                    pass
            elif producer and leak_connections:
                logger.warning(f"Leaking connection {conn_id} (intentional)")

    with tracer.start_as_current_span("chaos.kafka.connection_exhaustion") as span:
        try:
            span.set_attribute("messaging.system", mq_system)
            span.set_attribute("messaging.destination", topic)
            span.set_attribute("chaos.num_connections", num_connections)
            span.set_attribute("chaos.hold_duration_seconds", hold_duration_seconds)
            span.set_attribute("chaos.action", "connection_exhaustion")
            span.set_attribute("chaos.activity", "kafka_connection_exhaustion")
            span.set_attribute("chaos.activity.type", "action")
            span.set_attribute("chaos.system", "kafka")
            span.set_attribute("chaos.operation", "connection_exhaustion")

            logger.info(
                f"Starting Kafka connection exhaustion with {num_connections} connections"
            )

            threads = []
            for i in range(num_connections):
                thread = threading.Thread(
                    target=create_and_hold_connection, args=(i,), daemon=True
                )
                thread.start()
                threads.append(thread)
                time.sleep(0.1)

            time.sleep(hold_duration_seconds)
            _stop_event.set()
            for thread in threads:
                thread.join(timeout=5)

            if not leak_connections:
                for producer in _active_connections:
                    try:
                        producer.close()
                    except:
                        pass

            duration_ms = (time.time() - start_time) * 1000

            result = {
                "success": True,
                "duration_ms": duration_ms,
                "connections_created": connections_created,
                "connections_failed": connections_failed,
                "connections_leaked": (
                    len(_active_connections) if leak_connections else 0
                ),
                "errors": errors,
                "target_connections": num_connections,
            }

            span.set_attribute("chaos.connections_created", connections_created)
            span.set_attribute("chaos.connections_failed", connections_failed)
            span.set_status(StatusCode.OK)

            logger.info(f"Kafka connection exhaustion completed: {result}")
            flush()
            return result
        except Exception as e:
            _stop_event.set()
            metrics = get_metrics_core()
            metrics.record_messaging_error(
                mq_system=mq_system,
                error_type=type(e).__name__,
                mq_destination=topic,
                mq_operation="connection_exhaustion",
            )
            span.set_status(StatusCode.ERROR, str(e))
            span.record_exception(e)
            logger.error("Kafka connection exhaustion failed: %s", e)
            flush()
            raise


def stop_connection_exhaustion():
    global _stop_event, _active_connections
    _stop_event.set()
    for producer in _active_connections:
        try:
            producer.close()
        except:
            pass
    _active_connections = []
