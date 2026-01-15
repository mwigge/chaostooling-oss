import os

import psycopg2
from chaosotel import ensure_initialized, get_logger, get_tracer
from opentelemetry.trace import StatusCode


def get_db_connection():
    # For validation, we might want to check the Replica to ensure replication worked
    # Or check "any" to see if data exists.
    # Let's default to checking the primary or whatever is configured.
    host = os.getenv("POSTGRES_HOST", "postgres")
    # Simple connection for now
    return psycopg2.connect(
        host=(
            host.split(",")[0].split(":")[0] if "," in host else host
        ),  # Take first host if list
        port=os.getenv("POSTGRES_PORT", "5432"),
        dbname=os.getenv("POSTGRES_DB", "testdb"),
        user=os.getenv("POSTGRES_USER", "postgres"),
        password=os.getenv("POSTGRES_PASSWORD", "postgres"),
    )


def validate_data_consistency(expected_count: int, item_id: str) -> bool:
    """
    Validate that the expected number of transactions for an item exist in the DB.
    """
    ensure_initialized()
    tracer = get_tracer()
    logger = get_logger()

    with tracer.start_as_current_span("mobile.observability.validate_data") as span:
        conn = get_db_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute(
                    "SELECT COUNT(*) FROM mobile_purchases WHERE item_id = %s",
                    (item_id,),
                )
                count = cursor.fetchone()[0]

            span.set_attribute("validation.expected_count", expected_count)
            span.set_attribute("validation.actual_count", count)

            if count >= expected_count:
                span.set_status(StatusCode.OK)
                logger.info(
                    f"Data consistency check passed: Found {count} records (Expected >= {expected_count})"
                )
                return True
            else:
                span.set_status(StatusCode.ERROR, "Data missing")
                logger.error(
                    f"Data consistency check failed: Found {count} records (Expected >= {expected_count})"
                )
                return False
        except Exception as e:
            span.set_status(StatusCode.ERROR, str(e))
            logger.error(f"Validation failed: {e}")
            return False
        finally:
            conn.close()
