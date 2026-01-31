#!/usr/bin/env python3
"""
Phase 4: Baseline Manager Commands

Implements three new command methods for the BaselineManager class:
1. discover() - Find and load baselines by system/service/labels
2. status() - Show baseline status for an experiment
3. suggest_for_experiment() - Recommend baselines for an experiment

This module provides production-ready implementations with full error handling,
logging, and type safety.
"""

import logging
import re
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any

from chaosgeneric.data.chaos_db import ChaosDb
from chaosgeneric.tools.baseline_loader import BaselineLoader, BaselineMetric

logger = logging.getLogger(__name__)


# ============================================================================
# Scoring Constants
# ============================================================================

# Weights for baseline scoring in suggest_for_experiment()
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
        db_client: Optional[ChaosDb] = None,
        logger: Optional[logging.Logger] = None,
    ):
        """
        Initialize BaselineManager.

        Args:
            db_client: ChaosDb instance for database access
            logger: Logger instance (uses module logger if not provided)
        """
        self.db = db_client
        self.baseline_loader = BaselineLoader(db_client=db_client, logger=logger)
        self.logger = logger or globals()["logger"]

    # ========================================================================
    # COMMAND 1: discover()
    # ========================================================================

    def discover(
        self,
        system_id: Optional[str] = None,
        service_id: Optional[str] = None,
        labels: Optional[Dict[str, str]] = None,
        show_details: bool = False,
    ) -> Dict[str, Any]:
        """
        Discover and load baselines by system, service, or labels.

        Discovers baseline metrics that match the specified discovery criteria.
        At least one of system_id, service_id, or labels must be provided.

        Args:
            system_id: System/environment name (e.g., 'api-server', 'postgres')
                      Optional; case-insensitive
            service_id: Service name (e.g., 'postgres', 'redis', 'payment-api')
                       Optional; case-insensitive
            labels: Dictionary of label key-value pairs to match
                   (e.g., {'environment': 'production', 'region': 'us-east-1'})
                   Optional; all labels must match (AND logic)
            show_details: If True, include detailed statistics (percentile_999, etc.)
                         Default: False for better performance

        Returns:
            Dictionary with keys:
                - status: "success" or "error"
                - discovered_count: Number of baselines found
                - discovery_method: "system", "service", or "labels"
                - baselines: List of baseline dictionaries
                - metadata: Dictionary with discovery metadata
                - message: Human-readable summary message

        Raises:
            ValueError: If no discovery parameters provided or invalid
            Exception: If database query fails

        Example:
            >>> manager = BaselineManager(db_client)
            >>> result = manager.discover(system_id='postgres')
            >>> print(f"Found {result['discovered_count']} baselines")
            >>> for baseline in result['baselines']:
            ...     print(f"  {baseline['metric_name']}: {baseline['mean_value']}")
        """
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

            # Validate system_id format
            if system_id and not self._is_valid_identifier(system_id):
                raise ValueError(f"system_id contains invalid characters: {system_id}")

            # Validate service_id format
            if service_id and not self._is_valid_identifier(service_id):
                raise ValueError(
                    f"service_id contains invalid characters: {service_id}"
                )

            # Discover baselines
            baselines_dict: Dict[str, BaselineMetric] = {}
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
                    "total_requested": None,  # Unknown for discovery
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

    # ========================================================================
    # COMMAND 2: status()
    # ========================================================================

    def status(
        self,
        experiment_id: int,
        show_inactive: bool = False,
        show_skipped: bool = False,
    ) -> Dict[str, Any]:
        """
        Get baseline status for an experiment.

        Queries v_experiment_baselines view to retrieve all baselines that were
        loaded for the specified experiment, including their current status
        and calculated threshold bounds.

        Args:
            experiment_id: ID of the experiment (required)
                          Must exist in experiments table
            show_inactive: If True, include INACTIVE baselines
                          Default: False (show only ACTIVE)
            show_skipped: If True, include SKIPPED baselines
                         Default: False (show only ACTIVE)

        Returns:
            Dictionary with keys:
                - status: "success" or "error"
                - experiment_id: The queried experiment ID
                - experiment_name: Name/title of the experiment
                - baselines: List of baseline status dictionaries
                - active_count: Number of ACTIVE baselines
                - inactive_count: Number of INACTIVE baselines
                - skipped_count: Number of SKIPPED baselines
                - message: Human-readable summary

        Raises:
            ValueError: If experiment_id is invalid
            Exception: If database query fails

        Example:
            >>> manager = BaselineManager(db_client)
            >>> result = manager.status(experiment_id=42)
            >>> print(f"Experiment {result['experiment_name']}")
            >>> print(f"  Active: {result['active_count']}")
            >>> print(f"  Inactive: {result['inactive_count']}")
            >>> for baseline in result['baselines']:
            ...     print(f"  {baseline['metric_name']}: {baseline['status']}")
        """
        start_time = datetime.utcnow()

        try:
            # Validation
            if not isinstance(experiment_id, int):
                raise ValueError(
                    f"experiment_id must be int, got {type(experiment_id)}"
                )
            if experiment_id <= 0:
                raise ValueError(f"experiment_id must be positive, got {experiment_id}")

            # Check if experiment exists
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
                    "status": "success",
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

    # ========================================================================
    # COMMAND 3: suggest_for_experiment()
    # ========================================================================

    def suggest_for_experiment(
        self, experiment_id: int, min_quality_score: int = 75, top_n: int = 20
    ) -> Dict[str, Any]:
        """
        Suggest baselines for an experiment based on service.

        Analyzes all baselines for the experiment's service and ranks them
        by a composite scoring function that weights:
        - Quality score (40%)
        - Freshness (30%)
        - Stability/low variance (20%)
        - Validity of bounds (10%)

        Args:
            experiment_id: ID of the experiment (required)
                          Must exist in experiments table
            min_quality_score: Minimum quality score to consider (0-100)
                             Default: 75
            top_n: Maximum number of suggestions to return
                  Default: 20

        Returns:
            Dictionary with keys:
                - status: "success" or "error"
                - experiment_id: The queried experiment ID
                - service_name: Name of the service
                - suggestions: List of recommended baseline dictionaries
                - total_suggestions: Number of recommendations
                - metadata: Dictionary with scoring metadata
                - message: Human-readable summary

        Raises:
            ValueError: If experiment_id is invalid
            Exception: If database query fails

        Example:
            >>> manager = BaselineManager(db_client)
            >>> result = manager.suggest_for_experiment(experiment_id=42)
            >>> print(f"Top {len(result['suggestions'])} suggestions for {result['service_name']}")
            >>> for i, suggestion in enumerate(result['suggestions'], 1):
            ...     print(f"{i}. {suggestion['metric_name']}: {suggestion['recommendation_score']:.1f}")
        """
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

            # Get experiment and service
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

    # ========================================================================
    # Helper Methods
    # ========================================================================

    def _is_valid_identifier(self, identifier: str) -> bool:
        """
        Check if identifier contains only valid characters.

        Valid: alphanumeric, underscore, hyphen, dot
        Invalid: special characters like ! @ # $ etc.
        """
        if not identifier:
            return False
        return bool(re.match(r"^[a-zA-Z0-9_\-\.]+$", identifier))

    def _build_discovery_params(
        self,
        system_id: Optional[str],
        service_id: Optional[str],
        labels: Optional[Dict[str, str]],
    ) -> Dict[str, Any]:
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
        self, metric: BaselineMetric, discovery_method: str, show_details: bool = False
    ) -> Dict[str, Any]:
        """Convert BaselineMetric to dictionary for discover() response."""
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

    def _baseline_status_row_to_dict(self, row: Dict[str, Any]) -> Dict[str, Any]:
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

    def _score_baseline(self, metric: BaselineMetric) -> tuple[float, Dict[str, float]]:
        """
        Calculate composite recommendation score for a baseline.

        Uses weighted combination of:
        - Quality score (normalized 0-1): 40%
        - Freshness score (0-1): 30%
        - Stability/low variance (0-1): 20%
        - Validity of bounds (0-1): 10%

        Returns:
            Tuple of (overall_score, score_breakdown_dict)
            overall_score ranges from 0-100
        """
        # Quality score (0-100 -> 0-1)
        quality_norm = metric.quality_score

        # Freshness score (based on age)
        age_days = (datetime.utcnow() - metric.collection_timestamp).days
        freshness_days = age_days / 30.0  # normalize to 30-day windows
        freshness_score = max(0.0, 1.0 - (freshness_days / FRESHNESS_WINDOW_DAYS))
        freshness_score = min(1.0, freshness_score)

        # Stability score (inverse of coefficient of variation)
        # Lower stddev/mean ratio = higher stability score
        if metric.mean > 0:
            cv_ratio = metric.stdev / metric.mean
            stability_score = 1.0 / (1.0 + cv_ratio)
        else:
            stability_score = 0.5
        stability_score = min(1.0, max(0.0, stability_score))

        # Validity score (how reasonable are the bounds)
        # Check if max-min is reasonable relative to stddev
        if metric.stdev > 0:
            bounds_range = metric.max_value - metric.min_value
            expected_range = 4.0 * metric.stdev  # ~4 sigma encompasses most values
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
        metric: BaselineMetric,
        metric_name: str,
        overall_score: float,
        score_breakdown: Dict[str, float],
    ) -> Dict[str, Any]:
        """Convert scored baseline to dictionary for suggest_for_experiment() response."""
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

    def _generate_recommendation_reason(self, score_breakdown: Dict[str, float]) -> str:
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

    def _estimate_quality_percentile(self, score_breakdown: Dict[str, float]) -> str:
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

    def _get_experiment(self, experiment_id: int) -> Optional[Dict[str, Any]]:
        """
        Get experiment by ID from database.

        Returns:
            Dictionary with experiment data or None if not found
        """
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

    def _query_experiment_baselines(self, experiment_id: int) -> List[Dict[str, Any]]:
        """
        Query v_experiment_baselines view for an experiment.

        Returns:
            List of baseline rows from the view
        """
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
