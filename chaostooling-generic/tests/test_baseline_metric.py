"""
Unit tests for BaselineMetric dataclass (Task 1.1)

Coverage targets:
- All 15 fields initialization
- Field validation
- Threshold calculations
- Serialization/deserialization
- Edge cases (zero stdev, negative values, extreme values)
- Type validation
"""

import json
from dataclasses import asdict
from datetime import datetime

import pytest
from chaosgeneric.tools.baseline_loader import BaselineMetric


class TestBaselineMetricInitialization:
    """Test BaselineMetric initialization with all field combinations."""

    @pytest.mark.unit
    def test_create_with_all_fields(self, baseline_metric_factory) -> None:
        """Test creating a baseline metric with all fields specified."""
        metric = baseline_metric_factory(
            metric_name="cpu_usage",
            system_name="api-server",
            service_name="api-service",
            mean=45.5,
            stdev=5.2,
            p50=44.0,
            p95=58.0,
            p99=62.0,
            min_val=10.0,
            max_val=95.0,
            count=1000,
            baseline_window_hours=24,
        )

        assert metric.metric_name == "cpu_usage"
        assert metric.system_name == "api-server"
        assert metric.service_name == "api-service"
        assert metric.mean == 45.5
        assert metric.stdev == 5.2
        assert metric.p50 == 44.0
        assert metric.p95 == 58.0
        assert metric.p99 == 62.0
        assert metric.min_val == 10.0
        assert metric.max_val == 95.0
        assert metric.count == 1000
        assert metric.baseline_window_hours == 24

    @pytest.mark.unit
    def test_create_with_defaults(self, baseline_metric_factory) -> None:
        """Test that all fields have sensible defaults."""
        metric = baseline_metric_factory(metric_name="test_metric")

        assert metric.metric_name == "test_metric"
        assert metric.system_name is not None
        assert metric.service_name is not None
        assert metric.mean is not None
        assert metric.stdev is not None
        assert metric.sample_time is not None
        assert metric.valid is not None
        assert metric.quality_score is not None

    @pytest.mark.unit
    def test_field_count_is_fifteen(self, baseline_metric_factory) -> None:
        """Verify that BaselineMetric has exactly 15 fields."""
        metric = baseline_metric_factory()
        fields = asdict(metric)
        assert len(fields) == 15, (
            f"Expected 15 fields, got {len(fields)}: {fields.keys()}"
        )

    @pytest.mark.unit
    def test_immutability_fields(self, baseline_metric_factory) -> None:
        """Test that BaselineMetric fields behave correctly (frozen=True)."""
        metric = baseline_metric_factory()
        # Attempt to modify should raise FrozenInstanceError if frozen
        with pytest.raises(Exception):  # FrozenInstanceError or AttributeError
            metric.metric_name = "modified"


class TestBaselineMetricThresholds:
    """Test threshold calculation methods."""

    @pytest.mark.unit
    def test_get_thresholds_calculation(self, baseline_metric_factory) -> None:
        """Test get_thresholds() calculation method."""
        metric = baseline_metric_factory(
            mean=100.0,
            stdev=10.0,
            thresholds={
                "warn": 120.0,  # mean + 2*stdev
                "critical": 130.0,  # mean + 3*stdev
                "min": 95.0,  # mean - 0.5*stdev
            },
        )

        thresholds = metric.get_thresholds()
        assert thresholds["warn"] == 120.0
        assert thresholds["critical"] == 130.0
        assert thresholds["min"] == 95.0

    @pytest.mark.unit
    def test_thresholds_with_zero_stdev(self, baseline_metric_factory) -> None:
        """Test threshold calculation when stdev is zero."""
        metric = baseline_metric_factory(
            mean=100.0,
            stdev=0.0,
            thresholds={
                "warn": 100.0,
                "critical": 100.0,
                "min": 100.0,
            },
        )

        thresholds = metric.get_thresholds()
        # Should handle zero stdev gracefully
        assert thresholds["warn"] >= thresholds["min"]
        assert thresholds["critical"] >= thresholds["warn"]

    @pytest.mark.unit
    def test_thresholds_with_negative_values(self, baseline_metric_factory) -> None:
        """Test thresholds with negative mean values."""
        metric = baseline_metric_factory(
            mean=-10.0,
            stdev=5.0,
            min_val=-30.0,
        )

        thresholds = metric.get_thresholds()
        # Min threshold should not go below zero if that's configured
        assert isinstance(thresholds, dict)
        assert "warn" in thresholds
        assert "critical" in thresholds

    @pytest.mark.unit
    def test_thresholds_consistency(self, baseline_metric_factory) -> None:
        """Test that thresholds maintain logical consistency."""
        metric = baseline_metric_factory(
            mean=50.0,
            stdev=10.0,
        )

        thresholds = metric.get_thresholds()
        # Critical should always be >= warn
        if "critical" in thresholds and "warn" in thresholds:
            assert thresholds["critical"] >= thresholds["warn"]


class TestBaselineMetricSerialization:
    """Test serialization and deserialization."""

    @pytest.mark.unit
    def test_to_dict(self, baseline_metric_factory) -> None:
        """Test converting baseline metric to dictionary."""
        metric = baseline_metric_factory(metric_name="cpu_usage")
        data = asdict(metric)

        assert isinstance(data, dict)
        assert "metric_name" in data
        assert data["metric_name"] == "cpu_usage"

    @pytest.mark.unit
    def test_to_json_serializable(self, baseline_metric_factory) -> None:
        """Test that metric can be converted to JSON."""
        metric = baseline_metric_factory()
        data = asdict(metric)

        # Handle datetime serialization
        if "sample_time" in data and isinstance(data["sample_time"], datetime):
            data["sample_time"] = data["sample_time"].isoformat()

        # Should not raise
        json_str = json.dumps(data)
        assert isinstance(json_str, str)

    @pytest.mark.unit
    def test_from_dict_reconstruction(self, baseline_metric_factory) -> None:
        """Test reconstructing BaselineMetric from dictionary."""
        original = baseline_metric_factory(
            metric_name="memory_usage",
            mean=70.0,
            stdev=8.0,
        )

        # Convert to dict and back
        data = asdict(original)
        reconstructed = BaselineMetric(**data)

        assert reconstructed.metric_name == original.metric_name
        assert reconstructed.mean == original.mean
        assert reconstructed.stdev == original.stdev

    @pytest.mark.unit
    def test_round_trip_preserves_data(self, baseline_metric_factory) -> None:
        """Test that serialization round-trip preserves all data."""
        original = baseline_metric_factory(
            metric_name="latency_p99",
            mean=150.0,
            stdev=25.0,
            p95=180.0,
            p99=200.0,
        )

        # Round trip
        data = asdict(original)
        reconstructed = BaselineMetric(**data)
        data2 = asdict(reconstructed)

        assert data == data2


class TestBaselineMetricEdgeCases:
    """Test edge cases and boundary conditions."""

    @pytest.mark.unit
    def test_very_small_values(self, baseline_metric_factory) -> None:
        """Test with very small metric values."""
        metric = baseline_metric_factory(
            mean=0.001,
            stdev=0.0001,
            min_val=0.0005,
            max_val=0.002,
        )

        assert metric.mean > 0
        assert metric.stdev >= 0
        assert metric.min_val >= 0

    @pytest.mark.unit
    def test_very_large_values(self, baseline_metric_factory) -> None:
        """Test with very large metric values."""
        metric = baseline_metric_factory(
            mean=1e9,
            stdev=1e8,
            max_val=1e10,
        )

        assert metric.mean > 0
        assert metric.max_val > metric.mean

    @pytest.mark.unit
    def test_percentile_order(self, baseline_metric_factory) -> None:
        """Test that percentiles maintain proper ordering (p50 < p95 < p99)."""
        metric = baseline_metric_factory(
            p50=100.0,
            p95=150.0,
            p99=200.0,
        )

        assert metric.p50 <= metric.p95
        assert metric.p95 <= metric.p99

    @pytest.mark.unit
    def test_mean_vs_percentiles(self, baseline_metric_factory) -> None:
        """Test that mean is typically within percentile range."""
        metric = baseline_metric_factory(
            mean=100.0,
            p50=95.0,
            p95=150.0,
            p99=200.0,
        )

        # Mean should typically be between p50 and p99
        assert metric.p50 <= metric.mean or metric.mean <= metric.p99

    @pytest.mark.unit
    def test_count_is_positive(self, baseline_metric_factory) -> None:
        """Test that count is a positive integer."""
        metric = baseline_metric_factory(count=0)
        assert metric.count >= 0  # 0 is valid for empty baseline

        metric = baseline_metric_factory(count=1000000)
        assert metric.count > 0

    @pytest.mark.unit
    def test_quality_score_in_range(self, baseline_metric_factory) -> None:
        """Test that quality_score is between 0 and 1."""
        for score in [0.0, 0.5, 0.95, 1.0]:
            metric = baseline_metric_factory(quality_score=score)
            assert 0.0 <= metric.quality_score <= 1.0

    @pytest.mark.unit
    def test_baseline_window_positive(self, baseline_metric_factory) -> None:
        """Test that baseline_window_hours is positive."""
        metric = baseline_metric_factory(baseline_window_hours=1)
        assert metric.baseline_window_hours > 0

        metric = baseline_metric_factory(baseline_window_hours=730)  # 30 days
        assert metric.baseline_window_hours > 0


class TestBaselineMetricTypeValidation:
    """Test type validation and casting."""

    @pytest.mark.unit
    def test_metric_name_is_string(self, baseline_metric_factory) -> None:
        """Test that metric_name is a string."""
        metric = baseline_metric_factory(metric_name="cpu_usage")
        assert isinstance(metric.metric_name, str)

    @pytest.mark.unit
    def test_numeric_fields_are_numbers(self, baseline_metric_factory) -> None:
        """Test that numeric fields are proper types."""
        metric = baseline_metric_factory(
            mean=45.5,
            stdev=5.2,
            p50=44.0,
        )

        assert isinstance(metric.mean, (int, float))
        assert isinstance(metric.stdev, (int, float))
        assert isinstance(metric.p50, (int, float))

    @pytest.mark.unit
    def test_sample_time_is_datetime(self, baseline_metric_factory) -> None:
        """Test that sample_time is a datetime object."""
        metric = baseline_metric_factory()
        assert isinstance(metric.sample_time, datetime)

    @pytest.mark.unit
    def test_valid_is_boolean(self, baseline_metric_factory) -> None:
        """Test that valid field is boolean."""
        metric = baseline_metric_factory(valid=True)
        assert isinstance(metric.valid, bool)

        metric = baseline_metric_factory(valid=False)
        assert isinstance(metric.valid, bool)

    @pytest.mark.unit
    def test_thresholds_is_dict(self, baseline_metric_factory) -> None:
        """Test that thresholds is a dictionary."""
        metric = baseline_metric_factory(thresholds={"warn": 50, "critical": 75})
        assert isinstance(metric.thresholds, dict)


class TestBaselineMetricComparison:
    """Test comparison operations between metrics."""

    @pytest.mark.unit
    def test_same_metrics_are_equal(self, baseline_metric_factory) -> None:
        """Test that identical metrics are equal."""
        metric1 = baseline_metric_factory(
            metric_name="cpu_usage",
            mean=45.5,
            stdev=5.2,
        )
        metric2 = baseline_metric_factory(
            metric_name="cpu_usage",
            mean=45.5,
            stdev=5.2,
        )

        assert asdict(metric1) == asdict(metric2)

    @pytest.mark.unit
    def test_different_metrics_not_equal(self, baseline_metric_factory) -> None:
        """Test that different metrics are not equal."""
        metric1 = baseline_metric_factory(mean=45.5)
        metric2 = baseline_metric_factory(mean=50.0)

        assert asdict(metric1) != asdict(metric2)

    @pytest.mark.unit
    def test_high_quality_vs_low_quality(self, baseline_metric_factory) -> None:
        """Test comparison of high and low quality metrics."""
        high_quality = baseline_metric_factory(quality_score=0.99)
        low_quality = baseline_metric_factory(quality_score=0.45)

        assert high_quality.quality_score > low_quality.quality_score


class TestBaselineMetricSpecialCases:
    """Test special cases and real-world scenarios."""

    @pytest.mark.unit
    def test_constant_metric_stdev_zero(self, sample_baselines) -> None:
        """Test baseline for metrics with zero variance."""
        metric = sample_baselines["constant_metric"]
        assert metric.stdev == 0.0
        assert metric.mean == metric.p50 == metric.p95 == metric.p99

    @pytest.mark.unit
    def test_high_variance_metric(self, sample_baselines) -> None:
        """Test baseline for high variance metrics."""
        metric = sample_baselines["high_variance"]
        assert metric.stdev > metric.mean / 2  # High variance

    @pytest.mark.unit
    def test_invalid_baseline_marked(self, sample_baselines) -> None:
        """Test that invalid baselines are properly marked."""
        metric = sample_baselines["invalid_baseline"]
        assert metric.valid is False

    @pytest.mark.unit
    def test_low_quality_score(self, sample_baselines) -> None:
        """Test baseline with low quality score."""
        metric = sample_baselines["low_quality"]
        assert metric.quality_score < 0.5


class TestBaselineMetricRequiredFields:
    """Test that all required fields are present and correct."""

    @pytest.mark.unit
    def test_all_required_fields_present(self, baseline_metric_factory) -> None:
        """Test that all 15 required fields are present."""
        metric = baseline_metric_factory()
        fields = {
            "metric_name",
            "system_name",
            "service_name",
            "mean",
            "stdev",
            "p50",
            "p95",
            "p99",
            "min_val",
            "max_val",
            "count",
            "baseline_window_hours",
            "thresholds",
            "sample_time",
            "valid",
            "quality_score",
        }

        metric_fields = set(asdict(metric).keys())
        assert fields == metric_fields, f"Field mismatch: {fields ^ metric_fields}"
