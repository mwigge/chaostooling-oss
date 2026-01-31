import logging
from typing import Optional

from chaosdb.probes.postgres.postgres_pool_exhaustion_status import (
    probe_pool_exhaustion_status,
)

logger = logging.getLogger(__name__)


def check_connection_pool_status(
    host: Optional[str] = None,
    port: Optional[int] = None,
    database: Optional[str] = None,
    user: Optional[str] = None,
    password: Optional[str] = None,
) -> bool:
    """
    Check connection pool status.
    Returns True if the check ran successfully.
    """
    result = probe_pool_exhaustion_status(host, port, database, user, password)
    logger.info(f"Connection Pool Status: {result}")
    return result.get("success", False)
