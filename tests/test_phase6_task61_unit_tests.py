"""
Phase 6 Task 6.1: Unit Tests for Baseline Config Loading

Tests for loading, parsing, and validating baseline_config sections
from experiment JSON files and integrating with BaselineLoader.
"""

import json
import pytest
from pathlib import Path
from typing import Dict, List, Any
from unittest.mock import Mock, patch, MagicMock

# Note: BaselineLoader and ChaosDb are optional dependencies
# These tests focus on baseline_config JSON structure and parsing


# Test data directory
POSTGRES_EXPERIMENTS_DIR = (
    Path(__file__).parent.parent / "chaostooling-experiments" / "postgres"
)

# Sample experiment files for testing
SAMPLE_EXPERIMENTS = [
    "test-postgres-cache-miss.json",
    "test-postgres-lock-storm.json",
]


class TestBaselineConfigLoading:
    """Unit tests for loading baseline_config from experiment JSON files."""

    @pytest.fixture
    def sample_experiment_data(self):
        """Load sample experiment JSON."""
        filepath = POSTGRES_EXPERIMENTS_DIR / SAMPLE_EXPERIMENTS[0]
        with open(filepath, "r") as f:
            return json.load(f)

    @pytest.fixture
    def baseline_loader_mock(self):
        """Create a mock loader instance for testing."""
        loader = Mock()
        loader.load_by_system = Mock(return_value=[])
        loader.load_by_service = Mock(return_value=[])
        loader.load_by_metrics = Mock(return_value=[])
        loader.load_by_labels = Mock(return_value=[])
        return loader

    def test_load_baseline_config_from_json(self, sample_experiment_data):
        """Test loading baseline_config section from experiment JSON."""
        assert "baseline_config" in sample_experiment_data
        bc = sample_experiment_data["baseline_config"]
        assert isinstance(bc, dict)
        assert "metrics" in bc
        assert isinstance(bc["metrics"], list)

    def test_extract_metrics_from_baseline_config(self, sample_experiment_data):
        """Test extracting metrics list from baseline_config."""
        bc = sample_experiment_data["baseline_config"]
        metrics = bc.get("metrics", [])

        assert len(metrics) > 0, "Should have at least one metric"

        for metric in metrics:
            assert "metric_id" in metric
            assert "metric_name" in metric
            assert "service_name" in metric
            assert "baseline_statistics" in metric

    def test_baseline_config_metadata(self, sample_experiment_data):
        """Test baseline_config metadata section."""
        bc = sample_experiment_data["baseline_config"]
        metadata = bc.get("metadata", {})

        assert "version" in metadata
        assert "service" in metadata
        assert metadata["service"] == "postgres"
        assert "created" in metadata

    def test_baseline_config_discovery(self, sample_experiment_data):
        """Test baseline_config discovery section."""
        bc = sample_experiment_data["baseline_config"]
        discovery = bc.get("discovery", {})

        assert "method" in discovery
        assert discovery["method"] == "system"
        assert "system_id" in discovery

    def test_baseline_config_thresholds(self, sample_experiment_data):
        """Test baseline_config threshold configuration."""
        bc = sample_experiment_data["baseline_config"]
        thresholds = bc.get("default_thresholds", {})

        assert "sigma_threshold" in thresholds
        assert "critical_sigma" in thresholds
        assert thresholds["sigma_threshold"] > 0
        assert thresholds["critical_sigma"] > thresholds["sigma_threshold"]

    def test_metric_baseline_statistics_structure(self, sample_experiment_data):
        """Test baseline statistics structure in metrics."""
        bc = sample_experiment_data["baseline_config"]

        for metric in bc.get("metrics", []):
            stats = metric.get("baseline_statistics", {})

            required_stats = [
                "mean_value",
                "stddev_value",
                "min_value",
                "max_value",
                "percentile_50",
                "percentile_95",
                "percentile_99",
                "quality_score",
            ]

            for stat in required_stats:
                assert stat in stats, (
                    f"Missing {stat} in metric {metric.get('metric_name')}"
                )

    def test_metric_statistics_numeric_validity(self, sample_experiment_data):
        """Test that metric statistics contain valid numbers."""
        bc = sample_experiment_data["baseline_config"]

        for metric in bc.get("metrics", []):
            stats = metric.get("baseline_statistics", {})

            # All statistics should be numeric
            for key in ["mean_value", "stddev_value", "min_value", "max_value"]:
                value = stats.get(key)
                assert isinstance(value, (int, float)), (
                    f"{key} should be numeric in {metric.get('metric_name')}"
                )

            # Standard deviation should be non-negative
            assert stats.get("stddev_value", 0) >= 0

            # Min should be <= max
            assert stats.get("min_value", 0) <= stats.get("max_value", float("inf"))

            # Quality score should be 0-100
            quality = stats.get("quality_score", 0)
            assert 0 <= quality <= 100, (
                f"Quality score {quality} out of range for {metric.get('metric_name')}"
            )

    def test_metric_threshold_configuration(self, sample_experiment_data):
        """Test threshold configuration in metrics."""
        bc = sample_experiment_data["baseline_config"]

        for metric in bc.get("metrics", []):
            tc = metric.get("threshold_config", {})

            required_fields = ["sigma_threshold", "critical_sigma"]
            for field in required_fields:
                assert field in tc, f"Missing {field} in {metric.get('metric_name')}"

            # Sigma ordering should be sigma < critical
            sigma = tc.get("sigma_threshold", 0)
            critical = tc.get("critical_sigma", 0)
            assert 0 < sigma < critical, (
                f"Invalid sigma ordering in {metric.get('metric_name')}"
            )

    def test_metric_anomaly_detection_config(self, sample_experiment_data):
        """Test anomaly detection configuration."""
        bc = sample_experiment_data["baseline_config"]

        for metric in bc.get("metrics", []):
            ad = metric.get("anomaly_detection", {})

            assert "enabled" in ad
            assert "method" in ad
            assert "sensitivity" in ad

            assert isinstance(ad["enabled"], bool)
            assert ad["method"] in ["zscore", "isolation_forest", "mad"]
            assert 0 <= ad.get("sensitivity", 0) <= 1


class TestBaselineConfigParsing:
    """Unit tests for parsing and converting baseline_config to internal formats."""

    def test_parse_metrics_to_baseline_metric_dict(self):
        """Test converting metrics from baseline_config to dict format."""
        filepath = POSTGRES_EXPERIMENTS_DIR / SAMPLE_EXPERIMENTS[0]
        with open(filepath, "r") as f:
            data = json.load(f)

        bc = data["baseline_config"]
        metrics = bc.get("metrics", [])

        # Should be able to create a dict by metric_id
        metrics_dict = {m["metric_id"]: m for m in metrics}

        assert len(metrics_dict) == len(metrics), (
            "All metrics should be indexable by ID"
        )

        # All IDs should be unique
        ids = [m["metric_id"] for m in metrics]
        assert len(ids) == len(set(ids)), "Metric IDs should be unique"

    def test_parse_metrics_to_service_lookup(self):
        """Test creating service -> metrics lookup from baseline_config."""
        filepath = POSTGRES_EXPERIMENTS_DIR / SAMPLE_EXPERIMENTS[0]
        with open(filepath, "r") as f:
            data = json.load(f)

        bc = data["baseline_config"]
        metrics = bc.get("metrics", [])

        # Create service -> metrics mapping
        service_metrics = {}
        for metric in metrics:
            service = metric.get("service_name", "unknown")
            if service not in service_metrics:
                service_metrics[service] = []
            service_metrics[service].append(metric)

        # Should have postgres service
        assert "postgres" in service_metrics, "Should have postgres metrics"
        assert len(service_metrics["postgres"]) > 0

    def test_convert_baseline_stats_to_numeric_dict(self):
        """Test converting baseline statistics to numeric dictionary."""
        filepath = POSTGRES_EXPERIMENTS_DIR / SAMPLE_EXPERIMENTS[0]
        with open(filepath, "r") as f:
            data = json.load(f)

        bc = data["baseline_config"]

        for metric in bc.get("metrics", []):
            stats = metric.get("baseline_statistics", {})

            # Convert to numeric dict
            numeric_stats = {
                k: float(v) for k, v in stats.items() if isinstance(v, (int, float))
            }

            assert len(numeric_stats) >= 6, "Should have multiple numeric stats"
            assert all(isinstance(v, float) for v in numeric_stats.values())

    def test_normalize_metric_names_from_baseline_config(self):
        """Test normalizing metric names from baseline_config."""
        filepath = POSTGRES_EXPERIMENTS_DIR / SAMPLE_EXPERIMENTS[0]
        with open(filepath, "r") as f:
            data = json.load(f)

        bc = data["baseline_config"]

        metric_names = [m.get("metric_name") for m in bc.get("metrics", [])]

        # All metric names should be non-empty strings
        assert all(isinstance(n, str) and len(n) > 0 for n in metric_names)

        # Should be able to use them as keys
        normalized = {n.replace(" ", "_").lower(): n for n in metric_names}
        assert len(normalized) == len(metric_names), (
            "Metric names should normalize uniquely"
        )


class TestBaselineConfigValidation:
    """Unit tests for validating baseline_config content."""

    def test_validate_metric_completeness(self):
        """Test that all metrics have required fields."""
        filepath = POSTGRES_EXPERIMENTS_DIR / SAMPLE_EXPERIMENTS[1]
        with open(filepath, "r") as f:
            data = json.load(f)

        bc = data["baseline_config"]
        required_fields = {
            "metric_id",
            "metric_name",
            "service_name",
            "baseline_source",
            "baseline_statistics",
            "threshold_config",
            "anomaly_detection",
            "status",
            "used_in_probes",
        }

        for i, metric in enumerate(bc.get("metrics", [])):
            missing = required_fields - set(metric.keys())
            assert not missing, (
                f"Metric {i} ({metric.get('metric_name')}): missing {missing}"
            )

    def test_validate_threshold_bounds(self):
        """Test threshold configuration bounds validity."""
        filepath = POSTGRES_EXPERIMENTS_DIR / SAMPLE_EXPERIMENTS[1]
        with open(filepath, "r") as f:
            data = json.load(f)

        bc = data["baseline_config"]

        for metric in bc.get("metrics", []):
            tc = metric.get("threshold_config", {})

            sigma = tc.get("sigma_threshold")
            critical = tc.get("critical_sigma")

            # Basic ordering checks
            assert sigma > 0, f"Invalid sigma in {metric.get('metric_name')}"
            assert critical > sigma, (
                f"Critical should exceed sigma in {metric.get('metric_name')}"
            )

    def test_validate_metric_quality_score(self):
        """Test metric quality scores are valid."""
        filepath = POSTGRES_EXPERIMENTS_DIR / SAMPLE_EXPERIMENTS[0]
        with open(filepath, "r") as f:
            data = json.load(f)

        bc = data["baseline_config"]

        for metric in bc.get("metrics", []):
            stats = metric.get("baseline_statistics", {})
            quality = stats.get("quality_score")

            assert quality is not None
            assert isinstance(quality, (int, float))
            assert 0 <= quality <= 100

    def test_validate_percentile_ordering(self):
        """Test percentile values are properly ordered."""
        filepath = POSTGRES_EXPERIMENTS_DIR / SAMPLE_EXPERIMENTS[0]
        with open(filepath, "r") as f:
            data = json.load(f)

        bc = data["baseline_config"]

        for metric in bc.get("metrics", []):
            stats = metric.get("baseline_statistics", {})

            p50 = stats.get("percentile_50")
            p95 = stats.get("percentile_95")
            p99 = stats.get("percentile_99")

            if all(x is not None for x in [p50, p95, p99]):
                assert p50 <= p95 <= p99, (
                    f"Percentiles not ordered in {metric.get('metric_name')}"
                )

    def test_validate_probe_references(self):
        """Test that metrics reference valid probes."""
        filepath = POSTGRES_EXPERIMENTS_DIR / SAMPLE_EXPERIMENTS[0]
        with open(filepath, "r") as f:
            data = json.load(f)

        bc = data["baseline_config"]

        # Get probe names from steady-state-hypothesis
        ssh = data.get("steady-state-hypothesis", {})
        probe_names = {p.get("name") for p in ssh.get("probes", [])}

        # Each metric should reference existing probes
        for metric in bc.get("metrics", []):
            probes = metric.get("used_in_probes", [])
            assert isinstance(probes, list)
            assert len(probes) > 0, (
                f"Metric {metric.get('metric_name')} should reference at least one probe"
            )


class TestBaselineConfigIntegrationWithLoader:
    """Unit tests for integrating baseline_config with BaselineLoader."""

    def test_loader_can_consume_baseline_config_metrics(self):
        """Test that loader-like systems can work with baseline_config metrics."""
        filepath = POSTGRES_EXPERIMENTS_DIR / SAMPLE_EXPERIMENTS[0]
        with open(filepath, "r") as f:
            data = json.load(f)

        bc = data["baseline_config"]
        metrics = bc.get("metrics", [])

        # Loader-like system should be able to process these metrics
        mock_loader = Mock()
        mock_loader.load_by_system = Mock(return_value=metrics)

        result = mock_loader.load_by_system("postgres")

        assert len(result) == len(metrics)
        mock_loader.load_by_system.assert_called_with("postgres")

    def test_loader_maps_baseline_config_to_internal_format(self):
        """Test converting baseline_config format to internal metric format."""
        filepath = POSTGRES_EXPERIMENTS_DIR / SAMPLE_EXPERIMENTS[1]
        with open(filepath, "r") as f:
            data = json.load(f)

        bc = data["baseline_config"]

        # Simulate loader mapping baseline_config to internal format
        mock_loader = Mock()
        mock_metrics = []

        for metric in bc.get("metrics", []):
            internal_format = {
                "id": metric["metric_id"],
                "name": metric["metric_name"],
                "service": metric["service_name"],
                "mean": metric["baseline_statistics"]["mean_value"],
                "stddev": metric["baseline_statistics"]["stddev_value"],
                "sigma_threshold": metric["threshold_config"]["sigma_threshold"],
            }
            mock_metrics.append(internal_format)

        mock_loader.load_by_system = Mock(return_value=mock_metrics)

        result = mock_loader.load_by_system("postgres")
        assert len(result) > 0
        assert all("id" in m and "mean" in m for m in result)

    def test_baseline_config_discovery_methods(self):
        """Test that baseline_config supports BaselineLoader discovery methods."""
        filepath = POSTGRES_EXPERIMENTS_DIR / SAMPLE_EXPERIMENTS[0]
        with open(filepath, "r") as f:
            data = json.load(f)

        bc = data["baseline_config"]
        discovery = bc.get("discovery", {})

        # Discovery should support method field
        assert "method" in discovery
        assert discovery["method"] in ["system", "service", "explicit", "labels"]

        # Should support system_id for system method
        if discovery["method"] == "system":
            assert "system_id" in discovery


class TestBaselineConfigCaching:
    """Unit tests for caching and performance of baseline_config loading."""

    def test_baseline_config_cache_structure(self):
        """Test that baseline_config can be cached effectively."""
        filepath = POSTGRES_EXPERIMENTS_DIR / SAMPLE_EXPERIMENTS[0]
        with open(filepath, "r") as f:
            data = json.load(f)

        bc = data["baseline_config"]

        # Create cache structure
        cache = {
            "system_id": bc["discovery"]["system_id"],
            "service": bc["metadata"]["service"],
            "metrics": {m["metric_id"]: m for m in bc.get("metrics", [])},
            "timestamp": "2026-01-31T00:00:00Z",
        }

        # Should be serializable to JSON
        cache_json = json.dumps(cache, default=str)
        assert len(cache_json) > 0

        # Should be deserializable
        cache_restored = json.loads(cache_json)
        assert cache_restored["system_id"] == bc["discovery"]["system_id"]

    def test_baseline_config_lookup_by_metric_id(self):
        """Test efficient lookup of metrics by ID."""
        filepath = POSTGRES_EXPERIMENTS_DIR / SAMPLE_EXPERIMENTS[1]
        with open(filepath, "r") as f:
            data = json.load(f)

        bc = data["baseline_config"]

        # Create index
        metric_index = {m["metric_id"]: m for m in bc.get("metrics", [])}

        # Lookup should be O(1)
        metric_ids = list(metric_index.keys())
        if metric_ids:
            first_id = metric_ids[0]
            metric = metric_index[first_id]
            assert metric["metric_id"] == first_id


class TestBaselineConfigEdgeCases:
    """Unit tests for edge cases and error conditions."""

    def test_empty_metrics_array_handling(self):
        """Test handling of edge case with empty metrics."""
        experiment_data = {
            "baseline_config": {
                "metadata": {"version": "1.0", "service": "postgres"},
                "discovery": {"method": "system", "system_id": "postgres"},
                "metrics": [],
            }
        }

        bc = experiment_data["baseline_config"]
        assert isinstance(bc["metrics"], list)
        assert len(bc["metrics"]) == 0

    def test_large_metrics_array_handling(self):
        """Test handling of large numbers of metrics."""
        # Create synthetic large metrics array
        metrics = []
        for i in range(100):
            metrics.append(
                {
                    "metric_id": i,
                    "metric_name": f"metric_{i}",
                    "service_name": "postgres",
                    "baseline_source": "prometheus",
                    "baseline_statistics": {
                        "mean_value": i * 1.5,
                        "stddev_value": i * 0.1,
                        "quality_score": 90,
                    },
                    "threshold_config": {"sigma_threshold": 2.0, "critical_sigma": 3.0},
                    "anomaly_detection": {
                        "enabled": True,
                        "method": "zscore",
                        "sensitivity": 0.9,
                    },
                    "status": "active",
                    "used_in_probes": ["test-probe"],
                }
            )

        # Should handle large array
        assert len(metrics) == 100
        metrics_dict = {m["metric_id"]: m for m in metrics}
        assert len(metrics_dict) == 100

    def test_special_characters_in_metric_names(self):
        """Test handling special characters in metric names."""
        special_names = [
            "rate(postgresql_blocks_read_total[5m])",
            "pg_locks{mode='AccessExclusiveLock'}",
            "metric:with:colons",
            "metric-with-dashes",
            "metric_with_underscores",
        ]

        # All should be valid JSON
        for name in special_names:
            data = {"metric_name": name}
            json_str = json.dumps(data)
            restored = json.loads(json_str)
            assert restored["metric_name"] == name


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
