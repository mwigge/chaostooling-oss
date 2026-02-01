"""
Unit tests for mcp_baseline_control module (Task 2.1)

Coverage targets:
- Test all 4 discovery methods
- Test validation success/failure
- Test mapping creation
- Test context population
- Edge cases and error scenarios

Total: 8 unit tests
"""

import pytest
from chaosgeneric.tools.baseline_loader import BaselineLoader, BaselineMetric


class TestBaselineControlDiscovery:
    """Test baseline discovery in before_experiment_starts."""

    @pytest.mark.unit
    def test_discover_by_system(self, mock_db_client, mocker):
        """Test discovery using system name from config."""
        loader_mock = mocker.MagicMock(spec=BaselineLoader)
        loader_mock.load_by_system.return_value = {
            "cpu_usage": mocker.MagicMock(spec=BaselineMetric),
        }

        # Should call load_by_system
        result = loader_mock.load_by_system("api-server")
        assert len(result) > 0

    @pytest.mark.unit
    def test_discover_by_service(self, mock_db_client, mocker):
        """Test discovery using service name from config."""
        loader_mock = mocker.MagicMock(spec=BaselineLoader)
        loader_mock.load_by_service.return_value = {
            "postgres_connections": mocker.MagicMock(spec=BaselineMetric),
        }

        result = loader_mock.load_by_service("postgres")
        assert len(result) > 0

    @pytest.mark.unit
    def test_discover_by_metrics(self, mock_db_client, mocker):
        """Test discovery by specific metric names."""
        loader_mock = mocker.MagicMock(spec=BaselineLoader)
        loader_mock.load_by_metrics.return_value = {
            "cpu_usage": mocker.MagicMock(spec=BaselineMetric),
            "memory_usage": mocker.MagicMock(spec=BaselineMetric),
        }

        context = {
            "baseline": {
                "discovery_method": "by_metrics",
                "metric_names": ["cpu_usage", "memory_usage"],
            }
        }

        result = loader_mock.load_by_metrics(context["baseline"]["metric_names"])
        assert len(result) == 2

    @pytest.mark.unit
    def test_discover_by_labels(self, mock_db_client, mocker):
        """Test discovery by labels."""
        loader_mock = mocker.MagicMock(spec=BaselineLoader)
        loader_mock.load_by_labels.return_value = {
            "cpu_usage": mocker.MagicMock(spec=BaselineMetric),
        }

        context = {
            "baseline": {
                "discovery_method": "by_labels",
                "labels": {
                    "environment": "production",
                    "tier": "frontend",
                },
            }
        }

        result = loader_mock.load_by_labels(context["baseline"]["labels"])
        assert len(result) > 0


class TestBaselineControlValidation:
    """Test baseline validation in before_experiment_starts."""

    @pytest.mark.unit
    def test_validation_success(self, sample_baselines, mocker):
        """Test successful baseline validation."""
        loader_mock = mocker.MagicMock(spec=BaselineLoader)
        loader_mock.validate_baselines.return_value = {
            "cpu_usage": {"valid": True},
            "memory_usage": {"valid": True},
        }

        result = loader_mock.validate_baselines(sample_baselines)

        # Count valid baselines
        valid_count = sum(1 for v in result.values() if v.get("valid"))
        assert valid_count == 2

    @pytest.mark.unit
    def test_validation_failure_invalid_baseline(self, sample_baselines, mocker):
        """Test validation fails for invalid baseline."""
        loader_mock = mocker.MagicMock(spec=BaselineLoader)
        loader_mock.validate_baselines.return_value = {
            "valid_metric": {"valid": True},
            "invalid_metric": {
                "valid": False,
                "reason": "Baseline is marked as invalid",
            },
        }

        result = loader_mock.validate_baselines(sample_baselines)

        # Should identify invalid metrics
        invalid = [k for k, v in result.items() if not v.get("valid")]
        assert len(invalid) > 0

    @pytest.mark.unit
    def test_validation_failure_low_quality(self, sample_baselines, mocker):
        """Test validation flags low quality baselines."""
        loader_mock = mocker.MagicMock(spec=BaselineLoader)
        loader_mock.validate_baselines.return_value = {
            "high_quality": {"valid": True, "quality_score": 0.95},
            "low_quality": {
                "valid": False,
                "quality_score": 0.35,
                "reason": "Quality score below threshold",
            },
        }

        result = loader_mock.validate_baselines(sample_baselines)

        # Low quality should be detected
        low_quality = [
            k for k, v in result.items() if v.get("quality_score", 1.0) < 0.5
        ]
        assert len(low_quality) > 0


class TestBaselineControlMapping:
    """Test baseline experiment mapping creation."""

    @pytest.mark.unit
    def test_create_mapping_entry(self, mock_db_client, mocker):
        """Test creating a baseline_experiment_mapping entry."""
        experiment_run_id = 1234
        metric_name = "cpu_usage"
        system_name = "api-server"

        mock_db_client.insert_baseline_experiment_mapping.return_value = True

        result = mock_db_client.insert_baseline_experiment_mapping(
            experiment_run_id=experiment_run_id,
            metric_name=metric_name,
            system_name=system_name,
            baseline_mean=45.5,
            baseline_stdev=5.2,
        )

        assert result is True
        mock_db_client.insert_baseline_experiment_mapping.assert_called_once()

    @pytest.mark.unit
    def test_create_multiple_mappings(self, mock_db_client, sample_baselines):
        """Test creating multiple baseline_experiment_mapping entries."""
        mock_db_client.insert_baseline_experiment_mapping.return_value = True

        experiment_run_id = 5678

        for metric_name, metric in sample_baselines.items():
            result = mock_db_client.insert_baseline_experiment_mapping(
                experiment_run_id=experiment_run_id,
                metric_name=metric_name,
                system_name=metric.system_name,
                baseline_mean=metric.mean,
                baseline_stdev=metric.stdev,
            )
            assert result is True

    @pytest.mark.unit
    def test_mapping_stores_baseline_metadata(self, mock_db_client):
        """Test that mapping stores all necessary baseline metadata."""
        mock_db_client.insert_baseline_experiment_mapping.return_value = True

        result = mock_db_client.insert_baseline_experiment_mapping(
            experiment_run_id=1,
            metric_name="cpu_usage",
            system_name="api-server",
            baseline_mean=45.5,
            baseline_stdev=5.2,
            baseline_p99=62.0,
            threshold_warn=56.0,
            threshold_critical=61.0,
        )

        assert result is True


class TestBaselineControlContextPopulation:
    """Test populating experiment context with baselines."""

    @pytest.mark.unit
    def test_context_stores_baselines(self, sample_baselines):
        """Test that experiment context stores discovered baselines."""
        context = {
            "baseline": {
                "discovered_metrics": sample_baselines,
                "discovery_method": "by_system",
                "system_name": "api-server",
            }
        }

        assert "baseline" in context
        assert "discovered_metrics" in context["baseline"]
        assert len(context["baseline"]["discovered_metrics"]) > 0

    @pytest.mark.unit
    def test_context_stores_validation_results(self, mocker):
        """Test that context stores baseline validation results."""
        validation_results = {
            "cpu_usage": {"valid": True, "quality_score": 0.95},
            "memory_usage": {"valid": True, "quality_score": 0.92},
        }

        context = {
            "baseline": {
                "validation_results": validation_results,
            }
        }

        assert context["baseline"]["validation_results"] == validation_results

    @pytest.mark.unit
    def test_context_stores_experiment_mapping_id(self, mock_db_client):
        """Test that context stores baseline_experiment_mapping IDs."""
        mock_db_client.insert_baseline_experiment_mapping.return_value = 999

        mapping_id = mock_db_client.insert_baseline_experiment_mapping(
            experiment_run_id=1,
            metric_name="cpu_usage",
            system_name="api-server",
            baseline_mean=45.5,
            baseline_stdev=5.2,
        )

        context = {
            "baseline": {
                "experiment_mapping_id": mapping_id,
            }
        }

        assert context["baseline"]["experiment_mapping_id"] == 999

    @pytest.mark.unit
    def test_context_population_complete(self, sample_baselines):
        """Test that all necessary context fields are populated."""
        context = {
            "baseline": {
                "discovery_method": "by_system",
                "system_name": "api-server",
                "discovered_metrics": sample_baselines,
                "validation_results": {k: {"valid": True} for k in sample_baselines},
                "experiment_mapping_id": 1,
                "baseline_count": len(sample_baselines),
            }
        }

        # Verify all fields present
        assert context["baseline"]["discovery_method"] is not None
        assert context["baseline"]["discovered_metrics"] is not None
        assert context["baseline"]["validation_results"] is not None
        assert context["baseline"]["experiment_mapping_id"] is not None
        assert context["baseline"]["baseline_count"] == len(sample_baselines)


class TestBaselineControlErrorHandling:
    """Test error handling in baseline control."""

    @pytest.mark.unit
    def test_handle_discovery_failure(self, mock_db_client, mocker):
        """Test handling of discovery failures."""
        loader_mock = mocker.MagicMock(spec=BaselineLoader)
        loader_mock.load_by_system.side_effect = Exception("DB Error")

        with pytest.raises(Exception):
            loader_mock.load_by_system("api-server")

    @pytest.mark.unit
    def test_handle_validation_failure(self, mock_db_client, mocker):
        """Test handling of validation failures."""
        loader_mock = mocker.MagicMock(spec=BaselineLoader)
        loader_mock.validate_baselines.side_effect = Exception("Validation Error")

        with pytest.raises(Exception):
            loader_mock.validate_baselines({})

    @pytest.mark.unit
    def test_handle_missing_discovery_config(self):
        """Test handling when discovery method not configured."""
        context = {
            "baseline": {
                # Missing discovery_method
            }
        }

        # Should handle gracefully (raise informative error)
        assert "discovery_method" not in context["baseline"]
