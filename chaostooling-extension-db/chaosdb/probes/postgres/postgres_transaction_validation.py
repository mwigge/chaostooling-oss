"""PostgreSQL transaction validation probes."""

import logging
import os
import time
from contextlib import nullcontext
from typing import Optional

import psycopg2
import requests
from chaosotel import flush, get_metric_tags, get_metrics_core, get_tracer
from opentelemetry._logs import get_logger_provider
from opentelemetry.sdk._logs import LoggingHandler
from opentelemetry.trace import StatusCode


def probe_transaction_count(
    host: Optional[str] = None,
    port: Optional[int] = None,
    database: Optional[str] = None,
    user: Optional[str] = None,
    password: Optional[str] = None,
    table_name: str = "mobile_purchases",
) -> dict:
    """

    Probe transaction count in the database.

    Observability: Uses chaosotel (chaostooling-otel) as the central observability location. chaosotel must be initialized via chaosotel.control in the experiment configuration.

    """

    # Handle string input from Chaos Toolkit configuration

    if port is not None:
        port = int(port) if isinstance(port, str) else port

    host = host or os.getenv("POSTGRES_HOST", "postgres")

    port = port or int(os.getenv("POSTGRES_PORT", "5432"))

    database = database or os.getenv("POSTGRES_DB", "testdb")

    user = user or os.getenv("POSTGRES_USER", "postgres")

    password = password or os.getenv("POSTGRES_PASSWORD", "changeme")

    # chaosotel is initialized via chaosotel.control - use directly

    tracer = get_tracer()

    # Setup OpenTelemetry logger via LoggingHandler

    logger_provider = get_logger_provider()

    if logger_provider:
        handler = LoggingHandler(level=logging.INFO, logger_provider=logger_provider)

        logger = logging.getLogger("chaosdb.postgres.postgres_transaction_validation")

        logger.addHandler(handler)

        logger.setLevel(logging.INFO)

    else:
        logger = logging.getLogger("chaosdb.postgres.postgres_transaction_validation")

    metrics = get_metrics_core()

    db_system = "postgresql"

    start = time.time()

    span_context = (
        tracer.start_as_current_span("probe.postgres.transaction_count")
        if tracer
        else nullcontext()
    )

    with span_context as span:
        try:
            if span:
                span.set_attribute("db.system", db_system)

                span.set_attribute("db.operation", "probe_transaction_count")

                span.set_attribute("db.table", table_name)

                span.set_attribute("chaos.activity", "postgresql_transaction_count")

                span.set_attribute("chaos.activity.type", "probe")

                span.set_attribute("chaos.system", "postgresql")

                span.set_attribute("chaos.operation", "transaction_count")

            conn = psycopg2.connect(
                host=host,
                port=port,
                database=database,
                user=user,
                password=password,
                connect_timeout=5,
            )

            cursor = conn.cursor()

            # Get total count

            cursor.execute(f"SELECT COUNT(*) FROM {table_name}")

            total_count = cursor.fetchone()[0]

            # Get count by status

            cursor.execute(f"SELECT status, COUNT(*) FROM {table_name} GROUP BY status")

            status_counts = dict(cursor.fetchall())

            # Get max ID

            cursor.execute(f"SELECT COALESCE(MAX(id), 0) FROM {table_name}")

            max_id = cursor.fetchone()[0]

            # Get recent transactions (last 5 minutes)

            cursor.execute(
                f"SELECT COUNT(*) FROM {table_name} WHERE created_at > NOW() - INTERVAL '5 minutes'"
            )

            recent_count = cursor.fetchone()[0]

            cursor.close()

            conn.close()

            probe_time_ms = (time.time() - start) * 1000

            metrics.record_db_query_latency(
                probe_time_ms,
                db_system=db_system,
                db_name=database,
                db_operation="probe_transaction_count",
            )

            metrics.record_db_query_count(
                db_system=db_system,
                db_name=database,
                db_operation="probe_transaction_count",
                count=1,
            )

            metrics.record_db_gauge(
                "transaction.total_count",
                float(total_count),
                db_system=db_system,
                db_name=database,
            )

            result = {
                "success": True,
                "total_count": total_count,
                "max_id": max_id,
                "recent_count": recent_count,
                "status_counts": status_counts,
                "probe_time_ms": probe_time_ms,
            }

            if span:
                span.set_attribute("transaction.total_count", total_count)

                span.set_attribute("transaction.max_id", max_id)

                span.set_attribute("transaction.recent_count", recent_count)

                span.set_status(StatusCode.OK)

            logger.info(f"Transaction count probe: {result}")

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
            logger.error(
                f"Transaction count probe failed: {str(e)}", extra={"error": str(e)}
            )

            flush()

            raise


def probe_transaction_integrity(
    host: Optional[str] = None,
    port: Optional[int] = None,
    database: Optional[str] = None,
    user: Optional[str] = None,
    password: Optional[str] = None,
    table_name: str = "mobile_purchases",
    expected_transaction_ids: Optional[list[int]] = None,
) -> dict:
    """

    Probe transaction integrity by checking if expected transactions exist.

    Observability: Uses chaosotel (chaostooling-otel) as the central observability location. chaosotel must be initialized via chaosotel.control in the experiment configuration.

    """

    # Handle string input from Chaos Toolkit configuration

    if port is not None:
        port = int(port) if isinstance(port, str) else port

    host = host or os.getenv("POSTGRES_HOST", "postgres")

    port = port or int(os.getenv("POSTGRES_PORT", "5432"))

    database = database or os.getenv("POSTGRES_DB", "testdb")

    user = user or os.getenv("POSTGRES_USER", "postgres")

    password = password or os.getenv("POSTGRES_PASSWORD", "changeme")

    # chaosotel is initialized via chaosotel.control - use directly

    tracer = get_tracer()

    # Setup OpenTelemetry logger via LoggingHandler

    logger_provider = get_logger_provider()

    if logger_provider:
        handler = LoggingHandler(level=logging.INFO, logger_provider=logger_provider)

        logger = logging.getLogger("chaosdb.postgres.postgres_transaction_validation")

        logger.addHandler(handler)

        logger.setLevel(logging.INFO)

    else:
        logger = logging.getLogger("chaosdb.postgres.postgres_transaction_validation")

    metrics = get_metrics_core()

    db_system = "postgresql"

    start = time.time()

    span_context = (
        tracer.start_as_current_span("probe.postgres.transaction_integrity")
        if tracer
        else nullcontext()
    )

    with span_context as span:
        try:
            if span:
                span.set_attribute("db.system", db_system)

                span.set_attribute("db.operation", "probe_transaction_integrity")

                span.set_attribute("db.table", table_name)

                span.set_attribute("chaos.activity", "postgresql_transaction_integrity")

                span.set_attribute("chaos.activity.type", "probe")

                span.set_attribute("chaos.system", "postgresql")

                span.set_attribute("chaos.operation", "transaction_integrity")

            conn = psycopg2.connect(
                host=host,
                port=port,
                database=database,
                user=user,
                password=password,
                connect_timeout=5,
            )

            cursor = conn.cursor()

            missing_ids = []

            found_ids = []

            if expected_transaction_ids:
                # Check which IDs exist

                for tx_id in expected_transaction_ids:
                    cursor.execute(
                        f"SELECT COUNT(*) FROM {table_name} WHERE id = %s", (tx_id,)
                    )

                    if cursor.fetchone()[0] > 0:
                        found_ids.append(tx_id)

                    else:
                        missing_ids.append(tx_id)

            # Check for gaps in ID sequence

            cursor.execute(f"SELECT id FROM {table_name} ORDER BY id")

            all_ids = [row[0] for row in cursor.fetchall()]

            gaps = []

            if all_ids:
                for i in range(1, len(all_ids)):
                    if all_ids[i] - all_ids[i - 1] > 1:
                        gaps.append((all_ids[i - 1], all_ids[i]))

            cursor.close()

            conn.close()

            is_integrity_ok = len(missing_ids) == 0 and len(gaps) == 0

            lost_count = len(missing_ids)

            probe_time_ms = (time.time() - start) * 1000

            # Record transaction integrity check result
            metrics.record_transaction_integrity(
                is_integrity_ok=is_integrity_ok,
                db_system=db_system,
                tags={"database": database, "table_name": table_name},
            )

            metrics.record_db_query_latency(
                probe_time_ms,
                db_system=db_system,
                db_name=database,
                db_operation="probe_transaction_integrity",
            )

            metrics.record_db_query_count(
                db_system=db_system,
                db_name=database,
                db_operation="probe_transaction_integrity",
                count=1,
            )

            metrics.record_db_gauge(
                "transaction.integrity",
                1.0 if is_integrity_ok else 0.0,
                db_system=db_system,
                db_name=database,
            )

            # Track lost/missing transactions

            if lost_count > 0:
                metrics.record_db_gauge(
                    "transaction.missing",
                    float(lost_count),
                    db_system=db_system,
                    db_name=database,
                )

                metrics.record_db_counter(
                    "transaction.lost",
                    db_system=db_system,
                    db_name=database,
                    count=lost_count,
                )

            result = {
                "success": True,
                "is_integrity_ok": is_integrity_ok,
                "expected_count": (
                    len(expected_transaction_ids) if expected_transaction_ids else None
                ),
                "found_count": len(found_ids),
                "missing_ids": missing_ids,
                "found_ids": found_ids,
                "gaps": gaps,
                "lost_count": lost_count,
                "probe_time_ms": probe_time_ms,
            }

            if span:
                span.set_attribute("integrity.is_ok", is_integrity_ok)

                span.set_attribute("integrity.missing_count", len(missing_ids))

                span.set_attribute("integrity.gap_count", len(gaps))

                span.set_attribute("integrity.lost_count", lost_count)

                span.set_status(StatusCode.OK)

            logger.info(f"Transaction integrity probe: {result}")

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

            logger.error(
                f"Transaction integrity probe failed: {str(e)}", extra={"error": str(e)}
            )

            flush()

            raise


def probe_api_transaction_flow(
    api_url: Optional[str] = None,
    num_transactions: int = 10,
) -> dict:
    """

    Probe API transaction flow by making purchase requests and tracking them.

    Observability: Uses chaosotel (chaostooling-otel) as the central observability location. chaosotel must be initialized via chaosotel.control in the experiment configuration.

    """

    # Handle string input from Chaos Toolkit configuration

    if isinstance(num_transactions, str):
        num_transactions = int(num_transactions)

    api_url = api_url or os.getenv("API_URL", "http://haproxy:80")

    # chaosotel is initialized via chaosotel.control - use directly

    tracer = get_tracer()

    # Setup OpenTelemetry logger via LoggingHandler

    logger_provider = get_logger_provider()

    if logger_provider:
        handler = LoggingHandler(level=logging.INFO, logger_provider=logger_provider)

        logger = logging.getLogger("chaosdb.postgres.postgres_transaction_validation")

        logger.addHandler(handler)

        logger.setLevel(logging.INFO)

    else:
        logger = logging.getLogger("chaosdb.postgres.postgres_transaction_validation")

    metrics = get_metrics_core()

    start = time.time()

    span_context = (
        tracer.start_as_current_span("probe.api.transaction_flow")
        if tracer
        else nullcontext()
    )

    with span_context as span:
        try:
            if span:
                span.set_attribute("http.url", api_url)

            transaction_ids = []

            successful = 0

            failed = 0

            errors = []

            from opentelemetry.propagate import inject

            reconnection_attempts = 0

            reconnection_successes = 0

            # Add overall timeout to prevent hanging
            overall_start = time.time()
            max_overall_timeout = 300  # 5 minutes max for all transactions

            for i in range(num_transactions):
                # Check if we've exceeded overall timeout
                if time.time() - overall_start > max_overall_timeout:
                    logger.warning(
                        f"Overall timeout exceeded after {num_transactions - i} transactions remaining"
                    )
                    break

                # Log progress every 10 transactions
                if i > 0 and i % 10 == 0:
                    logger.info(
                        f"Progress: {i}/{num_transactions} transactions completed (successful: {successful}, failed: {failed})"
                    )

                max_retries = 3

                retry_count = 0

                success = False

                while retry_count < max_retries and not success:
                    try:
                        headers = {}

                        inject(headers)

                        response = requests.post(
                            f"{api_url}/purchase",
                            json={
                                "user_id": f"user_{i}",
                                "amount": 100.0 + i,
                                "item_id": f"item_{i}",
                            },
                            headers=headers,
                            timeout=5,  # Reduced from 10 to 5 seconds
                        )

                        if response.status_code == 200:
                            successful += 1

                            success = True

                            # Try to extract transaction ID from response if available

                            data = response.json()

                            if "transaction_id" in data:
                                transaction_ids.append(data["transaction_id"])

                            # Track successful reconnection if this was a retry

                            if retry_count > 0:
                                reconnection_successes += 1
                                # Record reconnection attempt
                                metrics.record_transaction_reconnection_attempt(
                                    db_operation="api_transaction_flow",
                                    db_system="postgresql",
                                )

                            # Record successful transaction
                            metrics.record_transaction(
                                db_operation="api_transaction_flow",
                                status="successful",
                                db_system="postgresql",
                            )

                        else:
                            failed += 1

                            errors.append(
                                f"HTTP {response.status_code}: {response.text}"
                            )

                            # Record failed transaction
                            metrics.record_transaction(
                                db_operation="api_transaction_flow",
                                status="failed",
                                db_system="postgresql",
                            )

                            success = True  # Don't retry on HTTP errors

                    except (
                        requests.exceptions.ConnectionError,
                        requests.exceptions.ConnectTimeout,
                        requests.exceptions.Timeout,
                        requests.exceptions.ReadTimeout,
                    ) as e:
                        # Track connection/timeout failures

                        retry_count += 1

                        reconnection_attempts += 1

                        if retry_count < max_retries:
                            # Track reconnection attempt

                            time.sleep(0.5)  # Reduced wait time from 1 to 0.5 seconds

                        else:
                            failed += 1

                            errors.append(
                                f"Connection/timeout failed after {max_retries} attempts: {str(e)}"
                            )

                            # Record failed transaction
                            metrics.record_transaction(
                                db_operation="api_transaction_flow",
                                status="failed",
                                db_system="postgresql",
                            )

                            success = True  # Stop retrying after max attempts

                    except Exception as e:
                        errors.append(str(e))

                        failed += 1

                        # Record failed transaction
                        metrics.record_transaction(
                            db_operation="api_transaction_flow",
                            status="failed",
                            db_system="postgresql",
                        )

                        success = True  # Don't retry on other errors

            probe_time_ms = (time.time() - start) * 1000

            result = {
                "success": True,
                "total_transactions": num_transactions,
                "successful": successful,
                "failed": failed,
                "transaction_ids": transaction_ids,
                "reconnection_attempts": reconnection_attempts,
                "reconnection_successes": reconnection_successes,
                "errors": errors[:10],  # Limit errors to first 10
                "probe_time_ms": probe_time_ms,
            }

            if span:
                span.set_attribute("transaction.successful", successful)

                span.set_attribute("transaction.failed", failed)

                span.set_attribute(
                    "transaction.reconnection_attempts", reconnection_attempts
                )

                span.set_attribute(
                    "transaction.reconnection_successes", reconnection_successes
                )

                span.set_status(StatusCode.OK)

            # Record metrics using MetricsCore

            db_system = "http"  # API transactions use http as system

            tags = get_metric_tags(
                db_name="api",
                db_system=db_system,
                db_operation="probe_api_transaction_flow",
            )

            # Record custom transaction metrics (using underscores and _total suffix for Prometheus compatibility)
            metrics.record_custom_metric(
                "chaos_transaction_total",
                float(num_transactions),
                metric_type="counter",
                tags=tags,
                description="Total transactions attempted",
            )
            metrics.record_custom_metric(
                "chaos_transaction_successful_total",
                float(successful),
                metric_type="counter",
                tags=tags,
                description="Successful transactions",
            )
            metrics.record_custom_metric(
                "chaos_transaction_failed_total",
                float(failed),
                metric_type="counter",
                tags=tags,
                description="Failed transactions",
            )
            # Also record reconnection attempts using the dedicated method for proper metric naming
            if reconnection_attempts > 0:
                for _ in range(reconnection_attempts):
                    metrics.record_transaction_reconnection_attempt(
                        db_operation="probe_api_transaction_flow",
                        db_system=db_system,
                        tags=tags,
                    )

            metrics.record_db_query_latency(
                probe_time_ms,
                db_system=db_system,
                db_name="api",
                db_operation="probe_api_transaction_flow",
                tags=tags,
            )

            metrics.record_db_query_count(
                db_system=db_system,
                db_name="api",
                db_operation="probe_api_transaction_flow",
                count=num_transactions,
            )

            metrics.record_db_counter(
                "transaction.count",
                db_system=db_system,
                db_name="api",
                count=successful,
            )

            if failed > 0:
                metrics.record_db_counter(
                    "transaction.failed",
                    db_system=db_system,
                    db_name="api",
                    count=failed,
                )

            if reconnection_attempts > 0:
                metrics.record_db_counter(
                    "client.reconnection_attempts",
                    db_system=db_system,
                    db_name="api",
                    count=reconnection_attempts,
                )

            if reconnection_successes > 0:
                metrics.record_db_counter(
                    "client.reconnection",
                    db_system=db_system,
                    db_name="api",
                    count=reconnection_successes,
                )

            # Track lost transactions (failed after max retries)

            lost_transactions = failed - (num_transactions - successful)

            if lost_transactions > 0:
                metrics.record_db_counter(
                    "transaction.lost",
                    db_system=db_system,
                    db_name="api",
                    count=lost_transactions,
                )

            # Track recovered transactions (successful after retry)

            if reconnection_successes > 0:
                metrics.record_db_counter(
                    "transaction.recovered",
                    db_system=db_system,
                    db_name="api",
                    count=reconnection_successes,
                )

            logger.info(f"API transaction flow probe: {result}")

            flush()

            return result

        except Exception as e:
            if span:
                span.record_exception(e)
                span.set_status(StatusCode.ERROR, str(e))
            logger.error(
                f"API transaction flow probe failed: {str(e)}", extra={"error": str(e)}
            )

            flush()

            raise
