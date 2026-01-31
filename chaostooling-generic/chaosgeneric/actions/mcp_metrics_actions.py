"""
MCP Metrics Actions - Context-aware wrappers

Wraps mcp_metrics_collector functions to extract run_id from experiment context
and automatically pass it to the database storage layer.

This allows seamless database integration without requiring run_id in experiment JSON.
"""

import logging
import os
from typing import Any

logger = logging.getLogger(__name__)


def collect_baseline_snapshot_with_context(
    context: dict[str, Any],
    grafana_url: str,
    metrics: list[str],
    service_name: str,
    output_file: str = "./baseline_snapshot.json",
    datasource_uid: str = "prometheus",
    time_range: str = "24h",
) -> dict[str, Any]:
    """
    Collect baseline metrics snapshot with automatic database storage.

    Extracts run_id from experiment context and passes to database layer.
    Falls back to file-only storage if context doesn't have run_id.

    IMPORTANT: Uses 24h time range by default for proper steady-state baseline.
    Override with time_range="30d" for longer-term baseline or time_range="7d" for weekly.

    Args:
        context: Chaos Toolkit experiment context (contains chaos_run_id from database-storage control)
        grafana_url: Grafana endpoint URL
        metrics: List of metric queries (PromQL, LogQL, etc.)
        service_name: Service name
        output_file: File path for snapshot backup
        datasource_uid: Grafana datasource UID
        time_range: Time range for metrics aggregation (default: '24h' - last 24 hours average)

    Returns:
        Dict with collection status
    """
    from chaosgeneric.actions.mcp_metrics_collector import collect_baseline_snapshot

    # Extract run_id from context (set by database-storage control)
    run_id = context.get("chaos_run_id") if context else None
    db_host = os.getenv("CHAOS_DB_HOST", "chaos-platform-db")
    db_port = os.getenv("CHAOS_DB_PORT", "5432")

    logger.info(f"Collecting baseline snapshot (run_id={run_id})")

    return collect_baseline_snapshot(
        grafana_url=grafana_url,
        metrics=metrics,
        service_name=service_name,
        output_file=output_file,
        datasource_uid=datasource_uid,
        time_range=time_range,
        run_id=run_id,
        phase="pre_chaos",
        db_host=db_host,
        db_port=int(db_port),
    )


def collect_chaos_snapshot_with_context(
    context: dict[str, Any],
    grafana_url: str,
    metrics: list[str],
    service_name: str,
    output_file: str = "./chaos_snapshot.json",
    datasource_uid: str = "prometheus",
    time_range: str = "5m",
) -> dict[str, Any]:
    """
    Collect during-chaos metrics snapshot with automatic database storage.

    IMPORTANT: Uses 5m time range to capture immediate chaos impact.

    Args:
        context: Chaos Toolkit experiment context
        grafana_url: Grafana endpoint URL
        metrics: List of metric queries
        service_name: Service name
        output_file: File path for snapshot backup
        datasource_uid: Grafana datasource UID
        time_range: Time range for metrics aggregation (default: '5m' - immediate impact)

    Returns:
        Dict with collection status
    """
    from chaosgeneric.actions.mcp_metrics_collector import collect_baseline_snapshot

    run_id = context.get("chaos_run_id") if context else None
    db_host = os.getenv("CHAOS_DB_HOST", "chaos-platform-db")
    db_port = os.getenv("CHAOS_DB_PORT", "5432")

    logger.info(f"Collecting chaos snapshot (run_id={run_id})")

    return collect_baseline_snapshot(
        grafana_url=grafana_url,
        metrics=metrics,
        service_name=service_name,
        output_file=output_file,
        datasource_uid=datasource_uid,
        time_range=time_range,
        run_id=run_id,
        phase="during_chaos",
        db_host=db_host,
        db_port=int(db_port),
    )


def collect_recovery_snapshot_with_context(
    context: dict[str, Any],
    grafana_url: str,
    metrics: list[str],
    service_name: str,
    output_file: str = "./recovery_snapshot.json",
    datasource_uid: str = "prometheus",
    time_range: str = "5m",
) -> dict[str, Any]:
    """
    Collect post-chaos/recovery metrics snapshot with automatic database storage.

    IMPORTANT: Uses 5m time range to verify recovery has occurred.

    Args:
        context: Chaos Toolkit experiment context
        grafana_url: Grafana endpoint URL
        metrics: List of metric queries
        service_name: Service name
        output_file: File path for snapshot backup
        datasource_uid: Grafana datasource UID
        time_range: Time range for metrics aggregation (default: '5m' - recovery verification)

    Returns:
        Dict with collection status
    """
    from chaosgeneric.actions.mcp_metrics_collector import collect_baseline_snapshot

    run_id = context.get("chaos_run_id") if context else None
    db_host = os.getenv("CHAOS_DB_HOST", "chaos-platform-db")
    db_port = os.getenv("CHAOS_DB_PORT", "5432")

    logger.info(f"Collecting recovery snapshot (run_id={run_id})")

    return collect_baseline_snapshot(
        grafana_url=grafana_url,
        metrics=metrics,
        service_name=service_name,
        output_file=output_file,
        datasource_uid=datasource_uid,
        time_range=time_range,
        run_id=run_id,
        phase="post_chaos",
        db_host=db_host,
        db_port=int(db_port),
    )
