from typing import Optional

from chaosdb.probes.postgres.postgres_system_metrics import (
    collect_postgres_system_metrics,
)
import logging

logger = logging.getLogger(__name__)


def check_temp_file_usage(
    host: Optional[str] = None,
    port: Optional[int] = None,
    database: Optional[str] = None,
    user: Optional[str] = None,
    password: Optional[str] = None,
) -> int:
    """
    Check the temp file usage (number of files) in the PostgreSQL database.
    """
    metrics = collect_postgres_system_metrics(host, port, database, user, password)
    temp_files = metrics.get("temp_files", 0)
    logger.info(f"Temp Files: {temp_files}")
    return int(temp_files)
