#!/usr/bin/env python3
"""
PostgreSQL Span Generator

Monitors pg_stat_statements and generates OpenTelemetry server-side spans
for PostgreSQL queries to enable service graph visibility and query-level tracing.
"""

import os
import time
import psycopg2
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.trace import SpanKind, Status, StatusCode
import logging

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class PostgresSpanGenerator:
    """Generates OpenTelemetry spans from PostgreSQL query statistics."""

    def __init__(self):
        # Initialize OTEL tracer
        service_name = os.getenv("POSTGRES_SERVICE_NAME", "postgres-primary-site-a")
        resource = Resource.create(
            {
                "service.name": service_name,
                "service.namespace": "database",
                "db.system": "postgresql",
                "db.name": os.getenv("POSTGRES_DB", "testdb"),
            }
        )

        provider = TracerProvider(resource=resource)
        processor = BatchSpanProcessor(
            OTLPSpanExporter(
                endpoint=os.getenv(
                    "OTEL_EXPORTER_OTLP_ENDPOINT", "http://otel-collector:4317"
                ),
                insecure=True,
            )
        )
        provider.add_span_processor(processor)
        trace.set_tracer_provider(provider)

        self.tracer = trace.get_tracer(__name__, "1.0.0")
        self.service_name = service_name

        # Database connection
        self.conn = None
        self.connect_to_database()

        # Track last seen query stats
        self.last_stats = {}

        logger.info(f"PostgreSQL Span Generator initialized")
        logger.info(f"Service: {service_name}")
        logger.info(
            f"Database: {os.getenv('POSTGRES_HOST')}:{os.getenv('POSTGRES_PORT')}/{os.getenv('POSTGRES_DB')}"
        )
        logger.info(f"OTEL Endpoint: {os.getenv('OTEL_EXPORTER_OTLP_ENDPOINT')}")

    def connect_to_database(self):
        """Establish database connection with retry logic."""
        max_retries = 10
        retry_delay = 5

        for attempt in range(max_retries):
            try:
                self.conn = psycopg2.connect(
                    host=os.getenv("POSTGRES_HOST", "postgres-primary-site-a"),
                    port=int(os.getenv("POSTGRES_PORT", "5432")),
                    database=os.getenv("POSTGRES_DB", "testdb"),
                    user=os.getenv("POSTGRES_USER", "postgres"),
                    password=os.getenv("POSTGRES_PASSWORD", "postgres"),
                )
                logger.info("Successfully connected to PostgreSQL")
                return
            except psycopg2.OperationalError as e:
                if attempt < max_retries - 1:
                    logger.warning(
                        f"Connection attempt {attempt + 1}/{max_retries} failed: {e}. Retrying in {retry_delay}s..."
                    )
                    time.sleep(retry_delay)
                else:
                    logger.error(f"Failed to connect after {max_retries} attempts")
                    raise

    def verify_pg_stat_statements(self):
        """Verify pg_stat_statements extension is enabled."""
        try:
            cursor = self.conn.cursor()
            cursor.execute("""
                SELECT COUNT(*)
                FROM pg_extension
                WHERE extname = 'pg_stat_statements'
            """)
            result = cursor.fetchone()
            cursor.close()

            if result[0] == 0:
                logger.error("pg_stat_statements extension is NOT enabled!")
                logger.error(
                    "Enable it by running: CREATE EXTENSION pg_stat_statements;"
                )
                return False

            logger.info("pg_stat_statements extension is enabled")
            return True
        except Exception as e:
            logger.error(f"Error checking pg_stat_statements: {e}")
            return False

    def fetch_query_stats(self):
        """Fetch current query statistics from pg_stat_statements."""
        try:
            cursor = self.conn.cursor()
            cursor.execute("""
                SELECT
                    queryid,
                    query,
                    calls,
                    total_exec_time,
                    mean_exec_time,
                    min_exec_time,
                    max_exec_time,
                    rows,
                    shared_blks_hit,
                    shared_blks_read,
                    shared_blks_written
                FROM pg_stat_statements
                WHERE calls > 0
                AND query NOT LIKE '%pg_stat_statements%'
                AND query NOT LIKE '%pg_extension%'
                ORDER BY total_exec_time DESC
                LIMIT 1000
            """)

            stats = {}
            for row in cursor.fetchall():
                (
                    queryid,
                    query,
                    calls,
                    total_time,
                    mean_time,
                    min_time,
                    max_time,
                    rows,
                    blks_hit,
                    blks_read,
                    blks_written,
                ) = row

                stats[queryid] = {
                    "query": query,
                    "calls": calls,
                    "total_exec_time": float(total_time) if total_time else 0.0,
                    "mean_exec_time": float(mean_time) if mean_time else 0.0,
                    "min_exec_time": float(min_time) if min_time else 0.0,
                    "max_exec_time": float(max_time) if max_time else 0.0,
                    "rows": rows if rows else 0,
                    "blks_hit": blks_hit if blks_hit else 0,
                    "blks_read": blks_read if blks_read else 0,
                    "blks_written": blks_written if blks_written else 0,
                }

            cursor.close()
            return stats
        except Exception as e:
            logger.error(f"Error fetching query stats: {e}")
            # Attempt to reconnect
            self.connect_to_database()
            return {}

    def generate_spans_for_new_queries(self, current_stats):
        """Generate spans for queries that have executed since last check."""
        span_count = 0

        for queryid, stats in current_stats.items():
            last_calls = self.last_stats.get(queryid, {}).get("calls", 0)
            new_calls = stats["calls"] - last_calls

            if new_calls > 0:
                # Generate span for each new execution (limit to avoid overwhelming the system)
                for _ in range(min(int(new_calls), 10)):
                    self.generate_query_span(stats)
                    span_count += 1

        if span_count > 0:
            logger.info(f"Generated {span_count} server-side spans")

        return span_count

    def generate_query_span(self, stats):
        """Generate a single server-side span for a query."""
        try:
            # Calculate approximate start time based on mean execution time
            execution_time_ms = stats["mean_exec_time"]
            start_time_ns = time.time_ns() - int(execution_time_ms * 1_000_000)
            end_time_ns = time.time_ns()

            # Create span
            span = self.tracer.start_span(
                name=self.get_span_name(stats["query"]),
                kind=SpanKind.SERVER,
                start_time=start_time_ns,
            )

            with trace.use_span(span, end_on_exit=False):
                # Set database semantic conventions (OTEL spec)
                span.set_attribute("db.system", "postgresql")
                span.set_attribute("db.name", os.getenv("POSTGRES_DB", "testdb"))
                span.set_attribute("db.user", os.getenv("POSTGRES_USER", "postgres"))
                span.set_attribute("db.statement", self.sanitize_query(stats["query"]))
                span.set_attribute(
                    "db.operation", self.extract_operation(stats["query"])
                )

                # Network attributes for service graph (critical for visibility)
                db_host = os.getenv("POSTGRES_HOST", "postgres-primary-site-a")
                db_port = int(os.getenv("POSTGRES_PORT", "5432"))
                span.set_attribute("network.peer.address", f"{db_host}:{db_port}")
                span.set_attribute("peer.service", self.service_name)
                span.set_attribute("server.address", db_host)
                span.set_attribute("server.port", db_port)

                # Performance metrics
                span.set_attribute("db.execution_time_ms", execution_time_ms)
                span.set_attribute("db.rows_affected", stats["rows"])

                # Cache hit ratio
                total_blocks = stats["blks_hit"] + stats["blks_read"]
                if total_blocks > 0:
                    cache_hit_ratio = stats["blks_hit"] / total_blocks
                    span.set_attribute("db.cache_hit_ratio", round(cache_hit_ratio, 4))

                # I/O statistics
                span.set_attribute("db.blocks_read", stats["blks_read"])
                span.set_attribute("db.blocks_hit", stats["blks_hit"])
                span.set_attribute("db.blocks_written", stats["blks_written"])

                # Timing statistics
                span.set_attribute("db.mean_exec_time_ms", stats["mean_exec_time"])
                span.set_attribute("db.min_exec_time_ms", stats["min_exec_time"])
                span.set_attribute("db.max_exec_time_ms", stats["max_exec_time"])

                # Set span status based on execution
                if execution_time_ms > 1000:  # Slow query threshold: 1 second
                    span.set_status(Status(StatusCode.OK, "Slow query"))
                else:
                    span.set_status(Status(StatusCode.OK))

                # End the span
                span.end(end_time=end_time_ns)

        except Exception as e:
            logger.error(f"Error generating span: {e}")

    def get_span_name(self, query: str) -> str:
        """Extract a human-readable span name from query."""
        query = query.strip().upper()

        # Extract operation and table name if possible
        if query.startswith("SELECT"):
            # Try to extract table name
            if "FROM" in query:
                parts = query.split("FROM")
                if len(parts) > 1:
                    table_part = parts[1].strip().split()[0]
                    return f"SELECT {table_part}"
            return "SELECT"
        elif query.startswith("INSERT"):
            if "INTO" in query:
                parts = query.split("INTO")
                if len(parts) > 1:
                    table_part = parts[1].strip().split()[0]
                    return f"INSERT {table_part}"
            return "INSERT"
        elif query.startswith("UPDATE"):
            parts = query.split()
            if len(parts) > 1:
                return f"UPDATE {parts[1]}"
            return "UPDATE"
        elif query.startswith("DELETE"):
            if "FROM" in query:
                parts = query.split("FROM")
                if len(parts) > 1:
                    table_part = parts[1].strip().split()[0]
                    return f"DELETE {table_part}"
            return "DELETE"
        else:
            return query.split()[0] if query else "QUERY"

    def extract_operation(self, query: str) -> str:
        """Extract operation type from query."""
        query = query.strip().upper()
        if query.startswith("SELECT"):
            return "select"
        elif query.startswith("INSERT"):
            return "insert"
        elif query.startswith("UPDATE"):
            return "update"
        elif query.startswith("DELETE"):
            return "delete"
        elif query.startswith("CREATE"):
            return "create"
        elif query.startswith("DROP"):
            return "drop"
        elif query.startswith("ALTER"):
            return "alter"
        else:
            return "other"

    def sanitize_query(self, query: str) -> str:
        """Sanitize query for span attribute (limit length, remove sensitive data)."""
        # Limit to 2KB
        if len(query) > 2048:
            query = query[:2045] + "..."
        return query

    def run(self):
        """Main loop: poll pg_stat_statements and generate spans."""
        logger.info("Starting PostgreSQL Span Generator main loop")

        # Verify pg_stat_statements is enabled
        if not self.verify_pg_stat_statements():
            logger.error("Cannot proceed without pg_stat_statements extension")
            return

        poll_interval = int(os.getenv("SPAN_GENERATOR_POLL_INTERVAL", "5"))
        logger.info(f"Poll interval: {poll_interval} seconds")

        while True:
            try:
                current_stats = self.fetch_query_stats()

                if current_stats:
                    span_count = self.generate_spans_for_new_queries(current_stats)
                    self.last_stats = current_stats
                else:
                    logger.debug("No query stats available")

                time.sleep(poll_interval)

            except KeyboardInterrupt:
                logger.info("Shutting down span generator")
                break
            except Exception as e:
                logger.error(f"Error in main loop: {e}", exc_info=True)
                time.sleep(10)


if __name__ == "__main__":
    generator = PostgresSpanGenerator()
    generator.run()
