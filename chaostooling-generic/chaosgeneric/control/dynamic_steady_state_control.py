"""
Dynamic Steady-State Control - Automatic metrics retrieval and steady-state calculation.

Fetches metrics from Grafana, Prometheus, DB, and files, calculates dynamic steady-state,
and updates experiment steady-state-hypothesis before experiment execution.
"""

import logging
import os
from datetime import datetime
from typing import Any, Optional

from chaosgeneric.tools.baseline_loader import BaselineMetric
from chaosgeneric.tools.dynamic_metrics_fetcher import DynamicMetricsFetcher
from chaosgeneric.tools.dynamic_steady_state_calculator import (
    DynamicSteadyStateCalculator,
)
from chaosgeneric.tools.steady_state_formatter import SteadyStateFormatter

logger = logging.getLogger(__name__)


def configure_control(experiment: Optional[dict[str, Any]] = None, **kwargs) -> None:
    """Configure control (Chaos Toolkit hook)."""
    enabled = os.getenv("DYNAMIC_STEADY_STATE_ENABLED", "true").lower() == "true"
    if enabled:
        logger.info("Dynamic steady-state control enabled")
    else:
        logger.info("Dynamic steady-state control disabled")


def before_experiment_control(
    context: dict[str, Any],
    state: Any = None,
    experiment: Optional[dict[str, Any]] = None,
    **kwargs: Any,
) -> None:
    """
    Calculate and inject dynamic steady-state before experiment starts.

    This is the main entry point called by Chaos Toolkit.
    """
    # Check if enabled
    enabled = os.getenv("DYNAMIC_STEADY_STATE_ENABLED", "true").lower() == "true"
    if not enabled:
        logger.debug("Dynamic steady-state disabled via DYNAMIC_STEADY_STATE_ENABLED")
        return

    if not experiment:
        logger.warning(
            "No experiment provided, skipping dynamic steady-state calculation"
        )
        return

    try:
        logger.info("=" * 80)
        logger.info("DYNAMIC STEADY-STATE CALCULATION")
        logger.info("=" * 80)

        # Get configuration
        config = experiment.get("dynamic_steady_state", {})
        period = config.get("period") or os.getenv("DYNAMIC_STEADY_STATE_PERIOD", "30d")
        sources_str = config.get("sources") or os.getenv(
            "DYNAMIC_STEADY_STATE_SOURCES", "grafana,prometheus,database,file"
        )
        sources = (
            [s.strip() for s in sources_str.split(",")]
            if isinstance(sources_str, str)
            else sources_str
        )

        # Get metrics to analyze
        metrics_to_analyze = _extract_metrics(experiment, config)

        if not metrics_to_analyze:
            logger.warning("No metrics found to analyze, skipping dynamic steady-state")
            return

        logger.info(f"Analyzing {len(metrics_to_analyze)} metrics over {period}")
        logger.info(f"Sources: {', '.join(sources)}")

        # Get service name
        service_name = _extract_service_name(experiment)

        # Get baseline files
        baseline_files_str = os.getenv("DYNAMIC_STEADY_STATE_BASELINE_FILES", "")
        baseline_files = [f.strip() for f in baseline_files_str.split(",") if f.strip()]

        # Initialize fetcher
        fetcher = DynamicMetricsFetcher()

        # Calculate steady-state for each metric
        calculated_metrics = []
        for metric_name in metrics_to_analyze:
            logger.info(f"Processing metric: {metric_name}")

            # Fetch from all sources
            source_data = fetcher.fetch_all(
                metric_name=metric_name,
                service_name=service_name,
                time_range=period,
                sources=sources,
                baseline_files=baseline_files,
            )

            # Aggregate and calculate statistics
            metric_stats = DynamicSteadyStateCalculator.aggregate_sources(
                source_data, metric_name
            )
            metric_stats["service_name"] = service_name
            metric_stats["metric_name"] = metric_name  # Ensure metric_name is included
            calculated_metrics.append(metric_stats)

        if not calculated_metrics:
            logger.warning("No metrics calculated, skipping steady-state update")
            return

        # Generate steady-state-hypothesis
        threshold_sigma = float(config.get("threshold_sigma", 2.0))
        hypothesis = DynamicSteadyStateCalculator.generate_steady_state_hypothesis(
            calculated_metrics, threshold_sigma
        )

        # Update experiment steady-state-hypothesis
        experiment["steady-state-hypothesis"] = hypothesis

        # Store in context for probes (both formats for compatibility)
        context["dynamic_steady_state"] = {
            "metrics": calculated_metrics,
            "hypothesis": hypothesis,
            "period": period,
            "sources": sources,
        }

        # Convert to BaselineMetric objects and store in loaded_baselines for probe compatibility
        loaded_baselines: dict[str, BaselineMetric] = {}
        for metric_stats in calculated_metrics:
            metric_name = metric_stats.get("metric_name", "")
            if not metric_name:
                continue

            # Create BaselineMetric from calculated statistics
            baseline_metric = BaselineMetric(
                metric_id=0,  # Dynamic baselines don't have DB IDs
                metric_name=metric_name,
                service_name=metric_stats.get("service_name", ""),
                system="",
                mean=float(metric_stats.get("mean", 0.0)),
                stdev=float(metric_stats.get("stddev", 0.0)),
                min_value=float(metric_stats.get("min", 0.0)),
                max_value=float(metric_stats.get("max", 0.0)),
                percentile_50=float(metric_stats.get("p50", 0.0)),
                percentile_95=float(metric_stats.get("p95", 0.0)),
                percentile_99=float(metric_stats.get("p99", 0.0)),
                percentile_999=float(
                    metric_stats.get("p999", metric_stats.get("p99", 0.0))
                ),
                upper_bound_2sigma=float(metric_stats.get("mean", 0.0))
                + (2.0 * float(metric_stats.get("stddev", 0.0))),
                upper_bound_3sigma=float(metric_stats.get("mean", 0.0))
                + (3.0 * float(metric_stats.get("stddev", 0.0))),
                baseline_version_id=1,
                collection_timestamp=datetime.now(),
                quality_score=1.0,  # Dynamic baselines are considered high quality
            )
            loaded_baselines[metric_name] = baseline_metric

        # Store in context for probes to use
        if "loaded_baselines" not in context:
            context["loaded_baselines"] = {}
        context["loaded_baselines"].update(loaded_baselines)

        logger.info(
            f"Stored {len(loaded_baselines)} baseline metrics in context for probes"
        )

        # Print to console
        console_output = (
            os.getenv("DYNAMIC_STEADY_STATE_CONSOLE_OUTPUT", "true").lower() == "true"
        )
        if console_output:
            _print_to_console(calculated_metrics, hypothesis, period)

        logger.info("=" * 80)
        logger.info("Dynamic steady-state calculation complete")
        logger.info("=" * 80)

    except Exception as e:
        logger.error(f"Error calculating dynamic steady-state: {e}", exc_info=True)
        # Don't fail experiment, just log error


def _extract_metrics(experiment: dict[str, Any], config: dict[str, Any]) -> list[str]:
    """
    Extract metrics to analyze from experiment configuration.

    Priority:
    1. dynamic_steady_state.metrics (explicit)
    2. baseline_config.metrics[].metric_name
    3. steady-state-hypothesis.probes[].arguments.metric_name
    """
    metrics = []

    # Priority 1: Explicit metrics in config
    if "metrics" in config:
        metrics.extend(config["metrics"])
        return metrics

    # Priority 2: baseline_config.metrics
    baseline_config = experiment.get("baseline_config", {})
    baseline_metrics = baseline_config.get("metrics", [])
    for metric in baseline_metrics:
        metric_name = metric.get("metric_name")
        if metric_name:
            metrics.append(metric_name)

    # Priority 3: steady-state-hypothesis.probes
    ssh = experiment.get("steady-state-hypothesis", {})
    probes = ssh.get("probes", [])
    for probe in probes:
        args = probe.get("provider", {}).get("arguments", {})
        metric_name = args.get("metric_name")
        if metric_name:
            metrics.append(metric_name)

    # Remove duplicates
    return list(dict.fromkeys(metrics))


def _extract_service_name(experiment: dict[str, Any]) -> str:
    """Extract service name from experiment."""
    # Try baseline_config first
    baseline_config = experiment.get("baseline_config", {})
    discovery = baseline_config.get("discovery", {})
    service_name = discovery.get("service_name")
    if service_name:
        return service_name

    # Try from experiment title/description
    title = experiment.get("title", "").lower()
    if "postgres" in title:
        return "postgres"
    elif "mysql" in title:
        return "mysql"
    elif "redis" in title:
        return "redis"
    elif "kafka" in title:
        return "kafka"

    # Default
    return "unknown"


def _print_to_console(
    metrics: list[dict[str, Any]], hypothesis: dict[str, Any], time_range: str
) -> None:
    """Print formatted steady-state to console."""
    verbose = os.getenv("DYNAMIC_STEADY_STATE_VERBOSE", "false").lower() == "true"

    # Always print summary
    summary = SteadyStateFormatter.format_summary(metrics, time_range)
    print(summary)

    # Print metrics table
    table = SteadyStateFormatter.format_metrics_table(metrics)
    print(table)

    # Print hypothesis if verbose
    if verbose:
        hypothesis_str = SteadyStateFormatter.format_steady_state_hypothesis(hypothesis)
        print(hypothesis_str)
