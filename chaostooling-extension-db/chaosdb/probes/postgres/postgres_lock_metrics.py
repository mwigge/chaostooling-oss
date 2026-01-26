from typing import Optional

from chaosdb.probes.postgres.postgres_lock_storm_status import probe_lock_storm_status
import logging

logger = logging.getLogger(__name__)


def check_lock_contention(
    host: Optional[str] = None,
    port: Optional[int] = None,
    database: Optional[str] = None,
    user: Optional[str] = None,
    password: Optional[str] = None,
) -> bool:
    """
    Check for lock contention (waiting locks and deadlocks).
    Returns True if the check ran successfully (tolerance is handled by the experiment).
    """
    result = probe_lock_storm_status(host, port, database, user, password)
    logger.info(f"Lock Contention Status: {result}")
    return result.get("success", False)
