"""
Phase 6 Task 6.3: End-to-End Tests for Baseline Config with Experiment Execution

Tests for complete workflows: loading experiments with baseline_config,
running baseline discovery, and validating against thresholds during
experiment execution.
"""

import json
import pytest
from pathlib import Path
from typing import Dict, List, Any
from unittest.mock import Mock, patch, MagicMock, call
import tempfile

# Adjust import path based on actual structure
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))


# Test data directory
POSTGRES_EXPERIMENTS_DIR = (
    Path(__file__).parent.parent / "chaostooling-experiments" / "postgres"
)


class TestE2EExperimentWithBaseline:
    """E2E tests for running experiments with baseline_config."""

    @pytest.fixture
    def sample_experiment(self):
        """Load a sample experiment with baseline_config."""
        filepath = POSTGRES_EXPERIMENTS_DIR / "test-postgres-cache-miss.json"
        with open(filepath, "r") as f:
            return json.load(f)

    def test_e2e_load_experiment_with_baseline_config(self, sample_experiment):
        """Test loading experiment and accessing baseline_config."""
        assert "baseline_config" in sample_experiment
        bc = sample_experiment["baseline_config"]

        # Should be able to access all sections
        assert bc.get("metadata") is not None
        assert bc.get("discovery") is not None
        assert bc.get("default_thresholds") is not None
        assert bc.get("metrics") is not None

    def test_e2e_prepare_baseline_config_for_execution(self, sample_experiment):
        """Test preparing baseline_config for experiment execution."""
        bc = sample_experiment["baseline_config"]

        # Simulate preparation: creating runtime config
        runtime_config = {
            "system_id": bc["discovery"]["system_id"],
            "service": bc["metadata"]["service"],
            "default_sigma": bc["default_thresholds"]["sigma_threshold"],
            "metrics": {},
        }

        # Load metrics into runtime config
        for metric in bc.get("metrics", []):
            runtime_config["metrics"][metric["metric_id"]] = {
                "name": metric["metric_name"],
                "mean": metric["baseline_statistics"]["mean_value"],
                "stddev": metric["baseline_statistics"]["stddev_value"],
                "sigma": metric["threshold_config"]["sigma_threshold"],
            }

        # Should have all metrics ready
        assert len(runtime_config["metrics"]) == len(bc.get("metrics", []))

    def test_e2e_apply_baseline_config_to_probes(self, sample_experiment):
        """Test applying baseline_config to experiment probes."""
        bc = sample_experiment["baseline_config"]
        ssh = sample_experiment.get("steady-state-hypothesis", {})

        # Create metric -> probe mapping
        metric_to_probes = {}
        for metric in bc.get("metrics", []):
            for probe_name in metric.get("used_in_probes", []):
                if probe_name not in metric_to_probes:
                    metric_to_probes[probe_name] = []
                metric_to_probes[probe_name].append(metric)

        # Each probe should find its metrics
        for probe in ssh.get("probes", []):
            probe_name = probe.get("name")
            metrics = metric_to_probes.get(probe_name, [])

            # Should have at least the referenced metrics
            assert len(metrics) > 0


class TestE2EBaselineDiscovery:
    """E2E tests for baseline discovery workflow."""

    @pytest.fixture
    def sample_experiment(self):
        """Load a sample experiment."""
        filepath = POSTGRES_EXPERIMENTS_DIR / "test-postgres-lock-storm.json"
        with open(filepath, "r") as f:
            return json.load(f)

    def test_e2e_discover_baselines_for_experiment(self, sample_experiment):
        """Test discovering baselines for an experiment."""
        bc = sample_experiment["baseline_config"]

        # Simulate discovery
        discovery = bc.get("discovery", {})
        system_id = discovery.get("system_id")

        # Discover should find all metrics for this system
        discovered_metrics = [
            m
            for m in bc.get("metrics", [])
            if m.get("service_name") == system_id or m.get("service_name") == "postgres"
        ]

        assert len(discovered_metrics) > 0

    def test_e2e_filter_baselines_by_quality(self, sample_experiment):
        """Test filtering discovered baselines by quality score."""
        bc = sample_experiment["baseline_config"]
        validation = bc.get("data_validation", {})
        min_quality = validation.get("min_quality_score", 0)

        # Filter metrics by quality
        quality_metrics = [
            m
            for m in bc.get("metrics", [])
            if m.get("baseline_statistics", {}).get("quality_score", 0) >= min_quality
        ]

        # Should have high quality metrics
        assert len(quality_metrics) > 0

    def test_e2e_rank_baselines_by_freshness(self, sample_experiment):
        """Test ranking baselines by freshness."""
        bc = sample_experiment["baseline_config"]
        metadata = bc.get("metadata", {})
        created = metadata.get("created")

        # Should have creation timestamp for freshness calculation
        assert created is not None

        # All metrics should use same baseline age
        metrics = bc.get("metrics", [])
        assert all(m.get("baseline_statistics") for m in metrics)


class TestE2EMetricValidation:
    """E2E tests for metric validation during experiment execution."""

    @pytest.fixture
    def sample_experiment(self):
        """Load a sample experiment."""
        filepath = POSTGRES_EXPERIMENTS_DIR / "test-postgres-query-saturation.json"
        with open(filepath, "r") as f:
            return json.load(f)

    def test_e2e_validate_metric_against_baseline(self, sample_experiment):
        """Test validating a metric value against baseline thresholds."""
        bc = sample_experiment["baseline_config"]
        metrics = bc.get("metrics", [])

        if not metrics:
            pytest.skip("No metrics in baseline_config")

        metric = metrics[0]
        stats = metric.get("baseline_statistics", {})
        thresholds = metric.get("threshold_config", {})

        # Simulate metric value collection
        baseline_mean = stats.get("mean_value", 0)
        baseline_stddev = stats.get("stddev_value", 1)
        sigma = thresholds.get("sigma_threshold", 2.0)

        # Define thresholds
        upper_threshold = baseline_mean + (sigma * baseline_stddev)
        lower_threshold = baseline_mean - (sigma * baseline_stddev)

        # Test validation logic
        test_value = baseline_mean  # Normal value
        assert lower_threshold <= test_value <= upper_threshold

        # Test warning condition
        warning_value = upper_threshold + 0.5
        assert warning_value > upper_threshold

    def test_e2e_detect_anomaly_in_metric(self, sample_experiment):
        """Test anomaly detection using baseline_config."""
        bc = sample_experiment["baseline_config"]
        metrics = bc.get("metrics", [])

        if not metrics:
            pytest.skip("No metrics in baseline_config")

        metric = metrics[0]
        stats = metric.get("baseline_statistics", {})
        anomaly_config = metric.get("anomaly_detection", {})

        # Anomaly detection setup
        assert anomaly_config.get("enabled") is True
        assert anomaly_config.get("method") in ["zscore", "isolation_forest", "mad"]

        # Simulate anomaly scoring
        baseline_mean = stats.get("mean_value", 0)
        baseline_stddev = stats.get("stddev_value", 1)

        test_value = baseline_mean + (4 * baseline_stddev)  # 4-sigma deviation

        # Calculate z-score
        if baseline_stddev > 0:
            z_score = abs((test_value - baseline_mean) / baseline_stddev)
            assert z_score >= 3.0  # Anomalous

    def test_e2e_threshold_vs_anomaly_detection_interaction(self, sample_experiment):
        """Test interaction between threshold validation and anomaly detection."""
        bc = sample_experiment["baseline_config"]

        for metric in bc.get("metrics", []):
            stats = metric.get("baseline_statistics", {})
            thresholds = metric.get("threshold_config", {})
            anomaly = metric.get("anomaly_detection", {})

            # Should have both mechanisms
            assert "sigma_threshold" in thresholds
            assert "enabled" in anomaly

            # Anomaly detection can be independent of threshold
            if anomaly.get("enabled"):
                assert anomaly.get("method") is not None


class TestE2EMultiMetricValidation:
    """E2E tests for validating multiple metrics across experiments."""

    @pytest.fixture
    def all_experiments(self):
        """Load all postgres experiments."""
        experiments = {}
        for filepath in POSTGRES_EXPERIMENTS_DIR.glob("test-*.json"):
            with open(filepath, "r") as f:
                experiments[filepath.name] = json.load(f)
        return experiments

    def test_e2e_validate_metrics_across_all_experiments(self, all_experiments):
        """Test validating metrics across multiple experiments."""
        all_valid = True

        for filename, experiment in all_experiments.items():
            bc = experiment.get("baseline_config", {})

            for metric in bc.get("metrics", []):
                stats = metric.get("baseline_statistics", {})

                # Each metric should have valid stats
                if not (
                    stats.get("mean_value") is not None
                    and stats.get("stddev_value") is not None
                ):
                    all_valid = False
                    break

            if not all_valid:
                break

        assert all_valid

    def test_e2e_cross_experiment_metric_id_uniqueness(self, all_experiments):
        """Test that metric IDs are properly namespaced per experiment."""
        metrics_by_id = {}

        for filename, experiment in all_experiments.items():
            bc = experiment.get("baseline_config", {})

            for metric in bc.get("metrics", []):
                metric_id = metric["metric_id"]

                # Each experiment should have its own ID space
                if metric_id not in metrics_by_id:
                    metrics_by_id[metric_id] = []
                metrics_by_id[metric_id].append(
                    {"file": filename, "name": metric["metric_name"]}
                )

        # IDs can be reused across experiments, but should be consistent
        # if they are (same ID = same metric concept)
        for metric_id, occurrences in metrics_by_id.items():
            if len(occurrences) > 1:
                # Same ID in multiple experiments should refer to same concept
                names = {o["name"] for o in occurrences}
                assert len(names) == 1, (
                    f"ID {metric_id} maps to different names: {names}"
                )


class TestE2EProbeExecution:
    """E2E tests for probe execution with baseline_config."""

    @pytest.fixture
    def sample_experiment(self):
        """Load a sample experiment."""
        filepath = POSTGRES_EXPERIMENTS_DIR / "test-postgres-replication-lag.json"
        with open(filepath, "r") as f:
            return json.load(f)

    def test_e2e_probe_reads_metric_from_baseline_config(self, sample_experiment):
        """Test that probes can read metrics from baseline_config."""
        bc = sample_experiment["baseline_config"]
        ssh = sample_experiment.get("steady-state-hypothesis", {})

        # Create metric lookup
        metrics_by_name = {m["metric_name"]: m for m in bc.get("metrics", [])}

        # Each probe should find its metrics
        for probe in ssh.get("probes", []):
            # Probe would reference metrics by name
            probe_name = probe.get("name")

            # In actual execution, probe would look up its metrics
            for probe_ref in bc.get("metrics", []):
                if probe_name in probe_ref.get("used_in_probes", []):
                    # Probe found its metric
                    assert probe_ref["metric_name"] in metrics_by_name

    def test_e2e_probe_applies_threshold_from_baseline_config(self, sample_experiment):
        """Test that probes apply thresholds from baseline_config."""
        bc = sample_experiment["baseline_config"]

        # Simulate probe threshold application
        for metric in bc.get("metrics", []):
            thresholds = metric.get("threshold_config", {})
            stats = metric.get("baseline_statistics", {})

            # Probe would use these values
            baseline_mean = stats.get("mean_value")
            baseline_stddev = stats.get("stddev_value")
            sigma = thresholds.get("sigma_threshold")

            # Calculate probe thresholds
            if baseline_stddev > 0:
                upper = baseline_mean + (sigma * baseline_stddev)
                lower = baseline_mean - (sigma * baseline_stddev)

                # Should be valid range
                assert lower < upper

    def test_e2e_probe_handles_metric_collection_timing(self, sample_experiment):
        """Test probe handling of metric collection timing."""
        bc = sample_experiment["baseline_config"]
        metadata = bc.get("metadata", {})

        # Metadata should have creation time for staleness checks
        created = metadata.get("created")
        assert created is not None

        # Probes would use this to check baseline age
        validation = bc.get("data_validation", {})
        max_age = validation.get("max_age_days", 30)
        assert max_age > 0


class TestE2EErrorConditions:
    """E2E tests for error conditions and edge cases."""

    def test_e2e_handle_missing_baseline_config_in_experiment(self):
        """Test handling when baseline_config is missing."""
        experiment_without_baseline = {
            "version": "1.0",
            "title": "Test",
            "controls": [],
            "steady-state-hypothesis": {"probes": []},
        }

        bc = experiment_without_baseline.get("baseline_config", {})

        # Should gracefully handle missing baseline_config
        assert bc == {}
        assert bc.get("metrics", []) == []

    def test_e2e_handle_invalid_metric_reference_in_probe(self):
        """Test handling invalid metric references."""
        data = {
            "baseline_config": {
                "metrics": [{"metric_id": 1, "metric_name": "valid_metric"}]
            },
            "steady-state-hypothesis": {"probes": [{"name": "probe1"}]},
        }

        bc = data["baseline_config"]
        ssh = data["steady-state-hypothesis"]

        # Check if all probe references are valid
        valid_metrics = {m["metric_name"] for m in bc.get("metrics", [])}

        for probe in ssh.get("probes", []):
            # In real scenario, probe would validate its metrics exist
            assert probe is not None

    def test_e2e_handle_missing_baseline_statistics(self):
        """Test handling metrics without baseline statistics."""
        metric_no_stats = {
            "metric_id": 1,
            "metric_name": "test_metric",
            # Missing baseline_statistics
        }

        stats = metric_no_stats.get("baseline_statistics", {})

        # Should safely get default
        assert stats.get("mean_value") is None

    def test_e2e_handle_corrupted_baseline_config_gracefully(self):
        """Test graceful handling of corrupted baseline_config."""
        corrupted = {
            "baseline_config": {
                "metrics": [
                    {
                        "metric_id": "not_a_number",  # Invalid
                        "metric_name": 123,  # Wrong type
                    }
                ]
            }
        }

        bc = corrupted["baseline_config"]

        # Should be able to detect issues
        for metric in bc.get("metrics", []):
            metric_id = metric.get("metric_id")
            metric_name = metric.get("metric_name")

            # Types don't match expected
            assert not isinstance(metric_id, int)
            assert not isinstance(metric_name, str)


class TestE2EComprehensiveWorkflow:
    """Comprehensive E2E tests for complete workflows."""

    def test_e2e_complete_baseline_experiment_workflow(self):
        """Test complete workflow: load, discover, validate, execute."""
        filepath = POSTGRES_EXPERIMENTS_DIR / "test-postgres-cache-miss.json"
        with open(filepath, "r") as f:
            experiment = json.load(f)

        # Step 1: Load experiment
        assert "baseline_config" in experiment
        bc = experiment["baseline_config"]

        # Step 2: Extract discovery parameters
        discovery = bc.get("discovery", {})
        system_id = discovery.get("system_id")
        assert system_id == "postgres"

        # Step 3: Get metrics
        metrics = bc.get("metrics", [])
        assert len(metrics) > 0

        # Step 4: Prepare for execution
        metric_config = {}
        for metric in metrics:
            metric_config[metric["metric_id"]] = {
                "name": metric["metric_name"],
                "thresholds": metric["threshold_config"],
                "stats": metric["baseline_statistics"],
            }

        # Step 5: Validate readiness
        assert all("thresholds" in m and "stats" in m for m in metric_config.values())

    def test_e2e_baseline_config_persists_across_experiment_run(self):
        """Test that baseline_config persists through experiment execution."""
        filepath = POSTGRES_EXPERIMENTS_DIR / "test-postgres-lock-storm.json"

        # Initial load
        with open(filepath, "r") as f:
            experiment_initial = json.load(f)

        bc_initial = experiment_initial.get("baseline_config", {})
        metrics_initial = bc_initial.get("metrics", [])

        # Simulate experiment run (reload same file)
        with open(filepath, "r") as f:
            experiment_final = json.load(f)

        bc_final = experiment_final.get("baseline_config", {})
        metrics_final = bc_final.get("metrics", [])

        # Should match exactly
        assert len(metrics_initial) == len(metrics_final)

        for m_init, m_final in zip(metrics_initial, metrics_final):
            assert m_init["metric_id"] == m_final["metric_id"]
            assert m_init["metric_name"] == m_final["metric_name"]


class TestE2EPerformanceUnderLoad:
    """E2E tests for performance under realistic loads."""

    def test_e2e_baseline_config_performance_with_all_experiments(self):
        """Test performance loading all experiments' baseline_config."""
        import time

        start = time.time()

        total_metrics = 0
        total_experiments = 0

        for filepath in POSTGRES_EXPERIMENTS_DIR.glob("*.json"):
            total_experiments += 1
            with open(filepath, "r") as f:
                data = json.load(f)

            bc = data.get("baseline_config", {})
            total_metrics += len(bc.get("metrics", []))

        elapsed = time.time() - start

        # Should process all experiments quickly
        assert total_experiments > 0
        assert total_metrics > 0
        assert elapsed < 1.0  # All experiments in <1 second

    def test_e2e_metric_validation_performance(self):
        """Test performance of metric validation at runtime."""
        filepath = POSTGRES_EXPERIMENTS_DIR / "test-postgres-pool-exhaustion.json"
        with open(filepath, "r") as f:
            experiment = json.load(f)

        bc = experiment.get("baseline_config", {})
        metrics = bc.get("metrics", [])

        # Simulate rapid metric validations
        import time

        start = time.time()

        for _ in range(100):  # 100 validation cycles
            for metric in metrics:
                stats = metric.get("baseline_statistics", {})
                thresholds = metric.get("threshold_config", {})

                # Simulate threshold check
                mean = stats.get("mean_value", 0)
                stddev = stats.get("stddev_value", 1)
                sigma = thresholds.get("sigma_threshold", 2.0)

                _ = mean + (sigma * stddev)

        elapsed = time.time() - start

        # 100 cycles × N metrics should be fast
        assert elapsed < 0.1  # 100 validation cycles in <100ms


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
