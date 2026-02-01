#!/usr/bin/env python3
"""
Unified Baseline Manager

Consolidates baseline metrics sync, validation, and analysis into a single tool.

This tool provides comprehensive baseline management:
1. Sync: Extract from Grafana/Prometheus → store in database
2. Validate: Validate baselines in database or files
3. Analyze: Full steady state analysis (SLOs, topology, anomalies)
4. Generate: Create baseline_metrics.json files (legacy)
5. Query: Query baseline data from database

Usage Examples:
    # Sync from Grafana to database
    python baseline_manager.py sync --system postgres --dashboard postgres.json

    # Validate all baselines in database
    python baseline_manager.py validate --source database --all-systems

    # Full steady state analysis
    python baseline_manager.py analyze --period 14d --output-dir ./analysis/

    # Generate legacy baseline file
    python baseline_manager.py generate --system postgres --output baselines.json

    # Query baseline data
    python baseline_manager.py query --system postgres --metric pg_commits
"""

import argparse
import json
import logging
import os
import statistics
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Optional

try:
    import psycopg2
    import psycopg2.extras
except ImportError:
    psycopg2 = None

try:
    import requests
except ImportError:
    requests = None

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Configuration
EXPERIMENTS_DIR = Path(
    os.getenv(
        "EXPERIMENTS_DIR",
        "/home/morgan/dev/src/chaostooling-oss/chaostooling-experiments",
    )
)
EXPECTED_DATABASES = [
    "postgres",
    "mysql",
    "mongodb",
    "redis",
    "cassandra",
    "kafka",
    "rabbitmq",
    "mssql",
]


# ============================================================================
# Shared Data Structures
# ============================================================================


@dataclass
class BaselineMetric:
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


# ============================================================================
# Shared Utility Functions
# ============================================================================


def parse_time_range(time_range: str) -> timedelta:
    """Parse time range string (e.g., '1h', '24h', '7d') to timedelta."""
    unit = time_range[-1]
    value = int(time_range[:-1])

    if unit == "h":
        return timedelta(hours=value)
    elif unit == "d":
        return timedelta(days=value)
    elif unit == "m":
        return timedelta(minutes=value)
    elif unit == "s":
        return timedelta(seconds=value)
    else:
        raise ValueError(f"Invalid time range format: {time_range}")


def calculate_percentile(values: list[float], percentile: float) -> float:
    """Calculate percentile from list of values."""
    if not values:
        return 0.0
    sorted_values = sorted(values)
    index = (len(sorted_values) - 1) * percentile / 100
    lower = int(index)
    upper = lower + 1
    if upper >= len(sorted_values):
        return sorted_values[-1]
    weight = index - lower
    return sorted_values[lower] * (1 - weight) + sorted_values[upper] * weight


def calculate_statistics(values: list[float]) -> dict[str, float]:
    """Calculate comprehensive statistics from values."""
    if not values:
        return {
            "mean": 0.0,
            "median": 0.0,
            "stdev": 0.0,
            "min": 0.0,
            "max": 0.0,
            "p50": 0.0,
            "p95": 0.0,
            "p99": 0.0,
            "p999": 0.0,
            "count": 0,
        }

    return {
        "mean": statistics.mean(values),
        "median": statistics.median(values),
        "stdev": statistics.stdev(values) if len(values) > 1 else 0.0,
        "min": min(values),
        "max": max(values),
        "p50": calculate_percentile(values, 50),
        "p95": calculate_percentile(values, 95),
        "p99": calculate_percentile(values, 99),
        "p999": calculate_percentile(values, 99.9),
        "count": len(values),
    }


# ============================================================================
# Prometheus Client
# ============================================================================


class GrafanaClient:
    """Client for querying Grafana datasources."""

    def __init__(self, grafana_url: str, grafana_token: str = ""):
        if not requests:
            raise ImportError(
                "requests library required. Install with: pip install requests"
            )
        self.grafana_url = grafana_url
        self.grafana_token = grafana_token
        self.headers = {
            "Authorization": f"Bearer {grafana_token}" if grafana_token else {},
            "Content-Type": "application/json",
        }

    def query_datasource(
        self,
        datasource_name: str,
        query: str,
        start_time: datetime,
        end_time: datetime,
        step: str = "60",
    ) -> dict:
        """Query a Grafana datasource for time-series data."""
        try:
            params = {
                "datasource": datasource_name,
                "expr": query,
                "start": int(start_time.timestamp()),
                "end": int(end_time.timestamp()),
                "step": step,
            }

            response = requests.post(
                f"{self.grafana_url}/api/datasources/query",
                json=params,
                headers=self.headers,
                timeout=30,
            )
            response.raise_for_status()

            data = response.json()
            if data.get("status") == "success":
                return {"status": "success", "data": data.get("results", [])}
            else:
                return {
                    "status": "error",
                    "error": data.get("message", "Unknown error"),
                }
        except Exception as e:
            logger.error(f"Grafana query failed: {e}")
            return {"status": "error", "error": str(e)}

    def discover_metrics(self, labels: dict[str, str]) -> list[str]:
        """Discover metrics from Prometheus based on labels.

        Args:
            labels: Dictionary of labels to match (e.g., {'system': 'postgres', 'service': 'api'})

        Returns:
            List of metric names matching labels
        """
        try:
            # Build label matcher from dict
            label_matchers = []
            for key, value in labels.items():
                label_matchers.append(f'{key}="{value}"')
            label_query = "{" + ",".join(label_matchers) + "}"

            response = requests.get(
                f"{self.grafana_url}/api/prometheus/api/v1/query",
                params={"query": label_query},
                headers=self.headers,
                timeout=30,
            )
            response.raise_for_status()

            data = response.json()
            metrics = set()

            if data.get("status") == "success":
                for result in data.get("data", {}).get("result", []):
                    metric_name = result.get("metric", {}).get("__name__")
                    if metric_name:
                        metrics.add(metric_name)

            return list(metrics)
        except Exception as e:
            logger.error(f"Metric discovery failed: {e}")
            return []


# ============================================================================
# Database Client
# ============================================================================


class ChaosplatformDatabaseClient:
    """Client for chaos_platform database operations."""

    def __init__(
        self,
        host: str,
        port: int,
        user: str,
        password: str,
        database: str = "chaos_platform",
    ):
        if not psycopg2:
            raise ImportError(
                "psycopg2 required. Install with: pip install psycopg2-binary"
            )

        self.host = host
        self.port = port
        self.user = user
        self.password = password
        self.database = database
        self.conn = None

    def connect(self):
        """Establish database connection."""
        try:
            self.conn = psycopg2.connect(
                host=self.host,
                port=self.port,
                user=self.user,
                password=self.password,
                database=self.database,
            )
            logger.info(
                f"✓ Connected to chaos_platform database at {self.host}:{self.port}"
            )
        except Exception as e:
            logger.error(f"✗ Database connection failed: {e}")
            raise

    def close(self):
        """Close database connection."""
        if self.conn:
            self.conn.close()
            logger.info("✓ Database connection closed")

    def store_baseline(self, baseline: BaselineMetric):
        """Store or update baseline metric in database."""
        if not self.conn:
            self.connect()

        try:
            cursor = self.conn.cursor()

            # Upsert baseline metric
            cursor.execute(
                """
                INSERT INTO baseline_metrics (
                    metric_name, service_name, metric_type, unit, description,
                    mean, stdev, min_value, max_value,
                    percentile_50, percentile_95, percentile_99, percentile_999,
                    min_valid, max_valid, datasource, time_range, phase, status,
                    collection_timestamp, updated_at
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
                ON CONFLICT (metric_name, service_name)
                DO UPDATE SET
                    metric_type = EXCLUDED.metric_type,
                    unit = EXCLUDED.unit,
                    description = EXCLUDED.description,
                    mean = EXCLUDED.mean,
                    stdev = EXCLUDED.stdev,
                    min_value = EXCLUDED.min_value,
                    max_value = EXCLUDED.max_value,
                    percentile_50 = EXCLUDED.percentile_50,
                    percentile_95 = EXCLUDED.percentile_95,
                    percentile_99 = EXCLUDED.percentile_99,
                    percentile_999 = EXCLUDED.percentile_999,
                    min_valid = EXCLUDED.min_valid,
                    max_valid = EXCLUDED.max_valid,
                    datasource = EXCLUDED.datasource,
                    time_range = EXCLUDED.time_range,
                    phase = EXCLUDED.phase,
                    status = EXCLUDED.status,
                    collection_timestamp = EXCLUDED.collection_timestamp,
                    updated_at = NOW()
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

            self.conn.commit()
            logger.debug(
                f"  ✓ Stored baseline: {baseline.metric_name} ({baseline.service_name})"
            )

        except Exception as e:
            self.conn.rollback()
            logger.error(f"  ✗ Failed to store baseline: {e}")
            raise

    def query_baselines(
        self, service_name: Optional[str] = None, metric_name: Optional[str] = None
    ) -> list[dict]:
        """Query baselines from database."""
        if not self.conn:
            self.connect()

        try:
            cursor = self.conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

            if service_name and metric_name:
                cursor.execute(
                    "SELECT * FROM baseline_metrics WHERE service_name = %s AND metric_name = %s",
                    (service_name, metric_name),
                )
            elif service_name:
                cursor.execute(
                    "SELECT * FROM baseline_metrics WHERE service_name = %s",
                    (service_name,),
                )
            else:
                cursor.execute("SELECT * FROM baseline_metrics")

            return [dict(row) for row in cursor.fetchall()]

        except Exception as e:
            logger.error(f"Failed to query baselines: {e}")
            return []


# ============================================================================
# Grafana Dashboard Parser
# ============================================================================


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
            if panel.get("type") == "row":
                continue

            targets = panel.get("targets", [])
            for target in targets:
                if "expr" in target:
                    expr = target["expr"]
                    # Extract base metric names from PromQL
                    metric_name = self._extract_metric_name(expr)
                    if metric_name:
                        metrics.add(metric_name)

        return list(metrics)

    def _extract_metric_name(self, promql: str) -> Optional[str]:
        """Extract base metric name from PromQL expression."""
        import re

        # Remove functions like rate(), increase(), etc.
        promql = re.sub(
            r"(rate|increase|irate|delta|idelta|sum|avg|min|max|count)\s*\(", "", promql
        )

        # Extract metric name (word characters before { or [)
        match = re.search(r"([a-zA-Z_:][a-zA-Z0-9_:]*)", promql)
        if match:
            return match.group(1)

        return None


# ============================================================================
# Baseline Sync (from baseline_metrics_sync.py)
# ============================================================================


class BaselineSyncer:
    """Sync baselines from Grafana to database."""

    def __init__(
        self,
        grafana_url: str,
        grafana_token: str,
        db_host: str,
        db_port: int,
        db_user: str,
        db_password: str,
        time_range: str = "24h",
    ):
        self.grafana = GrafanaClient(grafana_url, grafana_token)
        self.database = ChaosplatformDatabaseClient(
            db_host, db_port, db_user, db_password
        )
        self.time_range = time_range

    def sync_by_labels(self, labels: dict[str, str]):
        """Sync baselines for metrics matching labels.

        Args:
            labels: Dictionary of labels (e.g., {'system': 'postgres', 'service': 'api'})
        """
        label_str = ",".join([f"{k}={v}" for k, v in labels.items()])
        logger.info(f"Starting baseline sync for labels: {label_str}")

        # Discover metrics matching labels
        metrics = self.grafana.discover_metrics(labels)

        if not metrics:
            logger.warning(f"No metrics found for labels: {label_str}")
            return

        logger.info(f"Found {len(metrics)} unique metrics")
        self._process_metrics(metrics, labels)

    def _process_metrics(self, metrics: list[str], labels: dict[str, str]):
        """Process list of metrics and store baselines."""
        # Connect to database
        self.database.connect()

        success_count = 0
        failed_count = 0

        # Use first label as service_name (or use specific label if provided)
        service_name = (
            labels.get("system") or labels.get("service") or list(labels.values())[0]
        )

        # Process each metric
        for metric_name in metrics:
            try:
                baseline = self._fetch_and_calculate_baseline(
                    metric_name, service_name, labels
                )
                if baseline:
                    self.database.store_baseline(baseline)
                    success_count += 1
                else:
                    failed_count += 1
            except Exception as e:
                logger.error(f"  ✗ Failed to process {metric_name}: {e}")
                failed_count += 1

        self.database.close()

        logger.info(f"✓ Sync complete: {success_count} success, {failed_count} failed")

    def _fetch_and_calculate_baseline(
        self, metric_name: str, service_name: str, labels: dict[str, str]
    ) -> Optional[BaselineMetric]:
        """Fetch metric data from Grafana and calculate baseline statistics."""
        logger.info(f"Processing metric: {metric_name}")

        # Build query with labels
        label_str = ",".join([f'{k}="{v}"' for k, v in labels.items()])
        query = f"{metric_name}{{{label_str}}}"

        # Fetch data from Grafana
        end_time = datetime.utcnow()
        start_time = end_time - parse_time_range(self.time_range)

        result = self.grafana.query_datasource(
            "Prometheus", query, start_time, end_time
        )

        if result["status"] != "success":
            logger.error(f"  ✗ Query failed: {result.get('error')}")
            return None

        # Extract values from Grafana response
        values = []
        for series in result["data"]:
            if "series" in series:
                for point in series.get("values", []):
                    try:
                        values.append(float(point[1]))
                    except (ValueError, TypeError, IndexError):
                        continue

        if not values:
            logger.warning("  ⚠ No data points found")
            return None

        # Calculate statistics
        stats = calculate_statistics(values)

        # Determine metric type and unit
        metric_type = self._infer_metric_type(metric_name)
        unit = self._infer_unit(metric_name)

        # Create baseline
        baseline = BaselineMetric(
            metric_name=metric_name,
            service_name=service_name,
            metric_type=metric_type,
            unit=unit,
            description=f"Baseline for {metric_name} ({','.join([f'{k}={v}' for k, v in labels.items()])})",
            mean=stats["mean"],
            stdev=stats["stdev"],
            min_value=stats["min"],
            max_value=stats["max"],
            percentile_50=stats["p50"],
            percentile_95=stats["p95"],
            percentile_99=stats["p99"],
            percentile_999=stats["p999"],
            min_valid=max(0, stats["mean"] - 2 * stats["stdev"]),
            max_valid=stats["mean"] + 2 * stats["stdev"],
            datasource="grafana",
            time_range=self.time_range,
        )

        logger.info(
            f"  ✓ Baseline calculated: mean={stats['mean']:.2f}, stdev={stats['stdev']:.2f}"
        )

        return baseline

    def _infer_metric_type(self, metric_name: str) -> str:
        """Infer metric type from name."""
        if "total" in metric_name or "count" in metric_name:
            return "counter"
        elif "duration" in metric_name or "latency" in metric_name:
            return "histogram"
        elif "ratio" in metric_name or "percent" in metric_name:
            return "gauge"
        else:
            return "gauge"

    def _infer_unit(self, metric_name: str) -> str:
        """Infer unit from metric name."""
        if "seconds" in metric_name:
            return "seconds"
        elif "milliseconds" in metric_name:
            return "milliseconds"
        elif "bytes" in metric_name:
            return "bytes"
        elif "percent" in metric_name:
            return "percent"
        elif "total" in metric_name or "count" in metric_name:
            return "count"
        else:
            return "unit"


# ============================================================================
# Baseline Validator (from validate_baseline_metrics.py)
# ============================================================================


class BaselineValidator:
    """Validate baseline metrics in database or files."""

    def __init__(self):
        self.errors = []
        self.warnings = []
        self.passed = []

    def validate_database(
        self,
        db_host: str,
        db_port: int,
        db_user: str,
        db_password: str,
        systems: list[str] = None,
    ):
        """Validate baselines in database."""
        logger.info("Validating baselines in database...")

        database = ChaosplatformDatabaseClient(db_host, db_port, db_user, db_password)
        database.connect()

        systems_to_check = systems or EXPECTED_DATABASES

        for system in systems_to_check:
            baselines = database.query_baselines(service_name=system)

            if not baselines:
                self.warnings.append(f"{system}: No baselines found in database")
                continue

            for baseline in baselines:
                self._validate_baseline_record(baseline, system)

        database.close()
        self._print_report()

    def validate_files(self, systems: list[str] = None):
        """Validate baseline_metrics.json files."""
        logger.info("Validating baseline_metrics.json files...")

        systems_to_check = systems or EXPECTED_DATABASES

        for system in systems_to_check:
            baseline_file = EXPERIMENTS_DIR / system / "baseline_metrics.json"

            if not baseline_file.exists():
                self.warnings.append(f"{system}: baseline_metrics.json not found")
                continue

            # Validate JSON syntax
            try:
                with open(baseline_file) as f:
                    data = json.load(f)
            except json.JSONDecodeError as e:
                self.errors.append(f"{system}: JSON syntax error - {e}")
                continue
            except Exception as e:
                self.errors.append(f"{system}: Error reading file - {e}")
                continue

            # Validate structure
            self._validate_file_structure(data, system)

        self._print_report()

    def _validate_baseline_record(self, baseline: dict, system: str):
        """Validate single baseline record from database."""
        metric_name = baseline.get("metric_name", "unknown")

        # Check required fields
        required = [
            "mean",
            "stdev",
            "min_value",
            "max_value",
            "percentile_50",
            "percentile_95",
            "percentile_99",
        ]
        for field in required:
            if field not in baseline or baseline[field] is None:
                self.errors.append(f"{system}/{metric_name}: Missing {field}")
                return

        # Validate statistics
        if baseline["stdev"] < 0:
            self.errors.append(f"{system}/{metric_name}: Invalid stdev (negative)")

        if baseline["min_value"] > baseline["max_value"]:
            self.errors.append(f"{system}/{metric_name}: min > max")

        if baseline["percentile_50"] > baseline["percentile_95"]:
            self.errors.append(f"{system}/{metric_name}: p50 > p95")

        if baseline["percentile_95"] > baseline["percentile_99"]:
            self.errors.append(f"{system}/{metric_name}: p95 > p99")

        self.passed.append(f"{system}/{metric_name}: ✓")

    def _validate_file_structure(self, data: dict, system: str):
        """Validate baseline_metrics.json structure."""
        # Check top-level fields
        required_top = ["timestamp", "service_name", "phase", "datasource", "metrics"]
        for field in required_top:
            if field not in data:
                self.errors.append(f"{system}: Missing top-level field '{field}'")
                return

        # Validate service_name
        if data.get("service_name") != system:
            self.warnings.append(f"{system}: service_name mismatch")

        # Validate metrics
        metrics = data.get("metrics", {})
        if not isinstance(metrics, dict):
            self.errors.append(f"{system}: 'metrics' must be a dictionary")
            return

        if len(metrics) == 0:
            self.warnings.append(f"{system}: No metrics defined")
            return

        for metric_name, metric_data in metrics.items():
            self._validate_metric_data(metric_data, system, metric_name)

        self.passed.append(f"{system}: ✓ File structure valid")

    def _validate_metric_data(self, metric_data: dict, system: str, metric_name: str):
        """Validate single metric data."""
        required = ["query", "metric_type", "unit", "baseline"]
        for field in required:
            if field not in metric_data:
                self.errors.append(f"{system}/{metric_name}: Missing '{field}'")
                return

        baseline = metric_data.get("baseline", {})
        required_baseline = [
            "mean",
            "stdev",
            "min",
            "max",
            "percentile_50",
            "percentile_95",
            "percentile_99",
        ]
        for field in required_baseline:
            if field not in baseline:
                self.errors.append(f"{system}/{metric_name}: Missing baseline.{field}")

    def _print_report(self):
        """Print validation report."""
        logger.info("\n" + "=" * 80)
        logger.info("VALIDATION REPORT")
        logger.info("=" * 80)

        if self.errors:
            logger.error(f"\n❌ ERRORS ({len(self.errors)}):")
            for error in self.errors:
                logger.error(f"  - {error}")

        if self.warnings:
            logger.warning(f"\n⚠️  WARNINGS ({len(self.warnings)}):")
            for warning in self.warnings:
                logger.warning(f"  - {warning}")

        if self.passed:
            logger.info(f"\n✅ PASSED ({len(self.passed)}):")
            for item in self.passed[:10]:  # Show first 10
                logger.info(f"  - {item}")
            if len(self.passed) > 10:
                logger.info(f"  ... and {len(self.passed) - 10} more")

        logger.info("\n" + "=" * 80)
        logger.info(
            f"Total: {len(self.errors)} errors, {len(self.warnings)} warnings, {len(self.passed)} passed"
        )
        logger.info("=" * 80 + "\n")


# ============================================================================
# Steady State Analyzer (from steady_state_analyzer.py)
# ============================================================================


class SteadyStateAnalyzer:
    """Full steady state analysis with SLOs, topology, and anomalies."""

    def __init__(
        self,
        prometheus_url: str,
        tempo_url: str = None,
        loki_url: str = None,
        analysis_period_days: int = 14,
    ):
        # TODO: PrometheusClient class is not defined - needs implementation
        self.prometheus_url = prometheus_url
        self.prometheus = None
        self.tempo_url = tempo_url
        self.loki_url = loki_url
        self.analysis_period_days = analysis_period_days
        self.analysis_end_time = datetime.utcnow()
        self.analysis_start_time = self.analysis_end_time - timedelta(
            days=analysis_period_days
        )

    def analyze(self, output_dir: str = "./analysis"):
        """Execute full steady state analysis."""
        logger.info(
            f"Starting steady state analysis for {self.analysis_period_days} days"
        )
        logger.info(f"Period: {self.analysis_start_time} to {self.analysis_end_time}")

        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        # Collect data
        metrics_data = self._collect_metrics()

        # Calculate baselines
        baselines = self._calculate_baselines(metrics_data)

        # Generate SLOs
        slos = self._generate_slos(baselines)

        # Calculate anomaly thresholds
        anomalies = self._calculate_anomaly_thresholds(baselines)

        # Save results
        with open(output_path / "baseline_metrics.json", "w") as f:
            json.dump(baselines, f, indent=2)

        with open(output_path / "slo_targets.json", "w") as f:
            json.dump(slos, f, indent=2)

        with open(output_path / "anomaly_thresholds.json", "w") as f:
            json.dump(anomalies, f, indent=2)

        logger.info(f"✓ Analysis complete. Results saved to {output_dir}")

        return {
            "baseline_metrics": baselines,
            "slo_targets": slos,
            "anomaly_thresholds": anomalies,
        }

    def _collect_metrics(self) -> dict:
        """Collect metrics from Prometheus."""
        logger.info("Collecting metrics from Prometheus...")

        # Key metrics to collect
        metrics_queries = [
            "up",
            "http_request_duration_seconds",
            "http_requests_total",
            "postgresql_commits_total",
            "postgresql_rollbacks_total",
        ]

        metrics_data = {}

        for query in metrics_queries:
            result = self.prometheus.query_range(
                query, self.analysis_start_time, self.analysis_end_time
            )
            if result["status"] == "success":
                metrics_data[query] = result["data"]
                logger.info(f"  ✓ Collected {query}")
            else:
                logger.warning(f"  ⚠ Failed to collect {query}")

        return metrics_data

    def _calculate_baselines(self, metrics_data: dict) -> dict:
        """Calculate baseline statistics for each metric."""
        logger.info("Calculating metric baselines...")

        baselines = {}

        for metric_name, metric_data in metrics_data.items():
            services_data = {}

            if isinstance(metric_data, dict) and "result" in metric_data:
                for result in metric_data.get("result", []):
                    labels = result.get("metric", {})
                    service = labels.get("service", labels.get("job", "unknown"))
                    values = [float(v[1]) for v in result.get("values", [])]

                    if values:
                        stats = calculate_statistics(values)
                        services_data[service] = stats

            baselines[metric_name] = services_data
            logger.info(f"  ✓ Calculated baseline for {metric_name}")

        return baselines

    def _generate_slos(self, baselines: dict) -> dict:
        """Generate SLO targets based on baselines."""
        logger.info("Generating SLO targets...")

        slos = {}

        # Latency SLOs
        if "http_request_duration_seconds" in baselines:
            slos["latency"] = {}
            for service, stats in baselines["http_request_duration_seconds"].items():
                target = stats["p99"] * 1.1
                slos["latency"][service] = {
                    "p99_ms": stats["p99"] * 1000,
                    "slo_target_ms": target * 1000,
                    "unit": "milliseconds",
                }

        # Throughput SLOs
        if "http_requests_total" in baselines:
            slos["throughput"] = {}
            for service, stats in baselines["http_requests_total"].items():
                target = stats["mean"] * 0.9
                slos["throughput"][service] = {
                    "baseline_rps": stats["mean"],
                    "slo_target_rps": target,
                    "unit": "requests_per_second",
                }

        logger.info(f"  ✓ Generated {len(slos)} SLO categories")
        return slos

    def _calculate_anomaly_thresholds(self, baselines: dict) -> dict:
        """Calculate anomaly detection thresholds."""
        logger.info("Calculating anomaly thresholds...")

        thresholds = {}

        for metric_name, services in baselines.items():
            thresholds[metric_name] = {}
            for service, stats in services.items():
                mean = stats["mean"]
                stdev = stats["stdev"]

                thresholds[metric_name][service] = {
                    "warning_lower": mean - 2 * stdev,
                    "warning_upper": mean + 2 * stdev,
                    "critical_lower": mean - 3 * stdev,
                    "critical_upper": mean + 3 * stdev,
                }

        logger.info(f"  ✓ Calculated thresholds for {len(thresholds)} metrics")
        return thresholds


# ============================================================================
# BaselineManager Class (from baseline_manager_phase4.py)
# ============================================================================

# Scoring constants for baseline recommendations
SCORING_WEIGHTS = {
    "quality": 0.40,  # 40% weight to quality score
    "freshness": 0.30,  # 30% weight to freshness
    "stability": 0.20,  # 20% weight to low variance
    "validity": 0.10,  # 10% weight to reasonable bounds
}

# Maximum age before a baseline is considered stale
MAX_BASELINE_AGE_DAYS = 30

# Minimum quality score for suggestion (0-100)
MIN_QUALITY_SCORE = 75

# Freshness thresholds (in days)
FRESHNESS_WINDOW_DAYS = 4  # Compare to 4x 30-day windows = 120 days

# Coefficient of variation threshold (stddev/mean %)
# If higher, baseline is considered high variance
HIGH_VARIANCE_THRESHOLD = 50


class BaselineManager:
    """
    Unified manager for baseline metrics operations.

    Provides high-level commands for discovering, analyzing, and suggesting
    baselines for chaos engineering experiments.
    """

    def __init__(
        self,
        db_client: Optional[Any] = None,
        logger: Optional[logging.Logger] = None,
    ):
        """
        Initialize BaselineManager.

        Args:
            db_client: ChaosDb instance for database access
            logger: Logger instance (uses module logger if not provided)
        """
        from chaosgeneric.tools.baseline_loader import BaselineLoader

        self.db = db_client
        self.baseline_loader = BaselineLoader(db_client=db_client, logger=logger)
        self.logger = logger or globals()["logger"]

    def discover(
        self,
        system_id: Optional[str] = None,
        service_id: Optional[str] = None,
        labels: Optional[dict[str, str]] = None,
        show_details: bool = False,
    ) -> dict[str, Any]:
        """
        Discover and load baselines by system, service, or labels.

        Discovers baseline metrics that match the specified discovery criteria.
        At least one of system_id, service_id, or labels must be provided.

        Args:
            system_id: System/environment name (e.g., 'api-server', 'postgres')
            service_id: Service name (e.g., 'postgres', 'redis', 'payment-api')
            labels: Dictionary of label key-value pairs to match
            show_details: If True, include detailed statistics

        Returns:
            Dictionary with status, discovered_count, baselines, etc.
        """
        from datetime import datetime

        start_time = datetime.utcnow()

        try:
            # Validation: At least one parameter required
            if not system_id and not service_id and not labels:
                error_msg = (
                    "At least one of system_id, service_id, or labels must be provided"
                )
                self.logger.error(error_msg)
                return {
                    "status": "error",
                    "message": error_msg,
                    "discovered_count": 0,
                    "baselines": [],
                }

            # Validate parameters
            if system_id and not isinstance(system_id, str):
                raise ValueError(f"system_id must be string, got {type(system_id)}")
            if service_id and not isinstance(service_id, str):
                raise ValueError(f"service_id must be string, got {type(service_id)}")
            if labels and not isinstance(labels, dict):
                raise ValueError(f"labels must be dict, got {type(labels)}")
            if labels and len(labels) == 0:
                raise ValueError("labels dict cannot be empty")

            # Validate identifiers
            if system_id and not self._is_valid_identifier(system_id):
                raise ValueError(f"system_id contains invalid characters: {system_id}")
            if service_id and not self._is_valid_identifier(service_id):
                raise ValueError(
                    f"service_id contains invalid characters: {service_id}"
                )

            # Discover baselines
            baselines_dict: dict[str, Any] = {}
            discovery_method = None

            if system_id:
                self.logger.info(f"Discovering baselines for system: {system_id}")
                baselines_dict = self.baseline_loader.load_by_system(system_id)
                discovery_method = "system"
            elif service_id:
                self.logger.info(f"Discovering baselines for service: {service_id}")
                baselines_dict = self.baseline_loader.load_by_service(service_id)
                discovery_method = "service"
            elif labels:
                self.logger.info(f"Discovering baselines for labels: {labels}")
                baselines_dict = self.baseline_loader.load_by_labels(
                    labels, match_all=True
                )
                discovery_method = "labels"

            # Convert to response format
            baselines_list = []
            for metric_name, metric in baselines_dict.items():
                baseline_dict = self._baseline_metric_to_dict(
                    metric, discovery_method, show_details=show_details
                )
                baselines_list.append(baseline_dict)

            # Calculate metadata
            query_time_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)

            self.logger.info(
                f"Successfully discovered {len(baselines_list)} baselines "
                f"via {discovery_method} discovery"
            )

            return {
                "status": "success",
                "discovered_count": len(baselines_list),
                "discovery_method": discovery_method,
                "discovery_params": self._build_discovery_params(
                    system_id, service_id, labels
                ),
                "baselines": baselines_list,
                "metadata": {
                    "total_requested": None,
                    "total_discovered": len(baselines_list),
                    "discovery_method_used": discovery_method,
                    "query_time_ms": query_time_ms,
                    "notes": "",
                },
                "discovery_timestamp": start_time.isoformat() + "Z",
                "message": f"Successfully discovered {len(baselines_list)} baselines via {discovery_method} discovery",
            }

        except ValueError as e:
            self.logger.warning(f"Validation error in discover(): {str(e)}")
            return {
                "status": "error",
                "message": f"Validation error: {str(e)}",
                "discovered_count": 0,
                "baselines": [],
            }
        except Exception as e:
            self.logger.error(f"Error in discover(): {str(e)}", exc_info=True)
            return {
                "status": "error",
                "message": f"Database error: {str(e)}",
                "discovered_count": 0,
                "baselines": [],
            }

    def status(
        self,
        experiment_id: int,
        show_inactive: bool = False,
        show_skipped: bool = False,
    ) -> dict[str, Any]:
        """
        Get baseline status for an experiment.

        Args:
            experiment_id: ID of the experiment
            show_inactive: If True, include INACTIVE baselines
            show_skipped: If True, include SKIPPED baselines

        Returns:
            Dictionary with baseline status information
        """
        from datetime import datetime

        start_time = datetime.utcnow()

        try:
            # Validation
            if not isinstance(experiment_id, int):
                raise ValueError(
                    f"experiment_id must be int, got {type(experiment_id)}"
                )
            if experiment_id <= 0:
                raise ValueError(f"experiment_id must be positive, got {experiment_id}")

            if not self.db:
                raise ValueError("db_client is required for status() command")

            experiment = self._get_experiment(experiment_id)
            if not experiment:
                error_msg = f"Experiment {experiment_id} not found"
                self.logger.warning(error_msg)
                return {
                    "status": "error",
                    "message": error_msg,
                    "experiment_id": experiment_id,
                    "baselines": [],
                }

            self.logger.info(f"Querying baseline status for experiment {experiment_id}")

            # Query v_experiment_baselines view
            baselines_rows = self._query_experiment_baselines(experiment_id)

            if not baselines_rows:
                self.logger.info(f"No baselines found for experiment {experiment_id}")
                return {
                    "experiment_id": experiment_id,
                    "experiment_name": experiment.get("title", ""),
                    "baselines": [],
                    "active_count": 0,
                    "inactive_count": 0,
                    "skipped_count": 0,
                    "status": "NO_BASELINES",
                    "message": f"No baselines configured for experiment {experiment_id}",
                }

            # Process baselines and filter by status
            baselines_list = []
            active_count = 0
            inactive_count = 0
            skipped_count = 0

            for row in baselines_rows:
                mapping_status = row.get("mapping_status", "ACTIVE")

                # Filter based on parameters
                if mapping_status == "INACTIVE" and not show_inactive:
                    inactive_count += 1
                    continue
                if mapping_status == "SKIPPED" and not show_skipped:
                    skipped_count += 1
                    continue

                # Count status
                if mapping_status == "ACTIVE":
                    active_count += 1
                elif mapping_status == "INACTIVE":
                    inactive_count += 1
                elif mapping_status == "SKIPPED":
                    skipped_count += 1

                # Convert to response format
                baseline_dict = self._baseline_status_row_to_dict(row)
                baselines_list.append(baseline_dict)

            # Overall status
            overall_status = "ACTIVE" if active_count > 0 else "NO_ACTIVE"

            query_time_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)

            self.logger.info(
                f"Found baselines for experiment {experiment_id}: "
                f"{active_count} active, {inactive_count} inactive, {skipped_count} skipped"
            )

            return {
                "status": "success",
                "experiment_id": experiment_id,
                "experiment_name": experiment.get("title", ""),
                "baselines": baselines_list,
                "active_count": active_count,
                "inactive_count": inactive_count,
                "skipped_count": skipped_count,
                "experiment_status": overall_status,
                "metadata": {
                    "total_baselines": len(baselines_rows),
                    "shown_baselines": len(baselines_list),
                    "query_time_ms": query_time_ms,
                    "show_inactive": show_inactive,
                    "show_skipped": show_skipped,
                },
                "timestamp": start_time.isoformat() + "Z",
                "message": (
                    f"Found {len(baselines_list)} baselines: "
                    f"{active_count} active, {inactive_count} inactive, {skipped_count} skipped"
                ),
            }

        except ValueError as e:
            self.logger.warning(f"Validation error in status(): {str(e)}")
            return {
                "status": "error",
                "message": f"Validation error: {str(e)}",
                "experiment_id": experiment_id,
                "baselines": [],
            }
        except Exception as e:
            self.logger.error(f"Error in status(): {str(e)}", exc_info=True)
            return {
                "status": "error",
                "message": f"Database error: {str(e)}",
                "experiment_id": experiment_id,
                "baselines": [],
            }

    def suggest_for_experiment(
        self, experiment_id: int, min_quality_score: int = 75, top_n: int = 20
    ) -> dict[str, Any]:
        """
        Suggest baselines for an experiment based on service.

        Args:
            experiment_id: ID of the experiment
            min_quality_score: Minimum quality score to consider (0-100)
            top_n: Maximum number of suggestions to return

        Returns:
            Dictionary with baseline suggestions
        """
        from datetime import datetime

        start_time = datetime.utcnow()

        try:
            # Validation
            if not isinstance(experiment_id, int):
                raise ValueError(
                    f"experiment_id must be int, got {type(experiment_id)}"
                )
            if experiment_id <= 0:
                raise ValueError(f"experiment_id must be positive, got {experiment_id}")
            if min_quality_score < 0 or min_quality_score > 100:
                raise ValueError(
                    f"min_quality_score must be 0-100, got {min_quality_score}"
                )
            if top_n <= 0:
                raise ValueError(f"top_n must be positive, got {top_n}")

            if not self.db:
                raise ValueError(
                    "db_client is required for suggest_for_experiment() command"
                )

            experiment = self._get_experiment(experiment_id)
            if not experiment:
                error_msg = f"Experiment {experiment_id} not found"
                self.logger.warning(error_msg)
                return {
                    "status": "error",
                    "message": error_msg,
                    "experiment_id": experiment_id,
                    "suggestions": [],
                }

            service_id = experiment.get("service_id")
            service_name = experiment.get("service_name", "unknown")

            if not service_id:
                error_msg = f"Experiment {experiment_id} has no associated service"
                self.logger.warning(error_msg)
                return {
                    "status": "error",
                    "message": error_msg,
                    "experiment_id": experiment_id,
                    "service_name": service_name,
                    "suggestions": [],
                }

            self.logger.info(
                f"Generating baseline suggestions for experiment {experiment_id} "
                f"(service: {service_name})"
            )

            # Load baselines for service
            baselines_dict = self.baseline_loader.load_by_service(service_name)

            if not baselines_dict:
                self.logger.info(f"No baselines found for service {service_name}")
                return {
                    "status": "success",
                    "experiment_id": experiment_id,
                    "service_name": service_name,
                    "suggestions": [],
                    "total_suggestions": 0,
                    "message": f"No baselines available for service {service_name}",
                }

            # Score each baseline
            scored_baselines = []
            for metric_name, metric in baselines_dict.items():
                # Skip low quality baselines
                if metric.quality_score * 100 < min_quality_score:
                    self.logger.debug(
                        f"Skipping {metric_name}: quality_score {metric.quality_score:.2f} "
                        f"below minimum {min_quality_score / 100:.2f}"
                    )
                    continue

                # Calculate composite score
                overall_score, score_breakdown = self._score_baseline(metric)

                scored_baselines.append(
                    {
                        "metric": metric,
                        "metric_name": metric_name,
                        "overall_score": overall_score,
                        "score_breakdown": score_breakdown,
                    }
                )

            # Sort by overall score (descending) and limit to top_n
            scored_baselines.sort(key=lambda x: x["overall_score"], reverse=True)
            top_baselines = scored_baselines[:top_n]

            # Convert to response format
            suggestions_list = []
            for rank, item in enumerate(top_baselines, 1):
                suggestion_dict = self._baseline_suggestion_to_dict(
                    rank,
                    item["metric"],
                    item["metric_name"],
                    item["overall_score"],
                    item["score_breakdown"],
                )
                suggestions_list.append(suggestion_dict)

            query_time_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)

            self.logger.info(
                f"Generated {len(suggestions_list)} baseline suggestions for "
                f"experiment {experiment_id} (service: {service_name})"
            )

            return {
                "status": "success",
                "experiment_id": experiment_id,
                "service_name": service_name,
                "suggestions": suggestions_list,
                "total_suggestions": len(suggestions_list),
                "metadata": {
                    "total_candidates": len(baselines_dict),
                    "quality_filtered": len(baselines_dict) - len(scored_baselines),
                    "suggestions_returned": len(suggestions_list),
                    "min_quality_filter": min_quality_score,
                    "max_suggestions_requested": top_n,
                    "query_time_ms": query_time_ms,
                    "scoring_weights": SCORING_WEIGHTS,
                },
                "suggestion_timestamp": start_time.isoformat() + "Z",
                "message": f"Found {len(suggestions_list)} baseline recommendations for service {service_name}",
            }

        except ValueError as e:
            self.logger.warning(
                f"Validation error in suggest_for_experiment(): {str(e)}"
            )
            return {
                "status": "error",
                "message": f"Validation error: {str(e)}",
                "experiment_id": experiment_id,
                "suggestions": [],
            }
        except Exception as e:
            self.logger.error(
                f"Error in suggest_for_experiment(): {str(e)}", exc_info=True
            )
            return {
                "status": "error",
                "message": f"Database error: {str(e)}",
                "experiment_id": experiment_id,
                "suggestions": [],
            }

    # Helper methods
    def _is_valid_identifier(self, identifier: str) -> bool:
        """Check if identifier contains only valid characters."""
        import re

        if not identifier:
            return False
        return bool(re.match(r"^[a-zA-Z0-9_\-\.]+$", identifier))

    def _build_discovery_params(
        self,
        system_id: Optional[str],
        service_id: Optional[str],
        labels: Optional[dict[str, str]],
    ) -> dict[str, Any]:
        """Build discovery parameters dictionary."""
        params = {}
        if system_id:
            params["system_id"] = system_id
        if service_id:
            params["service_id"] = service_id
        if labels:
            params["labels"] = labels
        return params

    def _baseline_metric_to_dict(
        self, metric: Any, discovery_method: str, show_details: bool = False
    ) -> dict[str, Any]:
        """Convert BaselineMetric to dictionary for discover() response."""
        from datetime import datetime

        age_days = (datetime.utcnow() - metric.collection_timestamp).days
        is_fresh = age_days <= MAX_BASELINE_AGE_DAYS

        result = {
            "metric_id": metric.metric_id,
            "metric_name": metric.metric_name,
            "service_name": metric.service_name,
            "system_name": metric.system,
            "discovery_method": discovery_method,
            "mean_value": round(metric.mean, 2),
            "stddev_value": round(metric.stdev, 2),
            "min_value": round(metric.min_value, 2),
            "max_value": round(metric.max_value, 2),
            "percentile_50": round(metric.percentile_50, 2),
            "percentile_95": round(metric.percentile_95, 2),
            "percentile_99": round(metric.percentile_99, 2),
            "quality_score": round(metric.quality_score * 100, 1),
            "sigma_threshold": 2.0,
            "upper_bound_2sigma": round(metric.upper_bound_2sigma, 2),
            "upper_bound_3sigma": round(metric.upper_bound_3sigma, 2),
            "baseline_age_days": age_days,
            "is_fresh": is_fresh,
        }

        # Add detailed fields if requested
        if show_details:
            result["percentile_999"] = round(metric.percentile_999, 2)
            result["version_id"] = metric.baseline_version_id
            result["collected_at"] = metric.collection_timestamp.isoformat() + "Z"

        return result

    def _baseline_status_row_to_dict(self, row: dict[str, Any]) -> dict[str, Any]:
        """Convert v_experiment_baselines row to dictionary for status() response."""
        mean = float(row.get("mean_value", 0.0))
        stdev = float(row.get("stddev_value", 0.0))

        # Calculate bounds
        warning_lower = mean - (2.0 * stdev)
        warning_upper = mean + (2.0 * stdev)
        critical_lower = mean - (3.0 * stdev)
        critical_upper = mean + (3.0 * stdev)

        age_days = row.get("baseline_age_days", 0)
        is_fresh = age_days <= MAX_BASELINE_AGE_DAYS if age_days is not None else False

        return {
            "mapping_id": row.get("mapping_id"),
            "metric_id": row.get("metric_id"),
            "metric_name": row.get("metric_name"),
            "service_name": row.get("service_name"),
            "system": row.get("system_name", ""),
            "mapping_status": row.get("mapping_status", "ACTIVE"),
            "discovery_method": row.get("discovery_method", ""),
            "loaded_at": row.get("loaded_at", ""),
            "baseline_version": row.get("version", 1),
            "baseline_collected_at": row.get("collection_timestamp", ""),
            "baseline_age_days": age_days,
            "is_fresh": is_fresh,
            "baseline_mean": round(mean, 2),
            "baseline_stdev": round(stdev, 2),
            "baseline_min": round(float(row.get("min_value", 0.0)), 2),
            "baseline_max": round(float(row.get("max_value", 0.0)), 2),
            "baseline_p95": round(float(row.get("p95", 0.0)), 2),
            "baseline_p99": round(float(row.get("p99", 0.0)), 2),
            "quality_score": round(float(row.get("quality_score", 0.0)) * 100, 1),
            "used_sigma_threshold": 2.0,
            "used_critical_sigma": 3.0,
            "warning_lower_bound": round(warning_lower, 2),
            "warning_upper_bound": round(warning_upper, 2),
            "critical_lower_bound": round(critical_lower, 2),
            "critical_upper_bound": round(critical_upper, 2),
            "skip_reason": row.get("skip_reason"),
            "is_active": row.get("mapping_status") == "ACTIVE",
            "created_at": row.get("created_at", ""),
            "updated_at": row.get("updated_at", ""),
        }

    def _score_baseline(self, metric: Any) -> tuple[float, dict[str, float]]:
        """Calculate composite recommendation score for a baseline."""
        from datetime import datetime

        # Quality score (0-100 -> 0-1)
        quality_norm = metric.quality_score

        # Freshness score (based on age)
        age_days = (datetime.utcnow() - metric.collection_timestamp).days
        freshness_days = age_days / 30.0  # normalize to 30-day windows
        freshness_score = max(0.0, 1.0 - (freshness_days / FRESHNESS_WINDOW_DAYS))
        freshness_score = min(1.0, freshness_score)

        # Stability score (inverse of coefficient of variation)
        if metric.mean > 0:
            cv_ratio = metric.stdev / metric.mean
            stability_score = 1.0 / (1.0 + cv_ratio)
        else:
            stability_score = 0.5
        stability_score = min(1.0, max(0.0, stability_score))

        # Validity score (how reasonable are the bounds)
        if metric.stdev > 0:
            bounds_range = metric.max_value - metric.min_value
            expected_range = 4.0 * metric.stdev
            validity_score = min(1.0, bounds_range / expected_range)
        else:
            validity_score = 0.5
        validity_score = min(1.0, max(0.0, validity_score))

        # Composite score (weighted average)
        overall_score = (
            (SCORING_WEIGHTS["quality"] * quality_norm)
            + (SCORING_WEIGHTS["freshness"] * freshness_score)
            + (SCORING_WEIGHTS["stability"] * stability_score)
            + (SCORING_WEIGHTS["validity"] * validity_score)
        )

        # Scale to 0-100
        overall_score_scaled = overall_score * 100

        score_breakdown = {
            "quality_score": round(quality_norm * 100, 1),
            "freshness_score": round(freshness_score * 100, 1),
            "stability_score": round(stability_score * 100, 1),
            "validity_score": round(validity_score * 100, 1),
            "overall_score": round(overall_score_scaled, 1),
        }

        return overall_score_scaled, score_breakdown

    def _baseline_suggestion_to_dict(
        self,
        rank: int,
        metric: Any,
        metric_name: str,
        overall_score: float,
        score_breakdown: dict[str, float],
    ) -> dict[str, Any]:
        """Convert scored baseline to dictionary for suggest_for_experiment() response."""
        from datetime import datetime

        age_days = (datetime.utcnow() - metric.collection_timestamp).days

        return {
            "rank": rank,
            "metric_id": metric.metric_id,
            "metric_name": metric_name,
            "recommendation_score": round(overall_score, 1),
            "quality_score": round(metric.quality_score * 100, 1),
            "freshness_score": round(score_breakdown["freshness_score"], 1),
            "stability_score": round(score_breakdown["stability_score"], 1),
            "validity_score": round(score_breakdown["validity_score"], 1),
            "reason": self._generate_recommendation_reason(score_breakdown),
            "mean_value": round(metric.mean, 2),
            "stddev_value": round(metric.stdev, 2),
            "data_age_days": age_days,
            "suggested_sigma": 2.0,
            "quality_percentile": self._estimate_quality_percentile(score_breakdown),
        }

    def _generate_recommendation_reason(self, score_breakdown: dict[str, float]) -> str:
        """Generate human-readable reason for recommendation based on scores."""
        reasons = []

        if score_breakdown["quality_score"] >= 90:
            reasons.append("High quality recent baseline")
        elif score_breakdown["quality_score"] >= 75:
            reasons.append("Good quality baseline")

        if score_breakdown["freshness_score"] >= 80:
            reasons.append("Recent collection")
        elif score_breakdown["freshness_score"] >= 50:
            reasons.append("Moderately recent")

        if score_breakdown["stability_score"] >= 80:
            reasons.append("Low variance")

        if score_breakdown["validity_score"] >= 80:
            reasons.append("Good statistical properties")

        return " with ".join(reasons) if reasons else "Recommended baseline"

    def _estimate_quality_percentile(self, score_breakdown: dict[str, float]) -> str:
        """Estimate quality percentile from score breakdown."""
        overall = score_breakdown.get("overall_score", 0)
        if overall >= 90:
            return "top-10%"
        elif overall >= 80:
            return "top-25%"
        elif overall >= 70:
            return "top-50%"
        else:
            return "below-average"

    def _get_experiment(self, experiment_id: int) -> Optional[dict[str, Any]]:
        """Get experiment by ID from database."""
        try:
            with self.db._get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        SELECT
                            experiment_id,
                            title,
                            description,
                            service_id,
                            (SELECT service_name FROM chaos_platform.services
                             WHERE service_id = experiments.service_id) as service_name
                        FROM chaos_platform.experiments
                        WHERE experiment_id = %s
                    """,
                        (experiment_id,),
                    )

                    result = cur.fetchone()
                    if result:
                        cols = [desc[0] for desc in cur.description]
                        return dict(zip(cols, result))
                    return None
        except Exception as e:
            self.logger.error(f"Failed to get experiment {experiment_id}: {str(e)}")
            return None

    def _query_experiment_baselines(self, experiment_id: int) -> list[dict[str, Any]]:
        """Query v_experiment_baselines view for an experiment."""
        try:
            with self.db._get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        SELECT *
                        FROM chaos_platform.v_experiment_baselines
                        WHERE experiment_id = %s
                        ORDER BY metric_name
                    """,
                        (experiment_id,),
                    )

                    results = cur.fetchall()
                    if not results:
                        return []

                    cols = [desc[0] for desc in cur.description]
                    return [dict(zip(cols, row)) for row in results]
        except Exception as e:
            self.logger.error(f"Failed to query v_experiment_baselines: {str(e)}")
            return []


# ============================================================================
# CLI Interface
# ============================================================================


def cmd_sync(args):
    """Sync command: Auto-discover metrics by labels and store in chaos_platform."""
    # Build labels dict
    labels = {}

    if args.system:
        labels["system"] = args.system
    if args.service:
        labels["service"] = args.service
    if args.platform:
        labels["platform"] = args.platform
    if args.labels:
        # Parse --labels "key1=value1,key2=value2"
        for pair in args.labels.split(","):
            key, value = pair.strip().split("=")
            labels[key.strip()] = value.strip()

    if not labels:
        logger.error(
            "ERROR: Must provide at least one of: --system, --service, --platform, or --labels"
        )
        sys.exit(1)

    syncer = BaselineSyncer(
        grafana_url=args.grafana_url,
        grafana_token=args.grafana_token,
        db_host=args.db_host,
        db_port=args.db_port,
        db_user=args.db_user,
        db_password=args.db_password,
        time_range=args.time_range,
    )

    syncer.sync_by_labels(labels)


def cmd_validate(args):
    """Validate command: Validate baselines."""
    validator = BaselineValidator()

    systems = None if args.all_systems else [args.system] if args.system else None

    if args.source == "database":
        validator.validate_database(
            db_host=args.db_host,
            db_port=args.db_port,
            db_user=args.db_user,
            db_password=args.db_password,
            systems=systems,
        )
    else:
        validator.validate_files(systems=systems)

    # Exit with error if there are errors
    if validator.errors:
        sys.exit(1)


def cmd_analyze(args):
    """Analyze command: Full steady state analysis."""
    analyzer = SteadyStateAnalyzer(
        prometheus_url=args.prometheus_url,
        tempo_url=args.tempo_url,
        loki_url=args.loki_url,
        analysis_period_days=int(args.period[:-1]) if args.period.endswith("d") else 14,
    )

    analyzer.analyze(output_dir=args.output_dir)


def cmd_generate(args):
    """Generate command: Create baseline_metrics.json file (legacy)."""
    logger.info(f"Generating baseline_metrics.json for {args.system}...")

    # Use steady state analyzer
    analyzer = SteadyStateAnalyzer(
        prometheus_url=args.prometheus_url,
        analysis_period_days=int(args.period[:-1]) if args.period.endswith("d") else 1,
    )

    metrics_data = analyzer._collect_metrics()
    baselines = analyzer._calculate_baselines(metrics_data)

    output_data = {
        "timestamp": datetime.utcnow().isoformat(),
        "service_name": args.system,
        "phase": "baseline_collection",
        "datasource": "prometheus",
        "metrics": baselines,
    }

    with open(args.output, "w") as f:
        json.dump(output_data, f, indent=2)

    logger.info(f"✓ Baseline saved to {args.output}")


def cmd_query(args):
    """Query command: Query baseline data from database."""
    database = ChaosplatformDatabaseClient(
        host=args.db_host,
        port=args.db_port,
        user=args.db_user,
        password=args.db_password,
    )

    database.connect()
    baselines = database.query_baselines(
        service_name=args.system, metric_name=args.metric
    )
    database.close()

    if not baselines:
        logger.warning("No baselines found matching criteria")
        return

    logger.info(f"Found {len(baselines)} baseline(s):\n")
    for baseline in baselines:
        print(json.dumps(baseline, indent=2, default=str))


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Unified Baseline Manager - Comprehensive baseline management",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    subparsers = parser.add_subparsers(dest="command", help="Command to execute")

    # Sync command
    sync_parser = subparsers.add_parser(
        "sync", help="Auto-discover metrics by labels and sync to chaos_platform"
    )
    sync_parser.add_argument(
        "--system", help="Database system (postgres, mysql, mongodb, etc.)"
    )
    sync_parser.add_argument(
        "--service", help="Service name (order-service, payment-service, etc.)"
    )
    sync_parser.add_argument("--platform", help="Platform identifier")
    sync_parser.add_argument(
        "--labels", help='Custom labels: "key1=value1,key2=value2"'
    )
    sync_parser.add_argument(
        "--grafana-url", default=os.getenv("GRAFANA_URL", "http://grafana:3000")
    )
    sync_parser.add_argument(
        "--grafana-token", default=os.getenv("GRAFANA_API_TOKEN", "")
    )
    sync_parser.add_argument(
        "--db-host", default=os.getenv("CHAOS_DB_HOST", "postgres-primary-site-a")
    )
    sync_parser.add_argument(
        "--db-port", type=int, default=int(os.getenv("CHAOS_DB_PORT", "5432"))
    )
    sync_parser.add_argument(
        "--db-user", default=os.getenv("CHAOS_DB_USER", "postgres")
    )
    sync_parser.add_argument(
        "--db-password", default=os.getenv("CHAOS_DB_PASSWORD", "postgres")
    )
    sync_parser.add_argument(
        "--time-range",
        default="24h",
        help="Time range for data collection (1h, 24h, 7d, etc.)",
    )

    # Validate command
    validate_parser = subparsers.add_parser(
        "validate", help="Validate baseline metrics"
    )
    validate_parser.add_argument(
        "--source", choices=["database", "file"], default="database"
    )
    validate_parser.add_argument("--system", help="Specific system to validate")
    validate_parser.add_argument(
        "--all-systems", action="store_true", help="Validate all systems"
    )
    validate_parser.add_argument(
        "--db-host", default=os.getenv("CHAOS_DB_HOST", "postgres-primary-site-a")
    )
    validate_parser.add_argument(
        "--db-port", type=int, default=int(os.getenv("CHAOS_DB_PORT", "5432"))
    )
    validate_parser.add_argument(
        "--db-user", default=os.getenv("CHAOS_DB_USER", "postgres")
    )
    validate_parser.add_argument(
        "--db-password", default=os.getenv("CHAOS_DB_PASSWORD", "postgres")
    )

    # Analyze command
    analyze_parser = subparsers.add_parser("analyze", help="Full steady state analysis")
    analyze_parser.add_argument(
        "--period", default="14d", help="Analysis period (e.g., 14d, 7d)"
    )
    analyze_parser.add_argument(
        "--output-dir", default="./analysis", help="Output directory"
    )
    analyze_parser.add_argument(
        "--prometheus-url",
        default=os.getenv("PROMETHEUS_URL", "http://prometheus:9090"),
    )
    analyze_parser.add_argument(
        "--tempo-url", default=os.getenv("TEMPO_URL", "http://tempo:3100")
    )
    analyze_parser.add_argument(
        "--loki-url", default=os.getenv("LOKI_URL", "http://loki:3100")
    )

    # Generate command
    generate_parser = subparsers.add_parser(
        "generate", help="Generate baseline_metrics.json file (legacy)"
    )
    generate_parser.add_argument("--system", required=True, help="Database system")
    generate_parser.add_argument("--output", required=True, help="Output file path")
    generate_parser.add_argument("--period", default="1d", help="Analysis period")
    generate_parser.add_argument(
        "--prometheus-url",
        default=os.getenv("PROMETHEUS_URL", "http://prometheus:9090"),
    )

    # Query command
    query_parser = subparsers.add_parser(
        "query", help="Query baseline data from database"
    )
    query_parser.add_argument("--system", help="Filter by system")
    query_parser.add_argument("--metric", help="Filter by metric name")
    query_parser.add_argument(
        "--db-host", default=os.getenv("CHAOS_DB_HOST", "postgres-primary-site-a")
    )
    query_parser.add_argument(
        "--db-port", type=int, default=int(os.getenv("CHAOS_DB_PORT", "5432"))
    )
    query_parser.add_argument(
        "--db-user", default=os.getenv("CHAOS_DB_USER", "postgres")
    )
    query_parser.add_argument(
        "--db-password", default=os.getenv("CHAOS_DB_PASSWORD", "postgres")
    )

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    # Execute command
    if args.command == "sync":
        cmd_sync(args)
    elif args.command == "validate":
        cmd_validate(args)
    elif args.command == "analyze":
        cmd_analyze(args)
    elif args.command == "generate":
        cmd_generate(args)
    elif args.command == "query":
        cmd_query(args)


if __name__ == "__main__":
    main()
