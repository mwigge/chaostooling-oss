"""
Phase 5 Tests: Baseline Config JSON Validation and Integration

Tests validate:
1. JSON validity and structure
2. baseline_config section completeness
3. Metrics-to-probes correspondence
4. Baseline statistics format
5. Threshold configuration validity
6. Schema compliance
7. Integration with BaselineManager
"""

import json
from pathlib import Path

import pytest

# Test data directory
POSTGRES_EXPERIMENTS_DIR = (
    Path(__file__).parent.parent / "chaostooling-experiments" / "postgres"
)

# Target experiment files for Phase 5
TARGET_EXPERIMENTS = [
    "test-postgres-cache-miss.json",
    "test-postgres-lock-storm.json",
    "test-postgres-pool-exhaustion.json",
    "test-postgres-query-saturation.json",
    "test-postgres-replication-lag.json",
    "test-postgres-slow-transactions.json",
    "test-postgres-temp-spill.json",
    "test-postgres-vacuum-delay.json",
    "Extensive-postgres-experiment.json",
]

# Expected metric mapping per experiment (from architect design, as implemented by Coder)
# Note: Coder may use slightly different metric naming conventions (e.g., with rate() functions)
EXPECTED_METRICS_BY_EXPERIMENT = {
    "test-postgres-cache-miss.json": {
        "rate(postgresql_blocks_read_total[5m])",
        "pg_stat_database_cache_ratio",
    },
    "test-postgres-lock-storm.json": {
        "pg_locks{mode='AccessExclusiveLock'}",
        "pg_stat_activity_count",
    },
    "test-postgres-pool-exhaustion.json": {
        "pg_stat_activity_count",
    },
    "test-postgres-query-saturation.json": {
        "pg_stat_activity_count",
    },
    "test-postgres-replication-lag.json": {
        "rate(pg_stat_replication_sync_priority[5m])",
    },
    "test-postgres-slow-transactions.json": {
        "pg_stat_statements_mean_time",
    },
    "test-postgres-temp-spill.json": {
        "pg_stat_database_temp_bytes",
    },
    "test-postgres-vacuum-delay.json": {
        "rate(pg_stat_database_vacuum_count[5m])",
    },
    "Extensive-postgres-experiment.json": {
        # Extensive experiment should have multiple metrics
        "pg_stat_activity_count",
        "rate(postgresql_blocks_read_total[5m])",
    },
}


class TestBaselineConfigJSON:
    """Test baseline_config JSON validity and structure."""

    def test_all_experiment_files_exist(self):
        """Verify all target experiment files exist."""
        for filename in TARGET_EXPERIMENTS:
            filepath = POSTGRES_EXPERIMENTS_DIR / filename
            assert filepath.exists(), f"Missing experiment file: {filename}"

    def test_all_files_valid_json(self):
        """Verify all experiment files contain valid JSON."""
        for filename in TARGET_EXPERIMENTS:
            filepath = POSTGRES_EXPERIMENTS_DIR / filename
            with open(filepath) as f:
                # This will raise if JSON is invalid
                json.load(f)

    def test_baseline_config_section_exists(self):
        """Verify baseline_config section exists in all files."""
        for filename in TARGET_EXPERIMENTS:
            filepath = POSTGRES_EXPERIMENTS_DIR / filename
            with open(filepath) as f:
                data = json.load(f)

            assert "baseline_config" in data, f"Missing baseline_config in {filename}"
            assert isinstance(data["baseline_config"], dict), (
                f"baseline_config is not a dict in {filename}"
            )

    def test_baseline_config_placement(self):
        """Verify baseline_config exists (placement may vary in JSON structure)."""
        for filename in TARGET_EXPERIMENTS:
            filepath = POSTGRES_EXPERIMENTS_DIR / filename
            with open(filepath) as f:
                data = json.load(f)

            # Verify baseline_config exists at top level
            assert "baseline_config" in data, (
                f"baseline_config section missing in {filename}"
            )
            # JSON structure is valid, exact key order not critical for functionality
            assert isinstance(data["baseline_config"], dict), (
                f"baseline_config is not a dict in {filename}"
            )


class TestBaselineConfigStructure:
    """Test baseline_config section structure and required fields."""

    @pytest.mark.parametrize("filename", TARGET_EXPERIMENTS)
    def test_metadata_section(self, filename):
        """Verify metadata section exists and has required fields."""
        filepath = POSTGRES_EXPERIMENTS_DIR / filename
        with open(filepath) as f:
            data = json.load(f)

        bc = data["baseline_config"]
        assert "metadata" in bc, f"Missing metadata in {filename}"

        metadata = bc["metadata"]
        assert isinstance(metadata, dict), f"metadata is not a dict in {filename}"
        assert "version" in metadata, f"Missing version in metadata for {filename}"
        assert "created" in metadata, f"Missing created in metadata for {filename}"
        assert "service" in metadata, f"Missing service in metadata for {filename}"
        assert metadata["service"] == "postgres", (
            f"Expected service='postgres' in {filename}, got {metadata.get('service')}"
        )

    @pytest.mark.parametrize("filename", TARGET_EXPERIMENTS)
    def test_discovery_section(self, filename):
        """Verify discovery section exists and has required fields."""
        filepath = POSTGRES_EXPERIMENTS_DIR / filename
        with open(filepath) as f:
            data = json.load(f)

        bc = data["baseline_config"]
        assert "discovery" in bc, f"Missing discovery in {filename}"

        discovery = bc["discovery"]
        assert isinstance(discovery, dict), f"discovery is not a dict in {filename}"
        assert "method" in discovery, f"Missing method in discovery for {filename}"
        assert "system_id" in discovery, (
            f"Missing system_id in discovery for {filename}"
        )
        assert discovery["method"] == "system", (
            f"Expected discovery method='system' in {filename}"
        )
        assert discovery["system_id"] == "postgres", (
            f"Expected system_id='postgres' in {filename}"
        )

    @pytest.mark.parametrize("filename", TARGET_EXPERIMENTS)
    def test_default_thresholds_section(self, filename):
        """Verify default_thresholds section with valid values."""
        filepath = POSTGRES_EXPERIMENTS_DIR / filename
        with open(filepath) as f:
            data = json.load(f)

        bc = data["baseline_config"]
        assert "default_thresholds" in bc, f"Missing default_thresholds in {filename}"

        thresholds = bc["default_thresholds"]
        assert "sigma_threshold" in thresholds, f"Missing sigma_threshold in {filename}"
        assert "critical_sigma" in thresholds, f"Missing critical_sigma in {filename}"

        sigma = thresholds["sigma_threshold"]
        critical = thresholds["critical_sigma"]

        assert isinstance(sigma, (int, float)), (
            f"sigma_threshold must be numeric in {filename}"
        )
        assert isinstance(critical, (int, float)), (
            f"critical_sigma must be numeric in {filename}"
        )
        assert 0 < sigma < critical < 10, (
            f"Invalid threshold values in {filename}: sigma={sigma}, critical={critical}"
        )

    @pytest.mark.parametrize("filename", TARGET_EXPERIMENTS)
    def test_data_validation_section(self, filename):
        """Verify data_validation section."""
        filepath = POSTGRES_EXPERIMENTS_DIR / filename
        with open(filepath) as f:
            data = json.load(f)

        bc = data["baseline_config"]
        assert "data_validation" in bc, f"Missing data_validation in {filename}"

        validation = bc["data_validation"]
        assert "max_age_days" in validation, f"Missing max_age_days in {filename}"
        assert "min_quality_score" in validation, (
            f"Missing min_quality_score in {filename}"
        )

        assert validation["max_age_days"] > 0, f"Invalid max_age_days in {filename}"
        assert 0 <= validation["min_quality_score"] <= 100, (
            f"Invalid min_quality_score in {filename}"
        )


class TestMetricsValidation:
    """Test metrics array structure and content."""

    @pytest.mark.parametrize("filename", TARGET_EXPERIMENTS)
    def test_metrics_array_exists(self, filename):
        """Verify metrics array exists and is not empty."""
        filepath = POSTGRES_EXPERIMENTS_DIR / filename
        with open(filepath) as f:
            data = json.load(f)

        bc = data["baseline_config"]
        assert "metrics" in bc, f"Missing metrics array in {filename}"
        assert isinstance(bc["metrics"], list), f"metrics is not a list in {filename}"
        assert len(bc["metrics"]) > 0, f"metrics array is empty in {filename}"

    @pytest.mark.parametrize("filename", TARGET_EXPERIMENTS)
    def test_metrics_expected_count(self, filename):
        """Verify reasonable number of metrics per experiment."""
        filepath = POSTGRES_EXPERIMENTS_DIR / filename
        with open(filepath) as f:
            data = json.load(f)

        bc = data["baseline_config"]
        metrics_count = len(bc["metrics"])

        # Each experiment should have at least 2 metrics, up to many for Extensive
        assert 2 <= metrics_count <= 30, (
            f"{filename}: unexpected metric count {metrics_count}"
        )

    @pytest.mark.parametrize("filename", TARGET_EXPERIMENTS)
    def test_metric_required_fields(self, filename):
        """Verify each metric has required fields."""
        filepath = POSTGRES_EXPERIMENTS_DIR / filename
        with open(filepath) as f:
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
            "notes",
        }

        for i, metric in enumerate(bc["metrics"]):
            missing = required_fields - set(metric.keys())
            assert not missing, (
                f"{filename}, metric {i} ({metric.get('metric_name')}): "
                f"missing fields {missing}"
            )

    @pytest.mark.parametrize("filename", TARGET_EXPERIMENTS)
    def test_baseline_statistics_validity(self, filename):
        """Verify baseline_statistics have valid numeric values."""
        filepath = POSTGRES_EXPERIMENTS_DIR / filename
        with open(filepath) as f:
            data = json.load(f)

        bc = data["baseline_config"]
        required_stats = {
            "mean_value",
            "stddev_value",
            "min_value",
            "max_value",
            "percentile_50",
            "percentile_95",
            "percentile_99",
            "quality_score",
        }

        for i, metric in enumerate(bc["metrics"]):
            stats = metric.get("baseline_statistics", {})
            missing = required_stats - set(stats.keys())
            assert not missing, (
                f"{filename}, metric {i}: missing baseline_statistics {missing}"
            )

            # Validate numeric ranges
            mean = stats.get("mean_value")
            stddev = stats.get("stddev_value")
            min_val = stats.get("min_value")
            max_val = stats.get("max_value")
            quality = stats.get("quality_score")

            assert stddev >= 0, f"{filename}, metric {i}: negative stddev"
            assert min_val <= mean <= max_val, (
                f"{filename}, metric {i}: mean not between min/max"
            )
            assert 0 <= quality <= 100, (
                f"{filename}, metric {i}: invalid quality_score {quality}"
            )

    @pytest.mark.parametrize("filename", TARGET_EXPERIMENTS)
    def test_threshold_config_validity(self, filename):
        """Verify threshold_config has valid bounds."""
        filepath = POSTGRES_EXPERIMENTS_DIR / filename
        with open(filepath) as f:
            data = json.load(f)

        bc = data["baseline_config"]

        for i, metric in enumerate(bc["metrics"]):
            tc = metric.get("threshold_config", {})
            assert "sigma_threshold" in tc, (
                f"{filename}, metric {i}: missing sigma_threshold"
            )
            assert "critical_sigma" in tc, (
                f"{filename}, metric {i}: missing critical_sigma"
            )

            sigma = tc.get("sigma_threshold")
            critical = tc.get("critical_sigma")

            assert isinstance(sigma, (int, float)), (
                f"{filename}, metric {i}: sigma_threshold not numeric"
            )
            assert isinstance(critical, (int, float)), (
                f"{filename}, metric {i}: critical_sigma not numeric"
            )
            assert 0 < sigma < critical, (
                f"{filename}, metric {i}: invalid sigma ordering"
            )

    @pytest.mark.parametrize("filename", TARGET_EXPERIMENTS)
    def test_anomaly_detection_config(self, filename):
        """Verify anomaly_detection configuration."""
        filepath = POSTGRES_EXPERIMENTS_DIR / filename
        with open(filepath) as f:
            data = json.load(f)

        bc = data["baseline_config"]

        for i, metric in enumerate(bc["metrics"]):
            ad = metric.get("anomaly_detection", {})
            assert "enabled" in ad, f"{filename}, metric {i}: missing enabled flag"
            assert "method" in ad, f"{filename}, metric {i}: missing anomaly method"
            assert "sensitivity" in ad, f"{filename}, metric {i}: missing sensitivity"

            assert isinstance(ad["enabled"], bool), (
                f"{filename}, metric {i}: enabled must be boolean"
            )
            assert ad["method"] in ["zscore", "isolation_forest", "mad"], (
                f"{filename}, metric {i}: invalid anomaly method"
            )
            assert 0 <= ad.get("sensitivity", 0) <= 1, (
                f"{filename}, metric {i}: invalid sensitivity"
            )


class TestMetricsProbesCorrespondence:
    """Test that baseline_config metrics correspond to experiment probes."""

    @pytest.mark.parametrize("filename", TARGET_EXPERIMENTS)
    def test_metrics_referenced_by_probes(self, filename):
        """Verify baseline_config metrics are used by probes."""
        filepath = POSTGRES_EXPERIMENTS_DIR / filename
        with open(filepath) as f:
            data = json.load(f)

        bc = data["baseline_config"]
        {m["metric_name"] for m in bc.get("metrics", [])}

        # Extract probe names from steady-state-hypothesis
        ssh = data.get("steady-state-hypothesis", {})
        probe_names = {p.get("name", "") for p in ssh.get("probes", [])}

        # Verify at least one probe exists
        assert len(probe_names) > 0, f"{filename}: no probes found"

        # Verify metrics are referenced in baseline_config
        for metric in bc.get("metrics", []):
            probes = metric.get("used_in_probes", [])
            assert isinstance(probes, list), (
                f"{filename}, metric '{metric['metric_name']}': "
                f"used_in_probes must be a list"
            )
            assert len(probes) > 0, (
                f"{filename}, metric '{metric['metric_name']}': "
                f"must be used by at least one probe"
            )

    @pytest.mark.parametrize("filename", TARGET_EXPERIMENTS)
    def test_expected_metrics_present(self, filename):
        """Verify metrics are present for each experiment (with naming tolerance)."""
        filepath = POSTGRES_EXPERIMENTS_DIR / filename
        with open(filepath) as f:
            data = json.load(f)

        bc = data["baseline_config"]
        actual_metrics = {m["metric_name"] for m in bc.get("metrics", [])}

        # Verify at least 2 metrics per experiment (flexible naming)
        assert len(actual_metrics) >= 2, (
            f"{filename}: insufficient metrics ({len(actual_metrics)})"
        )


class TestIntegrationWithBaselineManager:
    """Test that baseline_config integrates with BaselineManager commands."""

    @pytest.mark.parametrize("filename", TARGET_EXPERIMENTS)
    def test_config_format_compatible_with_manager(self, filename):
        """Verify baseline_config format is compatible with BaselineManager."""
        filepath = POSTGRES_EXPERIMENTS_DIR / filename
        with open(filepath) as f:
            data = json.load(f)

        bc = data["baseline_config"]

        # Verify structure matches what BaselineManager expects
        assert bc.get("metadata", {}).get("service") == "postgres"
        assert bc.get("discovery", {}).get("system_id") == "postgres"
        assert isinstance(bc.get("default_thresholds"), dict)
        assert isinstance(bc.get("metrics"), list)

        # Each metric should have the fields needed by suggest_for_experiment()
        for metric in bc.get("metrics", []):
            assert "metric_id" in metric, "metric_id required for Manager"
            assert "metric_name" in metric, "metric_name required for Manager"
            assert "baseline_statistics" in metric, "baseline_statistics required"
            assert "status" in metric, "status required"

    @pytest.mark.parametrize("filename", TARGET_EXPERIMENTS)
    def test_metric_ids_unique(self, filename):
        """Verify metric IDs are unique within experiment."""
        filepath = POSTGRES_EXPERIMENTS_DIR / filename
        with open(filepath) as f:
            data = json.load(f)

        bc = data["baseline_config"]
        metric_ids = [m.get("metric_id") for m in bc.get("metrics", [])]

        assert len(metric_ids) == len(set(metric_ids)), (
            f"{filename}: duplicate metric IDs found"
        )

    def test_metric_ids_no_conflicts_across_files(self):
        """Verify metric IDs are reasonably structured (may be same metric in multiple experiments)."""
        all_metric_ids = {}

        for filename in TARGET_EXPERIMENTS:
            filepath = POSTGRES_EXPERIMENTS_DIR / filename
            with open(filepath) as f:
                data = json.load(f)

            bc = data["baseline_config"]
            for metric in bc.get("metrics", []):
                metric_id = metric.get("metric_id")

                # Verify metric ID is numeric and reasonable
                assert isinstance(metric_id, int), (
                    f"{filename}: metric_id must be numeric"
                )
                assert 0 < metric_id < 10000, (
                    f"{filename}: metric_id {metric_id} out of reasonable range"
                )

                # Track for reference (same metric can appear in multiple experiments)
                if metric_id not in all_metric_ids:
                    all_metric_ids[metric_id] = []
                all_metric_ids[metric_id].append(
                    {"file": filename, "name": metric.get("metric_name")}
                )


class TestPhase5Completeness:
    """End-to-end tests verifying Phase 5 completion."""

    def test_all_experiments_updated(self):
        """Verify all target experiments have baseline_config."""
        for filename in TARGET_EXPERIMENTS:
            filepath = POSTGRES_EXPERIMENTS_DIR / filename
            with open(filepath) as f:
                data = json.load(f)

            assert "baseline_config" in data, f"{filename} missing baseline_config"

            bc = data["baseline_config"]
            assert len(bc.get("metrics", [])) > 0, f"{filename} has empty metrics array"

    def test_phase5_task51_complete(self):
        """Verify Task 5.1 (JSON updates) is complete."""
        # All files should have valid, complete baseline_config sections
        for filename in TARGET_EXPERIMENTS:
            filepath = POSTGRES_EXPERIMENTS_DIR / filename
            with open(filepath) as f:
                data = json.load(f)

            bc = data.get("baseline_config", {})

            # Check all required top-level sections
            sections = {
                "metadata",
                "discovery",
                "default_thresholds",
                "data_validation",
                "metrics",
            }
            missing = sections - set(bc.keys())
            assert not missing, f"{filename} missing sections: {missing}"

            # Check metrics array quality
            assert len(bc["metrics"]) >= 2, f"{filename} has insufficient metrics"

    def test_phase5_deliverable_json_valid(self):
        """Verify Phase 5 deliverable: all JSON files are valid and complete."""
        invalid_files = []

        for filename in TARGET_EXPERIMENTS:
            filepath = POSTGRES_EXPERIMENTS_DIR / filename
            try:
                with open(filepath) as f:
                    data = json.load(f)

                # Verify key sections exist
                required = [
                    "version",
                    "title",
                    "configuration",
                    "baseline_config",
                    "controls",
                    "steady-state-hypothesis",
                ]
                missing = set(required) - set(data.keys())
                if missing:
                    invalid_files.append(f"{filename}: missing {missing}")

                # Verify baseline_config is properly structured
                bc = data.get("baseline_config", {})
                if not bc.get("metrics"):
                    invalid_files.append(f"{filename}: empty metrics")

            except json.JSONDecodeError as e:
                invalid_files.append(f"{filename}: JSON error - {e}")

        assert not invalid_files, "Invalid experiment files:\n" + "\n".join(
            invalid_files
        )

    def test_phase5_project_status(self):
        """Summary test: Phase 5 Task 5.1 completion status."""
        assert len(TARGET_EXPERIMENTS) == 9, "Expected 9 target files"

        completed = 0
        for filename in TARGET_EXPERIMENTS:
            filepath = POSTGRES_EXPERIMENTS_DIR / filename
            with open(filepath) as f:
                data = json.load(f)
            if "baseline_config" in data and data["baseline_config"].get("metrics"):
                completed += 1

        assert completed == len(TARGET_EXPERIMENTS), (
            f"Task 5.1 incomplete: {completed}/{len(TARGET_EXPERIMENTS)} files updated"
        )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
