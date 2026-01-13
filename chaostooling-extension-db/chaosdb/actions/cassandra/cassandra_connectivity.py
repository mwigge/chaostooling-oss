import os
import time
from typing import Optional

from cassandra.cluster import Cluster
from chaosotel import ( get_metric_tags, get_metrics_core
    ensure_initialized,
    flush,
    get_logger,
    get_metric_tags,
    get_metrics_core,
    get_tracer,
)
from opentelemetry.trace import StatusCode


def test_cassandra_connection(
    host: Optional[str] = None,
    port: Optional[int] = None,
    keyspace: Optional[str] = None,
    user: Optional[str] = None,
    password: Optional[str] = None,
) -> dict:
    host = host or os.getenv("CASSANDRA_HOST", "localhost")
    port = port or int(os.getenv("CASSANDRA_PORT", "9042"))
    keyspace = keyspace or os.getenv("CASSANDRA_KEYSPACE", "system")
    user = user or os.getenv("CASSANDRA_USER")
    password = password or os.getenv("CASSANDRA_PASSWORD")
    ensure_initialized()
    db_system = os.getenv("DB_SYSTEM", "cassandra")
    metrics = get_metrics_core()
    tracer = get_tracer()
    logger = get_logger()
    start = time.time()
    try:
        with tracer.start_as_current_span("test.cassandra.connection") as span:
            span.set_attribute("db.system", db_system)
            span.set_attribute("db.name", keyspace)
            span.set_attribute("network.peer.address", host)
            span.set_attribute("network.peer.port", port)
            span.set_attribute("db.operation", "connect")
            span.set_attribute("chaos.activity", "cassandra_connectivity")
            span.set_attribute("chaos.activity.type", "action")
            span.set_attribute("chaos.system", "cassandra")
            span.set_attribute("chaos.operation", "connectivity")
            cluster = Cluster([host], port=port)
            session = cluster.connect(keyspace)
            session.execute("SELECT release_version FROM system.local")
            session.shutdown()
            cluster.shutdown()
            connection_time_ms = (time.time() - start) * 1000
            tags = get_metric_tags(
                db_name=keyspace, db_system=db_system, db_operation="connect"
            )
            metrics.record_db_query_latency(
                connection_time_ms,
                db_system=db_system,
                db_name=keyspace,
                db_operation="connect",
                tags=tags,
            )
            metrics.record_db_query_count(
                db_system=db_system,
                db_name=keyspace,
                db_operation="connect",
                count=1,
                tags=tags,
            )
            span.set_status(StatusCode.OK)
            logger.info(
                f"Cassandra connection OK: {connection_time_ms:.2f}ms",
                extra={"connection_time_ms": connection_time_ms},
            )
            flush()
            return dict(
                success=True,
                connection_time_ms=connection_time_ms,
                database=keyspace,
                host=host,
            )
    except Exception as e:
        metrics.record_db_error(
            db_system=db_system, error_type=type(e).__name__, db_name=keyspace
        )
        span.set_status(StatusCode.ERROR, str(e))
        logger.error(f"Cassandra connection failed: {e}", extra={"error": str(e)})
        flush()
        raise
