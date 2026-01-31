#!/usr/bin/env python3
"""
DEPRECATED: This tool has been merged into baseline_manager.py

Please use baseline_manager.py instead:
    python baseline_manager.py sync --system postgres --dashboard postgres.json

This file is kept for backward compatibility and will be removed in a future release.
"""

import sys
import warnings

warnings.warn(
    "baseline_metrics_sync.py is deprecated. Use 'baseline_manager.py sync' instead.",
    DeprecationWarning,
    stacklevel=2,
)

print("\n" + "=" * 80)
print("⚠️  DEPRECATION WARNING")
print("=" * 80)
print("This tool has been merged into baseline_manager.py")
print("\nPlease use instead:")
print(
    "  python baseline_manager.py sync --system <system> --dashboard <dashboard.json>"
)
print("\nFor more options, run:")
print("  python baseline_manager.py sync --help")
print("=" * 80 + "\n")

sys.exit(1)
"""
Baseline Metrics Sync Tool

Extracts metrics from Grafana dashboards and injects baseline data into chaos_platform database.

Features:
- Queries Grafana API for available metrics
- Validates metrics against Prometheus
- Calculates baseline statistics (mean, stdev, percentiles)
- Stores baselines in chaos_platform.baseline_metrics table
- Supports multiple database systems (PostgreSQL, MySQL, MongoDB, Cassandra, Redis, etc.)

Usage:
    python baseline_metrics_sync.py --system postgres --dashboard postgres_dashboard.json
    python baseline_metrics_sync.py --all  # Sync all systems
    python baseline_metrics_sync.py --verify  # Verify all metrics in database
"""

import argparse
import json
import logging
import os
import statistics
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional

import psycopg2
import psycopg2.extras
import requests

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


@dataclass
class MetricBaseline:
    """Baseline statistics for a single metric."""

    metric_name: str
    service_name: str
    metric_type: str  # gauge, counter, histogram, summary, derived
    unit: str
    description: str
    mean: float
    stdev: float
    min_value: float
    max_value: float
    percentile_50: float
    percentile_95: float
    percentile_99: float
    percentile_999: Optional[float] = None
    min_valid: float = 0.0
    max_valid: float = 1000000.0
    datasource: str = "prometheus"
    time_range: str = "24h"
    phase: str = "normal"
    status: str = "valid"
    collection_timestamp: str = None

    def __post_init__(self):
        if self.collection_timestamp is None:
            self.collection_timestamp = datetime.utcnow().isoformat()


class GrafanaDashboardParser:
    """Parse Grafana dashboard JSON to extract metrics."""

    def __init__(self, dashboard_path: str):
        self.dashboard_path = dashboard_path
        self.dashboard_data = self._load_dashboard()

    def _load_dashboard(self) -> dict:
        """Load dashboard JSON file."""
        try:
            with open(self.dashboard_path) as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError) as e:
            logger.error(f"Failed to load dashboard {self.dashboard_path}: {e}")
            raise

    def extract_metrics(self) -> list[str]:
        """Extract unique metric names from dashboard."""
        metrics = set()

        if "panels" not in self.dashboard_data:
            return []

        for panel in self.dashboard_data["panels"]:
            # Skip title/description panels
            if panel.get("type") == "row":
                continue

            targets = panel.get("targets", [])
            for target in targets:
                if "expr" in target:
                    # Extract metric name from PromQL expression
                    metric = self._extract_metric_name(target["expr"])
                    if metric:
                        metrics.add(metric)

        return sorted(list(metrics))

    def _extract_metric_name(self, expr: str) -> Optional[str]:
        """Extract metric name from PromQL expression."""
        # Simple extraction - handles most common cases
        # Examples:
        # - rate(postgresql_commits_total[5m]) -> postgresql_commits_total
        # - chaos_db_query_count_total{db_system="postgresql"} -> chaos_db_query_count_total
        # - histogram_quantile(0.95, metric) -> metric

        import re

        # Remove function calls and labels
        cleaned = re.sub(r"[a-z_]+\(", "", expr)  # Remove function calls
        cleaned = re.sub(r"\{[^}]*\}", "", cleaned)  # Remove labels
        cleaned = re.sub(r"\[[^\]]*\]", "", cleaned)  # Remove duration
        cleaned = re.sub(r"[(),]", " ", cleaned)  # Remove special chars
        cleaned = re.sub(r"\s+", " ", cleaned).strip()

        # Extract first valid metric name
        tokens = cleaned.split()
        for token in tokens:
            if token and not token.isdigit() and "." not in token:
                return token

        return None


class PrometheusMetricsValidator:
    """Validate metrics exist in Prometheus and fetch sample data."""

    def __init__(self, prometheus_url: str):
        self.prometheus_url = prometheus_url.rstrip("/")
        self.session = requests.Session()

    def metric_exists(self, metric_name: str) -> bool:
        """Check if metric exists in Prometheus."""
        try:
            # Check if metric returned any data in the last hour
            query = f"last_over_time({metric_name}[1h])"
            response = self.session.get(
                f"{self.prometheus_url}/api/v1/query",
                params={"query": query},
                timeout=5,
            )

            if response.status_code != 200:
                logger.warning(
                    f"Prometheus query failed for {metric_name}: {response.status_code}"
                )
                return False

            data = response.json()
            return data.get("data", {}).get("result", []) != []
        except Exception as e:
            logger.warning(f"Error validating metric {metric_name}: {e}")
            return False

    def get_metric_statistics(
        self, metric_name: str, time_range: str = "24h"
    ) -> Optional[dict]:
        """Fetch metric data and calculate statistics."""
        try:
            # Query metric values over time range
            query = f"{metric_name}"
            response = self.session.get(
                f"{self.prometheus_url}/api/v1/query_range",
                params={
                    "query": query,
                    "start": (datetime.utcnow() - timedelta(hours=24)).isoformat()
                    + "Z",
                    "end": datetime.utcnow().isoformat() + "Z",
                    "step": "60",
                },
                timeout=30,
            )

            if response.status_code != 200:
                return None

            data = response.json()
            results = data.get("data", {}).get("result", [])

            if not results:
                return None

            # Extract all values from all series
            values = []
            for series in results:
                for timestamp, value in series.get("values", []):
                    try:
                        values.append(float(value))
                    except (ValueError, TypeError):
                        continue

            if not values:
                return None

            # Calculate statistics
            values.sort()
            stats = {
                "mean": statistics.mean(values),
                "stdev": statistics.stdev(values) if len(values) > 1 else 0,
                "min": min(values),
                "max": max(values),
                "count": len(values),
                "percentile_50": self._percentile(values, 50),
                "percentile_95": self._percentile(values, 95),
                "percentile_99": self._percentile(values, 99),
                "percentile_999": self._percentile(values, 99.9),
            }

            return stats
        except Exception as e:
            logger.warning(f"Error fetching statistics for {metric_name}: {e}")
            return None

    @staticmethod
    def _percentile(data: list[float], percentile: float) -> float:
        """Calculate percentile value."""
        if not data:
            return 0.0
        index = (len(data) - 1) * percentile / 100
        if index == int(index):
            return data[int(index)]
        lower = int(index)
        upper = lower + 1
        weight = index - lower
        return data[lower] * (1 - weight) + data[upper] * weight


class ChaosplatformDatabaseWriter:
    """Write baseline metrics to chaos_platform database."""

    def __init__(self, db_host: str, db_port: int, db_user: str, db_password: str):
        self.db_host = db_host
        self.db_port = db_port
        self.db_user = db_user
        self.db_password = db_password
        self.connection = None

    def connect(self):
        """Establish database connection."""
        try:
            self.connection = psycopg2.connect(
                host=self.db_host,
                port=self.db_port,
                database="chaos_platform",
                user=self.db_user,
                password=self.db_password,
            )
            logger.info(
                f"Connected to chaos_platform database at {self.db_host}:{self.db_port}"
            )
        except psycopg2.Error as e:
            logger.error(f"Failed to connect to database: {e}")
            raise

    def disconnect(self):
        """Close database connection."""
        if self.connection:
            self.connection.close()

    def insert_baseline_metric(self, baseline: MetricBaseline) -> bool:
        """Insert baseline metric into database."""
        if not self.connection:
            logger.error("Database not connected")
            return False

        try:
            cursor = self.connection.cursor()

            # Check if metric already exists
            cursor.execute(
                "SELECT id FROM baseline_metrics WHERE metric_name = %s AND service_name = %s",
                (baseline.metric_name, baseline.service_name),
            )

            existing = cursor.fetchone()

            if existing:
                # Update existing metric
                cursor.execute(
                    """
                    UPDATE baseline_metrics SET
                        metric_type = %s,
                        unit = %s,
                        description = %s,
                        mean = %s,
                        stdev = %s,
                        min_value = %s,
                        max_value = %s,
                        percentile_50 = %s,
                        percentile_95 = %s,
                        percentile_99 = %s,
                        percentile_999 = %s,
                        min_valid = %s,
                        max_valid = %s,
                        status = %s,
                        collection_timestamp = %s
                    WHERE metric_name = %s AND service_name = %s
                """,
                    (
                        baseline.metric_type,
                        baseline.unit,
                        baseline.description,
                        baseline.mean,
                        baseline.stdev,
                        baseline.min_value,
                        baseline.max_value,
                        baseline.percentile_50,
                        baseline.percentile_95,
                        baseline.percentile_99,
                        baseline.percentile_999,
                        baseline.min_valid,
                        baseline.max_valid,
                        baseline.status,
                        baseline.collection_timestamp,
                        baseline.metric_name,
                        baseline.service_name,
                    ),
                )
                logger.info(
                    f"Updated baseline metric: {baseline.metric_name} ({baseline.service_name})"
                )
            else:
                # Insert new metric
                cursor.execute(
                    """
                    INSERT INTO baseline_metrics
                    (metric_name, service_name, metric_type, unit, description,
                     mean, stdev, min_value, max_value,
                     percentile_50, percentile_95, percentile_99, percentile_999,
                     min_valid, max_valid, datasource, time_range, phase, status,
                     collection_timestamp)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                    (
                        baseline.metric_name,
                        baseline.service_name,
                        baseline.metric_type,
                        baseline.unit,
                        baseline.description,
                        baseline.mean,
                        baseline.stdev,
                        baseline.min_value,
                        baseline.max_value,
                        baseline.percentile_50,
                        baseline.percentile_95,
                        baseline.percentile_99,
                        baseline.percentile_999,
                        baseline.min_valid,
                        baseline.max_valid,
                        baseline.datasource,
                        baseline.time_range,
                        baseline.phase,
                        baseline.status,
                        baseline.collection_timestamp,
                    ),
                )
                logger.info(
                    f"Inserted baseline metric: {baseline.metric_name} ({baseline.service_name})"
                )

            self.connection.commit()
            cursor.close()
            return True
        except psycopg2.Error as e:
            logger.error(f"Database error inserting baseline metric: {e}")
            if self.connection:
                self.connection.rollback()
            return False

    def get_baseline_metrics(self, service_name: str) -> list[dict]:
        """Retrieve baseline metrics for a service."""
        if not self.connection:
            logger.error("Database not connected")
            return []

        try:
            cursor = self.connection.cursor(
                cursor_factory=psycopg2.extras.RealDictCursor
            )
            cursor.execute(
                "SELECT * FROM baseline_metrics WHERE service_name = %s ORDER BY metric_name",
                (service_name,),
            )
            results = cursor.fetchall()
            cursor.close()
            return [dict(row) for row in results]
        except psycopg2.Error as e:
            logger.error(f"Database error retrieving metrics: {e}")
            return []


class BaselineMetricsSyncOrchestrator:
    """Orchestrate the entire baseline metrics sync process."""

    # Metric type definitions and aliases
    METRIC_TYPE_ALIASES = {
        "commits": "counter",
        "rollbacks": "counter",
        "deadlocks": "counter",
        "errors": "counter",
        "latency": "histogram",
        "duration": "histogram",
        "utilization": "gauge",
        "ratio": "gauge",
        "rate": "gauge",
    }

    # Metric descriptions
    METRIC_DESCRIPTIONS = {
        "postgresql_commits_total": "PostgreSQL transaction commits",
        "rate(postgresql_commits_total": "PostgreSQL commit rate",
        "postgresql_rollbacks_total": "PostgreSQL transaction rollbacks",
        "db_transaction_deadlocks_total": "Database transaction deadlocks",
        "chaos_db_query_count_total": "Total database queries executed",
        "chaos_db_query_latency_milliseconds_sum": "Sum of query latencies",
        "chaos_db_connection_pool_utilization_percent": "Connection pool utilization percentage",
    }

    # Default statistics for metrics without Prometheus data (fallback)
    DEFAULT_STATISTICS = {
        "postgresql_commits_total": {
            "mean": 150.5,
            "stdev": 45.3,
            "min": 50.0,
            "max": 300.0,
            "percentile_50": 140.0,
            "percentile_95": 220.0,
            "percentile_99": 280.0,
            "percentile_999": 300.0,
        },
        "rate(postgresql_commits_total[5m])": {
            "mean": 2.51,
            "stdev": 0.76,
            "min": 0.8,
            "max": 5.0,
            "percentile_50": 2.33,
            "percentile_95": 3.67,
            "percentile_99": 4.67,
            "percentile_999": 5.0,
        },
        "chaos_db_query_count_total": {
            "mean": 15000.0,
            "stdev": 3500.0,
            "min": 5000.0,
            "max": 30000.0,
            "percentile_50": 14000.0,
            "percentile_95": 22000.0,
            "percentile_99": 28000.0,
            "percentile_999": 30000.0,
        },
    }

    def __init__(self, config: dict):
        self.config = config
        self.prometheus = PrometheusMetricsValidator(config["prometheus_url"])
        self.db = ChaosplatformDatabaseWriter(
            config["chaos_db_host"],
            config["chaos_db_port"],
            config["chaos_db_user"],
            config["chaos_db_password"],
        )

    def sync_system(self, system: str, dashboard_path: str) -> tuple[int, int]:
        """Sync all metrics for a database system."""
        logger.info(f"\n{'=' * 60}")
        logger.info(f"Syncing baseline metrics for {system.upper()}")
        logger.info(f"Dashboard: {dashboard_path}")
        logger.info(f"{'=' * 60}\n")

        # Parse dashboard
        try:
            parser = GrafanaDashboardParser(dashboard_path)
            metrics = parser.extract_metrics()
        except Exception as e:
            logger.error(f"Failed to parse dashboard: {e}")
            return 0, 0

        if not metrics:
            logger.warning(f"No metrics found in dashboard {dashboard_path}")
            return 0, 0

        logger.info(f"Found {len(metrics)} unique metrics in dashboard")

        # Connect to database
        try:
            self.db.connect()
        except Exception as e:
            logger.error(f"Failed to connect to database: {e}")
            return 0, 0

        # Process each metric
        success_count = 0
        fail_count = 0

        for metric_name in metrics:
            logger.info(f"\nProcessing metric: {metric_name}")

            # Validate metric exists in Prometheus
            if not self.prometheus.metric_exists(metric_name):
                logger.warning(
                    "  ⚠️  Metric not found in Prometheus, using default statistics"
                )
                # Use default statistics
                stats = self.DEFAULT_STATISTICS.get(
                    metric_name,
                    {
                        "mean": 100.0,
                        "stdev": 20.0,
                        "min": 10.0,
                        "max": 200.0,
                        "percentile_50": 95.0,
                        "percentile_95": 160.0,
                        "percentile_99": 190.0,
                        "percentile_999": 200.0,
                    },
                )
            else:
                logger.info("  ✓ Metric found in Prometheus")
                # Fetch actual statistics
                stats = self.prometheus.get_metric_statistics(metric_name)
                if stats is None:
                    logger.warning("  ⚠️  Could not fetch statistics, using defaults")
                    stats = self.DEFAULT_STATISTICS.get(metric_name, {})
                else:
                    logger.info(
                        f"  ✓ Statistics: mean={stats['mean']:.2f}, stdev={stats['stdev']:.2f}"
                    )

            # Determine metric type
            metric_type = self._determine_metric_type(metric_name)

            # Create baseline object
            baseline = MetricBaseline(
                metric_name=metric_name,
                service_name=system,
                metric_type=metric_type,
                unit=self._determine_unit(metric_name),
                description=self.METRIC_DESCRIPTIONS.get(
                    metric_name, f"{system} metric: {metric_name}"
                ),
                mean=stats.get("mean", 100.0),
                stdev=stats.get("stdev", 20.0),
                min_value=stats.get("min", 0.0),
                max_value=stats.get("max", 1000.0),
                percentile_50=stats.get("percentile_50", stats.get("mean", 100.0)),
                percentile_95=stats.get("percentile_95", 200.0),
                percentile_99=stats.get("percentile_99", 250.0),
                percentile_999=stats.get("percentile_999", 300.0),
            )

            # Insert into database
            if self.db.insert_baseline_metric(baseline):
                success_count += 1
                logger.info("  ✓ Baseline metric stored in database")
            else:
                fail_count += 1
                logger.error("  ✗ Failed to store baseline metric")

        self.db.disconnect()

        logger.info(f"\n{'=' * 60}")
        logger.info(
            f"Sync complete for {system}: {success_count} success, {fail_count} failed"
        )
        logger.info(f"{'=' * 60}\n")

        return success_count, fail_count

    def _determine_metric_type(self, metric_name: str) -> str:
        """Determine metric type from metric name."""
        metric_lower = metric_name.lower()

        for keyword, metric_type in self.METRIC_TYPE_ALIASES.items():
            if keyword in metric_lower:
                return metric_type

        # Default to gauge
        return "gauge"

    def _determine_unit(self, metric_name: str) -> str:
        """Determine unit from metric name."""
        metric_lower = metric_name.lower()

        if "percent" in metric_lower or "utilization" in metric_lower:
            return "percent"
        elif "bytes" in metric_lower or "size" in metric_lower:
            return "bytes"
        elif "milliseconds" in metric_lower or "latency" in metric_lower:
            return "milliseconds"
        elif "rate" in metric_lower:
            return "per_second"
        else:
            return "count"


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Sync baseline metrics from Grafana dashboards to chaos_platform database"
    )
    parser.add_argument(
        "--system",
        choices=[
            "postgres",
            "mysql",
            "mongodb",
            "cassandra",
            "redis",
            "rabbitmq",
            "kafka",
            "mssql",
        ],
        help="Database system to sync",
    )
    parser.add_argument("--dashboard", help="Path to Grafana dashboard JSON file")
    parser.add_argument("--all", action="store_true", help="Sync all systems")
    parser.add_argument(
        "--verify", action="store_true", help="Verify all metrics in database"
    )
    parser.add_argument(
        "--prometheus-url",
        default=os.getenv("PROMETHEUS_URL", "http://prometheus:9090"),
        help="Prometheus URL (default: http://prometheus:9090)",
    )
    parser.add_argument(
        "--db-host",
        default=os.getenv("CHAOS_DB_HOST", "localhost"),
        help="Chaos platform database host",
    )
    parser.add_argument(
        "--db-port",
        type=int,
        default=int(os.getenv("CHAOS_DB_PORT", 5432)),
        help="Chaos platform database port",
    )
    parser.add_argument(
        "--db-user",
        default=os.getenv("CHAOS_DB_USER", "chaos_admin"),
        help="Chaos platform database user",
    )
    parser.add_argument(
        "--db-password",
        default=os.getenv("CHAOS_DB_PASSWORD", ""),
        help="Chaos platform database password",
    )

    args = parser.parse_args()

    # Load configuration
    config = {
        "prometheus_url": args.prometheus_url,
        "chaos_db_host": args.db_host,
        "chaos_db_port": args.db_port,
        "chaos_db_user": args.db_user,
        "chaos_db_password": args.db_password,
    }

    # Create orchestrator
    orchestrator = BaselineMetricsSyncOrchestrator(config)

    if args.verify:
        # Verify metrics in database
        logger.info("Verifying baseline metrics in database...")
        # TODO: Implement verification logic
    elif args.all:
        # Sync all systems
        total_success = 0
        total_fail = 0

        systems = {
            "postgres": "chaostooling-demo/dashboards/extensive_postgres_dashboard.json",
            "mysql": "chaostooling-demo/dashboards/mysql_dashboard.json",
            "mongodb": "chaostooling-demo/dashboards/mongodb_dashboard.json",
            "cassandra": "chaostooling-demo/dashboards/cassandra_dashboard.json",
            "redis": "chaostooling-demo/dashboards/redis_dashboard.json",
        }

        for system, dashboard in systems.items():
            if os.path.exists(dashboard):
                success, fail = orchestrator.sync_system(system, dashboard)
                total_success += success
                total_fail += fail

        logger.info(f"\nTotal: {total_success} success, {total_fail} failed")
    elif args.system and args.dashboard:
        # Sync specific system
        orchestrator.sync_system(args.system, args.dashboard)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
