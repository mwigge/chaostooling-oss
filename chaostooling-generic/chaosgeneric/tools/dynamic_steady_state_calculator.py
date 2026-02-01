"""
Dynamic Steady-State Calculator - Calculate statistics from metric values.

Aggregates multi-source data and calculates mean, stddev, percentiles, and thresholds.
"""

import logging
import statistics
from typing import Any

logger = logging.getLogger(__name__)


class DynamicSteadyStateCalculator:
    """Calculate steady-state statistics from metric values."""

    @staticmethod
    def calculate_statistics(values: list[float]) -> dict[str, float]:
        """
        Calculate statistical baseline from metric values.

        Args:
            values: List of metric values

        Returns:
            Dict with mean, stddev, min, max, percentiles
        """
        if not values:
            return {
                "mean": 0.0,
                "stddev": 0.0,
                "min": 0.0,
                "max": 0.0,
                "p50": 0.0,
                "p95": 0.0,
                "p99": 0.0,
                "data_points": 0,
            }

        sorted_values = sorted(values)
        n = len(sorted_values)

        mean = statistics.mean(values)
        stddev = statistics.stdev(values) if n > 1 else 0.0

        return {
            "mean": round(mean, 2),
            "stddev": round(stddev, 2),
            "min": round(min(values), 2),
            "max": round(max(values), 2),
            "p50": round(
                DynamicSteadyStateCalculator._percentile(sorted_values, 50), 2
            ),
            "p95": round(
                DynamicSteadyStateCalculator._percentile(sorted_values, 95), 2
            ),
            "p99": round(
                DynamicSteadyStateCalculator._percentile(sorted_values, 99), 2
            ),
            "data_points": n,
        }

    @staticmethod
    def aggregate_sources(
        source_data: dict[str, Any], metric_name: str
    ) -> dict[str, Any]:
        """
        Aggregate metric values from multiple sources.

        Args:
            source_data: Dict with source names as keys and values/lists as values
            metric_name: Metric name for logging

        Returns:
            Aggregated statistics dict
        """
        all_values: list[float] = []

        # Collect values from time-series sources
        for source in ["grafana", "prometheus", "database"]:
            if source in source_data:
                values = source_data[source]
                if isinstance(values, list):
                    all_values.extend(values)
                    logger.debug(
                        f"Added {len(values)} values from {source} for {metric_name}"
                    )

        # If we have file data, use it as fallback or merge
        if "file" in source_data and source_data["file"]:
            file_data = source_data["file"]
            # File data is dict with stats, not raw values
            # Use it if we have no time-series data
            if not all_values:
                # Extract from file stats (approximate)
                for file_path, stats in file_data.items():
                    mean = stats.get("mean", 0)
                    stddev = stats.get("stddev", 0)
                    # Generate synthetic values around mean ± stddev
                    # This is approximate but better than nothing
                    if mean > 0:
                        synthetic = [
                            mean - stddev,
                            mean,
                            mean + stddev,
                            mean - 2 * stddev,
                            mean + 2 * stddev,
                        ]
                        all_values.extend(synthetic)
                        logger.debug(
                            f"Using file baseline from {file_path} for {metric_name}"
                        )

        if not all_values:
            logger.warning(f"No values found for {metric_name} from any source")
            return {
                "metric_name": metric_name,
                "mean": 0.0,
                "stddev": 0.0,
                "min": 0.0,
                "max": 0.0,
                "p50": 0.0,
                "p95": 0.0,
                "p99": 0.0,
                "data_points": 0,
                "sources": list(source_data.keys()),
                "quality_score": 0,
            }

        # Calculate statistics
        stats = DynamicSteadyStateCalculator.calculate_statistics(all_values)

        # Calculate quality score (0-100)
        quality_score = DynamicSteadyStateCalculator._calculate_quality_score(
            stats, len(source_data)
        )

        return {
            "metric_name": metric_name,
            **stats,
            "sources": list(source_data.keys()),
            "quality_score": quality_score,
        }

    @staticmethod
    def generate_steady_state_hypothesis(
        metrics: list[dict[str, Any]], threshold_sigma: float = 2.0
    ) -> dict[str, Any]:
        """
        Generate steady-state-hypothesis structure from calculated metrics.

        Args:
            metrics: List of metric statistics dicts
            threshold_sigma: Sigma threshold for tolerance (default: 2.0)

        Returns:
            Steady-state-hypothesis dict compatible with Chaos Toolkit
        """
        probes = []

        for metric in metrics:
            metric_name = metric.get("metric_name", "unknown")
            mean = metric.get("mean", 0)
            stddev = metric.get("stddev", 0)

            if mean == 0 and stddev == 0:
                continue  # Skip invalid metrics

            # Calculate tolerance bounds (for reference, not used in tolerance: true)
            # lower_bound = mean - (threshold_sigma * stddev)
            # upper_bound = mean + (threshold_sigma * stddev)

            probe = {
                "name": f"check-{metric_name.replace('.', '-').replace('{', '').replace('}', '')}",
                "type": "probe",
                "provider": {
                    "type": "python",
                    "module": "chaosgeneric.probes.mcp_baseline_probe",
                    "func": "check_metric_within_baseline",
                    "arguments": {
                        "metric_name": metric_name,
                        "service_name": metric.get("service_name", "unknown"),
                        "threshold_sigma": threshold_sigma,
                        "description": f"{metric_name} within {threshold_sigma}σ of baseline",
                    },
                },
                "tolerance": True,  # Probe returns boolean, not numeric value
            }

            probes.append(probe)

        return {
            "title": "Dynamic steady-state based on historical metrics",
            "probes": probes,
        }

    @staticmethod
    def _percentile(sorted_data: list[float], percentile: int) -> float:
        """Calculate percentile of sorted data."""
        if not sorted_data:
            return 0.0

        n = len(sorted_data)
        index = (percentile / 100.0) * (n - 1)

        if index.is_integer():
            return sorted_data[int(index)]
        else:
            lower = sorted_data[int(index)]
            upper = sorted_data[int(index) + 1] if int(index) + 1 < n else lower
            return lower + (upper - lower) * (index - int(index))

    @staticmethod
    def _calculate_quality_score(stats: dict[str, float], source_count: int) -> int:
        """
        Calculate data quality score (0-100).

        Factors:
        - Number of data points (more is better)
        - Number of sources (more is better)
        - Data completeness (stddev > 0 indicates variance)

        Args:
            stats: Statistics dict
            source_count: Number of sources used

        Returns:
            Quality score (0-100)
        """
        data_points = stats.get("data_points", 0)
        stddev = stats.get("stddev", 0)

        # Data points score (0-50 points)
        if data_points >= 1000:
            points_score = 50
        elif data_points >= 100:
            points_score = 40
        elif data_points >= 10:
            points_score = 30
        elif data_points > 0:
            points_score = 20
        else:
            points_score = 0

        # Source count score (0-30 points)
        if source_count >= 3:
            source_score = 30
        elif source_count == 2:
            source_score = 20
        elif source_count == 1:
            source_score = 10
        else:
            source_score = 0

        # Variance score (0-20 points) - stddev > 0 indicates real data
        if stddev > 0:
            variance_score = 20
        else:
            variance_score = 0

        return min(points_score + source_score + variance_score, 100)
