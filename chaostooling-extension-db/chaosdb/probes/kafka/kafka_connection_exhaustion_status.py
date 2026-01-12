"""Kafka connection exhaustion status probe."""

import os

import logging

from contextlib import nullcontext

import time

from typing import Optional, Dict

from kafka import KafkaAdminClient

from chaosotel import get_tracer, get_metrics_core, get_metric_tags, flush

from opentelemetry.sdk._logs import LoggingHandler

from opentelemetry._logs import get_logger_provider

import logging

from opentelemetry.trace import StatusCode



def probe_connection_exhaustion_status(

    bootstrap_servers: Optional[str] = None,

) -> Dict:

    """

    Probe to check Kafka connection exhaustion status.

    

    Observability: Uses chaosotel (chaostooling-otel) as the central

    observability location. chaosotel must be initialized via chaosotel.control in

    the experiment configuration.

    """

    bootstrap_servers = bootstrap_servers or os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")

    

    # chaosotel is initialized via chaosotel.control - use directly

    tracer = get_tracer()

    # Setup OpenTelemetry logger via LoggingHandler

    logger_provider = get_logger_provider()

    if logger_provider:

        handler = LoggingHandler(level=logging.INFO, logger_provider=logger_provider)

        logger = logging.getLogger("chaosdb.kafka.kafka_connection_exhaustion_status")

        logger.addHandler(handler)

        logger.setLevel(logging.INFO)

    else:

        logger = logging.getLogger("chaosdb.kafka.kafka_connection_exhaustion_status")

    metrics = get_metrics_core()

    

    mq_system = "kafka"

    start = time.time()

    span = None

    

    span_context = (

            tracer.start_as_current_span("probe.kafka.connection_exhaustion_status")

            if tracer

            else nullcontext()

        )

        

    with span_context as span:

        try:





        

            if span:

                span.set_attribute("messaging.system", "kafka")

                span.set_attribute("chaos.activity", "kafka_connection_exhaustion_status")

                span.set_attribute("chaos.activity.type", "probe")

                span.set_attribute("chaos.system", "kafka")

                span.set_attribute("chaos.operation", "connection_exhaustion_status")

            

            admin = KafkaAdminClient(bootstrap_servers=bootstrap_servers)

            

            # Get broker info

            cluster_metadata = admin.describe_cluster()

            broker_count = len(cluster_metadata.brokers) if hasattr(cluster_metadata, 'brokers') else 0

            

            admin.close()

            

            probe_time_ms = (time.time() - start) * 1000

            

            tags = get_metric_tags(

                mq_system=mq_system,

                mq_operation="probe",

            )

            metrics.record_messaging_operation_count(

                mq_system=mq_system,

                mq_operation="probe",

                tags=tags,

            )

            metrics.record_messaging_operation_latency(

                duration_ms=probe_time_ms,

                mq_system=mq_system,

                mq_operation="probe",

                tags=tags,

            )

            

            result = {

                "success": True,

                "broker_count": broker_count,

                "probe_time_ms": probe_time_ms

            }

            

            if span:

                span.set_attribute("chaos.broker_count", broker_count)

                span.set_status(StatusCode.OK)

            

            logger.info(f"Kafka connection exhaustion probe: {result}")

            flush()

            return result

        except Exception as e:
            metrics.record_messaging_error(
            mq_system=mq_system,
            error_type=type(e).__name__,
            mq_operation="probe",
        )

        if span:

            span.record_exception(e)

            span.set_status(StatusCode.ERROR, str(e))

            span.record_exception(e)

        logger.error(f"Kafka connection exhaustion probe failed: {str(e)}", extra={"error": str(e)})

        flush()

        return {"success": False, "error": str(e)}
