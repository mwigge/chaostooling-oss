"""
Steady-State Formatter - Format steady-state data for console output.

Creates human-readable tables and highlights for experiment console.
"""

import logging
from typing import Any

logger = logging.getLogger(__name__)


class SteadyStateFormatter:
    """Format steady-state data for console output."""

    @staticmethod
    def format_metrics_table(metrics: list[dict[str, Any]]) -> str:
        """
        Format metrics as a table for console output.

        Args:
            metrics: List of metric statistics dicts

        Returns:
            Formatted table string
        """
        if not metrics:
            return "No metrics calculated."

        lines = []
        lines.append("=" * 100)
        lines.append("DYNAMIC STEADY-STATE METRICS")
        lines.append("=" * 100)
        lines.append("")
        lines.append(
            f"{'Metric':<40} {'Mean':<12} {'StdDev':<12} {'P95':<12} {'P99':<12} {'Quality':<10}"
        )
        lines.append("-" * 100)

        for metric in metrics:
            metric_name = metric.get("metric_name", "unknown")
            mean = metric.get("mean", 0)
            stddev = metric.get("stddev", 0)
            p95 = metric.get("p95", 0)
            p99 = metric.get("p99", 0)
            quality = metric.get("quality_score", 0)

            # Truncate long metric names
            if len(metric_name) > 38:
                metric_name = metric_name[:35] + "..."

            lines.append(
                f"{metric_name:<40} {mean:<12.2f} {stddev:<12.2f} {p95:<12.2f} {p99:<12.2f} {quality:<10}"
            )

        lines.append("")
        lines.append("=" * 100)

        return "\n".join(lines)

    @staticmethod
    def format_summary(metrics: list[dict[str, Any]], time_range: str) -> str:
        """
        Format summary information.

        Args:
            metrics: List of metric statistics dicts
            time_range: Time range used (e.g., '24h', '30d')

        Returns:
            Formatted summary string
        """
        lines = []
        lines.append("")
        lines.append("DYNAMIC STEADY-STATE SUMMARY")
        lines.append("-" * 50)
        lines.append(f"Time Period: {time_range}")
        lines.append(f"Metrics Calculated: {len(metrics)}")
        lines.append(
            f"Average Quality Score: {SteadyStateFormatter._avg_quality(metrics):.1f}%"
        )
        lines.append("")

        # List sources used
        all_sources = set()
        for metric in metrics:
            sources = metric.get("sources", [])
            all_sources.update(sources)

        if all_sources:
            lines.append(f"Data Sources: {', '.join(sorted(all_sources))}")

        lines.append("")

        return "\n".join(lines)

    @staticmethod
    def format_steady_state_hypothesis(hypothesis: dict[str, Any]) -> str:
        """
        Format steady-state-hypothesis for console.

        Args:
            hypothesis: Steady-state-hypothesis dict

        Returns:
            Formatted string
        """
        lines = []
        lines.append("")
        lines.append("DYNAMIC STEADY-STATE HYPOTHESIS")
        lines.append("-" * 50)
        lines.append(f"Title: {hypothesis.get('title', 'N/A')}")
        lines.append(f"Probes: {len(hypothesis.get('probes', []))}")
        lines.append("")

        for probe in hypothesis.get("probes", []):
            name = probe.get("name", "unknown")
            tolerance = probe.get("tolerance", {})
            if isinstance(tolerance, dict) and "lower" in tolerance:
                lines.append(
                    f"  - {name}: {tolerance.get('lower', 0):.2f} to {tolerance.get('upper', 0):.2f}"
                )
            else:
                lines.append(f"  - {name}: {tolerance}")

        lines.append("")

        return "\n".join(lines)

    @staticmethod
    def _avg_quality(metrics: list[dict[str, Any]]) -> float:
        """Calculate average quality score."""
        if not metrics:
            return 0.0

        total = sum(m.get("quality_score", 0) for m in metrics)
        return total / len(metrics)
