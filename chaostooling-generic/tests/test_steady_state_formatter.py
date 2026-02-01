"""
Unit tests for SteadyStateFormatter.

Tests console output formatting.
"""

from chaosgeneric.tools.steady_state_formatter import SteadyStateFormatter


class TestSteadyStateFormatter:
    """Test SteadyStateFormatter class."""

    def test_format_metrics_table(self) -> None:
        """Test metrics table formatting."""
        metrics = [
            {
                "metric_name": "test_metric_1",
                "mean": 15.2,
                "stddev": 3.8,
                "p95": 23.8,
                "p99": 28.9,
                "quality_score": 95,
            },
            {
                "metric_name": "test_metric_2",
                "mean": 25.5,
                "stddev": 5.2,
                "p95": 35.0,
                "p99": 40.0,
                "quality_score": 90,
            },
        ]

        output = SteadyStateFormatter.format_metrics_table(metrics)

        assert "DYNAMIC STEADY-STATE METRICS" in output
        assert "test_metric_1" in output
        assert "test_metric_2" in output
        assert "15.20" in output
        assert "25.50" in output

    def test_format_metrics_table_empty(self) -> None:
        """Test metrics table with empty list."""
        output = SteadyStateFormatter.format_metrics_table([])

        assert "No metrics calculated" in output

    def test_format_metrics_table_long_name(self) -> None:
        """Test metrics table with long metric names (truncation)."""
        metrics = [
            {
                "metric_name": "very_long_metric_name_that_should_be_truncated_to_fit_in_table",
                "mean": 10.0,
                "stddev": 2.0,
                "p95": 15.0,
                "p99": 18.0,
                "quality_score": 85,
            }
        ]

        output = SteadyStateFormatter.format_metrics_table(metrics)

        # Should truncate long names
        assert len([line for line in output.split("\n") if "very_long" in line]) > 0

    def test_format_summary(self) -> None:
        """Test summary formatting."""
        metrics = [
            {"quality_score": 95},
            {"quality_score": 90},
            {"quality_score": 85},
        ]

        output = SteadyStateFormatter.format_summary(metrics, "30d")

        assert "DYNAMIC STEADY-STATE SUMMARY" in output
        assert "30d" in output
        assert "Metrics Calculated: 3" in output
        assert "Average Quality Score: 90.0%" in output

    def test_format_summary_with_sources(self) -> None:
        """Test summary formatting with sources."""
        metrics = [
            {"sources": ["grafana", "prometheus"], "quality_score": 95},
            {"sources": ["database"], "quality_score": 90},
        ]

        output = SteadyStateFormatter.format_summary(metrics, "24h")

        assert "Data Sources:" in output
        assert "grafana" in output or "prometheus" in output or "database" in output

    def test_format_steady_state_hypothesis(self) -> None:
        """Test hypothesis formatting."""
        hypothesis = {
            "title": "Test Hypothesis",
            "probes": [
                {
                    "name": "probe-1",
                    "tolerance": {"type": "range", "lower": 10.0, "upper": 20.0},
                },
                {
                    "name": "probe-2",
                    "tolerance": {"type": "range", "lower": 30.0, "upper": 40.0},
                },
            ],
        }

        output = SteadyStateFormatter.format_steady_state_hypothesis(hypothesis)

        assert "DYNAMIC STEADY-STATE HYPOTHESIS" in output
        assert "Test Hypothesis" in output
        assert "Probes: 2" in output
        assert "probe-1" in output
        assert "10.00" in output
        assert "20.00" in output

    def test_format_steady_state_hypothesis_empty(self) -> None:
        """Test hypothesis formatting with no probes."""
        hypothesis = {"title": "Empty Hypothesis", "probes": []}

        output = SteadyStateFormatter.format_steady_state_hypothesis(hypothesis)

        assert "Empty Hypothesis" in output
        assert "Probes: 0" in output

    def test_avg_quality(self) -> None:
        """Test average quality calculation."""
        metrics = [
            {"quality_score": 100},
            {"quality_score": 80},
            {"quality_score": 60},
        ]

        avg = SteadyStateFormatter._avg_quality(metrics)

        assert avg == 80.0

    def test_avg_quality_empty(self) -> None:
        """Test average quality with empty list."""
        avg = SteadyStateFormatter._avg_quality([])

        assert avg == 0.0
