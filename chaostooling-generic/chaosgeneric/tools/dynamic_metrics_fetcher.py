"""
Dynamic Metrics Fetcher - Multi-source metric retrieval.

Fetches metrics from Grafana, Prometheus, chaos_platform DB, and files.
Aggregates data from multiple sources for comprehensive steady-state calculation.
"""

import json
import logging
import os
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from typing import Any, Optional

import requests

from chaosgeneric.data.chaos_db import ChaosDb

logger = logging.getLogger(__name__)


class DynamicMetricsFetcher:
    """Fetch metrics from multiple sources (Grafana, Prometheus, DB, files)."""

    def __init__(
        self,
        grafana_url: Optional[str] = None,
        prometheus_url: Optional[str] = None,
        db_host: Optional[str] = None,
        db_port: Optional[int] = None,
        timeout: int = 5,
    ):
        """
        Initialize metrics fetcher.

        Args:
            grafana_url: Grafana API URL (default: GRAFANA_URL env var)
            prometheus_url: Prometheus API URL (default: PROMETHEUS_URL env var)
            db_host: Database host (default: CHAOS_DB_HOST env var)
            db_port: Database port (default: CHAOS_DB_PORT env var)
            timeout: Request timeout in seconds
        """
        self.grafana_url = grafana_url or os.getenv(
            "GRAFANA_URL", "http://grafana:3000"
        )
        self.prometheus_url = prometheus_url or os.getenv(
            "PROMETHEUS_URL", "http://prometheus:9090"
        )
        self.db_host = db_host or os.getenv("CHAOS_DB_HOST", "chaos-platform-db")
        self.db_port = db_port or int(os.getenv("CHAOS_DB_PORT", "5432"))
        self.timeout = timeout
        self._db: Optional[ChaosDb] = None

    def fetch_from_grafana(
        self, metric_name: str, time_range: str, datasource_uid: str = "prometheus"
    ) -> list[float]:
        """
        Fetch metric values from Grafana.

        Args:
            metric_name: PromQL query or metric name
            time_range: Time range (e.g., '24h', '30d')
            datasource_uid: Grafana datasource UID

        Returns:
            List of metric values
        """
        try:
            end_time = datetime.utcnow()
            start_time = self._parse_time_range(time_range, end_time)

            # Query via Grafana API
            api_key = os.getenv("GRAFANA_API_KEY", "")
            headers = {"Content-Type": "application/json"}
            if api_key:
                headers["Authorization"] = f"Bearer {api_key}"

            # Calculate appropriate step size based on time range
            # Prometheus recommends: step should be at least (end - start) / 11000
            time_delta = (end_time - start_time).total_seconds()
            if time_delta > 7 * 24 * 3600:  # > 7 days
                step = "3600"  # 1 hour
            elif time_delta > 24 * 3600:  # > 1 day
                step = "900"  # 15 minutes
            else:
                step = "300"  # 5 minutes

            url = f"{self.grafana_url}/api/datasources/proxy/uid/{datasource_uid}/api/v1/query_range"
            params = {
                "query": metric_name,
                "start": int(start_time.timestamp()),
                "end": int(end_time.timestamp()),
                "step": step,
            }

            response = requests.get(
                url, headers=headers, params=params, timeout=self.timeout
            )
            response.raise_for_status()
            data = response.json()

            if data.get("status") != "success":
                logger.warning(
                    f"Grafana query failed: {data.get('error', 'Unknown error')}"
                )
                return []

            # Extract values
            values = []
            for result in data.get("data", {}).get("result", []):
                for point in result.get("values", []):
                    try:
                        values.append(float(point[1]))
                    except (ValueError, TypeError, IndexError):
                        continue

            logger.debug(f"Fetched {len(values)} values from Grafana for {metric_name}")
            return values

        except Exception as e:
            logger.warning(f"Failed to fetch from Grafana: {e}")
            return []

    def fetch_from_prometheus(self, metric_name: str, time_range: str) -> list[float]:
        """
        Fetch metric values from Prometheus.

        Args:
            metric_name: PromQL query
            time_range: Time range (e.g., '24h', '30d')

        Returns:
            List of metric values
        """
        try:
            end_time = datetime.utcnow()
            start_time = self._parse_time_range(time_range, end_time)

            # Calculate appropriate step size based on time range
            # Prometheus recommends: step should be at least (end - start) / 11000
            time_delta = (end_time - start_time).total_seconds()
            if time_delta > 7 * 24 * 3600:  # > 7 days
                step = "3600"  # 1 hour
            elif time_delta > 24 * 3600:  # > 1 day
                step = "900"  # 15 minutes
            else:
                step = "300"  # 5 minutes

            url = f"{self.prometheus_url}/api/v1/query_range"
            params = {
                "query": metric_name,
                "start": int(start_time.timestamp()),
                "end": int(end_time.timestamp()),
                "step": step,
            }

            response = requests.get(url, params=params, timeout=self.timeout)
            response.raise_for_status()
            data = response.json()

            if data.get("status") != "success":
                logger.warning(
                    f"Prometheus query failed: {data.get('error', 'Unknown error')}"
                )
                return []

            # Extract values
            values = []
            for result in data.get("data", {}).get("result", []):
                for point in result.get("values", []):
                    try:
                        values.append(float(point[1]))
                    except (ValueError, TypeError, IndexError):
                        continue

            logger.debug(
                f"Fetched {len(values)} values from Prometheus for {metric_name}"
            )
            return values

        except Exception as e:
            logger.warning(f"Failed to fetch from Prometheus: {e}")
            return []

    def fetch_from_database(
        self, metric_name: str, service_name: str, time_range: str
    ) -> list[float]:
        """
        Fetch metric baseline statistics from chaos_platform database.

        Args:
            metric_name: Metric name (base name, not PromQL expression)
            service_name: Service name
            time_range: Time range (e.g., '24h', '30d') - used for context only

        Returns:
            List of synthetic values generated from baseline statistics
            (mean, mean±stddev, mean±2*stddev) to represent the baseline distribution
        """
        try:
            if not self._db:
                self._db = ChaosDb(host=self.db_host, port=self.db_port)

            # Extract base metric name if it's a PromQL expression
            base_metric_name = self._extract_base_metric_name(metric_name)
            
            # Query baseline_metrics table for stored statistics
            baseline_data = self._db.get_baseline_by_metric_and_service(
                base_metric_name, service_name
            )

            if not baseline_data:
                logger.debug(
                    f"No baseline found in database for {base_metric_name}/{service_name}"
                )
                return []

            # Extract statistics - use the field names from get_baseline_by_metric_and_service
            mean = float(baseline_data.get("mean", 0) or 0)
            stddev = float(baseline_data.get("stdev", 0) or 0)
            min_val = float(baseline_data.get("min_value", 0) or 0)
            max_val = float(baseline_data.get("max_value", 0) or 0)
            p50 = float(baseline_data.get("percentile_50", 0) or baseline_data.get("p50", 0) or 0)
            p95 = float(baseline_data.get("percentile_95", 0) or baseline_data.get("p95", 0) or 0)
            p99 = float(baseline_data.get("percentile_99", 0) or baseline_data.get("p99", 0) or 0)

            if mean == 0 and stddev == 0:
                logger.debug(f"Baseline has zero mean/stddev for {base_metric_name}")
                return []

            # Generate synthetic values representing the baseline distribution
            # This allows the calculator to work with the baseline statistics
            # We generate values around mean ± stddev to represent the distribution
            values = [
                mean - 2 * stddev,  # Lower bound
                mean - stddev,      # -1 sigma
                mean,               # Mean
                mean + stddev,      # +1 sigma
                mean + 2 * stddev,  # Upper bound
                p50,                # Median
                p95,                # 95th percentile
                p99,                # 99th percentile
                min_val,            # Min
                max_val,            # Max
            ]

            # Filter out invalid values
            values = [v for v in values if v >= 0 or mean < 0]  # Allow negative if mean is negative

            logger.debug(
                f"Fetched baseline statistics from database for {base_metric_name} "
                f"(mean: {mean:.2f}, stddev: {stddev:.2f})"
            )
            return values

        except Exception as e:
            logger.warning(f"Failed to fetch from database: {e}")
            return []

    def fetch_from_file(self, metric_name: str, file_path: str) -> dict[str, Any]:
        """
        Fetch metric baseline from JSON file.

        Args:
            metric_name: Metric name
            file_path: Path to baseline JSON file

        Returns:
            Baseline metric data dict
        """
        try:
            if not os.path.exists(file_path):
                logger.warning(f"Baseline file not found: {file_path}")
                return {}

            with open(file_path, encoding="utf-8") as f:
                data = json.load(f)

            # Search for metric in baseline_config.metrics[] or top-level metrics
            metrics = data.get("baseline_config", {}).get("metrics", []) or data.get(
                "metrics", []
            )

            for metric in metrics:
                if metric.get("metric_name") == metric_name:
                    baseline_stats = metric.get("baseline_statistics", {})
                    return {
                        "mean": baseline_stats.get("mean_value", 0),
                        "stddev": baseline_stats.get("stddev_value", 0),
                        "min": baseline_stats.get("min_value", 0),
                        "max": baseline_stats.get("max_value", 0),
                        "p50": baseline_stats.get("percentile_50", 0),
                        "p95": baseline_stats.get("percentile_95", 0),
                        "p99": baseline_stats.get("percentile_99", 0),
                    }

            logger.warning(f"Metric {metric_name} not found in {file_path}")
            return {}

        except Exception as e:
            logger.warning(f"Failed to fetch from file {file_path}: {e}")
            return {}

    def fetch_all(
        self,
        metric_name: str,
        service_name: str,
        time_range: str,
        sources: Optional[list[str]] = None,
        baseline_files: Optional[list[str]] = None,
    ) -> dict[str, Any]:
        """
        Fetch metric from all enabled sources in parallel.

        Args:
            metric_name: Metric name or PromQL query
            service_name: Service name
            time_range: Time range (e.g., '24h', '30d')
            sources: List of sources to use (default: all)
            baseline_files: List of baseline file paths to check

        Returns:
            Dict with source names as keys and values/lists as values
        """
        if sources is None:
            sources_str = os.getenv(
                "DYNAMIC_STEADY_STATE_SOURCES", "grafana,prometheus,database,file"
            )
            sources = [s.strip() for s in sources_str.split(",")]

        results: dict[str, Any] = {}

        # Fetch from time-series sources in parallel
        with ThreadPoolExecutor(max_workers=3) as executor:
            futures = {}

            if "grafana" in sources:
                futures["grafana"] = executor.submit(
                    self.fetch_from_grafana, metric_name, time_range
                )

            if "prometheus" in sources:
                futures["prometheus"] = executor.submit(
                    self.fetch_from_prometheus, metric_name, time_range
                )

            if "database" in sources:
                futures["database"] = executor.submit(
                    self.fetch_from_database, metric_name, service_name, time_range
                )

            # Wait for all futures
            for source, future in futures.items():
                try:
                    results[source] = future.result(timeout=self.timeout)
                except Exception as e:
                    logger.warning(f"Failed to fetch from {source}: {e}")
                    results[source] = []

        # Fetch from files (synchronous, fast)
        if "file" in sources and baseline_files:
            file_results = {}
            for file_path in baseline_files:
                file_data = self.fetch_from_file(metric_name, file_path)
                if file_data:
                    file_results[file_path] = file_data
            if file_results:
                results["file"] = file_results

        return results

    def _extract_base_metric_name(self, promql: str) -> str:
        """
        Extract base metric name from PromQL expression.
        
        Examples:
            rate(postgresql_commits_total[5m]) -> postgresql_commits_total
            increase(metric_name[1h]) -> metric_name
            metric_name -> metric_name
        """
        import re
        
        if not promql:
            return promql
        
        # Remove PromQL functions like rate(), increase(), etc.
        promql_clean = re.sub(
            r"(rate|increase|irate|delta|idelta|sum|avg|min|max|count|histogram_quantile)\s*\(",
            "",
            promql,
            flags=re.IGNORECASE,
        )
        
        # Remove closing parentheses and time ranges [5m], [1h], etc.
        promql_clean = re.sub(r"\[[^\]]+\]", "", promql_clean)
        promql_clean = re.sub(r"\)+", "", promql_clean)
        
        # Extract metric name (word characters, colons, underscores before { or whitespace)
        match = re.search(r"([a-zA-Z_:][a-zA-Z0-9_:]*)", promql_clean)
        if match:
            return match.group(1)
        
        # If no match, return original (might be a simple metric name)
        return promql

    @staticmethod
    def _parse_time_range(time_range: str, end_time: datetime) -> datetime:
        """
        Parse time range string to start time.

        Args:
            time_range: Time range (e.g., '24h', '30d', '7d')
            end_time: End time (default: now)

        Returns:
            Start time
        """
        time_range = time_range.lower().strip()

        if time_range.endswith("h"):
            hours = int(time_range[:-1])
            return end_time - timedelta(hours=hours)
        elif time_range.endswith("d"):
            days = int(time_range[:-1])
            return end_time - timedelta(days=days)
        elif time_range.endswith("m"):
            minutes = int(time_range[:-1])
            return end_time - timedelta(minutes=minutes)
        else:
            # Default to 24h
            logger.warning(
                f"Unknown time range format: {time_range}, defaulting to 24h"
            )
            return end_time - timedelta(hours=24)
