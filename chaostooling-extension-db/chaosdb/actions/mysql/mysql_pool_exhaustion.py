"""MySQL connection pool exhaustion chaos action."""

import logging
import os
import threading
import time
from typing import Optional

import mysql.connector
from chaosotel import ensure_initialized, flush, get_metrics_core, get_tracer
from opentelemetry.trace import StatusCode

_active_connections = []
_stop_event = threading.Event()


def inject_connection_pool_exhaustion(
    host: Optional[str] = None,
    port: Optional[int] = None,
    database: Optional[str] = None,
    user: Optional[str] = None,
    password: Optional[str] = None,
    num_connections: int = 100,
    duration_seconds: int = 60,
    leak_connections: bool = False,
) -> dict:
    """
    Exhaust the connection pool by creating many connections and holding them.

    Args:
        host: MySQL host
        port: MySQL port
        database: Database name
        user: Database user
        password: Database password
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

    host = host or os.getenv("MYSQL_HOST", "localhost")
    port = port or int(os.getenv("MYSQL_PORT", "3306"))
    database = database or os.getenv("MYSQL_DB", "testdb")
    user = user or os.getenv("MYSQL_USER", "root")
    password = password or os.getenv("MYSQL_PASSWORD", "")

    ensure_initialized()
    db_system = os.getenv("DB_SYSTEM", "mysql")
    tracer = get_tracer()
    logger = logging.getLogger("chaosdb.mysql.pool_exhaustion")
    start_time = time.time()

    global _active_connections, _stop_event
    _stop_event.clear()
    _active_connections = []

    connections_created = 0
    connections_failed = 0
    errors = 0

    def create_and_hold_connection(conn_id: int):
        """Create a connection and hold it."""
        nonlocal connections_created, connections_failed, errors
        conn = None
        try:
            with tracer.start_as_current_span(
                f"pool_exhaustion.connection.{conn_id}"
            ) as span:
                from chaosotel.core.trace_core import set_db_span_attributes
                set_db_span_attributes(
                    span,
                    db_system=db_system,
                    db_name=database,
                    host=host,
                    port=port,
                    chaos_activity="mysql_connection_pool_exhaustion",
                    chaos_action="connection_pool_exhaustion",
                    chaos_operation="connection_pool_exhaustion",
                    chaos_connection_id=conn_id
                )

                acquisition_start = time.time()

                try:
                    conn = mysql.connector.connect(
                        host=host,
                        port=port,
                        database=database,
                        user=user,
                        password=password,
                        connect_timeout=10,
                    )

                    acquisition_time_ms = (time.time() - acquisition_start) * 1000
                    connections_created += 1

                    metrics = get_metrics_core()
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
                    
                    # Record connection pool utilization (assuming default max_connections=151 for MySQL)
                    max_connections = 151  # Default MySQL max_connections
                    current_connections = len(_active_connections) + 1
                    utilization_percent = min(100.0, (current_connections / max_connections) * 100.0)
                    metrics.record_db_connection_pool_utilization(
                        db_system=db_system,
                        utilization_percent=utilization_percent,
                        db_name=database,
                    )

                    _active_connections.append(conn)

                    # Hold the connection
                    end_time = time.time() + duration_seconds
                    while not _stop_event.is_set() and time.time() < end_time:
                        try:
                            cursor = conn.cursor()
                            cursor.execute("SELECT 1")
                            cursor.fetchone()
                            cursor.close()
                            time.sleep(1)
                        except Exception as e:
                            logger.warning(
                                f"Connection {conn_id} error during hold: {e}"
                            )
                            break

                    span.set_status(StatusCode.OK)

                except mysql.connector.errors.DatabaseError as e:
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
                        error_type="DatabaseError",
                        db_name=database,
                    )

                    logger.warning(f"Failed to create connection {conn_id}: {e}")
                    span.set_status(StatusCode.ERROR, str(e))

        except Exception as e:
            errors += 1
            logger.error(f"Connection {conn_id} failed: {e}")
        finally:
            if conn and not leak_connections:
                try:
                    metrics = get_metrics_core()
                    # Note: Gauges can't be decremented directly, we'd need a different approach
                    # For now, we'll track this via a separate metric or use a different method
                    conn.close()
                except:
                    pass
            elif conn and leak_connections:
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
            "chaos.mysql.connection_pool_exhaustion"
        ) as span:
            from chaosotel.core.trace_core import set_db_span_attributes
            set_db_span_attributes(
                span,
                db_system=db_system,
                db_name=database,
                host=host,
                port=port,
                chaos_activity="mysql_connection_pool_exhaustion",
                chaos_action="connection_pool_exhaustion",
                chaos_operation="connection_pool_exhaustion",
                chaos_num_connections=num_connections,
                chaos_duration_seconds=duration_seconds,
                chaos_leak_connections=leak_connections
            )
            span.set_attribute("chaos.system", "mysql")
            span.set_attribute("chaos.operation", "connection_pool_exhaustion")

            logger.info(
                f"Starting connection pool exhaustion with {num_connections} connections"
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
                for conn in _active_connections:
                    try:
                        conn.close()
                    except:
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

            logger.info(f"Connection pool exhaustion completed: {result}")
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
        logger.error(f"Connection pool exhaustion failed: {e}")
        flush()
        raise


def stop_pool_exhaustion():
    """Stop any running pool exhaustion and close connections."""
    global _stop_event, _active_connections
    _stop_event.set()
    for conn in _active_connections:
        try:
            conn.close()
        except:
            pass
    _active_connections = []
