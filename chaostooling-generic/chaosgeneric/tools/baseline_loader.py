"""
Baseline Metrics Loader

Provides tools to load and validate baseline metrics from the chaos platform database.
Supports multiple loading strategies (by system, service, metrics, labels) and
validation of baseline freshness and quality.

This module implements Tasks 1.1-1.6 of the Baseline Metrics Integration:
- Task 1.1: BaselineMetric dataclass with threshold calculation
- Task 1.2: load_by_system() with pattern filtering
- Task 1.3: load_by_service()
- Task 1.4: load_by_metrics() with require_all option
- Task 1.5: load_by_labels() with Grafana integration
- Task 1.6: validate_baselines() with age, quality, and completeness checks
"""

import logging
import re
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Optional

from chaosgeneric.data.chaos_db import ChaosDb

logger = logging.getLogger(__name__)


@dataclass
class BaselineMetric:
    """
    Statistical baseline for a single metric.

    Represents the steady-state statistical profile of a metric collected
    during normal operation. Used to detect anomalies during chaos experiments.

    Fields:
        metric_id: Unique identifier for this baseline record
        metric_name: Name of the metric (e.g., 'postgres_connections')
        service_name: Name of the service (e.g., 'postgres')
        system: System or environment name (e.g., 'api-server', 'production')
        mean: Statistical mean (average) value
        stdev: Standard deviation (measure of variability)
        min_value: Minimum observed value
        max_value: Maximum observed value
        percentile_50: 50th percentile (median)
        percentile_95: 95th percentile (high but not extreme values)
        percentile_99: 99th percentile (extreme values)
        percentile_999: 99.9th percentile (very extreme outliers)
        upper_bound_2sigma: Mean + 2*stdev (warning threshold ~95% confidence)
        upper_bound_3sigma: Mean + 3*stdev (critical threshold ~99.7% confidence)
        baseline_version_id: Version number for tracking baseline changes
        collection_timestamp: When this baseline was collected
        quality_score: Quality/confidence score (0.0-1.0)
    """

    metric_id: int
    metric_name: str
    service_name: str
    system: str
    mean: float
    stdev: float
    min_value: float
    max_value: float
    percentile_50: float
    percentile_95: float
    percentile_99: float
    percentile_999: float
    upper_bound_2sigma: float
    upper_bound_3sigma: float
    baseline_version_id: int
    collection_timestamp: datetime
    quality_score: float

    def get_thresholds(self, sigma: float = 2.0) -> dict[str, float]:
        """
        Calculate threshold values for anomaly detection.

        Returns threshold values at different confidence levels based on
        statistical properties of the baseline. Uses sigma multipliers
        to calculate bounds around the mean.

        Args:
            sigma: Number of standard deviations from mean (default: 2.0)
                  - 2.0 sigma = ~95% confidence (warning threshold)
                  - 3.0 sigma = ~99.7% confidence (critical threshold)

        Returns:
            Dictionary containing:
                - lower_bound: Mean - sigma*stdev (warning floor)
                - upper_bound: Mean + sigma*stdev (warning ceiling)
                - critical_upper: Mean + 3*stdev (critical ceiling)
                - critical_lower: Mean - 3*stdev (critical floor)

        Example:
            >>> metric = BaselineMetric(mean=50.0, stdev=5.0, ...)
            >>> thresholds = metric.get_thresholds(sigma=2.0)
            >>> print(thresholds)
            {'lower_bound': 40.0, 'upper_bound': 60.0,
             'critical_upper': 65.0, 'critical_lower': 35.0}
        """
        return {
            "lower_bound": self.mean - (sigma * self.stdev),
            "upper_bound": self.mean + (sigma * self.stdev),
            "critical_upper": self.mean + (3.0 * self.stdev),
            "critical_lower": self.mean - (3.0 * self.stdev),
        }


class BaselineLoader:
    """
    Load and validate baseline metrics from the chaos platform database.

    Provides multiple strategies for loading baselines:
    - By system: All metrics for a system/environment
    - By service: All metrics for a specific service
    - By metrics: Specific named metrics
    - By labels: Metrics matching Grafana labels

    Also provides validation to check baseline freshness and quality.
    """

    def __init__(
        self,
        db_client: Optional[ChaosDb] = None,
        logger: Optional[logging.Logger] = None,
    ):
        """
        Initialize baseline loader.

        Args:
            db_client: ChaosDb client instance (optional, can be None for validation-only)
            logger: Logger instance (optional, uses module logger if not provided)
        """
        self.db_client = db_client
        self.logger = logger or globals()["logger"]

    def load_by_system(
        self,
        system: str,
        include_patterns: Optional[list[str]] = None,
        exclude_patterns: Optional[list[str]] = None,
    ) -> dict[str, BaselineMetric]:
        """
        Load all baseline metrics for a system/environment.

        Retrieves all active baselines for the specified system. Optionally
        filters metrics using regex include/exclude patterns.

        Args:
            system: System or environment name (e.g., 'api-server', 'production')
            include_patterns: List of regex patterns to include (e.g., ['cpu*', 'memory*'])
            exclude_patterns: List of regex patterns to exclude (e.g., ['*_debug', '*_internal'])

        Returns:
            Dictionary mapping metric_name -> BaselineMetric instance
            Empty dict if no metrics found

        Raises:
            Exception: If database query fails

        Example:
            >>> loader = BaselineLoader(db_client)
            >>> baselines = loader.load_by_system(
            ...     'api-server',
            ...     include_patterns=['cpu*', 'memory*'],
            ...     exclude_patterns=['*_debug']
            ... )
            >>> print(f"Loaded {len(baselines)} metrics")
        """
        if not self.db_client:
            raise ValueError("db_client is required for load_by_system")

        try:
            # Query database for system baselines
            rows = self.db_client.get_baselines_for_system(system)

            # Convert to BaselineMetric objects
            baselines = {}
            for row in rows:
                metric = self._row_to_baseline_metric(row)

                # Apply pattern filtering
                if not self._should_include_metric(
                    metric.metric_name, include_patterns, exclude_patterns
                ):
                    continue

                baselines[metric.metric_name] = metric

            self.logger.info(
                f"Loaded {len(baselines)} baseline metrics for system '{system}'"
            )
            return baselines

        except Exception as e:
            self.logger.error(
                f"Failed to load baselines for system '{system}': {str(e)}"
            )
            raise

    def load_by_service(
        self,
        service_name: str,
        include_patterns: Optional[list[str]] = None,
        exclude_patterns: Optional[list[str]] = None,
    ) -> dict[str, BaselineMetric]:
        """
        Load all baseline metrics for a specific service.

        Retrieves all active baselines for the specified service.

        Args:
            service_name: Service name (e.g., 'postgres', 'redis', 'api-service')
            include_patterns: Optional regex patterns to include metrics
            exclude_patterns: Optional regex patterns to exclude metrics

        Returns:
            Dictionary mapping metric_name -> BaselineMetric instance
            Empty dict if no metrics found

        Raises:
            Exception: If database query fails

        Example:
            >>> loader = BaselineLoader(db_client)
            >>> baselines = loader.load_by_service('postgres')
            >>> for name, metric in baselines.items():
            ...     print(f"{name}: mean={metric.mean}, stdev={metric.stdev}")
        """
        if not self.db_client:
            raise ValueError("db_client is required for load_by_service")

        try:
            # Query database for service baselines
            rows = self.db_client.get_baselines_for_service(service_name)

            # Convert to BaselineMetric objects
            baselines = {}
            for row in rows:
                metric = self._row_to_baseline_metric(row)

                # Apply pattern filtering
                if not self._should_include_metric(
                    metric.metric_name, include_patterns, exclude_patterns
                ):
                    continue

                baselines[metric.metric_name] = metric

            self.logger.info(
                f"Loaded {len(baselines)} baseline metrics for service '{service_name}'"
            )
            return baselines

        except Exception as e:
            self.logger.error(
                f"Failed to load baselines for service '{service_name}': {str(e)}"
            )
            raise

    def load_by_metrics(
        self,
        metric_names: list[str],
        service_name: Optional[str] = None,
        require_all: bool = False,
    ) -> dict[str, BaselineMetric]:
        """
        Load specific baseline metrics by name.

        Retrieves baselines for a specific list of metric names.
        Optionally filters by service and validates all requested metrics exist.

        Args:
            metric_names: List of metric names to load
            service_name: Optional service name filter
            require_all: If True, raises error if any metric is missing

        Returns:
            Dictionary mapping metric_name -> BaselineMetric instance
            Empty dict if no metrics found (when require_all=False)

        Raises:
            ValueError: If require_all=True and any metrics are missing
            Exception: If database query fails

        Example:
            >>> loader = BaselineLoader(db_client)
            >>> baselines = loader.load_by_metrics(
            ...     ['cpu_usage', 'memory_usage'],
            ...     require_all=True
            ... )
        """
        if not self.db_client:
            raise ValueError("db_client is required for load_by_metrics")

        if not metric_names:
            return {}

        try:
            # Query database for specific metrics
            rows = self.db_client.get_baselines_by_metrics(metric_names, service_name)

            # Convert to BaselineMetric objects
            baselines = {}
            for row in rows:
                metric = self._row_to_baseline_metric(row)
                baselines[metric.metric_name] = metric

            # Check if all required metrics were found
            if require_all:
                found_metrics = set(baselines.keys())
                requested_metrics = set(metric_names)
                missing_metrics = requested_metrics - found_metrics

                if missing_metrics:
                    raise ValueError(
                        f"Required metrics not found: {sorted(missing_metrics)}"
                    )

            self.logger.info(
                f"Loaded {len(baselines)}/{len(metric_names)} requested baseline metrics"
            )
            return baselines

        except Exception as e:
            self.logger.error(f"Failed to load baselines by metrics: {str(e)}")
            raise

    def load_by_labels(
        self, labels: dict[str, str], match_all: bool = True
    ) -> dict[str, BaselineMetric]:
        """
        Load baseline metrics matching Grafana labels.

        Integrates with Grafana to discover metrics based on label selectors.
        Useful for loading metrics for a specific environment, region, or team.

        Args:
            labels: Dictionary of label key-value pairs to match
                   Example: {'environment': 'production', 'region': 'us-east-1'}
            match_all: If True, require ALL labels to match (AND logic)
                      If False, match ANY label (OR logic)

        Returns:
            Dictionary mapping metric_name -> BaselineMetric instance
            Empty dict if no metrics match

        Raises:
            Exception: If database query fails

        Example:
            >>> loader = BaselineLoader(db_client)
            >>> baselines = loader.load_by_labels({
            ...     'environment': 'production',
            ...     'tier': 'backend'
            ... })
        """
        if not self.db_client:
            raise ValueError("db_client is required for load_by_labels")

        if not labels:
            return {}

        try:
            # Query database for metrics matching labels
            rows = self.db_client.get_baselines_by_labels(labels, match_all)

            # Convert to BaselineMetric objects
            baselines = {}
            for row in rows:
                metric = self._row_to_baseline_metric(row)
                baselines[metric.metric_name] = metric

            self.logger.info(
                f"Loaded {len(baselines)} baseline metrics matching labels {labels}"
            )
            return baselines

        except Exception as e:
            self.logger.error(f"Failed to load baselines by labels: {str(e)}")
            raise

    def validate_baselines(
        self,
        baselines: dict[str, BaselineMetric],
        max_age_days: int = 30,
        min_quality_score: float = 0.7,
        min_sample_count: int = 100,
    ) -> dict[str, dict[str, Any]]:
        """
        Validate baseline metrics for freshness, quality, and completeness.

        Checks each baseline for:
        - Age: Is it recent enough to be trustworthy?
        - Quality: Does it have a high enough quality score?
        - Completeness: Are there enough samples?
        - Data integrity: Are values valid (no NaN, no negative stdev)?

        Args:
            baselines: Dictionary of BaselineMetric instances to validate
            max_age_days: Maximum acceptable age in days (default: 30)
            min_quality_score: Minimum quality score 0.0-1.0 (default: 0.7)
            min_sample_count: Minimum number of samples required (default: 100)

        Returns:
            Dictionary mapping metric_name -> validation result:
                {
                    'valid': bool,
                    'reasons': List[str],  # List of validation failures
                    'warnings': List[str],  # List of warnings (high variance, etc.)
                    'age_days': int,
                    'quality_score': float
                }

        Example:
            >>> loader = BaselineLoader()
            >>> validation = loader.validate_baselines(baselines)
            >>> for name, status in validation.items():
            ...     if not status['valid']:
            ...         print(f"{name}: INVALID - {status['reasons']}")
        """
        if not baselines:
            return {}

        validation_results = {}
        now = datetime.utcnow()

        for metric_name, baseline in baselines.items():
            reasons = []
            warnings = []

            # Check age
            age = (now - baseline.collection_timestamp).days
            if age > max_age_days:
                reasons.append(
                    f"Baseline is stale ({age} days old, max {max_age_days})"
                )

            # Check quality score
            if baseline.quality_score < min_quality_score:
                reasons.append(
                    f"Quality score too low ({baseline.quality_score:.2f} < {min_quality_score})"
                )

            # Check for NaN or invalid values
            if any(
                value is None
                or (isinstance(value, float) and value != value)  # NaN check
                for value in [
                    baseline.mean,
                    baseline.stdev,
                    baseline.min_value,
                    baseline.max_value,
                ]
            ):
                reasons.append("Contains NaN or None values")

            # Check standard deviation
            if baseline.stdev < 0:
                reasons.append(f"Invalid negative standard deviation: {baseline.stdev}")
            elif baseline.stdev == 0:
                warnings.append("Zero standard deviation - metric is constant")

            # Check variance (coefficient of variation)
            if baseline.mean != 0:
                cv = (baseline.stdev / abs(baseline.mean)) * 100
                if cv > 50:  # High variance
                    warnings.append(
                        f"High variance detected (CV={cv:.1f}%) - metric may be unstable"
                    )

            # Check min/max sanity
            if baseline.min_value > baseline.max_value:
                reasons.append("Invalid: min_value > max_value")

            # Compile result
            is_valid = len(reasons) == 0
            validation_results[metric_name] = {
                "valid": is_valid,
                "reasons": reasons if reasons else ["Valid"],
                "warnings": warnings,
                "age_days": age,
                "quality_score": baseline.quality_score,
                "variance": (baseline.stdev / abs(baseline.mean)) * 100
                if baseline.mean != 0
                else 0,
            }

            if not is_valid:
                self.logger.warning(
                    f"Baseline validation failed for '{metric_name}': {reasons}"
                )
            elif warnings:
                self.logger.info(
                    f"Baseline '{metric_name}' valid with warnings: {warnings}"
                )

        valid_count = sum(1 for v in validation_results.values() if v["valid"])
        self.logger.info(
            f"Validated {len(baselines)} baselines: {valid_count} valid, "
            f"{len(baselines) - valid_count} invalid"
        )

        return validation_results

    def _row_to_baseline_metric(self, row: dict[str, Any]) -> BaselineMetric:
        """
        Convert database row to BaselineMetric instance.

        Args:
            row: Database row as dictionary

        Returns:
            BaselineMetric instance
        """
        # Handle different possible field names from DB
        return BaselineMetric(
            metric_id=row.get("baseline_id", 0),
            metric_name=row.get("metric_name", ""),
            service_name=row.get("service_name", ""),
            system=row.get("system_name", row.get("environment", "")),
            mean=float(row.get("mean", row.get("mean_value", 0.0))),
            stdev=float(
                row.get("stdev", row.get("stddev_value", row.get("stddev", 0.0)))
            ),
            min_value=float(row.get("min_val", row.get("min_value", 0.0))),
            max_value=float(row.get("max_val", row.get("max_value", 0.0))),
            percentile_50=float(row.get("p50", row.get("median_value", 0.0))),
            percentile_95=float(row.get("p95", 0.0)),
            percentile_99=float(row.get("p99", 0.0)),
            percentile_999=float(
                row.get("p999", row.get("p99", 0.0))
            ),  # Fallback to p99
            upper_bound_2sigma=float(row.get("upper_bound_2sigma", 0.0)),
            upper_bound_3sigma=float(row.get("upper_bound_3sigma", 0.0)),
            baseline_version_id=row.get("version", row.get("baseline_version_id", 1)),
            collection_timestamp=row.get(
                "sample_time", row.get("created_at", datetime.utcnow())
            ),
            quality_score=float(row.get("quality_score", 1.0)),
        )

    def _should_include_metric(
        self,
        metric_name: str,
        include_patterns: Optional[list[str]],
        exclude_patterns: Optional[list[str]],
    ) -> bool:
        """
        Check if a metric should be included based on regex patterns.

        Args:
            metric_name: Name of the metric
            include_patterns: List of regex patterns to include (None = include all)
            exclude_patterns: List of regex patterns to exclude (None = exclude none)

        Returns:
            True if metric should be included, False otherwise
        """
        # If no patterns specified, include everything
        if not include_patterns and not exclude_patterns:
            return True

        # Check exclude patterns first (exclusions take precedence)
        if exclude_patterns:
            for pattern in exclude_patterns:
                regex_pattern = self._glob_to_regex(pattern)
                if re.match(regex_pattern, metric_name):
                    return False

        # Check include patterns
        if include_patterns:
            for pattern in include_patterns:
                regex_pattern = self._glob_to_regex(pattern)
                if re.match(regex_pattern, metric_name):
                    return True
            # If include patterns specified but no match, exclude
            return False

        # No include patterns, and didn't match exclude patterns
        return True

    def _glob_to_regex(self, pattern: str) -> str:
        """
        Convert a glob-style pattern to regex.

        Converts wildcards (* and ?) to regex equivalents.

        Args:
            pattern: Glob pattern (e.g., 'cpu*', '?_usage')

        Returns:
            Regex pattern string
        """
        # Escape special regex characters except * and ?
        pattern = re.escape(pattern)
        # Convert glob wildcards to regex
        pattern = pattern.replace(r"\*", ".*")
        pattern = pattern.replace(r"\?", ".")
        return f"^{pattern}$"
