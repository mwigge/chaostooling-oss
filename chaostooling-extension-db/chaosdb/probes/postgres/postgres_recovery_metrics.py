import logging
import time
from typing import Optional

from chaosdb.probes.postgres.postgres_connectivity import probe_postgres_connectivity

logger = logging.getLogger(__name__)


def measure_recovery_time(
    replica_host: Optional[str] = None,
    replica_port: Optional[int] = None,
    database: Optional[str] = None,
    user: Optional[str] = None,
    password: Optional[str] = None,
    timeout: int = 60,
) -> float:
    """
    Measure the time it takes for the replica to become available (RTO).
    Returns the recovery time in seconds.
    """
    start_time = time.time()
    end_time = start_time + timeout

    while time.time() < end_time:
        result = probe_postgres_connectivity(
            replica_host, replica_port, database, user, password
        )
        if result:
            recovery_time = time.time() - start_time
            logger.info(f"Recovery Time (RTO): {recovery_time:.2f}s")
            return recovery_time
        time.sleep(1)

    logger.error(f"Recovery measurement timed out after {timeout}s")
    return float(timeout)
