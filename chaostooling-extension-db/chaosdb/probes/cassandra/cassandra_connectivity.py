"""Cassandra connectivity probe."""

import logging
import os
import time
from contextlib import nullcontext
from typing import Optional

from cassandra.cluster import Cluster
from chaosotel import flush, get_metric_tags, get_metrics_core, get_tracer
from opentelemetry._logs import get_logger_provider
from opentelemetry.sdk._logs import LoggingHandler
from opentelemetry.trace import StatusCode


def probe_cassandra_connectivity(
    host: Optional[str] = None,
    port: Optional[int] = None,
    keyspace: Optional[str] = None,
    user: Optional[str] = None,
    password: Optional[str] = None,
) -> bool:
    """

    Probe Cassandra connectivity.

    Observability: Uses chaosotel (chaostooling-otel) as the central observability location. chaosotel must be initialized via chaosotel.control in the experiment configuration.

    """

    host = host or os.getenv("CASSANDRA_HOST", "localhost")

    port = port or int(os.getenv("CASSANDRA_PORT", "9042"))

    keyspace = keyspace or os.getenv("CASSANDRA_KEYSPACE", "system")

    user = user or os.getenv("CASSANDRA_USER")

    password = password or os.getenv("CASSANDRA_PASSWORD")

    # chaosotel is initialized via chaosotel.control - use directly

    tracer = get_tracer()

    # Setup OpenTelemetry logger via LoggingHandler

    logger_provider = get_logger_provider()

    if logger_provider:
        handler = LoggingHandler(level=logging.INFO, logger_provider=logger_provider)

        logger = logging.getLogger("chaosdb.cassandra.cassandra_connectivity")

        logger.addHandler(handler)

        logger.setLevel(logging.INFO)

    else:
        logger = logging.getLogger("chaosdb.cassandra.cassandra_connectivity")

    metrics = get_metrics_core()

    db_system = "cassandra"

    database = keyspace

    start = time.time()

    span_context = (
        tracer.start_as_current_span("probe.cassandra.connectivity")
        if tracer
        else nullcontext()
    )

    with span_context as span:
        try:
            if span:
                # Use span helper for consistent attribute setting and resource updates
                # This matches Redis pattern - clean, simple, no duplicate attributes
                from chaosotel.core.trace_core import set_db_span_attributes

                set_db_span_attributes(
                    span,
                    db_system=db_system,
                    db_name=database,
                    host=host,
                    port=port,
                    db_operation="probe",
                    chaos_activity="cassandra_connectivity_probe",
                    chaos_action="connectivity_probe",
                    chaos_operation="probe",
                )

            # Retry logic for detached runs and slow startup (similar to MySQL)
            # Increased retries and delays for Cassandra which can be slow to start
            max_retries = 5
            retry_delay = 5  # seconds - increased for Cassandra startup time
            cluster = None
            session = None

            for attempt in range(max_retries):
                try:
                    # Increased connect_timeout for Cassandra which can be slow
                    # Use protocol version 4 for Cassandra 4.x compatibility
                    cluster = Cluster(
                        [host],
                        port=port,
                        connect_timeout=90,  # Increased to 90 seconds for slow startup
                        control_connection_timeout=90,
                        protocol_version=4,  # Use protocol version 4 for Cassandra 4.x
                        # Add connection pooling settings for better reliability
                        max_connections_per_host=2,
                        # Disable metadata refresh on connect to speed up initial connection
                        metadata_refresh_on_connect=False,
                    )
                    # Connect to cluster first, then to keyspace
                    # If keyspace doesn't exist, try connecting without it and use system keyspace
                    try:
                        session = cluster.connect(keyspace)
                    except Exception as keyspace_error:
                        # If keyspace doesn't exist, try system keyspace as fallback
                        logger.warning(
                            f"Could not connect to keyspace '{keyspace}': {keyspace_error}. Trying system keyspace..."
                        )
                        try:
                            session = cluster.connect("system")
                        except Exception as system_error:
                            logger.warning(
                                f"Could not connect to system keyspace either: {system_error}. Trying without keyspace..."
                            )
                            # Last resort: connect without specifying keyspace
                            session = cluster.connect()

                    # Execute a simple query to verify connectivity with timeout
                    # Use a simple query that works in any keyspace
                    # Increase query timeout for slow systems
                    result = session.execute(
                        "SELECT release_version FROM system.local", timeout=60
                    )
                    result.one()  # Fetch the result to ensure query completed
                    # Success, exit retry loop
                    break
                except Exception as e:
                    # Clean up on error
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
                    session = None
                    cluster = None

                    if attempt < max_retries - 1:
                        logger.warning(
                            f"Cassandra connection attempt {attempt + 1}/{max_retries} failed: {e}. Retrying in {retry_delay}s..."
                        )
                        time.sleep(retry_delay)
                    else:
                        # Final attempt failed, log the error and raise
                        logger.error(
                            f"All {max_retries} Cassandra connection attempts failed. Last error: {e}"
                        )
                        raise

            # Clean up after successful connection
            if session:
                session.shutdown()
            if cluster:
                cluster.shutdown()

            probe_time_ms = (time.time() - start) * 1000

            tags = get_metric_tags(
                db_name=database,
                db_system=db_system,
                db_operation="probe",
            )

            metrics.record_db_query_latency(
                probe_time_ms,
                db_system=db_system,
                db_name=database,
                db_operation="probe",
                tags=tags,
            )

            metrics.record_db_query_count(
                db_system=db_system,
                db_name=database,
                count=1,
                db_operation="probe",
                tags=tags,
            )

            if span:
                span.set_status(StatusCode.OK)

            logger.info(
                f"Cassandra probe OK: {probe_time_ms:.2f}ms",
                extra={"probe_time_ms": probe_time_ms},
            )

            flush()

            return True

        except Exception as e:
            metrics.record_db_error(
                db_system=db_system,
                error_type=type(e).__name__,
                db_name=database,
            )

            if span:
                span.record_exception(e)
                span.set_status(StatusCode.ERROR, str(e))

            logger.error(f"Cassandra probe failed: {str(e)}", extra={"error": str(e)})

            flush()

            return False
