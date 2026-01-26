from typing import Optional

from chaosdb.probes.postgres.postgres_system_metrics import (
    collect_postgres_system_metrics,
)
import logging

logger = logging.getLogger(__name__)


def check_cache_hit_ratio(
    host: Optional[str] = None,
    port: Optional[int] = None,
    database: Optional[str] = None,
    user: Optional[str] = None,
    password: Optional[str] = None,
) -> float:
    """
    Check the cache hit ratio of the PostgreSQL database.
    """
    metrics = collect_postgres_system_metrics(host, port, database, user, password)
    ratio = metrics.get("cache_hit_ratio", 0.0)
    logger.info(f"Cache Hit Ratio: {ratio}")
    return ratio
