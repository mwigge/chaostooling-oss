"""
Unit tests for DynamicSteadyStateCalculator.

Tests statistical calculation, aggregation, and hypothesis generation.
"""

import pytest

from chaosgeneric.tools.dynamic_steady_state_calculator import (
    DynamicSteadyStateCalculator,
)


class TestDynamicSteadyStateCalculator:
    """Test DynamicSteadyStateCalculator class."""

    def test_calculate_statistics_basic(self):
        """Test basic statistics calculation."""
        values = [10.0, 15.0, 20.0, 25.0, 30.0]
        stats = DynamicSteadyStateCalculator.calculate_statistics(values)

        assert stats["mean"] == 20.0
        assert stats["min"] == 10.0
        assert stats["max"] == 30.0
        assert stats["data_points"] == 5
        assert "p50" in stats
        assert "p95" in stats
        assert "p99" in stats

    def test_calculate_statistics_empty(self):
        """Test statistics calculation with empty values."""
        stats = DynamicSteadyStateCalculator.calculate_statistics([])

        assert stats["mean"] == 0.0
        assert stats["stddev"] == 0.0
        assert stats["min"] == 0.0
        assert stats["max"] == 0.0
        assert stats["data_points"] == 0

    def test_calculate_statistics_single_value(self):
        """Test statistics calculation with single value."""
        stats = DynamicSteadyStateCalculator.calculate_statistics([42.0])

        assert stats["mean"] == 42.0
        assert stats["stddev"] == 0.0
        assert stats["min"] == 42.0
        assert stats["max"] == 42.0
        assert stats["data_points"] == 1

    def test_aggregate_sources_time_series(self):
        """Test aggregation from time-series sources."""
        source_data = {
            "grafana": [10.0, 15.0, 20.0],
            "prometheus": [25.0, 30.0],
            "database": [35.0, 40.0],
        }

        result = DynamicSteadyStateCalculator.aggregate_sources(source_data, "test_metric")

        assert result["metric_name"] == "test_metric"
        assert result["data_points"] == 7  # 3 + 2 + 2
        assert result["mean"] > 0
        assert "sources" in result
        assert "quality_score" in result

    def test_aggregate_sources_file_fallback(self):
        """Test aggregation with file source as fallback."""
        source_data = {
            "file": {
                "baseline.json": {
                    "mean": 15.2,
                    "stddev": 3.8,
                    "min": 5.0,
                    "max": 32.1,
                    "p50": 14.6,
                    "p95": 23.8,
                    "p99": 28.9,
                }
            }
        }

        result = DynamicSteadyStateCalculator.aggregate_sources(source_data, "test_metric")

        assert result["metric_name"] == "test_metric"
        assert result["data_points"] > 0  # Synthetic values generated
        assert "sources" in result
        assert "file" in result["sources"]

    def test_aggregate_sources_no_data(self):
        """Test aggregation with no data."""
        source_data = {}

        result = DynamicSteadyStateCalculator.aggregate_sources(source_data, "test_metric")

        assert result["metric_name"] == "test_metric"
        assert result["data_points"] == 0
        assert result["quality_score"] == 0

    def test_generate_steady_state_hypothesis(self):
        """Test steady-state-hypothesis generation."""
        metrics = [
            {
                "metric_name": "test_metric_1",
                "mean": 15.0,
                "stddev": 3.0,
                "service_name": "test_service",
            },
            {
                "metric_name": "test_metric_2",
                "mean": 25.0,
                "stddev": 5.0,
                "service_name": "test_service",
            },
        ]

        hypothesis = DynamicSteadyStateCalculator.generate_steady_state_hypothesis(
            metrics, threshold_sigma=2.0
        )

        assert "title" in hypothesis
        assert "probes" in hypothesis
        assert len(hypothesis["probes"]) == 2

        # Check probe structure
        probe = hypothesis["probes"][0]
        assert "name" in probe
        assert "type" in probe
        assert probe["type"] == "probe"
        assert "provider" in probe
        assert "tolerance" in probe

    def test_generate_steady_state_hypothesis_empty(self):
        """Test hypothesis generation with empty metrics."""
        hypothesis = DynamicSteadyStateCalculator.generate_steady_state_hypothesis([])

        assert "title" in hypothesis
        assert "probes" in hypothesis
        assert len(hypothesis["probes"]) == 0

    def test_generate_steady_state_hypothesis_invalid_metrics(self):
        """Test hypothesis generation with invalid metrics (zero mean/stddev)."""
        metrics = [
            {
                "metric_name": "invalid_metric",
                "mean": 0.0,
                "stddev": 0.0,
                "service_name": "test_service",
            }
        ]

        hypothesis = DynamicSteadyStateCalculator.generate_steady_state_hypothesis(metrics)

        # Invalid metrics should be skipped
        assert len(hypothesis["probes"]) == 0

    def test_percentile_calculation(self):
        """Test percentile calculation."""
        sorted_data = [10.0, 20.0, 30.0, 40.0, 50.0]

        p50 = DynamicSteadyStateCalculator._percentile(sorted_data, 50)
        p95 = DynamicSteadyStateCalculator._percentile(sorted_data, 95)
        p99 = DynamicSteadyStateCalculator._percentile(sorted_data, 99)

        assert p50 == 30.0  # Median
        assert p95 > 40.0
        assert p99 > 45.0

    def test_percentile_empty(self):
        """Test percentile with empty data."""
        result = DynamicSteadyStateCalculator._percentile([], 50)
        assert result == 0.0

    def test_calculate_quality_score_high(self):
        """Test quality score calculation with high-quality data."""
        stats = {"data_points": 1000, "stddev": 5.0}
        score = DynamicSteadyStateCalculator._calculate_quality_score(stats, source_count=3)

        assert score >= 80  # High quality

    def test_calculate_quality_score_low(self):
        """Test quality score calculation with low-quality data."""
        stats = {"data_points": 5, "stddev": 0.0}
        score = DynamicSteadyStateCalculator._calculate_quality_score(stats, source_count=1)

        assert score < 50  # Low quality

    def test_calculate_quality_score_max(self):
        """Test quality score caps at 100."""
        stats = {"data_points": 10000, "stddev": 10.0}
        score = DynamicSteadyStateCalculator._calculate_quality_score(stats, source_count=4)

        assert score <= 100
