import logging
from typing import Optional

from chaosdb.probes.postgres.postgres_system_metrics import (
    collect_postgres_system_metrics,
)

logger = logging.getLogger(__name__)


def check_dead_tuples(
    host: Optional[str] = None,
    port: Optional[int] = None,
    database: Optional[str] = None,
    user: Optional[str] = None,
    password: Optional[str] = None,
    table_name: Optional[str] = None,
) -> int:
    """
    Check the number of dead tuples in the PostgreSQL database.
    """
    # Note: table_name is accepted but currently collect_postgres_system_metrics aggregates all user tables.
    # If table-specific dead tuples are needed, we might need to enhance the system metrics probe or write a specific query here.
    # For now, we return the total dead tuples as a proxy.
    metrics = collect_postgres_system_metrics(host, port, database, user, password)
    dead_tuples = metrics.get("dead_tuples", 0)
    logger.info(f"Dead Tuples: {dead_tuples}")
    return int(dead_tuples)
