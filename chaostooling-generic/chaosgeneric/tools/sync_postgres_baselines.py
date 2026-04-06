#!/usr/bin/env python3
"""Sync PostgreSQL baseline metrics from Prometheus to chaos_platform database."""

import os
import sys
from datetime import datetime, timedelta
from typing import Optional

import requests
from baseline_manager import calculate_statistics

from chaosgeneric.data.chaos_db import ChaosDb

# List of postgresql metrics to sync
METRICS = [
    "postgresql_commits_total",
    "postgresql_rollbacks_total",
    "postgresql_connections",
    "postgresql_database_size_bytes",
    "postgresql_numbackends",
    "postgresql_backends",
    "postgresql_bgwriter_buffers_allocated_total",
    "postgresql_bgwriter_buffers_writes_total",
    "chaos_db_connection_pool_utilization_percent",
    "chaos_db_query_count_total",
    "chaos_db_lock_count_total",
    "chaos_db_error_count_total",
    "chaos_db_cache_hit_ratio",
    "chaos_db_active_sessions_ratio",
    "chaos_db_active_transactions_ratio",
]

# Configuration
PROMETHEUS_URL = "http://prometheus:9090"
DB_HOST = "chaos-platform-db"
DB_PORT = 5432
DB_USER = os.getenv("CHAOS_DB_USER", "changeme")
DB_PASSWORD = os.getenv("CHAOS_DB_PASSWORD", "changeme")
SERVICE_NAME = "postgres"
TIME_RANGE_DAYS = 30


def sync_metric(metric_name: str, db: ChaosDb) -> Optional[dict]:
    """Sync a single metric from Prometheus to database."""
    try:
        # Query Prometheus for metric data
        time_range = timedelta(days=TIME_RANGE_DAYS)
        end_time = datetime.utcnow()
        start_time = end_time - time_range

        query = metric_name
        response = requests.get(
            f"{PROMETHEUS_URL}/api/v1/query_range",
            params={
                "query": query,
                "start": int(start_time.timestamp()),
                "end": int(end_time.timestamp()),
                "step": "3600",  # 1 hour steps
            },
            timeout=30,
        )

        if response.status_code != 200:
            print(f"  ✗ {metric_name}: Query failed ({response.status_code})")
            return None

        data = response.json()
        if data.get("status") != "success":
            error = data.get("error", "Unknown error")
            print(f"  ✗ {metric_name}: {error}")
            return None

        # Extract values
        values = []
        for result in data.get("data", {}).get("result", []):
            for point in result.get("values", []):
                try:
                    values.append(float(point[1]))
                except (ValueError, TypeError, IndexError):
                    continue

        if not values:
            print(f"  ⚠ {metric_name}: No data points")
            return None

        # Calculate statistics
        stats = calculate_statistics(values)

        # Return metric data for batch save
        metric_data = {
            "mean": stats["mean"],
            "p50": stats["p50"],
            "p95": stats["p95"],
            "p99": stats["p99"],
            "stddev": stats["stdev"],
            "min": stats["min"],
            "max": stats["max"],
        }

        print(
            f"  ✓ {metric_name}: Collected (mean: {stats['mean']:.2f}, "
            f"data points: {len(values)})"
        )
        return metric_data

    except Exception as e:
        print(f"  ✗ {metric_name}: Error - {str(e)}")
        return None


def main() -> None:
    """Main sync function."""
    print(f"Syncing {len(METRICS)} PostgreSQL metrics from Prometheus...")
    print(f"Time range: {TIME_RANGE_DAYS} days")
    print(f"Prometheus: {PROMETHEUS_URL}")
    print(f"Database: {DB_HOST}:{DB_PORT}")
    print()

    # Connect to database (auto-connects on init)
    try:
        db = ChaosDb(
            dbname="chaos_platform",
            user=DB_USER,
            password=DB_PASSWORD,
            host=DB_HOST,
            port=DB_PORT,
        )
    except Exception as e:
        print(f"✗ Database connection failed: {e}")
        sys.exit(1)

    # Collect all metrics first
    all_metrics_data = {}
    success_count = 0
    failed_count = 0

    for metric_name in METRICS:
        metric_data = sync_metric(metric_name, db)
        if metric_data:
            all_metrics_data[metric_name] = metric_data
            success_count += 1
        else:
            failed_count += 1

    # Save all metrics in batch
    if all_metrics_data:
        try:
            baseline_ids = db.save_baseline_metrics_batch(
                service_name=SERVICE_NAME, metrics=all_metrics_data
            )
            print(f"\n✓ Saved {len(baseline_ids)} baselines to database")
        except Exception as e:
            print(f"\n✗ Batch save failed: {e}")

    print()
    print("=" * 80)
    print(f"Sync complete: {success_count} success, {failed_count} failed")
    print("=" * 80)


if __name__ == "__main__":
    main()
