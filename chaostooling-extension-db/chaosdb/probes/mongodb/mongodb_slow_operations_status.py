"""MongoDB slow operations status probe."""

import os

import logging

from contextlib import nullcontext

import time

from typing import Optional, Dict

from pymongo import MongoClient

from chaosotel import (

    flush,

    get_metrics_core,

    get_metric_tags,

    get_tracer,

)

from opentelemetry.sdk._logs import LoggingHandler

from opentelemetry._logs import get_logger_provider

from opentelemetry.trace import StatusCode



def probe_slow_operations_status(

    host: Optional[str] = None,

    port: Optional[int] = None,

    database: Optional[str] = None,

    user: Optional[str] = None,

    password: Optional[str] = None,

    authSource: Optional[str] = None,

) -> Dict:

    """

    Probe to check MongoDB slow operations status.

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

        logger = logging.getLogger("chaosdb.mongodb.mongodb_slow_operations_status")

        logger.addHandler(handler)

        logger.setLevel(logging.INFO)

    else:

        logger = logging.getLogger("chaosdb.mongodb.mongodb_slow_operations_status")

    metrics = get_metrics_core()

    

    db_system = "mongodb"

    start = time.time()

    span = None

    

    span_context = (

            tracer.start_as_current_span("probe.mongodb.slow_operations_status")

            if tracer

            else nullcontext()

        )

        

    with span_context as span:

        try:





        

            if span:

                span.set_attribute("db.system", db_system)

                span.set_attribute("db.name", database)

                span.set_attribute("db.operation", "probe_slow_operations")

                span.set_attribute("chaos.activity", "mongodb_slow_operations_status")

                span.set_attribute("chaos.activity.type", "probe")

                span.set_attribute("chaos.system", "mongodb")

                span.set_attribute("chaos.operation", "slow_operations_status")

            

            uri = f"mongodb://{host}:{port}/"

            if user and password:

                uri = f"mongodb://{user}:{password}@{host}:{port}/"

                if authSource:

                    uri += f"?authSource={authSource}"

            

            client = MongoClient(uri)

            db = client[database]

            

            # Get current operations with duration

            current_ops = db.current_op({"active": True, "secs_running": {"$gt": 1}})

            slow_operations = []

            for op in current_ops:

                duration_ms = op.get("secs_running", 0) * 1000

                slow_operations.append({

                    "opid": op.get("opid"),

                    "duration_ms": duration_ms,

                    "op": op.get("op", "unknown")

                })

            

            # Get slow operation count

            slow_op_count = len(slow_operations)

            avg_duration_ms = sum(op["duration_ms"] for op in slow_operations) / slow_op_count if slow_op_count > 0 else 0

            max_duration_ms = max((op["duration_ms"] for op in slow_operations), default=0)

            

            client.close()

            

            probe_time_ms = (time.time() - start) * 1000

            

            tags = get_metric_tags(

                db_name=database,

                db_system=db_system,

                db_operation="probe_slow_operations",

            )

            metrics.record_db_query_latency(

                probe_time_ms,

                db_system=db_system,

                db_name=database,

                db_operation="probe_slow_operations",

                tags=tags,

            )

            metrics.record_db_query_count(

                db_system=db_system,

                db_name=database,

                db_operation="probe_slow_operations",

                count=1,

                tags=tags,

            )

            

            result = {

                "success": True,

                "slow_operations_count": slow_op_count,

                "average_duration_ms": avg_duration_ms,

                "max_duration_ms": max_duration_ms,

                "probe_time_ms": probe_time_ms

            }

            

            if span:

                span.set_attribute("chaos.slow_operations_count", slow_op_count)

                span.set_attribute("chaos.average_duration_ms", avg_duration_ms)

                span.set_status(StatusCode.OK)

            

            logger.info(f"MongoDB slow operations probe: {result}")

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

            logger.error(f"MongoDB slow operations probe failed: {str(e)}", extra={"error": str(e)})

            flush()

            raise
