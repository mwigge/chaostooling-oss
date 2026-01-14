"""MongoDB connection exhaustion status probe."""

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


def probe_connection_exhaustion_status(
    host: Optional[str] = None,
    port: Optional[int] = None,
    database: Optional[str] = None,
    user: Optional[str] = None,
    password: Optional[str] = None,
    authSource: Optional[str] = None,
) -> dict:
    """

    Probe to check MongoDB connection exhaustion status.

    Observability: Uses chaosotel (chaostooling-otel) as the central observability location. chaosotel must be initialized via chaosotel.control in the experiment configuration.

    """

    host = host or os.getenv("MONGO_HOST", "localhost")

    port = port or int(os.getenv("MONGO_PORT", "27017"))

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

        logger = logging.getLogger(
            "chaosdb.mongodb.mongodb_connection_exhaustion_status"
        )

        logger.addHandler(handler)

        logger.setLevel(logging.INFO)

    else:
        logger = logging.getLogger(
            "chaosdb.mongodb.mongodb_connection_exhaustion_status"
        )

    metrics = get_metrics_core()

    db_system = "mongodb"

    start = time.time()

    span_context = (
        tracer.start_as_current_span("probe.mongodb.connection_exhaustion_status")
        if tracer
        else nullcontext()
    )

    with span_context as span:
        try:
            if span:
                span.set_attribute("db.system", db_system)

                span.set_attribute("db.name", database)

                span.set_attribute("db.operation", "probe_connection_exhaustion")

                span.set_attribute(
                    "chaos.activity", "mongodb_connection_exhaustion_status"
                )

                span.set_attribute("chaos.activity.type", "probe")

                span.set_attribute("chaos.system", "mongodb")

                span.set_attribute("chaos.operation", "connection_exhaustion_status")

            uri = f"mongodb://{host}:{port}/"

            if user and password:
                uri = f"mongodb://{user}:{password}@{host}:{port}/"

                if authSource:
                    uri += f"?authSource={authSource}"

            client = MongoClient(uri)

            db = client[database]

            # Get connection stats

            server_status = db.command("serverStatus")

            conn_stats = server_status.get("connections", {})

            current_connections = conn_stats.get("current", 0)

            available_connections = conn_stats.get("available", 0)

            active_connections = current_connections - available_connections

            # Get max connections (from serverStatus or default)

            max_connections = (
                conn_stats.get("max", 0) or 1000
            )  # Default if not available

            connection_utilization = (
                (current_connections / max_connections * 100)
                if max_connections > 0
                else 0
            )

            client.close()

            probe_time_ms = (time.time() - start) * 1000

            tags = get_metric_tags(
                db_name=database,
                db_system=db_system,
                db_operation="probe_connection_exhaustion",
            )

            metrics.record_db_query_latency(
                probe_time_ms,
                db_system=db_system,
                db_name=database,
                db_operation="probe_connection_exhaustion",
                tags=tags,
            )

            metrics.record_db_query_count(
                db_system=db_system,
                db_name=database,
                db_operation="probe_connection_exhaustion",
                count=1,
                tags=tags,
            )

            result = {
                "success": True,
                "current_connections": current_connections,
                "active_connections": active_connections,
                "available_connections": available_connections,
                "max_connections": max_connections,
                "connection_utilization_percent": connection_utilization,
                "probe_time_ms": probe_time_ms,
            }

            if span:
                span.set_attribute("chaos.current_connections", current_connections)

                span.set_attribute("chaos.active_connections", active_connections)

                span.set_attribute(
                    "chaos.connection_utilization_percent", connection_utilization
                )

                span.set_status(StatusCode.OK)

            logger.info(f"MongoDB connection exhaustion probe: {result}")

            flush()

            return result

        except Exception as e:
            metrics.record_db_error(
                db_system=db_system,
                error_type=type(e).__name__,
                db_name=database,
            )

            if span:
                span.record_exception(e)

                span.set_status(StatusCode.ERROR, str(e))

            logger.error(
                f"MongoDB connection exhaustion probe failed: {str(e)}",
                extra={"error": str(e)},
            )

            flush()

            return {"success": False, "error": str(e)}
