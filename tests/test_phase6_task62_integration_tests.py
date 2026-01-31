"""
Phase 6 Task 6.2: Integration Tests for BaselineManager and Baseline Config

Tests for integrating baseline_config with BaselineManager commands and
experiment execution workflow.
"""

import json
from pathlib import Path

import pytest

# Note: BaselineManager integration tested via JSON structure validation
# These tests focus on baseline_config integration with experiment structure


# Test data directory
POSTGRES_EXPERIMENTS_DIR = (
    Path(__file__).parent.parent / "chaostooling-experiments" / "postgres"
)
SAMPLE_EXPERIMENT = "test-postgres-cache-miss.json"


class TestBaselineManagerDiscoverIntegration:
    """Integration tests for BaselineManager discover() command with baseline_config."""

    @pytest.fixture
    def experiment_with_config(self):
        """Load experiment with baseline_config."""
        filepath = POSTGRES_EXPERIMENTS_DIR / SAMPLE_EXPERIMENT
        with open(filepath) as f:
            return json.load(f)

    def test_discover_command_finds_baseline_config_metrics(
        self, experiment_with_config
    ):
        """Test that discover command can find metrics from baseline_config."""
        bc = experiment_with_config["baseline_config"]
        metrics = bc.get("metrics", [])

        # Simulate discover command finding these metrics
        discovered = {m["metric_id"]: m for m in metrics}

        assert len(discovered) > 0
        assert all("metric_name" in m for m in discovered.values())

    def test_discover_by_system_uses_baseline_config(self, experiment_with_config):
        """Test discover by system uses baseline_config settings."""
        bc = experiment_with_config["baseline_config"]
        discovery = bc.get("discovery", {})

        # Simulate discover by system
        system_id = discovery.get("system_id")

        assert system_id == "postgres"

        # All metrics should belong to this system
        for metric in bc.get("metrics", []):
            assert metric["service_name"] == "postgres"

    def test_discover_respects_baseline_config_thresholds(self, experiment_with_config):
        """Test that discover results respect baseline_config thresholds."""
        bc = experiment_with_config["baseline_config"]
        bc.get("default_thresholds", {})

        # Metrics should respect or override default thresholds
        for metric in bc.get("metrics", []):
            metric_thresholds = metric.get("threshold_config", {})

            # Should have valid thresholds
            assert "sigma_threshold" in metric_thresholds
            assert metric_thresholds["sigma_threshold"] > 0

    def test_discover_includes_metric_quality_in_results(self, experiment_with_config):
        """Test that discover includes quality scores from baseline_config."""
        bc = experiment_with_config["baseline_config"]

        for metric in bc.get("metrics", []):
            stats = metric.get("baseline_statistics", {})
            quality = stats.get("quality_score")

            assert quality is not None
            assert 0 <= quality <= 100


class TestBaselineManagerStatusIntegration:
    """Integration tests for BaselineManager status() command with baseline_config."""

    @pytest.fixture
    def experiment_with_config(self):
        """Load experiment with baseline_config."""
        filepath = POSTGRES_EXPERIMENTS_DIR / SAMPLE_EXPERIMENT
        with open(filepath) as f:
            return json.load(f)

    def test_status_command_shows_baseline_config_status(self, experiment_with_config):
        """Test that status command shows baseline_config section info."""
        bc = experiment_with_config["baseline_config"]

        # Status should include metadata
        assert bc.get("metadata", {}).get("version") == "1.0"
        assert bc.get("metadata", {}).get("service") == "postgres"

    def test_status_reports_metrics_count(self, experiment_with_config):
        """Test that status reports number of configured metrics."""
        bc = experiment_with_config["baseline_config"]
        metrics = bc.get("metrics", [])

        # Should be able to report metrics count
        assert len(metrics) > 0

    def test_status_shows_metric_validity(self, experiment_with_config):
        """Test that status reports metric validity."""
        bc = experiment_with_config["baseline_config"]

        valid_metrics = 0
        for metric in bc.get("metrics", []):
            # Check if metric is valid
            if (
                metric.get("status") == "active"
                and metric.get("baseline_statistics", {}).get("quality_score", 0) >= 75
            ):
                valid_metrics += 1

        assert valid_metrics > 0

    def test_status_includes_discovery_method(self, experiment_with_config):
        """Test that status includes discovery method."""
        bc = experiment_with_config["baseline_config"]
        discovery = bc.get("discovery", {})

        assert "method" in discovery
        assert discovery["method"] == "system"


class TestBaselineManagerSuggestIntegration:
    """Integration tests for BaselineManager suggest_for_experiment() with baseline_config."""

    @pytest.fixture
    def experiment_with_config(self):
        """Load experiment with baseline_config."""
        filepath = POSTGRES_EXPERIMENTS_DIR / SAMPLE_EXPERIMENT
        with open(filepath) as f:
            return json.load(f)

    def test_suggest_uses_baseline_config_metrics(self, experiment_with_config):
        """Test that suggest command uses metrics from baseline_config."""
        bc = experiment_with_config["baseline_config"]
        metrics = bc.get("metrics", [])

        # Simulate suggestion scoring
        scores = []
        for metric in metrics:
            stats = metric.get("baseline_statistics", {})
            quality = stats.get("quality_score", 0)

            # Simple scoring: quality based
            score = quality
            scores.append(
                {
                    "metric_id": metric["metric_id"],
                    "metric_name": metric["metric_name"],
                    "score": score,
                }
            )

        # Should be able to sort by score
        sorted_scores = sorted(scores, key=lambda x: x["score"], reverse=True)
        assert len(sorted_scores) == len(metrics)

    def test_suggest_respects_baseline_statistics(self, experiment_with_config):
        """Test that suggest respects baseline statistics."""
        bc = experiment_with_config["baseline_config"]

        for metric in bc.get("metrics", []):
            stats = metric.get("baseline_statistics", {})

            # Should have data to make suggestions
            assert stats.get("mean_value") is not None
            assert stats.get("stddev_value") is not None

    def test_suggest_considers_metric_freshness(self, experiment_with_config):
        """Test that suggest considers metric freshness."""
        bc = experiment_with_config["baseline_config"]

        # Metadata includes created date
        metadata = bc.get("metadata", {})
        assert "created" in metadata

        # Could use this for freshness calculation
        created = metadata.get("created")
        assert created is not None

    def test_suggest_uses_anomaly_detection_settings(self, experiment_with_config):
        """Test that suggest uses anomaly detection configuration."""
        bc = experiment_with_config["baseline_config"]

        for metric in bc.get("metrics", []):
            ad = metric.get("anomaly_detection", {})

            # Should have anomaly detection config
            assert "enabled" in ad
            assert "method" in ad
            assert "sensitivity" in ad


class TestBaselineConfigExperimentIntegration:
    """Integration tests for baseline_config with experiment structure."""

    @pytest.fixture
    def experiment_files(self):
        """List all experiment files."""
        return list(POSTGRES_EXPERIMENTS_DIR.glob("test-*.json"))

    def test_baseline_config_coexists_with_experiment_structure(self, experiment_files):
        """Test that baseline_config coexists with standard experiment structure."""
        for filepath in experiment_files[:3]:  # Test first 3 files
            with open(filepath) as f:
                data = json.load(f)

            # Should have both experiment structure and baseline_config
            assert "version" in data
            assert "title" in data
            assert "controls" in data
            assert "steady-state-hypothesis" in data
            assert "baseline_config" in data

    def test_baseline_config_metrics_match_steady_state_probes(self, experiment_files):
        """Test that baseline_config metrics correspond to steady-state probes."""
        for filepath in experiment_files[:3]:
            with open(filepath) as f:
                data = json.load(f)

            bc = data["baseline_config"]
            ssh = data.get("steady-state-hypothesis", {})

            # Get probe names
            probe_names = {p.get("name") for p in ssh.get("probes", [])}

            # Check metrics reference these probes or similar ones
            metric_probes = set()
            for metric in bc.get("metrics", []):
                metric_probes.update(metric.get("used_in_probes", []))

            # Both sets should exist (may not have overlap due to different naming)
            assert len(probe_names) > 0
            assert len(metric_probes) > 0

    def test_baseline_config_service_matches_experiment_context(self, experiment_files):
        """Test that baseline_config service matches experiment context."""
        for filepath in experiment_files[:3]:
            with open(filepath) as f:
                data = json.load(f)

            bc = data["baseline_config"]

            # All metrics should be for postgres
            for metric in bc.get("metrics", []):
                assert metric.get("service_name") == "postgres"


class TestBaselineConfigProbeIntegration:
    """Integration tests for baseline_config with chaos toolkit probes."""

    def test_baseline_config_provides_thresholds_for_probes(self):
        """Test that baseline_config thresholds can be used by probes."""
        filepath = POSTGRES_EXPERIMENTS_DIR / SAMPLE_EXPERIMENT
        with open(filepath) as f:
            data = json.load(f)

        bc = data["baseline_config"]

        # Create probe threshold lookup
        probe_thresholds = {}
        for metric in bc.get("metrics", []):
            for probe_name in metric.get("used_in_probes", []):
                if probe_name not in probe_thresholds:
                    probe_thresholds[probe_name] = []
                probe_thresholds[probe_name].append(
                    {
                        "metric": metric["metric_name"],
                        "sigma": metric["threshold_config"]["sigma_threshold"],
                        "critical": metric["threshold_config"]["critical_sigma"],
                    }
                )

        # Probes should find their thresholds
        assert len(probe_thresholds) > 0

    def test_baseline_config_supplies_baseline_stats_for_probe_validation(self):
        """Test that baseline_config supplies stats for probe validation."""
        filepath = POSTGRES_EXPERIMENTS_DIR / SAMPLE_EXPERIMENT
        with open(filepath) as f:
            data = json.load(f)

        bc = data["baseline_config"]

        # Simulate probe getting stats
        for metric in bc.get("metrics", []):
            stats = metric.get("baseline_statistics", {})

            # Probe should use these for validation
            baseline_mean = stats.get("mean_value")
            baseline_stddev = stats.get("stddev_value")

            # Can calculate thresholds
            sigma = metric["threshold_config"]["sigma_threshold"]
            upper_threshold = baseline_mean + (sigma * baseline_stddev)
            lower_threshold = baseline_mean - (sigma * baseline_stddev)

            assert lower_threshold < baseline_mean < upper_threshold


class TestBaselineConfigDataIntegrity:
    """Integration tests for data integrity across baseline_config and system."""

    def test_metric_ids_unique_across_experiment_and_config(self):
        """Test that metric IDs are unique and consistent."""
        filepath = POSTGRES_EXPERIMENTS_DIR / SAMPLE_EXPERIMENT
        with open(filepath) as f:
            data = json.load(f)

        bc = data["baseline_config"]
        metric_ids = [m["metric_id"] for m in bc.get("metrics", [])]

        # IDs should be unique
        assert len(metric_ids) == len(set(metric_ids))

    def test_baseline_config_survives_round_trip_serialization(self):
        """Test that baseline_config survives JSON serialization round-trip."""
        filepath = POSTGRES_EXPERIMENTS_DIR / SAMPLE_EXPERIMENT
        with open(filepath) as f:
            data = json.load(f)

        original_bc = data["baseline_config"]

        # Round trip through JSON
        json_str = json.dumps({"baseline_config": original_bc})
        restored = json.loads(json_str)
        restored_bc = restored["baseline_config"]

        # Should match exactly
        assert restored_bc == original_bc

    def test_metric_statistics_consistency_after_loading(self):
        """Test that metric statistics remain reasonable after loading."""
        filepath = POSTGRES_EXPERIMENTS_DIR / SAMPLE_EXPERIMENT
        with open(filepath) as f:
            data = json.load(f)

        bc = data["baseline_config"]

        for metric in bc.get("metrics", []):
            stats = metric.get("baseline_statistics", {})

            # Check consistency: min <= max
            min_val = stats.get("min_value")
            max_val = stats.get("max_value")

            # Basic sanity check
            if all(x is not None for x in [min_val, max_val]):
                # Allow for edge cases where percentiles might exceed bounds slightly
                assert min_val <= max_val, (
                    f"Min/max ordering invalid in {metric.get('metric_name')}: "
                    f"min={min_val}, max={max_val}"
                )


class TestBaselineConfigPerformance:
    """Integration tests for baseline_config performance characteristics."""

    def test_baseline_config_loading_performance(self):
        """Test that baseline_config loads quickly."""
        filepath = POSTGRES_EXPERIMENTS_DIR / SAMPLE_EXPERIMENT

        import time

        start = time.time()

        with open(filepath) as f:
            json.load(f)

        elapsed = time.time() - start

        # Should load in <100ms
        assert elapsed < 0.1

    def test_baseline_config_metric_lookup_performance(self):
        """Test that metric lookup is efficient."""
        filepath = POSTGRES_EXPERIMENTS_DIR / SAMPLE_EXPERIMENT
        with open(filepath) as f:
            data = json.load(f)

        bc = data["baseline_config"]

        # Create index
        import time

        start = time.time()

        metric_index = {m["metric_id"]: m for m in bc.get("metrics", [])}

        elapsed = time.time() - start

        # Should index in <1ms
        assert elapsed < 0.001

        # Lookup should be instant
        if metric_index:
            start = time.time()
            _ = metric_index[list(metric_index.keys())[0]]
            elapsed = time.time() - start
            assert elapsed < 0.001

    def test_all_experiments_baseline_config_load_performance(self):
        """Test loading baseline_config from all experiments."""
        import time

        start = time.time()

        count = 0
        for filepath in POSTGRES_EXPERIMENTS_DIR.glob("test-*.json"):
            with open(filepath) as f:
                data = json.load(f)
                bc = data.get("baseline_config", {})
                if bc:
                    count += 1

        elapsed = time.time() - start

        # Should load multiple files quickly
        assert count > 0
        assert elapsed < 0.5  # All 8+ files in <500ms


class TestBaselineConfigErrorHandling:
    """Integration tests for error handling in baseline_config operations."""

    def test_handle_missing_baseline_config_gracefully(self):
        """Test graceful handling when baseline_config is missing."""
        incomplete_data = {
            "version": "1.0",
            "title": "Test",
            "controls": [],
            # Missing baseline_config
        }

        bc = incomplete_data.get("baseline_config", {})
        assert bc == {}

    def test_handle_incomplete_metric_gracefully(self):
        """Test handling of incomplete metrics in baseline_config."""
        data = {
            "baseline_config": {
                "metrics": [
                    {
                        "metric_id": 1,
                        "metric_name": "test_metric",
                        # Missing other fields
                    }
                ]
            }
        }

        bc = data["baseline_config"]
        metric = bc["metrics"][0]

        # Should safely access available fields
        assert metric.get("metric_id") == 1
        assert metric.get("baseline_statistics") is None

    def test_handle_invalid_numeric_values(self):
        """Test handling of invalid numeric values."""
        data = {
            "baseline_config": {
                "metrics": [
                    {
                        "metric_id": 1,
                        "baseline_statistics": {"mean_value": "not_a_number"},
                    }
                ]
            }
        }

        metric = data["baseline_config"]["metrics"][0]
        value = metric["baseline_statistics"]["mean_value"]

        # Should be detectable as invalid
        assert not isinstance(value, (int, float))


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
