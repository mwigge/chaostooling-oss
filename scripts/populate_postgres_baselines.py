#!/usr/bin/env python3
"""
Populate PostgreSQL baselines from Grafana dashboard
Reads metrics from dashboard JSON and creates baseline entries
"""

import json
import psycopg2
import psycopg2.extras
import re
import sys
from pathlib import Path

# Database configuration
DB_CONFIG = {
    "host": "localhost",
    "port": 5434,
    "database": "chaos_platform",
    "user": "chaos_admin",
    "password": "chaos_admin_secure_password"
}

# Default baseline statistics (will be used until we have real Prometheus data)
DEFAULT_STATS = {
    # Commit rate metrics
    "rate(postgresql_commits_total[5m])": {
        "mean": 2.5,
        "stddev": 0.8,
        "min": 0.5,
        "max": 5.0,
        "p50": 2.3,
        "p95": 4.2,
        "p99": 4.8,
        "p999": 5.0
    },
    # Rollback rate metrics
    "rate(postgresql_rollbacks_total[5m])": {
        "mean": 0.1,
        "stddev": 0.05,
        "min": 0.0,
        "max": 0.5,
        "p50": 0.08,
        "p95": 0.25,
        "p99": 0.4,
        "p999": 0.5
    },
    # Active connections
    "postgresql_backends": {
        "mean": 15.0,
        "stddev": 5.0,
        "min": 5.0,
        "max": 30.0,
        "p50": 14.0,
        "p95": 25.0,
        "p99": 28.0,
        "p999": 30.0
    },
    # Tuple operations
    "rate(postgresql_tuples_inserted_total[5m])": {
        "mean": 100.0,
        "stddev": 30.0,
        "min": 10.0,
        "max": 200.0,
        "p50": 95.0,
        "p95": 160.0,
        "p99": 185.0,
        "p999": 200.0
    },
    "rate(postgresql_tuples_updated_total[5m])": {
        "mean": 50.0,
        "stddev": 20.0,
        "min": 5.0,
        "max": 120.0,
        "p50": 48.0,
        "p95": 90.0,
        "p99": 110.0,
        "p999": 120.0
    },
    "rate(postgresql_tuples_deleted_total[5m])": {
        "mean": 20.0,
        "stddev": 10.0,
        "min": 2.0,
        "max": 50.0,
        "p50": 18.0,
        "p95": 40.0,
        "p99": 48.0,
        "p999": 50.0
    },
    # Lock metrics
    "postgresql_locks": {
        "mean": 10.0,
        "stddev": 5.0,
        "min": 0.0,
        "max": 30.0,
        "p50": 9.0,
        "p95": 20.0,
        "p99": 28.0,
        "p999": 30.0
    },
    # Deadlock metrics
    "rate(postgresql_deadlocks_total[5m])": {
        "mean": 0.01,
        "stddev": 0.005,
        "min": 0.0,
        "max": 0.05,
        "p50": 0.008,
        "p95": 0.03,
        "p99": 0.045,
        "p999": 0.05
    }
}


def extract_metrics_from_dashboard(dashboard_path):
    """Extract metric names from Grafana dashboard JSON"""
    print(f"\n📊 Loading dashboard: {dashboard_path}")

    with open(dashboard_path) as f:
        dashboard = json.load(f)

    metrics = set()

    # Extract from panels
    for panel in dashboard.get("panels", []):
        # Check targets
        for target in panel.get("targets", []):
            expr = target.get("expr", "")
            if expr:
                # Extract base metric name (remove rate(), functions, labels)
                metric = re.sub(r'\{[^}]*\}', '', expr)  # Remove labels
                metric = re.sub(r'rate\((.*?)\[.*?\]\)', r'\1', metric)  # Extract from rate()
                metric = metric.strip()
                if metric:
                    # Keep the original expression for rate metrics
                    if "rate(" in expr:
                        metrics.add(expr.split("{")[0].strip())
                    else:
                        metrics.add(metric)

    print(f"✓ Found {len(metrics)} unique metrics")
    return sorted(metrics)


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

    # Calculate sigma bounds
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
            stddev_value = EXCLUDED.stddev_value,
            min_value = EXCLUDED.min_value,
            max_value = EXCLUDED.max_value,
            p50 = EXCLUDED.p50,
            p95 = EXCLUDED.p95,
            p99 = EXCLUDED.p99,
            p999 = EXCLUDED.p999,
            lower_bound_2sigma = EXCLUDED.lower_bound_2sigma,
            upper_bound_2sigma = EXCLUDED.upper_bound_2sigma,
            upper_bound_3sigma = EXCLUDED.upper_bound_3sigma
        """,
        (
            service_id,
            metric_name,
            stats["mean"],
            stats.get("p50", stats["mean"]),  # Use p50 as median
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
            14,  # analysis_period_days
            1000,  # sample_count
            95.0  # data_completeness_percent
        )
    )


def populate_baselines(dashboard_path):
    """Main function to populate baselines"""

    print("\n" + "="*80)
    print("PostgreSQL Baseline Population")
    print("="*80)

    # Extract metrics from dashboard
    metrics = extract_metrics_from_dashboard(dashboard_path)

    # Connect to database
    print(f"\n🔌 Connecting to database: {DB_CONFIG['host']}:{DB_CONFIG['port']}")
    conn = psycopg2.connect(**DB_CONFIG)
    conn.autocommit = False

    try:
        cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

        # Get or create service
        service_id = get_or_create_service(cursor, "postgres")
        print(f"✓ Service ID: {service_id}")

        # Insert baselines
        print(f"\n📝 Inserting baseline metrics...")
        success_count = 0
        skipped_count = 0

        for metric in metrics:
            # Try to find matching stats (with or without rate wrapper)
            stats = None

            # First try exact match
            if metric in DEFAULT_STATS:
                stats = DEFAULT_STATS[metric]
            else:
                # Try to find partial match
                for key in DEFAULT_STATS:
                    if key in metric or metric in key:
                        stats = DEFAULT_STATS[key]
                        break

            if stats:
                insert_baseline_metric(cursor, service_id, metric, stats)
                print(f"  ✓ {metric}")
                success_count += 1
            else:
                print(f"  ⊘ Skipped (no default stats): {metric}")
                skipped_count += 1

        # Commit transaction
        conn.commit()

        print(f"\n" + "="*80)
        print(f"✅ Baseline population complete!")
        print(f"   - Inserted/Updated: {success_count}")
        print(f"   - Skipped: {skipped_count}")
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
    dashboard_path = Path(__file__).parent.parent / "chaostooling-demo" / "dashboards" / "extensive_postgres_dashboard.json"

    if not dashboard_path.exists():
        print(f"❌ Dashboard not found: {dashboard_path}")
        print("\nUsage:")
        print(f"  python3 {sys.argv[0]} [dashboard_path]")
        sys.exit(1)

    # Allow custom dashboard path
    if len(sys.argv) > 1:
        dashboard_path = Path(sys.argv[1])

    populate_baselines(dashboard_path)
