"""PostgreSQL load generation actions."""
import os
import psycopg2
import time
import threading
import logging
from typing import Optional
from chaosotel import ensure_initialized, get_tracer, flush, get_metrics_core
from opentelemetry.sdk._logs import LoggingHandler
from opentelemetry._logs import get_logger_provider
from opentelemetry.trace import StatusCode

logger = logging.getLogger("chaosdb.postgres.load")

def force_sequential_scans(
    host: Optional[str] = None,
    port: Optional[int] = None,
    database: Optional[str] = None,
    user: Optional[str] = None,
    password: Optional[str] = None,
    table_name: str = "mobile_purchases",
    duration_seconds: int = 30,
    num_threads: int = 5
) -> bool:
    """
    Force sequential scans by running unindexed queries.
    """
    # Handle string input
    if port is not None:
        port = int(port) if isinstance(port, str) else port
    if isinstance(duration_seconds, str):
        duration_seconds = int(duration_seconds)
    if isinstance(num_threads, str):
        num_threads = int(num_threads)
        
    host = host or os.getenv("POSTGRES_HOST", "postgres")
    port = port or int(os.getenv("POSTGRES_PORT", "5432"))
    database = database or os.getenv("POSTGRES_DB", "testdb")
    user = user or os.getenv("POSTGRES_USER", "postgres")
    password = password or os.getenv("POSTGRES_PASSWORD", "postgres")
    
    ensure_initialized()
    tracer = get_tracer()
    
    stop_event = threading.Event()
    
    def run_scans():
        logger = logging.getLogger("chaosdb.postgres.run_scans")
        try:
            conn = psycopg2.connect(
                host=host, port=port, database=database,
                user=user, password=password, connect_timeout=5
            )
            # Disable index scans for this session to force seq scans
            cursor = conn.cursor()
            cursor.execute("SET enable_indexscan = off;")
            cursor.execute("SET enable_bitmapscan = off;")
            
            while not stop_event.is_set():
                # Run a query that forces a full table scan
                # Using a function call or unindexed column in WHERE clause
                cursor.execute(f"SELECT count(*) FROM {table_name} WHERE created_at::text LIKE '%202%';")
                conn.commit()
                
                # Record sequential scan metric
                metrics = get_metrics_core()

                # Setup OpenTelemetry logger via LoggingHandler
                logger_provider = get_logger_provider()
                if logger_provider:
                    handler = LoggingHandler(level=logging.INFO, logger_provider=logger_provider)
                    logger = logging.getLogger("chaosdb.postgres.run_scans")
                    logger.addHandler(handler)
                    logger.setLevel(logging.INFO)
                else:
                    logger = logging.getLogger("chaosdb.postgres.run_scans")
                db_system = os.getenv("DB_SYSTEM", "postgresql")
                metrics.record_db_counter("seq_scans", db_system=db_system, db_name=database, count=1)
                    
            cursor.close()
            conn.close()
        except Exception as e:
            logger.error("Scan thread failed: %s", e)

    threads = []
    try:
        with tracer.start_as_current_span("action.postgres.force_sequential_scans") as span:
            span.set_attribute("db.system", "postgresql")
            span.set_attribute("chaos.duration", duration_seconds)
            
            logger.info(f"Starting sequential scans on {table_name} for {duration_seconds}s with {num_threads} threads")
            
            for _ in range(num_threads):
                t = threading.Thread(target=run_scans)
                t.daemon = True
                t.start()
                threads.append(t)
                
            time.sleep(duration_seconds)
            stop_event.set()
            
            for t in threads:
                t.join(timeout=5)
                
            span.set_status(StatusCode.OK)
            return True
            
    except Exception as e:
        stop_event.set()
        logger.error("Force sequential scans failed: %s", e)
        flush()
        raise

def generate_dead_tuples(
    host: Optional[str] = None,
    port: Optional[int] = None,
    database: Optional[str] = None,
    user: Optional[str] = None,
    password: Optional[str] = None,
    table_name: str = "mobile_purchases",
    count: int = 1000
) -> bool:
    """
    Generate dead tuples by updating rows repeatedly.
    """
    if port is not None:
        port = int(port) if isinstance(port, str) else port
    if isinstance(count, str):
        count = int(count)
        
    host = host or os.getenv("POSTGRES_HOST", "postgres")
    port = port or int(os.getenv("POSTGRES_PORT", "5432"))
    database = database or os.getenv("POSTGRES_DB", "testdb")
    user = user or os.getenv("POSTGRES_USER", "postgres")
    password = password or os.getenv("POSTGRES_PASSWORD", "postgres")
    
    ensure_initialized()
    tracer = get_tracer()
    
    try:
        with tracer.start_as_current_span("action.postgres.generate_dead_tuples") as span:
            span.set_attribute("db.system", "postgresql")
            span.set_attribute("chaos.count", count)
            
            conn = psycopg2.connect(
                host=host, port=port, database=database,
                user=user, password=password, connect_timeout=5
            )
            conn.autocommit = True
            cursor = conn.cursor()
            
            # Disable autovacuum for this table temporarily to ensure dead tuples accumulate
            # Note: This requires superuser or owner privileges
            try:
                cursor.execute(f"ALTER TABLE {table_name} SET (autovacuum_enabled = false);")
            except Exception as e:
                logger.warning(f"Could not disable autovacuum: {e}")

            logger.info(f"Generating {count} dead tuples on {table_name}")
            
            # Update rows in a loop. Each update creates a dead tuple.
            # We'll update a dummy column or the same column to same value
            for i in range(count):
                # Update a random row or set of rows
                # Using a condition that matches some rows
                cursor.execute(f"UPDATE {table_name} SET amount = amount + 0.01 WHERE id = (SELECT id FROM {table_name} LIMIT 1 OFFSET {i % 100});")
                
            # Re-enable autovacuum
            try:
                cursor.execute(f"ALTER TABLE {table_name} SET (autovacuum_enabled = true);")
            except Exception as e:
                logger.warning(f"Could not re-enable autovacuum: {e}")
                
            cursor.close()
            conn.close()
            
            span.set_status(StatusCode.OK)
            return True
            
    except Exception as e:
        logger.error("Generate dead tuples failed: %s", e)
        flush()
        raise

def complex_sort_query(
    host: Optional[str] = None,
    port: Optional[int] = None,
    database: Optional[str] = None,
    user: Optional[str] = None,
    password: Optional[str] = None,
    table_name: str = "mobile_purchases",
    duration_seconds: int = 30
) -> bool:
    """
    Run complex sort queries to trigger temp file usage.
    """
    if port is not None:
        port = int(port) if isinstance(port, str) else port
    if isinstance(duration_seconds, str):
        duration_seconds = int(duration_seconds)
        
    host = host or os.getenv("POSTGRES_HOST", "postgres")
    port = port or int(os.getenv("POSTGRES_PORT", "5432"))
    database = database or os.getenv("POSTGRES_DB", "testdb")
    user = user or os.getenv("POSTGRES_USER", "postgres")
    password = password or os.getenv("POSTGRES_PASSWORD", "postgres")
    
    ensure_initialized()
    tracer = get_tracer()
    db_system = os.getenv("DB_SYSTEM", "postgresql")
    
    stop_event = threading.Event()
    
    def run_sorts():
        try:
            conn = psycopg2.connect(
                host=host, port=port, database=database,
                user=user, password=password, connect_timeout=5
            )
            cursor = conn.cursor()
            
            # Set low work_mem to force spill to disk
            cursor.execute("SET work_mem = '64kB';")
            
            while not stop_event.is_set():
                # Sort by random to force full sort
                cursor.execute(f"SELECT * FROM {table_name} ORDER BY random();")
                cursor.fetchall()
                
                metrics = get_metrics_core()

                # Setup OpenTelemetry logger via LoggingHandler
                logger_provider = get_logger_provider()
                if logger_provider:
                    handler = LoggingHandler(level=logging.INFO, logger_provider=logger_provider)
                    logger = logging.getLogger("chaosdb.postgres.run_sorts")
                    logger.addHandler(handler)
                    logger.setLevel(logging.INFO)
                else:
                    logger = logging.getLogger("chaosdb.postgres.run_sorts")
                metrics.record_db_gauge("temp_files", 1, db_system=db_system, db_name=database)
                    
            cursor.close()
            conn.close()
        except Exception as e:
            logger.error("Sort thread failed: %s", e)

    try:
        with tracer.start_as_current_span("action.postgres.complex_sort_query") as span:
            span.set_attribute("db.system", "postgresql")
            
            logger.info(f"Starting complex sort queries on {table_name} for {duration_seconds}s")
            
            # Run multiple threads to increase pressure
            threads = []
            for _ in range(3):
                t = threading.Thread(target=run_sorts)
                t.daemon = True
                t.start()
                threads.append(t)
                
            time.sleep(duration_seconds)
            stop_event.set()
            
            for t in threads:
                t.join(timeout=5)
                
            span.set_status(StatusCode.OK)
            return True
            
    except Exception as e:
        stop_event.set()
        logger.error("Complex sort query failed: %s", e)
        flush()
        raise
