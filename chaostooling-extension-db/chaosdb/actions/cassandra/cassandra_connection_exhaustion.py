"""Cassandra connection exhaustion chaos action."""

import os
import threading
import time
from typing import Optional

from cassandra.cluster import Cluster
from chaosotel import (
    ensure_initialized,
    flush,
    get_logger,
    get_metrics_core,
    get_tracer,
)
from opentelemetry.trace import StatusCode

_active_connections = []
_stop_event = threading.Event()


def inject_connection_exhaustion(
    host: Optional[str] = None,
    port: Optional[int] = None,
    keyspace: Optional[str] = None,
    user: Optional[str] = None,
    password: Optional[str] = None,
    num_connections: int = 100,
    hold_duration_seconds: int = 60,
    leak_connections: bool = False,
) -> dict:
    """Exhaust Cassandra connection pool."""
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
    start_time = time.time()

    global _active_connections, _stop_event
    _stop_event.clear()
    _active_connections = []

    connections_created = 0
    connections_failed = 0
    errors = 0

    def create_and_hold_connection(conn_id: int):
        nonlocal connections_created, connections_failed, errors
        cluster = None
        session = None
        try:
            with tracer.start_as_current_span(
                f"connection_exhaustion.connection.{conn_id}"
            ) as span:
                from chaosotel.core.trace_core import set_db_span_attributes

                set_db_span_attributes(
                    span,
                    db_system="cassandra",
                    db_name=keyspace,
                    host=host,
                    port=port,
                    chaos_activity="cassandra_connection_exhaustion",
                    chaos_action="connection_exhaustion",
                    chaos_operation="connection_exhaustion",
                    chaos_connection_id=conn_id,
                )

                try:
                    cluster = Cluster([host], port=port)
                    session = cluster.connect(keyspace)
                    session.execute("SELECT release_version FROM system.local")

                    connections_created += 1

                    _active_connections.append((cluster, session))

                    end_time = time.time() + hold_duration_seconds
                    while not _stop_event.is_set() and time.time() < end_time:
                        try:
                            session.execute("SELECT release_version FROM system.local")
                            time.sleep(1)
                        except Exception as e:
                            logger.warning(
                                f"Connection {conn_id} error during hold: {e}"
                            )
                            break

                    span.set_status(StatusCode.OK)
                except Exception as e:
                    connections_failed += 1
                    metrics.record_db_error(
                        db_system=db_system, error_type=type(e).__name__
                    )
                    logger.warning(f"Failed to create connection {conn_id}: {e}")
                    span.set_status(StatusCode.ERROR, str(e))
        except Exception as e:
            errors += 1
            logger.error(f"Connection {conn_id} failed: {e}")
        finally:
            if not leak_connections:
                if session:
                    try:
                        session.shutdown()
                    except Exception:
                        pass
                if cluster:
                    try:
                        cluster.shutdown()
                    except Exception:
                        pass
            elif (cluster, session) and leak_connections:
                logger.warning(f"Leaking connection {conn_id} (intentional)")

    try:
        with tracer.start_as_current_span(
            "chaos.cassandra.connection_exhaustion"
        ) as span:
            span.set_attribute("db.system", "cassandra")
            span.set_attribute("db.name", keyspace)
            span.set_attribute("chaos.num_connections", num_connections)
            span.set_attribute("chaos.hold_duration_seconds", hold_duration_seconds)
            span.set_attribute("chaos.leak_connections", leak_connections)
            span.set_attribute("chaos.action", "connection_exhaustion")
            span.set_attribute("chaos.activity", "cassandra_connection_exhaustion")
            span.set_attribute("chaos.activity.type", "action")
            span.set_attribute("chaos.system", "cassandra")
            span.set_attribute("chaos.operation", "connection_exhaustion")

            logger.info(
                f"Starting Cassandra connection exhaustion with {num_connections} connections"
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
                for cluster, session in _active_connections:
                    try:
                        session.shutdown()
                        cluster.shutdown()
                    except Exception:
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

            logger.info(f"Cassandra connection exhaustion completed: {result}")
            flush()
            return result
    except Exception as e:
        _stop_event.set()
        metrics.record_db_error(db_system=db_system, error_type=type(e).__name__)
        logger.error(f"Cassandra connection exhaustion failed: {e}")
        flush()
        raise


def stop_connection_exhaustion():
    global _stop_event, _active_connections
    _stop_event.set()
    for cluster, session in _active_connections:
        try:
            session.shutdown()
            cluster.shutdown()
        except Exception:
            pass
    _active_connections = []
