import logging
from typing import Optional

from chaosdb.probes.postgres.postgres_slow_transactions_status import (
    probe_slow_transactions_status,
)

logger = logging.getLogger(__name__)


def check_transaction_duration(
    host: Optional[str] = None,
    port: Optional[int] = None,
    database: Optional[str] = None,
    user: Optional[str] = None,
    password: Optional[str] = None,
) -> float:
    """
    Check transaction duration metrics.
    Returns the average transaction duration in milliseconds.
    """
    result = probe_slow_transactions_status(host, port, database, user, password)
    avg_duration = result.get("average_transaction_duration_ms", 0.0)
    logger.info(f"Average Transaction Duration: {avg_duration} ms")
    return float(avg_duration)
