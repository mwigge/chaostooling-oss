"""MSSQL connection pool exhaustion chaos action."""
import os
import threading
import time
from typing import Dict, Optional

import pyodbc
from chaosotel import (ensure_initialized, flush, get_logger, get_metrics_core,
                       get_tracer)
from opentelemetry.trace import StatusCode

_active_connections = []
_stop_event = threading.Event()

def inject_connection_pool_exhaustion(
    host: Optional[str] = None,
    port: Optional[int] = None,
    database: Optional[str] = None,
    user: Optional[str] = None,
    password: Optional[str] = None,
    driver: Optional[str] = None,
    num_connections: int = 100,
    hold_duration_seconds: int = 60,
    leak_connections: bool = False
) -> Dict:
    """Exhaust MSSQL connection pool."""
    host = host or os.getenv("MSSQL_HOST", "localhost")
    port = port or int(os.getenv("MSSQL_PORT", "1433"))
    database = database or os.getenv("MSSQL_DB", "master")
    user = user or os.getenv("MSSQL_USER", "sa")
    password = password or os.getenv("MSSQL_PASSWORD", "")
    driver = driver or os.getenv("MSSQL_DRIVER", "FreeTDS")
    
    ensure_initialized()
    metrics = get_metrics_core()
    tracer = get_tracer()
    logger = get_logger()
    start_time = time.time()
    
    global _active_connections, _stop_event
    _stop_event.clear()
    _active_connections = []
    
    connection_string = f"DRIVER={{{driver}}};SERVER={host},{port};DATABASE={database};UID={user};PWD={password};Encrypt=no"
    
    connections_created = 0
    connections_failed = 0
    errors = 0
    
    def create_and_hold_connection(conn_id: int):
        nonlocal connections_created, connections_failed, errors
        conn = None
        try:
            with tracer.start_as_current_span(f"pool_exhaustion.connection.{conn_id}") as span:
                span.set_attribute("db.system", "mssql")
                span.set_attribute("db.name", database)
                span.set_attribute("chaos.connection_id", conn_id)
                span.set_attribute("chaos.action", "connection_pool_exhaustion")
                span.set_attribute("chaos.activity", "mssql_connection_pool_exhaustion")
                span.set_attribute("chaos.activity.type", "action")
                span.set_attribute("chaos.system", "mssql")
                span.set_attribute("chaos.operation", "connection_pool_exhaustion")

                acquisition_start = time.time()
                try:
                    conn = pyodbc.connect(connection_string, timeout=10)

                    acquisition_time_ms = (time.time() - acquisition_start) * 1000
                    connections_created += 1

                    _active_connections.append(conn)
                    
                    end_time = time.time() + hold_duration_seconds
                    while not _stop_event.is_set() and time.time() < end_time:
                        try:
                            cursor = conn.cursor()
                            cursor.execute("SELECT 1")
                            cursor.fetchone()
                            cursor.close()
                            time.sleep(1)
                        except Exception as e:
                            logger.warning(f"Connection {conn_id} error during hold: {e}")
                            break
                    
                    span.set_status(StatusCode.OK)
                except pyodbc.Error as e:
                    connections_failed += 1
                    wait_time_ms = (time.time() - acquisition_start) * 1000

                    metrics.record_db_error(db_system=db_system, error_type=type(e).__name__)
                    logger.warning(f"Failed to create connection {conn_id}: {e}")
                    span.set_status(StatusCode.ERROR, str(e))
        except Exception as e:
            errors += 1
            logger.error(f"Connection {conn_id} failed: {e}")
        finally:
            if conn and not leak_connections:
                try:
                    conn.close()
                except:
                    pass
            elif conn and leak_connections:
                logger.warning(f"Leaking connection {conn_id} (intentional)")
    
    try:
        with tracer.start_as_current_span("chaos.mssql.connection_pool_exhaustion") as span:
            span.set_attribute("db.system", "mssql")
            span.set_attribute("db.name", database)
            span.set_attribute("chaos.num_connections", num_connections)
            span.set_attribute("chaos.hold_duration_seconds", hold_duration_seconds)
            span.set_attribute("chaos.leak_connections", leak_connections)
            span.set_attribute("chaos.action", "connection_pool_exhaustion")
            span.set_attribute("chaos.activity", "mssql_connection_pool_exhaustion")
            span.set_attribute("chaos.activity.type", "action")
            span.set_attribute("chaos.system", "mssql")
            span.set_attribute("chaos.operation", "connection_pool_exhaustion")
            
            logger.info(f"Starting MSSQL connection pool exhaustion with {num_connections} connections")
            
            threads = []
            for i in range(num_connections):
                thread = threading.Thread(target=create_and_hold_connection, args=(i,), daemon=True)
                thread.start()
                threads.append(thread)
                time.sleep(0.1)
            
            time.sleep(hold_duration_seconds)
            _stop_event.set()
            for thread in threads:
                thread.join(timeout=5)
            
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
                "connections_leaked": len(_active_connections) if leak_connections else 0,
                "errors": errors,
                "target_connections": num_connections
            }
            
            span.set_attribute("chaos.connections_created", connections_created)
            span.set_attribute("chaos.connections_failed", connections_failed)
            span.set_status(StatusCode.OK)
            
            logger.info(f"MSSQL connection pool exhaustion completed: {result}")
            flush()
            return result
    except Exception as e:
        _stop_event.set()
        metrics.record_db_error(db_system=db_system, error_type=type(e).__name__)
        logger.error(f"MSSQL connection pool exhaustion failed: {e}")
        flush()
        raise

def stop_pool_exhaustion():
    global _stop_event, _active_connections
    _stop_event.set()
    for conn in _active_connections:
        try:
            conn.close()
        except:
            pass
    _active_connections = []

