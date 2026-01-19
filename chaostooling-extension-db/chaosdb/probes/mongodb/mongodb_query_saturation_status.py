"""MongoDB query saturation status probe."""

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


def probe_query_saturation_status(
    host: Optional[str] = None,
    port: Optional[int] = None,
    database: Optional[str] = None,
    user: Optional[str] = None,
    password: Optional[str] = None,
    authSource: Optional[str] = None,
) -> dict:
    """
    Probe to check MongoDB query saturation status.
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
        logger = logging.getLogger("chaosdb.mongodb.mongodb_query_saturation_status")
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
    else:
        logger = logging.getLogger("chaosdb.mongodb.mongodb_query_saturation_status")
    metrics = get_metrics_core()

    db_system = "mongodb"
    start = time.time()

    span_context = (
        tracer.start_as_current_span("probe.mongodb.query_saturation_status")
        if tracer
        else nullcontext()
    )

    with span_context as span:
        try:
            if span:
                span.set_attribute("db.system", db_system)
                span.set_attribute("db.name", database)
                span.set_attribute("db.operation", "probe_query_saturation")
                span.set_attribute("chaos.activity", "mongodb_query_saturation_status")
                span.set_attribute("chaos.activity.type", "probe")
                span.set_attribute("chaos.system", "mongodb")
                span.set_attribute("chaos.operation", "query_saturation_status")

            uri = f"mongodb://{host}:{port}/"
            if user and password:
                uri = f"mongodb://{user}:{password}@{host}:{port}/"
                if authSource:
                    uri += f"?authSource={authSource}"

            client = MongoClient(uri)
            db = client[database]

            # Get active operations
            # Note: current_op() was removed in pymongo 4.0+, use command("currentOp") instead
            try:
                # Try new API first (pymongo 4.0+)
                current_ops_result = db.command("currentOp", {"active": True})
                # currentOp returns a dict with "inprog" key containing the list of operations
                current_ops = current_ops_result.get("inprog", [])
            except Exception:
                # Fallback to old API for older pymongo versions
                try:
                    current_ops = db.current_op({"active": True})
                except AttributeError:
                    # If current_op doesn't exist, try client.admin.command
                    current_ops_result = client.admin.command("currentOp", {"active": True})
                    current_ops = current_ops_result.get("inprog", [])
            
            active_operations = len(current_ops) if isinstance(current_ops, list) else 0

            # Get connection stats
            server_status = db.command("serverStatus")
            conn_stats = server_status.get("connections", {})
            current_connections = conn_stats.get("current", 0)
            available_connections = conn_stats.get("available", 0)

            # Get operation counters
            op_counters = server_status.get("opcounters", {})
            total_operations = sum(op_counters.values())

            client.close()

            probe_time_ms = (time.time() - start) * 1000

            tags = get_metric_tags(
                db_name=database,
                db_system=db_system,
                db_operation="probe_query_saturation",
            )
            metrics.record_db_query_latency(
                probe_time_ms,
                db_system=db_system,
                db_name=database,
                db_operation="probe_query_saturation",
                tags=tags,
            )
            metrics.record_db_query_count(
                db_system=db_system,
                db_name=database,
                db_operation="probe_query_saturation",
                count=1,
                tags=tags,
            )

            result = {
                "success": True,
                "active_operations": active_operations,
                "current_connections": current_connections,
                "available_connections": available_connections,
                "total_operations": total_operations,
                "probe_time_ms": probe_time_ms,
            }

            if span:
                span.set_attribute("chaos.active_operations", active_operations)
                span.set_attribute("chaos.current_connections", current_connections)
                span.set_status(StatusCode.OK)

            logger.info(f"MongoDB query saturation probe: {result}")
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
                f"MongoDB query saturation probe failed: {str(e)}",
                extra={"error": str(e)},
            )
            flush()
            raise
