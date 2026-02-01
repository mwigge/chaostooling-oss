#!/usr/bin/env python3
"""
Sync PostgreSQL baselines from Prometheus to chaos_platform database
Queries Prometheus directly for actual metric values
"""

import statistics
import sys
from datetime import datetime, timedelta

import psycopg2
import psycopg2.extras
import requests

# Configuration
PROMETHEUS_URL = "http://localhost:9090"
DB_CONFIG = {
    "host": "localhost",
    "port": 5434,
    "database": "chaos_platform",
    "user": "chaos_admin",
    "password": "chaos_admin_secure_password"
}

# Metrics to sync (from your dashboard)
POSTGRES_METRICS = [
    "postgresql_commits_total",
    "postgresql_rollbacks_total",
    "postgresql_backends",
    "postgresql_tuples_inserted_total",
    "postgresql_tuples_updated_total",
    "postgresql_tuples_deleted_total",
    "postgresql_locks",
    "postgresql_deadlocks_total",
    "postgresql_blocks_read_total",
    "postgresql_bgwriter_buffers_allocated_total",
    "postgresql_bgwriter_buffers_writes_total",
    "postgresql_table_vacuum_count_total",
]


def query_prometheus(query, start_time, end_time, step="60"):
    """Query Prometheus for time series data"""
    try:
        params = {
            "query": query,
            "start": int(start_time.timestamp()),
            "end": int(end_time.timestamp()),
            "step": step
        }

        response = requests.get(
            f"{PROMETHEUS_URL}/api/v1/query_range",
            params=params,
            timeout=30
        )
        response.raise_for_status()
        data = response.json()

        if data.get("status") == "success":
            return data["data"]["result"]
        else:
            print(f"  ✗ Query failed: {data.get('error')}")
            return []
    except Exception as e:
        print(f"  ✗ Prometheus query error: {e}")
        return []


def calculate_statistics(values):
    """Calculate baseline statistics from values"""
    if not values or len(values) < 2:
        return None

    try:
        mean = statistics.mean(values)
        stdev = statistics.stdev(values) if len(values) > 1 else 0
        min_val = min(values)
        max_val = max(values)

        sorted_values = sorted(values)
        p50 = statistics.median(sorted_values)
        p95 = sorted_values[int(len(sorted_values) * 0.95)] if len(sorted_values) > 0 else max_val
        p99 = sorted_values[int(len(sorted_values) * 0.99)] if len(sorted_values) > 0 else max_val
        p999 = sorted_values[int(len(sorted_values) * 0.999)] if len(sorted_values) > 1 else max_val

        return {
            "mean": mean,
            "stddev": stdev,
            "min": min_val,
            "max": max_val,
            "p50": p50,
            "p95": p95,
            "p99": p99,
            "p999": p999
        }
    except Exception as e:
        print(f"  ✗ Statistics calculation error: {e}")
        return None


def fetch_metric_stats(metric_name, time_range_hours=24, use_rate=True):
    """Fetch metric data from Prometheus and calculate statistics"""
    end_time = datetime.utcnow()
    start_time = end_time - timedelta(hours=time_range_hours)

    # Build query - use rate() for counter metrics
    if use_rate and ("_total" in metric_name or "count" in metric_name):
        query = f"rate({metric_name}[5m])"
        display_name = f"rate({metric_name}[5m])"
    else:
        query = metric_name
        display_name = metric_name

    print(f"\n📊 Processing: {display_name}")

    # Query Prometheus
    results = query_prometheus(query, start_time, end_time)

    if not results:
        print("  ⊘ No data found in Prometheus")
        return None, None

    # Extract values from all series
    all_values = []
    for series in results:
        values = series.get("values", [])
        for timestamp, value in values:
            try:
                all_values.append(float(value))
            except (ValueError, TypeError):
                continue

    if not all_values:
        print("  ⊘ No valid values found")
        return None, None

    # Calculate statistics
    stats = calculate_statistics(all_values)

    if stats:
        print(f"  ✓ Found {len(all_values)} data points")
        print(f"    Mean: {stats['mean']:.4f}, StdDev: {stats['stddev']:.4f}")
        print(f"    P95: {stats['p95']:.4f}, P99: {stats['p99']:.4f}")
        return display_name, stats
    else:
        print("  ⊘ Failed to calculate statistics")
        return None, None


def get_or_create_service(cursor, service_name="postgres"):
    """Get or create service record"""
    cursor.execute(
        """
        SELECT service_id FROM chaos_platform.services
        WHERE service_name = %s
        """,
        (service_name,)
    )

    row = cursor.fetchone()
    if row:
        return row[0]

    # Create service
    cursor.execute(
        """
        INSERT INTO chaos_platform.services (service_name, environment, team_name)
        VALUES (%s, 'production', 'platform')
        RETURNING service_id
        """,
        (service_name,)
    )

    return cursor.fetchone()[0]


def insert_baseline_metric(cursor, service_id, metric_name, stats):
    """Insert or update baseline metric"""
    mean = stats["mean"]
    stddev = stats["stddev"]
    lower_2sigma = mean - (2 * stddev)
    upper_2sigma = mean + (2 * stddev)
    upper_3sigma = mean + (3 * stddev)

    cursor.execute(
        """
        INSERT INTO chaos_platform.baseline_metrics (
            service_id, metric_name,
            mean_value, median_value, stddev_value, min_value, max_value,
            p50, p95, p99, p999,
            lower_bound_2sigma, upper_bound_2sigma, upper_bound_3sigma,
            analysis_period_days, sample_count, data_completeness_percent,
            analysis_date, is_active
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, CURRENT_DATE, true)
        ON CONFLICT (service_id, metric_name, analysis_date, version)
        DO UPDATE SET
            mean_value = EXCLUDED.mean_value,
            median_value = EXCLUDED.median_value,
            stddev_value = EXCLUDED.stddev_value,
            min_value = EXCLUDED.min_value,
            max_value = EXCLUDED.max_value,
            p50 = EXCLUDED.p50,
            p95 = EXCLUDED.p95,
            p99 = EXCLUDED.p99,
            p999 = EXCLUDED.p999,
            lower_bound_2sigma = EXCLUDED.lower_bound_2sigma,
            upper_bound_2sigma = EXCLUDED.upper_bound_2sigma,
            upper_bound_3sigma = EXCLUDED.upper_bound_3sigma,
            sample_count = EXCLUDED.sample_count,
            data_completeness_percent = EXCLUDED.data_completeness_percent
        """,
        (
            service_id,
            metric_name,
            stats["mean"],
            stats["p50"],
            stats["stddev"],
            stats["min"],
            stats["max"],
            stats["p50"],
            stats["p95"],
            stats["p99"],
            stats["p999"],
            lower_2sigma,
            upper_2sigma,
            upper_3sigma,
            24,  # analysis_period_days
            len(stats.get("values", [])) if "values" in stats else 1000,
            95.0  # data_completeness_percent
        )
    )


def sync_baselines(time_range_hours=24):
    """Main sync function"""
    print("\n" + "="*80)
    print("PostgreSQL Baseline Sync from Prometheus")
    print("="*80)
    print(f"Prometheus URL: {PROMETHEUS_URL}")
    print(f"Time Range: Last {time_range_hours} hours")

    # Connect to database
    print(f"\n🔌 Connecting to database: {DB_CONFIG['host']}:{DB_CONFIG['port']}")
    conn = psycopg2.connect(**DB_CONFIG)
    conn.autocommit = False

    try:
        cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

        # Get or create service
        service_id = get_or_create_service(cursor, "postgres")
        print(f"✓ Service ID: {service_id}")

        # Process each metric
        print(f"\n📝 Syncing {len(POSTGRES_METRICS)} metrics...")
        success_count = 0
        failed_count = 0

        for base_metric in POSTGRES_METRICS:
            metric_name, stats = fetch_metric_stats(base_metric, time_range_hours)

            if stats:
                insert_baseline_metric(cursor, service_id, metric_name, stats)
                success_count += 1
            else:
                failed_count += 1

        # Commit transaction
        conn.commit()

        print("\n" + "="*80)
        print("✅ Sync complete!")
        print(f"   - Synced: {success_count}")
        print(f"   - Failed: {failed_count}")
        print("="*80)

        # Verify
        cursor.execute(
            """
            SELECT COUNT(*) FROM chaos_platform.baseline_metrics
            WHERE service_id = %s AND is_active = true
            """,
            (service_id,)
        )
        count = cursor.fetchone()[0]
        print(f"\n📊 Total active baselines for postgres: {count}")

    except Exception as e:
        conn.rollback()
        print(f"\n❌ Error: {e}")
        raise
    finally:
        cursor.close()
        conn.close()


if __name__ == "__main__":
    # Allow custom time range
    time_range = 24
    if len(sys.argv) > 1:
        time_range = int(sys.argv[1])

    sync_baselines(time_range)
