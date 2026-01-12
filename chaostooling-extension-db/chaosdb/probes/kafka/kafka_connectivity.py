"""Kafka connectivity probe."""

import os

import logging

from contextlib import nullcontext

import time

from typing import Optional

from kafka import KafkaProducer
from kafka.errors import KafkaError, KafkaTimeoutError

from chaosotel import get_tracer, get_metrics_core, get_metric_tags, flush

import threading

from opentelemetry.sdk._logs import LoggingHandler

from opentelemetry._logs import get_logger_provider

import logging

from opentelemetry.trace import StatusCode



def probe_kafka_connectivity(

    bootstrap_servers: Optional[str] = None,

    topic: Optional[str] = None,

) -> bool:

    """

    Probe Kafka connectivity by sending a test message.

    

    Observability: Uses chaosotel (chaostooling-otel) as the central

    observability location. chaosotel must be initialized via chaosotel.control in

    the experiment configuration.

    """

    bootstrap_servers = bootstrap_servers or os.getenv(

        "KAFKA_BOOTSTRAP_SERVERS", "localhost:9092"

    )

    topic = topic or os.getenv("KAFKA_TOPIC", "test")

    

    # chaosotel is initialized via chaosotel.control - use directly

    tracer = get_tracer()

    # Setup OpenTelemetry logger via LoggingHandler

    logger_provider = get_logger_provider()

    if logger_provider:

        handler = LoggingHandler(level=logging.INFO, logger_provider=logger_provider)

        logger = logging.getLogger("chaosdb.kafka.kafka_connectivity")

        logger.addHandler(handler)

        logger.setLevel(logging.INFO)

    else:

        logger = logging.getLogger("chaosdb.kafka.kafka_connectivity")

    metrics = get_metrics_core()

    

    mq_system = "kafka"

    start = time.time()

    

    span_context = (

            tracer.start_as_current_span("probe.kafka.connectivity")

            if tracer

            else nullcontext()

        )

        

    with span_context as span:

        try:





        

            if span:

                span.set_attribute("chaos.activity", "kafka_connectivity_probe")

                span.set_attribute("chaos.activity.type", "probe")

                span.set_attribute("chaos.system", "kafka")

                span.set_attribute("chaos.operation", "connectivity")

                span.set_attribute("messaging.system", "kafka")

                span.set_attribute("messaging.destination", topic)

                span.set_attribute("network.peer.address", bootstrap_servers)

            

            # Use threading to enforce overall timeout
            max_probe_time = 8  # 8 seconds max for entire probe
            result = {"success": False, "error": None}
            exception_occurred = threading.Event()
            
            def kafka_operation():
                producer = None
                try:
                    logger.debug(f"Attempting to connect to Kafka at {bootstrap_servers}")
                    producer = KafkaProducer(
                        bootstrap_servers=bootstrap_servers,
                        request_timeout_ms=2000,  # 2 seconds
                        api_version=(0, 10, 1),
                        connections_max_idle_ms=2000,
                        metadata_max_age_ms=2000,
                        max_block_ms=2000  # Max time to block during send
                    )
                    logger.debug("KafkaProducer created successfully")

                    # Send with timeout
                    logger.debug(f"Sending test message to topic {topic}")
                    future = producer.send(topic, b'chaos-connectivity-test')
                    
                    # Wait for send with timeout
                    record_metadata = future.get(timeout=2)
                    logger.debug(f"Message sent to topic {record_metadata.topic}, partition {record_metadata.partition}")

                    # Flush with shorter timeout
                    producer.flush(timeout=1)
                    logger.debug("Producer flushed successfully")

                    producer.close()
                    result["success"] = True
                except Exception as e:
                    result["error"] = e
                    exception_occurred.set()
                    logger.error(f"Kafka operation failed: {str(e)}", exc_info=True)
                    if producer:
                        try:
                            producer.close()
                        except:
                            pass
            
            # Run in thread with timeout
            thread = threading.Thread(target=kafka_operation, daemon=True)
            thread.start()
            thread.join(timeout=max_probe_time)
            
            if thread.is_alive():
                # Thread is still running - timeout occurred
                error_msg = f"Kafka probe exceeded {max_probe_time}s timeout. Kafka may be unavailable at {bootstrap_servers}"
                logger.error(error_msg)
                raise TimeoutError(error_msg)
            
            if exception_occurred.is_set() and result["error"]:
                # Re-raise the original exception with more context
                error = result["error"]
                if isinstance(error, (KafkaError, KafkaTimeoutError)):
                    error_msg = f"Kafka connection failed to {bootstrap_servers}: {str(error)}. Ensure Kafka is running and accessible."
                else:
                    error_msg = f"Kafka probe failed: {str(error)}"
                logger.error(error_msg)
                raise type(error)(error_msg) from error
            
            if not result["success"]:
                error_msg = f"Kafka probe failed without error. Kafka may be unavailable at {bootstrap_servers}"
                logger.error(error_msg)
                raise TimeoutError(error_msg)

            

            probe_time_ms = (time.time() - start) * 1000

            

            tags = get_metric_tags(

                mq_system=mq_system,

                mq_destination=topic,

                mq_operation="probe",

            )

            metrics.record_messaging_operation_count(

                mq_system=mq_system,

                mq_destination=topic,

                mq_operation="probe",

                tags=tags,

            )

            metrics.record_messaging_operation_latency(

                duration_ms=probe_time_ms,

                mq_system=mq_system,

                mq_destination=topic,

                mq_operation="probe",

                tags=tags,

            )

            

            if span:

                span.set_status(StatusCode.OK)

            logger.info(

                f"Kafka probe OK: {probe_time_ms:.2f}ms", extra={"probe_time_ms": probe_time_ms}

            )

            flush()

            return True

        except (KafkaError, KafkaTimeoutError, TimeoutError) as e:
            metrics.record_messaging_error(
                mq_system=mq_system,
                error_type=type(e).__name__,
                mq_destination=topic,
                mq_operation="probe",
            )

            if span:

                span.record_exception(e)

                span.set_status(StatusCode.ERROR, str(e))

            logger.error(f"Kafka probe failed: {str(e)}", extra={"error": str(e)})

            flush()

            return False

        except Exception as e:
            metrics.record_messaging_error(
                mq_system=mq_system,
                error_type=type(e).__name__,
                mq_destination=topic,
                mq_operation="probe",
            )

            if span:

                span.record_exception(e)

                span.set_status(StatusCode.ERROR, str(e))

            logger.error(f"Kafka probe failed with unexpected error: {str(e)}", extra={"error": str(e)})

            flush()

            return False
