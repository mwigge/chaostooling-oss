"""MongoDB connectivity probe."""

import logging
import os
import time
from contextlib import nullcontext
from typing import Optional

from chaosotel import flush, get_metric_tags, get_metrics_core, get_tracer
from opentelemetry._logs import get_logger_provider
from opentelemetry.sdk._logs import LoggingHandler
from opentelemetry.trace import StatusCode
from pymongo import MongoClient


def probe_mongodb_connectivity(
    host: Optional[str] = None,
    port: Optional[int] = None,
    database: Optional[str] = None,
    user: Optional[str] = None,
    password: Optional[str] = None,
    authSource: Optional[str] = None,
) -> bool:
    """

    Probe MongoDB connectivity.

    Observability: Uses chaosotel (chaostooling-otel) as the central observability location. chaosotel must be initialized via chaosotel.control in the experiment configuration.

    """

    host = host or os.getenv("MONGO_HOST", "localhost")

    # Handle port as string or int from JSON configuration
    if port is not None:
        port = int(port) if isinstance(port, str) else port
    else:
        port = int(os.getenv("MONGO_PORT", "27017"))

    database = database or os.getenv("MONGO_DB", "test")

    user = user or os.getenv("MONGO_USER")

    password = password or os.getenv("MONGO_PASSWORD")

    authSource = authSource or os.getenv("MONGO_AUTHSOURCE")

    # chaosotel is initialized via chaosotel.control - use directly

    tracer = get_tracer()

    # Setup OpenTelemetry logger via LoggingHandler

    logger_provider = get_logger_provider()

    if logger_provider:
        handler = LoggingHandler(level=logging.INFO, logger_provider=logger_provider)

        logger = logging.getLogger("chaosdb.mongodb.mongodb_connectivity")

        logger.addHandler(handler)

        logger.setLevel(logging.INFO)

    else:
        logger = logging.getLogger("chaosdb.mongodb.mongodb_connectivity")

    metrics = get_metrics_core()

    db_system = "mongodb"

    start = time.time()

    span = None

    span_context = (
        tracer.start_as_current_span("probe.mongodb.connectivity")
        if tracer
        else nullcontext()
    )

    with span_context as span:
        try:
            if span:
                span.set_attribute("db.system", db_system)

                span.set_attribute("db.name", database)

                span.set_attribute("network.peer.address", host)

                span.set_attribute("network.peer.port", port)

                span.set_attribute("db.operation", "probe")

                span.set_attribute("chaos.activity", "mongodb_connectivity_probe")

                span.set_attribute("chaos.activity.type", "probe")

                span.set_attribute("chaos.system", "mongodb")

                span.set_attribute("chaos.operation", "connectivity")

            uri = f"mongodb://{host}:{port}/"

            if user and password:
                uri = f"mongodb://{user}:{password}@{host}:{port}/"

                if authSource:
                    uri += f"?authSource={authSource}"

            client = MongoClient(uri, serverSelectionTimeoutMS=5000)

            db = client[database]

            db.command("ping")

            client.close()

            probe_time_ms = (time.time() - start) * 1000

            tags = get_metric_tags(
                db_name=database,
                db_system=db_system,
                db_operation="probe",
            )

            metrics.record_db_query_latency(
                probe_time_ms,
                db_system=db_system,
                db_name=database,
                db_operation="probe",
                tags=tags,
            )

            metrics.record_db_query_count(
                db_system=db_system,
                db_name=database,
                count=1,
                db_operation="probe",
                tags=tags,
            )

            if span:
                span.set_status(StatusCode.OK)

            logger.info(
                f"MongoDB probe OK: {probe_time_ms:.2f}ms",
                extra={"probe_time_ms": probe_time_ms},
            )

            flush()

            return True

        except Exception as e:
            metrics.record_db_error(
                db_system=db_system,
                error_type=type(e).__name__,
                db_name=database,
            )

            if span:
                span.record_exception(e)

                span.set_status(StatusCode.ERROR, str(e))

            logger.error(f"MongoDB probe failed: {str(e)}", extra={"error": str(e)})

            flush()

            return False
