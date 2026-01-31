"""
MCP Metrics Collector Action Module

Actions that collect snapshots of metrics during experiment execution.
Stores snapshots in PostgreSQL database (primary) with optional JSON backup.
Used to capture metrics at different phases (pre-chaos, during-chaos, post-chaos).

Queries Grafana datasource-agnostically (works with Prometheus, Mimir, Loki, Tempo, etc.)
"""

import json
import logging
import os
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
import requests
from chaosgeneric.data.chaos_db import ChaosDb

logger = logging.getLogger(__name__)


def _query_grafana(
    grafana_url: str,
    query: str,
    datasource_uid: str = "prometheus",
    time_range: str = "5m",
) -> Dict[str, Any]:
    """
    Query Grafana's datasource-agnostic API.
    Works with Prometheus, Mimir, Loki, Tempo, or any Grafana datasource.

    Supports time range formats:
    - "5m", "30m", "1h", "6h", "24h", "7d", "30d" - relative time ranges
    - Returns average aggregation for baseline snapshots
    """
    try:
        # Calculate time range in milliseconds
        now = datetime.utcnow()

        # Parse time range - supports m, h, d suffixes
        if time_range.endswith("m"):
            delta = timedelta(minutes=int(time_range[:-1]))
        elif time_range.endswith("h"):
            delta = timedelta(hours=int(time_range[:-1]))
        elif time_range.endswith("d"):
            delta = timedelta(days=int(time_range[:-1]))
        else:
            delta = timedelta(minutes=5)

        from_time = int((now - delta).timestamp() * 1000)
        to_time = int(now.timestamp() * 1000)

        # Grafana QueryData API - works with any datasource
        url = f"{grafana_url}/api/ds/query"

        # For Prometheus-compatible queries (PromQL, LogQL, etc.)
        # Use avg() aggregation for baseline metrics over longer periods
        payload = {
            "queries": [
                {
                    "refId": "A",
                    "datasourceUid": datasource_uid,
                    "expr": query,  # Use 'expr' for PromQL
                    "queryType": "",
                    "interval": "",
                    "maxDataPoints": 43200,
                }
            ],
            "from": from_time,
            "to": to_time,
        }

        headers = {"Content-Type": "application/json", "Accept": "application/json"}

        logger.debug(f"Querying Grafana: {url} with query: {query}")
        response = requests.post(url, json=payload, headers=headers, timeout=10)

        if response.status_code != 200:
            logger.debug(f"Grafana response: {response.text}")
            # If query fails, return empty result but not an error (some datasources may not have the metric)
            return {
                "status": "success",
                "results": [{"status": "no data", "frames": []}],
            }

        return response.json()
    except Exception as e:
        logger.warning(f"Grafana query failed: {str(e)}")
        return {
            "status": "success",
            "results": [{"status": "error", "error": str(e), "frames": []}],
        }


def collect_baseline_snapshot(
    grafana_url: str,
    metrics: List[str],
    service_name: str,
    output_file: str,
    datasource_uid: str = "prometheus",
    time_range: str = "24h",
    run_id: Optional[int] = None,
    phase: str = "pre_chaos",
    db_host: str = "localhost",
    db_port: int = 5434,
) -> Dict[str, Any]:
    """
    Collect a snapshot of metrics from Grafana (datasource-agnostic).
    Works with Prometheus, Mimir, Loki, Tempo, or any Grafana datasource.
    Stores in database (primary) with optional file backup.

    Used during experiments to capture metrics before, during, and after chaos injection.
    Each snapshot can be compared to identify impact of chaos.

    BASELINE RECOMMENDATION:
    - Pre-chaos (baseline): Use 24h or 30d to establish steady state average
    - During-chaos: Use 5m to capture immediate impact
    - Post-chaos: Use 5m to verify recovery

    Args:
        grafana_url: Grafana endpoint URL (e.g., http://grafana:3000)
        metrics: List of queries (PromQL, LogQL, TraceQL, etc. depending on datasource)
        service_name: Service being monitored
        output_file: File path to save snapshot JSON (optional backup)
        datasource_uid: Grafana datasource UID (default: "prometheus")
        time_range: Time range for aggregation (e.g., '5m', '1h', '24h', '30d')
                   Default: '24h' (better for baseline, use '5m' for during/after)
        run_id: Experiment run ID (for database storage) - can also come from CHAOS_RUN_ID env var
        phase: Phase name (pre_chaos, during_chaos, post_chaos, baseline_collection)
        db_host: Database host
        db_port: Database port

    Returns:
        Dict with snapshot data and metadata
    """
    # If run_id not provided, try to get from environment (set by database_storage_control)
    if not run_id:
        run_id = os.getenv("CHAOS_RUN_ID")
        if run_id:
            run_id = int(run_id)

    logger.info(f"Collecting {phase} metric snapshot for {service_name}")
    logger.info(f"Metrics: {', '.join(metrics)}")
    logger.info(f"Querying via Grafana (datasource: {datasource_uid})")

    try:
        # Collect metrics via Grafana's datasource-agnostic API
        snapshot = {
            "timestamp": datetime.utcnow().isoformat(),
            "service_name": service_name,
            "phase": phase,
            "time_range": time_range,
            "datasource": datasource_uid,
            "metrics": {},
        }

        for metric in metrics:
            logger.debug(f"Querying metric: {metric}")

            try:
                # Query metric via Grafana (works with any datasource)
                result = _query_grafana(
                    grafana_url=grafana_url,
                    query=metric,
                    datasource_uid=datasource_uid,
                    time_range=time_range,
                )

                snapshot["metrics"][metric] = {
                    "query": metric,
                    "result": result.get("results", [{}])[0]
                    if result.get("results")
                    else result.get("data", {}),
                    "status": result.get("status", "error"),
                }
                logger.debug(f"[OK] Collected {metric}")

            except Exception as e:
                logger.warning(f"Failed to collect metric {metric}: {str(e)}")
                snapshot["metrics"][metric] = {
                    "query": metric,
                    "error": str(e),
                    "status": "error",
                }

        # Save to database (primary storage)
        # For baseline collection, save even without run_id
        if run_id or phase == "baseline_collection":
            try:
                db = ChaosDb(host=db_host, port=db_port)

                # For baseline collection, save as baseline metrics (steady state reference)
                if phase == "baseline_collection":
                    # Convert raw metrics to baseline format with simple statistics
                    # Since we're collecting point-in-time snapshots, use the value as mean
                    baseline_metrics = {}
                    for metric_name, metric_data in snapshot["metrics"].items():
                        if metric_data.get("status") == "success":
                            result = metric_data.get("result", {})
                            # Extract value from Grafana result structure
                            value = None
                            if isinstance(result, dict):
                                frames = result.get("frames", [])
                                if frames and len(frames) > 0:
                                    data = frames[0].get("data", {})
                                    values = data.get("values", [[]])
                                    if (
                                        values
                                        and len(values) > 0
                                        and len(values[0]) > 0
                                    ):
                                        value = values[0][0]

                            if value is not None:
                                # Store as baseline with value as mean (stddev=0 for single point)
                                baseline_metrics[metric_name] = {
                                    "mean": float(value),
                                    "median": float(value),
                                    "stddev": 0.0,  # Single point, no deviation
                                    "min": float(value),
                                    "max": float(value),
                                    "p50": float(value),
                                    "p95": float(value),
                                    "p99": float(value),
                                    "sample_count": 1,
                                }

                    db.save_baseline_metrics(
                        service_name=service_name, metrics=baseline_metrics
                    )
                    logger.info(f"[OK] Baseline metrics saved to database")
                else:
                    # For regular phases (pre/during/post chaos), save as metric snapshots
                    db.save_metric_snapshot(
                        run_id=run_id,
                        service_name=service_name,
                        phase=phase,
                        metrics=snapshot["metrics"],
                    )
                    logger.info(f"[OK] Snapshot saved to database (run_id: {run_id})")

            except Exception as db_error:
                logger.warning(f"Could not save to database: {str(db_error)}")
                import traceback

                traceback.print_exc()
                # Continue with file backup

        # Save snapshot to file (optional backup)
        try:
            with open(output_file, "w") as f:
                json.dump(snapshot, f, indent=2, default=str)
            logger.info(f"[OK] Snapshot also saved to {output_file}")
        except Exception as file_error:
            logger.warning(f"Could not save to file: {str(file_error)}")

        logger.info(
            f"  Collected {len([m for m in snapshot['metrics'].values() if m.get('status') == 'success'])}/{len(metrics)} metrics"
        )

        return {
            "status": "ok",
            "snapshot_file": output_file,
            "run_id": run_id,
            "timestamp": snapshot["timestamp"],
            "phase": phase,
            "metrics_collected": len(snapshot["metrics"]),
            "output": f"Snapshot saved",
        }

    except Exception as e:
        logger.error(f"Failed to collect snapshot: {str(e)}")
        raise


def collect_trace_snapshot(
    grafana_url: str,
    service_name: str,
    output_file: str,
    datasource_uid: str = "tempo",
    time_range: str = "1h",
) -> Dict[str, Any]:
    """
    Collect traces for service via Grafana's datasource-agnostic API.
    Works with Tempo, Jaeger, or any Grafana trace datasource.

    Args:
        grafana_url: Grafana endpoint URL
        service_name: Service to trace
        output_file: File path to save traces
        datasource_uid: Grafana datasource UID (default: "tempo")
        time_range: Time range to query

    Returns:
        Dict with trace collection status
    """
    logger.info(f"Collecting traces for {service_name} via Grafana")

    try:
        # Build trace query for the datasource
        query = f'service.name="{service_name}"'

        # Query traces via Grafana (works with Tempo, Jaeger, etc.)
        result = _query_grafana(
            grafana_url=grafana_url,
            query=query,
            datasource_uid=datasource_uid,
            time_range=time_range,
        )

        trace_snapshot = {
            "timestamp": datetime.utcnow().isoformat(),
            "service_name": service_name,
            "time_range": time_range,
            "datasource": datasource_uid,
            "query": query,
            "traces": result.get("results", [{}])[0].get("frames", [])
            if result.get("results")
            else [],
            "status": result.get("status", "error"),
        }

        # Save to file
        with open(output_file, "w") as f:
            json.dump(trace_snapshot, f, indent=2, default=str)

        logger.info(f"[OK] Traces collected for {service_name}")
        logger.info(f"[OK] Traces saved to {output_file}")

        return {"status": "ok", "trace_file": output_file, "datasource": datasource_uid}

    except Exception as e:
        logger.error(f"Failed to collect traces: {str(e)}")
        raise


def collect_log_snapshot(
    grafana_url: str,
    service_name: str,
    output_file: str,
    datasource_uid: str = "loki",
    time_range: str = "1h",
) -> Dict[str, Any]:
    """
    Collect logs for service via Grafana's datasource-agnostic API.
    Works with Loki, Elasticsearch, Datadog, or any Grafana log datasource.

    Args:
        grafana_url: Grafana endpoint URL
        service_name: Service name
        output_file: File path to save logs
        datasource_uid: Grafana datasource UID (default: "loki")
        time_range: Time range to query

    Returns:
        Dict with log collection status
    """
    logger.info(f"Collecting logs for {service_name} via Grafana")

    try:
        # Build log query for the datasource
        query = f'{{service="{service_name}"}}'

        # Query logs via Grafana (works with Loki, Elasticsearch, Datadog, etc.)
        result = _query_grafana(
            grafana_url=grafana_url,
            query=query,
            datasource_uid=datasource_uid,
            time_range=time_range,
        )

        log_snapshot = {
            "timestamp": datetime.utcnow().isoformat(),
            "service_name": service_name,
            "time_range": time_range,
            "datasource": datasource_uid,
            "query": query,
            "logs": result.get("results", [{}])[0].get("frames", [])
            if result.get("results")
            else [],
            "status": result.get("status", "error"),
        }

        # Save to file
        with open(output_file, "w") as f:
            json.dump(log_snapshot, f, indent=2, default=str)

        logger.info(f"[OK] Logs collected for {service_name}")
        logger.info(f"[OK] Logs saved to {output_file}")

        return {"status": "ok", "log_file": output_file, "datasource": datasource_uid}

    except Exception as e:
        logger.error(f"Failed to collect logs: {str(e)}")
        raise
