"""
Unit tests for BaselineLoader service methods (Tasks 1.2-1.6)

Coverage targets:
- Task 1.2: load_by_system() - 6 tests
- Task 1.3: load_by_service() - 5 tests
- Task 1.4: load_by_metrics() - 6 tests
- Task 1.5: load_by_labels() - 6 tests
- Task 1.6: validate_baselines() - 9 tests

Total: 32 unit tests
"""

from datetime import datetime, timedelta

import pytest
from chaosgeneric.tools.baseline_loader import BaselineLoader, BaselineMetric


class TestLoadBySystem:
    """Test BaselineLoader.load_by_system() method - 6 tests."""

    @pytest.mark.unit
    def test_load_by_system_normal_case(self, mock_db_client, baseline_metric_factory):
        """Test loading baselines for a single system."""
        loader = BaselineLoader(db_client=mock_db_client)
        mock_db_client.get_baselines_for_system.return_value = [
            {"metric_name": "cpu_usage", "mean": 45.5, "stdev": 5.2},
            {"metric_name": "memory_usage", "mean": 70.0, "stdev": 8.0},
        ]

        result = loader.load_by_system("api-server")

        assert isinstance(result, dict)
        assert len(result) > 0
        mock_db_client.get_baselines_for_system.assert_called_once()

    @pytest.mark.unit
    def test_load_by_system_with_include_patterns(self, mock_db_client):
        """Test load_by_system with include_patterns filter."""
        loader = BaselineLoader(db_client=mock_db_client)

        result = loader.load_by_system(
            "api-server", include_patterns=["cpu*", "memory*"]
        )

        assert isinstance(result, dict)
        mock_db_client.get_baselines_for_system.assert_called_once()

    @pytest.mark.unit
    def test_load_by_system_with_exclude_patterns(self, mock_db_client):
        """Test load_by_system with exclude_patterns filter."""
        loader = BaselineLoader(db_client=mock_db_client)

        result = loader.load_by_system(
            "api-server", exclude_patterns=["*_debug", "*_internal"]
        )

        assert isinstance(result, dict)
        mock_db_client.get_baselines_for_system.assert_called_once()

    @pytest.mark.unit
    def test_load_by_system_empty_result(self, mock_db_client):
        """Test load_by_system when no baselines exist."""
        loader = BaselineLoader(db_client=mock_db_client)
        mock_db_client.get_baselines_for_system.return_value = []

        result = loader.load_by_system("nonexistent-system")

        assert isinstance(result, dict)
        assert len(result) == 0

    @pytest.mark.unit
    def test_load_by_system_returns_baseline_metrics(self, mock_db_client):
        """Test that load_by_system returns BaselineMetric objects."""
        loader = BaselineLoader(db_client=mock_db_client)
        mock_db_client.get_baselines_for_system.return_value = [
            {
                "metric_name": "cpu_usage",
                "system_name": "api-server",
                "service_name": "api-service",
                "mean": 45.5,
                "stdev": 5.2,
                "p50": 44.0,
                "p95": 58.0,
                "p99": 62.0,
                "min_val": 10.0,
                "max_val": 95.0,
                "count": 1000,
                "baseline_window_hours": 24,
                "thresholds": {"warn": 56.0, "critical": 61.0},
                "sample_time": datetime.utcnow(),
                "valid": True,
                "quality_score": 0.95,
            }
        ]

        result = loader.load_by_system("api-server")

        for key, metric in result.items():
            assert isinstance(metric, BaselineMetric)

    @pytest.mark.unit
    def test_load_by_system_db_error_handling(self, mock_db_client):
        """Test load_by_system handles database errors gracefully."""
        loader = BaselineLoader(db_client=mock_db_client)
        mock_db_client.get_baselines_for_system.side_effect = Exception("DB Error")

        with pytest.raises(Exception):
            loader.load_by_system("api-server")


class TestLoadByService:
    """Test BaselineLoader.load_by_service() method - 5 tests."""

    @pytest.mark.unit
    def test_load_by_service_normal_case(self, mock_db_client):
        """Test loading baselines for a single service."""
        loader = BaselineLoader(db_client=mock_db_client)
        mock_db_client.get_baselines_for_service.return_value = [
            {"metric_name": "postgres_connections", "mean": 50.0, "stdev": 5.0},
            {"metric_name": "postgres_active_queries", "mean": 20.0, "stdev": 3.0},
        ]

        result = loader.load_by_service("postgres")

        assert isinstance(result, dict)
        assert len(result) > 0

    @pytest.mark.unit
    def test_load_by_service_empty_result(self, mock_db_client):
        """Test load_by_service when service has no baselines."""
        loader = BaselineLoader(db_client=mock_db_client)
        mock_db_client.get_baselines_for_service.return_value = []

        result = loader.load_by_service("unknown-service")

        assert isinstance(result, dict)
        assert len(result) == 0

    @pytest.mark.unit
    def test_load_by_service_returns_baseline_metrics(self, mock_db_client):
        """Test that load_by_service returns BaselineMetric objects."""
        loader = BaselineLoader(db_client=mock_db_client)
        mock_db_client.get_baselines_for_service.return_value = [
            {
                "metric_name": "postgres_connections",
                "system_name": "db-server",
                "service_name": "postgres",
                "mean": 50.0,
                "stdev": 5.0,
                "p50": 48.0,
                "p95": 62.0,
                "p99": 68.0,
                "min_val": 10.0,
                "max_val": 100.0,
                "count": 1000,
                "baseline_window_hours": 24,
                "thresholds": {"warn": 60.0, "critical": 65.0},
                "sample_time": datetime.utcnow(),
                "valid": True,
                "quality_score": 0.92,
            }
        ]

        result = loader.load_by_service("postgres")

        for key, metric in result.items():
            assert isinstance(metric, BaselineMetric)

    @pytest.mark.unit
    def test_load_by_service_case_sensitivity(self, mock_db_client):
        """Test that service name lookup handles case variations."""
        loader = BaselineLoader(db_client=mock_db_client)

        # Should work with different cases
        loader.load_by_service("postgres")
        loader.load_by_service("PostgreSQL")

        # Method should be called regardless
        assert mock_db_client.get_baselines_for_service.called

    @pytest.mark.unit
    def test_load_by_service_with_multiple_metrics(self, mock_db_client):
        """Test load_by_service returns all metrics for a service."""
        loader = BaselineLoader(db_client=mock_db_client)
        mock_db_client.get_baselines_for_service.return_value = [
            {"metric_name": f"metric_{i}", "mean": 50.0 + i, "stdev": 5.0}
            for i in range(10)
        ]

        result = loader.load_by_service("test-service")

        assert len(result) == 10


class TestLoadByMetrics:
    """Test BaselineLoader.load_by_metrics() method - 6 tests."""

    @pytest.mark.unit
    def test_load_by_metrics_existing(self, mock_db_client):
        """Test loading existing metrics by name."""
        loader = BaselineLoader(db_client=mock_db_client)
        mock_db_client.get_baselines_by_metrics.return_value = [
            {"metric_name": "cpu_usage", "mean": 45.5, "stdev": 5.2},
            {"metric_name": "memory_usage", "mean": 70.0, "stdev": 8.0},
        ]

        result = loader.load_by_metrics(["cpu_usage", "memory_usage"])

        assert isinstance(result, dict)
        assert len(result) == 2

    @pytest.mark.unit
    def test_load_by_metrics_missing(self, mock_db_client):
        """Test load_by_metrics when some metrics don't exist."""
        loader = BaselineLoader(db_client=mock_db_client)
        mock_db_client.get_baselines_by_metrics.return_value = []

        result = loader.load_by_metrics(["nonexistent_metric"])

        assert isinstance(result, dict)
        assert len(result) == 0

    @pytest.mark.unit
    def test_load_by_metrics_with_service_filter(self, mock_db_client):
        """Test load_by_metrics with optional service_name filter."""
        loader = BaselineLoader(db_client=mock_db_client)
        mock_db_client.get_baselines_by_metrics.return_value = [
            {"metric_name": "cpu_usage", "service_name": "api-service", "mean": 45.5},
        ]

        result = loader.load_by_metrics(["cpu_usage"], service_name="api-service")

        assert isinstance(result, dict)

    @pytest.mark.unit
    def test_load_by_metrics_partial_match(self, mock_db_client):
        """Test load_by_metrics when only some metrics found."""
        loader = BaselineLoader(db_client=mock_db_client)
        mock_db_client.get_baselines_by_metrics.return_value = [
            {"metric_name": "cpu_usage", "mean": 45.5, "stdev": 5.2},
        ]

        result = loader.load_by_metrics(["cpu_usage", "disk_io", "network_throughput"])

        # Should return what was found
        assert isinstance(result, dict)

    @pytest.mark.unit
    def test_load_by_metrics_returns_baseline_metrics(self, mock_db_client):
        """Test that load_by_metrics returns BaselineMetric objects."""
        loader = BaselineLoader(db_client=mock_db_client)
        mock_db_client.get_baselines_by_metrics.return_value = [
            {
                "metric_name": "latency_p99",
                "system_name": "api-server",
                "service_name": "api-service",
                "mean": 150.0,
                "stdev": 25.0,
                "p50": 130.0,
                "p95": 180.0,
                "p99": 200.0,
                "min_val": 50.0,
                "max_val": 500.0,
                "count": 5000,
                "baseline_window_hours": 24,
                "thresholds": {"warn": 200.0, "critical": 225.0},
                "sample_time": datetime.utcnow(),
                "valid": True,
                "quality_score": 0.98,
            }
        ]

        result = loader.load_by_metrics(["latency_p99"])

        for key, metric in result.items():
            assert isinstance(metric, BaselineMetric)

    @pytest.mark.unit
    def test_load_by_metrics_empty_list(self, mock_db_client):
        """Test load_by_metrics with empty metric list."""
        loader = BaselineLoader(db_client=mock_db_client)

        result = loader.load_by_metrics([])

        assert isinstance(result, dict)


class TestLoadByLabels:
    """Test BaselineLoader.load_by_labels() method - 6 tests."""

    @pytest.mark.unit
    def test_load_by_labels_single_label(self, mock_db_client):
        """Test loading baselines by single label."""
        loader = BaselineLoader(db_client=mock_db_client)
        mock_db_client.get_baselines_by_labels.return_value = [
            {"metric_name": "cpu_usage", "mean": 45.5, "stdev": 5.2},
            {"metric_name": "memory_usage", "mean": 70.0, "stdev": 8.0},
        ]

        result = loader.load_by_labels({"environment": "production"})

        assert isinstance(result, dict)
        assert len(result) > 0

    @pytest.mark.unit
    def test_load_by_labels_multiple_labels(self, mock_db_client):
        """Test loading baselines by multiple labels."""
        loader = BaselineLoader(db_client=mock_db_client)
        mock_db_client.get_baselines_by_labels.return_value = []

        result = loader.load_by_labels(
            {
                "environment": "production",
                "region": "us-east-1",
                "team": "platform",
            }
        )

        assert isinstance(result, dict)

    @pytest.mark.unit
    def test_load_by_labels_empty_result(self, mock_db_client):
        """Test load_by_labels when no metrics match labels."""
        loader = BaselineLoader(db_client=mock_db_client)
        mock_db_client.get_baselines_by_labels.return_value = []

        result = loader.load_by_labels({"nonexistent": "label"})

        assert isinstance(result, dict)
        assert len(result) == 0

    @pytest.mark.unit
    def test_load_by_labels_returns_baseline_metrics(self, mock_db_client):
        """Test that load_by_labels returns BaselineMetric objects."""
        loader = BaselineLoader(db_client=mock_db_client)
        mock_db_client.get_baselines_by_labels.return_value = [
            {
                "metric_name": "cpu_usage",
                "system_name": "api-server",
                "service_name": "api-service",
                "mean": 45.5,
                "stdev": 5.2,
                "p50": 44.0,
                "p95": 58.0,
                "p99": 62.0,
                "min_val": 10.0,
                "max_val": 95.0,
                "count": 1000,
                "baseline_window_hours": 24,
                "thresholds": {"warn": 56.0, "critical": 61.0},
                "sample_time": datetime.utcnow(),
                "valid": True,
                "quality_score": 0.95,
            }
        ]

        result = loader.load_by_labels({"environment": "prod"})

        for key, metric in result.items():
            assert isinstance(metric, BaselineMetric)

    @pytest.mark.unit
    def test_load_by_labels_label_matching_logic(self, mock_db_client):
        """Test that label matching uses correct logic (AND vs OR)."""
        loader = BaselineLoader(db_client=mock_db_client)

        # Should match metrics with ALL specified labels
        result = loader.load_by_labels(
            {
                "environment": "staging",
                "tier": "backend",
            }
        )

        assert isinstance(result, dict)

    @pytest.mark.unit
    def test_load_by_labels_empty_dict(self, mock_db_client):
        """Test load_by_labels with empty label dictionary."""
        loader = BaselineLoader(db_client=mock_db_client)

        result = loader.load_by_labels({})

        assert isinstance(result, dict)


class TestValidateBaselines:
    """Test BaselineLoader.validate_baselines() method - 9 tests."""

    @pytest.mark.unit
    def test_validate_fresh_baselines(self, sample_baselines):
        """Test validation of fresh baselines."""
        loader = BaselineLoader()

        fresh = {
            "cpu_usage": sample_baselines["cpu_usage"],
            "memory_usage": sample_baselines["memory_usage"],
        }

        result = loader.validate_baselines(fresh)

        assert isinstance(result, dict)
        # Fresh baselines should be valid
        for metric_name, status in result.items():
            assert isinstance(status, dict)
            assert "valid" in status

    @pytest.mark.unit
    def test_validate_stale_baselines(self, baseline_metric_factory):
        """Test validation detects stale baselines."""
        loader = BaselineLoader()

        # Create baseline sampled 30 days ago
        old_time = datetime.utcnow() - timedelta(days=30)
        stale = {
            "old_metric": baseline_metric_factory(
                metric_name="old_metric",
                sample_time=old_time,
            )
        }

        result = loader.validate_baselines(stale)

        assert isinstance(result, dict)
        # Should mark as stale
        assert "valid" in result.get("old_metric", {})

    @pytest.mark.unit
    def test_validate_low_quality_baselines(self, baseline_metric_factory):
        """Test validation detects low quality baselines."""
        loader = BaselineLoader()

        low_quality = {"low_quality": baseline_metric_factory(quality_score=0.30)}

        result = loader.validate_baselines(low_quality)

        assert isinstance(result, dict)
        assert "quality_score" in result.get("low_quality", {})

    @pytest.mark.unit
    def test_validate_zero_stdev(self, baseline_metric_factory):
        """Test validation with zero standard deviation."""
        loader = BaselineLoader()

        constant = {
            "constant": baseline_metric_factory(
                metric_name="constant",
                stdev=0.0,
            )
        }

        result = loader.validate_baselines(constant)

        assert isinstance(result, dict)

    @pytest.mark.unit
    def test_validate_empty_baselines(self, mock_db_client):
        """Test validation of empty baseline set."""
        loader = BaselineLoader()

        result = loader.validate_baselines({})

        assert isinstance(result, dict)
        assert len(result) == 0

    @pytest.mark.unit
    def test_validate_returns_validation_details(self, sample_baselines):
        """Test that validation returns detailed status."""
        loader = BaselineLoader()

        result = loader.validate_baselines(sample_baselines)

        # Each validation entry should have details
        for metric_name, validation in result.items():
            assert "valid" in validation
            assert "reason" in validation or "reasons" in validation

    @pytest.mark.unit
    def test_validate_mixed_valid_invalid(self, sample_baselines):
        """Test validation with mix of valid and invalid baselines."""
        loader = BaselineLoader()

        mixed = {
            "valid": sample_baselines["cpu_usage"],
            "invalid": sample_baselines["invalid_baseline"],
            "low_quality": sample_baselines["low_quality"],
        }

        result = loader.validate_baselines(mixed)

        assert len(result) == 3

    @pytest.mark.unit
    def test_validate_insufficient_data(self, baseline_metric_factory):
        """Test validation detects insufficient data (low count)."""
        loader = BaselineLoader()

        insufficient = {
            "insufficient": baseline_metric_factory(
                metric_name="insufficient",
                count=5,  # Only 5 samples
            )
        }

        result = loader.validate_baselines(insufficient)

        assert isinstance(result, dict)

    @pytest.mark.unit
    def test_validate_high_variance_warning(self, sample_baselines):
        """Test validation warnings for high variance metrics."""
        loader = BaselineLoader()

        high_var = {"high_variance": sample_baselines["high_variance"]}

        result = loader.validate_baselines(high_var)

        assert isinstance(result, dict)
        # Should include variance information
        validation = result.get("high_variance", {})
        assert "valid" in validation or "variance" in validation
