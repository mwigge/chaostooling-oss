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
from typing import Optional

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
        self.prometheus = PrometheusClient(prometheus_url)
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
