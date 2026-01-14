"""MongoDB connection exhaustion chaos action."""

import logging
import os
import threading
import time
from typing import Optional

from chaosotel import ensure_initialized, flush, get_metrics_core, get_tracer
from opentelemetry.trace import StatusCode
from pymongo import MongoClient

_active_connections = []
_stop_event = threading.Event()


def inject_connection_exhaustion(
    host: Optional[str] = None,
    port: Optional[int] = None,
    database: Optional[str] = None,
    user: Optional[str] = None,
    password: Optional[str] = None,
    authSource: Optional[str] = None,
    num_connections: int = 100,
    duration_seconds: int = 60,
    leak_connections: bool = False,
) -> dict:
    """
    Exhaust the connection pool by creating many connections and holding them.

    Args:
        host: MongoDB host
        port: MongoDB port
        database: Database name
        user: Database user
        password: Database password
        authSource: Authentication source
        num_connections: Number of connections to create
        duration_seconds: How long to hold connections
        leak_connections: If True, don't close connections (leak them)

    Returns:
        Dict with results including connections created, errors, etc.
    """
    # Handle string input from Chaos Toolkit configuration
    if port is not None:
        port = int(port) if isinstance(port, str) else port
    num_connections = (
        int(num_connections) if isinstance(num_connections, str) else num_connections
    )
    duration_seconds = (
        int(duration_seconds) if isinstance(duration_seconds, str) else duration_seconds
    )

    host = host or os.getenv("MONGO_HOST", "localhost")
    port = port or int(os.getenv("MONGO_PORT", "27017"))
    database = database or os.getenv("MONGO_DB", "test")
    user = user or os.getenv("MONGO_USER")
    password = password or os.getenv("MONGO_PASSWORD")
    authSource = authSource or os.getenv("MONGO_AUTHSOURCE")

    ensure_initialized()
    db_system = os.getenv("DB_SYSTEM", "mongodb")
    tracer = get_tracer()
    logger = logging.getLogger("chaosdb.mongodb.connection_exhaustion")
    start_time = time.time()

    uri = f"mongodb://{host}:{port}/"
    if user and password:
        uri = f"mongodb://{user}:{password}@{host}:{port}/"
        if authSource:
            uri += f"?authSource={authSource}"

    global _active_connections, _stop_event
    _stop_event.clear()
    _active_connections = []

    connections_created = 0
    connections_failed = 0
    errors = 0

    def create_and_hold_connection(conn_id: int):
        """Create a connection and hold it."""
        nonlocal connections_created, connections_failed, errors
        client = None
        try:
            with tracer.start_as_current_span(
                f"connection_exhaustion.connection.{conn_id}"
            ) as span:
                from chaosotel.core.trace_core import set_db_span_attributes

                set_db_span_attributes(
                    span,
                    db_system=db_system,
                    db_name=database,
                    host=host,
                    port=port,
                    chaos_activity="mongodb_connection_exhaustion",
                    chaos_action="connection_exhaustion",
                    chaos_operation="connection_exhaustion",
                    chaos_connection_id=conn_id,
                )

                acquisition_start = time.time()

                try:
                    client = MongoClient(
                        uri, maxPoolSize=1, serverSelectionTimeoutMS=5000
                    )
                    connections_created += 1

                    metrics = get_metrics_core()
                    acquisition_time_ms = (time.time() - acquisition_start) * 1000
                    metrics.record_db_histogram(
                        "connection.acquisition_time",
                        acquisition_time_ms,
                        db_system=db_system,
                        db_name=database,
                        unit="ms",
                    )
                    metrics.record_db_counter(
                        "connection.pool.active",
                        db_system=db_system,
                        db_name=database,
                        count=1,
                    )

                    _active_connections.append(client)

                    # Hold the connection
                    db = client[database]
                    end_time = time.time() + duration_seconds
                    while not _stop_event.is_set() and time.time() < end_time:
                        try:
                            db.command("ping")
                            time.sleep(1)
                        except Exception as e:
                            logger.warning(
                                f"Connection {conn_id} error during hold: {e}"
                            )
                            break

                    span.set_status(StatusCode.OK)

                except Exception as e:
                    connections_failed += 1
                    wait_time_ms = (time.time() - acquisition_start) * 1000

                    metrics = get_metrics_core()
                    metrics.record_db_histogram(
                        "connection.wait_time",
                        wait_time_ms,
                        db_system=db_system,
                        db_name=database,
                        unit="ms",
                    )
                    metrics.record_db_error(
                        db_system=db_system,
                        error_type=type(e).__name__,
                        db_name=database,
                    )

                    logger.warning(f"Failed to create connection {conn_id}: {e}")
                    span.set_status(StatusCode.ERROR, str(e))

        except Exception as e:
            errors += 1
            logger.error(f"Connection {conn_id} failed: {e}")
        finally:
            if client and not leak_connections:
                try:
                    client.close()
                except Exception:
                    pass
            elif client and leak_connections:
                metrics = get_metrics_core()
                metrics.record_db_counter(
                    "connection.leak",
                    db_system=db_system,
                    db_name=database,
                    count=1,
                )
                logger.warning(f"Leaking connection {conn_id} (intentional)")

    try:
        with tracer.start_as_current_span(
            "chaos.mongodb.connection_exhaustion"
        ) as span:
            from chaosotel.core.trace_core import set_db_span_attributes

            set_db_span_attributes(
                span,
                db_system=db_system,
                db_name=database,
                host=host,
                port=port,
                chaos_activity="mongodb_connection_exhaustion",
                chaos_action="connection_exhaustion",
                chaos_operation="connection_exhaustion",
                chaos_num_connections=num_connections,
                chaos_duration_seconds=duration_seconds,
                chaos_leak_connections=leak_connections,
            )

            logger.info(
                f"Starting connection exhaustion with {num_connections} connections"
            )

            # Create connections in parallel
            threads = []
            for i in range(num_connections):
                thread = threading.Thread(
                    target=create_and_hold_connection, args=(i,), daemon=True
                )
                thread.start()
                threads.append(thread)
                time.sleep(0.1)  # Stagger connection attempts

            # Wait for duration
            time.sleep(duration_seconds)

            # Signal stop
            _stop_event.set()
            for thread in threads:
                thread.join(timeout=5)

            # Close connections if not leaking
            if not leak_connections:
                for client in _active_connections:
                    try:
                        client.close()
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

            logger.info(f"Connection exhaustion completed: {result}")
            flush()
            return result
    except Exception as e:
        _stop_event.set()
        metrics = get_metrics_core()
        metrics.record_db_error(
            db_system=db_system,
            error_type=type(e).__name__,
            db_name=database,
        )
        logger.error(f"Connection exhaustion failed: {e}")
        flush()
        raise


def stop_connection_exhaustion():
    """Stop any running connection exhaustion and close connections."""
    global _stop_event, _active_connections
    _stop_event.set()
    for client in _active_connections:
        try:
            client.close()
        except Exception:
            pass
    _active_connections = []
