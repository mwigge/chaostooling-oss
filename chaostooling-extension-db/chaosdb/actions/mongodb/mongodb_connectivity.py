import logging
import os
import time
from typing import Optional

from chaosotel import (ensure_initialized, flush, get_metric_tags, get_metrics_core, get_tracer)
from opentelemetry.trace import StatusCode
from pymongo import MongoClient


def test_mongodb_connection(
    host: Optional[str] = None,
    port: Optional[int] = None,
    database: Optional[str] = None,
    user: Optional[str] = None,
    password: Optional[str] = None,
    authSource: Optional[str] = None,
) -> dict:
    """
    Simple connectivity check against MongoDB with chaosotel tracing/metrics.
    """
    # Handle string input from Chaos Toolkit configuration
    if port is not None:
        port = int(port) if isinstance(port, str) else port

    host = host or os.getenv("MONGO_HOST", "localhost")
    port = port or int(os.getenv("MONGO_PORT", "27017"))
    database = database or os.getenv("MONGO_DB", "test")
    user = user or os.getenv("MONGO_USER")
    password = password or os.getenv("MONGO_PASSWORD")
    authSource = authSource or os.getenv("MONGO_AUTHSOURCE")

    ensure_initialized()
    db_system = os.getenv("DB_SYSTEM", "mongodb")
    metrics = get_metrics_core()
    tracer = get_tracer()
    logger = logging.getLogger("chaosdb.mongodb.connectivity")
    start = time.time()
    span = None

    try:
        with tracer.start_as_current_span("test.mongodb.connection") as span:
            span.set_attribute("db.system", db_system)
            span.set_attribute("db.name", database)
            if user:
                span.set_attribute("db.user", user)
            span.set_attribute("network.peer.address", host)
            span.set_attribute("network.peer.port", port)
            span.set_attribute("db.operation", "connect")
            span.set_attribute("chaos.activity", "mongodb_connectivity")
            span.set_attribute("chaos.activity.type", "action")
            span.set_attribute("chaos.system", "mongodb")
            span.set_attribute("chaos.operation", "connectivity")

            uri = f"mongodb://{host}:{port}/"
            if user and password:
                uri = f"mongodb://{user}:{password}@{host}:{port}/"
                if authSource:
                    uri += f"?authSource={authSource}"

            client = MongoClient(uri, serverSelectionTimeoutMS=5000)
            db = client[database]
            query_start = time.time()
            db.command("ping")
            query_time_ms = (time.time() - query_start) * 1000
            client.close()

            connection_time_ms = (time.time() - start) * 1000
            tags = get_metric_tags(
                db_name=database,
                db_system=db_system,
                db_operation="connect",
            )
            metrics.record_db_query_latency(
                query_time_ms,
                db_system=db_system,
                db_name=database,
                db_operation="connect",
                tags=tags,
            )
            metrics.record_db_query_count(
                db_system=db_system,
                db_name=database,
                db_operation="connect",
                count=1,
                tags=tags,
            )

            span.set_status(StatusCode.OK)
            logger.info(
                f"MongoDB connection OK: {connection_time_ms:.2f}ms",
                extra={"connection_time_ms": connection_time_ms},
            )
            flush()
            return {
                "success": True,
                "connection_time_ms": connection_time_ms,
                "query_time_ms": query_time_ms,
                "database": database,
                "host": host,
            }
    except Exception as e:
        metrics.record_db_error(
            db_system=db_system,
            error_type=type(e).__name__,
            db_name=database,
        )
        if span:
            span.set_status(StatusCode.ERROR, str(e))
        logger.error(
            f"MongoDB connection failed: {e}",
            extra={"error": str(e)},
        )
        flush()
        raise
