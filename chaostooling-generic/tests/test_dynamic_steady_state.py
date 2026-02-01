"""
Comprehensive Unit and Integration Tests for Dynamic Steady-State Feature

Tests cover:
- DynamicMetricsFetcher: Multi-source metric retrieval
- DynamicSteadyStateCalculator: Statistical calculation and aggregation
- SteadyStateFormatter: Console output formatting
- DynamicSteadyStateControl: Chaos Toolkit lifecycle integration

Test Coverage Target: >95%

Usage:
    pytest tests/test_dynamic_steady_state.py -v
    pytest tests/test_dynamic_steady_state.py -v --cov=chaosgeneric.tools.dynamic --cov=chaosgeneric.control.dynamic_steady_state_control --cov-report=term-missing
"""

import json
import os
from datetime import datetime, timedelta
from typing import Any
from unittest.mock import MagicMock, Mock, patch

import pytest
from chaosgeneric.control.dynamic_steady_state_control import (
    _extract_metrics,
    _extract_service_name,
    before_experiment_start,
    configure_control,
)
from chaosgeneric.tools.dynamic_metrics_fetcher import DynamicMetricsFetcher
from chaosgeneric.tools.dynamic_steady_state_calculator import (
    DynamicSteadyStateCalculator,
)
from chaosgeneric.tools.steady_state_formatter import SteadyStateFormatter

# ============================================================================
# TEST FIXTURES
# ============================================================================


@pytest.fixture
def sample_metric_values():
    """Sample metric values for testing."""
    return [10.0, 12.0, 15.0, 18.0, 20.0, 22.0, 25.0, 28.0, 30.0, 32.0]


@pytest.fixture
def sample_prometheus_response():
    """Sample Prometheus API response."""
    return {
        "status": "success",
        "data": {
            "resultType": "matrix",
            "result": [
                {
                    "metric": {"service": "postgres"},
                    "values": [
                        [1000000000, "10.0"],
                        [1000000060, "12.0"],
                        [1000000120, "15.0"],
                    ],
                }
            ],
        },
    }


@pytest.fixture
def sample_grafana_response():
    """Sample Grafana API response."""
    return {
        "status": "success",
        "data": {
            "resultType": "matrix",
            "result": [
                {
                    "metric": {"service": "postgres"},
                    "values": [
                        [1000000000, "10.0"],
                        [1000000060, "12.0"],
                    ],
                }
            ],
        },
    }


@pytest.fixture
def sample_baseline_file(tmp_path):
    """Create a sample baseline JSON file."""
    baseline_data = {
        "baseline_config": {
            "metrics": [
                {
                    "metric_name": "postgresql_commits_total",
                    "baseline_statistics": {
                        "mean_value": 15.2,
                        "stddev_value": 3.8,
                        "min_value": 5.0,
                        "max_value": 32.1,
                        "percentile_50": 14.6,
                        "percentile_95": 23.8,
                        "percentile_99": 28.9,
                    },
                }
            ]
        }
    }
    file_path = tmp_path / "baseline_metrics.json"
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(baseline_data, f)
    return str(file_path)


@pytest.fixture
def sample_experiment():
    """Sample experiment configuration."""
    return {
        "version": "1.0",
        "title": "PostgreSQL Pool Exhaustion Test",
        "dynamic_steady_state": {
            "enabled": True,
            "period": "30d",
            "metrics": ["postgresql_commits_total"],
            "threshold_sigma": 2.0,
        },
        "baseline_config": {
            "discovery": {"service_name": "postgres"},
            "metrics": [
                {
                    "metric_name": "postgresql_commits_total",
                    "service_name": "postgres",
                }
            ],
        },
        "steady-state-hypothesis": {
            "probes": [
                {"provider": {"arguments": {"metric_name": "postgresql_commits_total"}}}
            ]
        },
    }


# ============================================================================
# DYNAMIC METRICS FETCHER TESTS
# ============================================================================


class TestDynamicMetricsFetcher:
    """Test DynamicMetricsFetcher class."""

    @pytest.mark.unit
    def test_init_defaults(self) -> None:
        """Test initialization with default values."""
        fetcher = DynamicMetricsFetcher()
        assert fetcher.grafana_url == "http://grafana:3000"
        assert fetcher.prometheus_url == "http://prometheus:9090"
        assert fetcher.db_host == "chaos-platform-db"
        assert fetcher.db_port == 5432
        assert fetcher.timeout == 5

    @pytest.mark.unit
    def test_init_custom_values(self) -> None:
        """Test initialization with custom values."""
        fetcher = DynamicMetricsFetcher(
            grafana_url="http://custom-grafana:3000",
            prometheus_url="http://custom-prometheus:9090",
            db_host="custom-db",
            db_port=5433,
            timeout=10,
        )
        assert fetcher.grafana_url == "http://custom-grafana:3000"
        assert fetcher.prometheus_url == "http://custom-prometheus:9090"
        assert fetcher.db_host == "custom-db"
        assert fetcher.db_port == 5433
        assert fetcher.timeout == 10

    @pytest.mark.unit
    @patch("chaosgeneric.tools.dynamic_metrics_fetcher.requests.get")
    def test_fetch_from_prometheus_success(
        self, mock_get, sample_prometheus_response
    ) -> None:
        """Test successful fetch from Prometheus."""
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = sample_prometheus_response
        mock_get.return_value.raise_for_status = Mock()

        fetcher = DynamicMetricsFetcher()
        values = fetcher.fetch_from_prometheus("test_metric", "24h")

        assert len(values) == 3
        assert values == [10.0, 12.0, 15.0]
        mock_get.assert_called_once()

    @pytest.mark.unit
    @patch("chaosgeneric.tools.dynamic_metrics_fetcher.requests.get")
    def test_fetch_from_prometheus_failure(self, mock_get) -> None:
        """Test Prometheus fetch failure handling."""
        mock_get.side_effect = Exception("Connection error")

        fetcher = DynamicMetricsFetcher()
        values = fetcher.fetch_from_prometheus("test_metric", "24h")

        assert values == []

    @pytest.mark.unit
    @patch("chaosgeneric.tools.dynamic_metrics_fetcher.requests.get")
    def test_fetch_from_grafana_success(
        self, mock_get, sample_grafana_response
    ) -> None:
        """Test successful fetch from Grafana."""
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = sample_grafana_response
        mock_get.return_value.raise_for_status = Mock()

        fetcher = DynamicMetricsFetcher()
        values = fetcher.fetch_from_grafana("test_metric", "24h")

        assert len(values) == 2
        assert values == [10.0, 12.0]

    @pytest.mark.unit
    @patch("chaosgeneric.tools.dynamic_metrics_fetcher.requests.get")
    def test_fetch_from_grafana_with_api_key(self, mock_get) -> None:
        """Test Grafana fetch with API key."""
        with patch.dict(os.environ, {"GRAFANA_API_KEY": "test-key"}):
            mock_get.return_value.status_code = 200
            mock_get.return_value.json.return_value = {
                "status": "success",
                "data": {"result": []},
            }
            mock_get.return_value.raise_for_status = Mock()

            fetcher = DynamicMetricsFetcher()
            fetcher.fetch_from_grafana("test_metric", "24h")

            # Verify Authorization header was set
            call_args = mock_get.call_args
            assert "Authorization" in call_args[1]["headers"]
            assert call_args[1]["headers"]["Authorization"] == "Bearer test-key"

    @pytest.mark.unit
    def test_fetch_from_file_success(self, sample_baseline_file) -> None:
        """Test successful fetch from file."""
        fetcher = DynamicMetricsFetcher()
        result = fetcher.fetch_from_file(
            "postgresql_commits_total", sample_baseline_file
        )

        assert result["mean"] == 15.2
        assert result["stddev"] == 3.8
        assert result["min"] == 5.0
        assert result["max"] == 32.1

    @pytest.mark.unit
    def test_fetch_from_file_not_found(self) -> None:
        """Test file fetch with non-existent file."""
        fetcher = DynamicMetricsFetcher()
        result = fetcher.fetch_from_file("test_metric", "/nonexistent/file.json")

        assert result == {}

    @pytest.mark.unit
    def test_fetch_from_file_metric_not_found(self, sample_baseline_file) -> None:
        """Test file fetch with metric not in file."""
        fetcher = DynamicMetricsFetcher()
        result = fetcher.fetch_from_file("nonexistent_metric", sample_baseline_file)

        assert result == {}

    @pytest.mark.unit
    @patch("chaosgeneric.tools.dynamic_metrics_fetcher.ChaosDb")
    def test_fetch_from_database_success(self, mock_chaos_db) -> None:
        """Test successful fetch from database."""
        # Mock database connection and cursor
        mock_db = MagicMock()
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_chaos_db.return_value = mock_db
        mock_db._get_connection.return_value.__enter__.return_value = mock_conn
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor

        # Mock query result
        mock_cursor.fetchall.return_value = [
            (
                json.dumps(
                    {
                        "values": [
                            [1000000000, "10.0"],
                            [1000000060, "12.0"],
                        ]
                    }
                ),
            )
        ]

        fetcher = DynamicMetricsFetcher()
        values = fetcher.fetch_from_database("test_metric", "postgres", "24h")

        assert len(values) == 2
        assert values == [10.0, 12.0]

    @pytest.mark.unit
    def test_parse_time_range_hours(self) -> None:
        """Test time range parsing for hours."""
        end_time = datetime(2026, 1, 31, 12, 0, 0)
        start_time = DynamicMetricsFetcher._parse_time_range("24h", end_time)

        expected = end_time - timedelta(hours=24)
        assert start_time == expected

    @pytest.mark.unit
    def test_parse_time_range_days(self) -> None:
        """Test time range parsing for days."""
        end_time = datetime(2026, 1, 31, 12, 0, 0)
        start_time = DynamicMetricsFetcher._parse_time_range("30d", end_time)

        expected = end_time - timedelta(days=30)
        assert start_time == expected

    @pytest.mark.unit
    def test_parse_time_range_minutes(self) -> None:
        """Test time range parsing for minutes."""
        end_time = datetime(2026, 1, 31, 12, 0, 0)
        start_time = DynamicMetricsFetcher._parse_time_range("60m", end_time)

        expected = end_time - timedelta(minutes=60)
        assert start_time == expected

    @pytest.mark.unit
    def test_parse_time_range_invalid_defaults_to_24h(self) -> None:
        """Test invalid time range defaults to 24h."""
        end_time = datetime(2026, 1, 31, 12, 0, 0)
        start_time = DynamicMetricsFetcher._parse_time_range("invalid", end_time)

        expected = end_time - timedelta(hours=24)
        assert start_time == expected

    @pytest.mark.unit
    @patch("chaosgeneric.tools.dynamic_metrics_fetcher.requests.get")
    def test_fetch_all_parallel(self, mock_get, sample_prometheus_response) -> None:
        """Test fetch_all with parallel execution."""
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = sample_prometheus_response
        mock_get.return_value.raise_for_status = Mock()

        fetcher = DynamicMetricsFetcher()
        results = fetcher.fetch_all(
            "test_metric",
            "postgres",
            "24h",
            sources=["prometheus"],
        )

        assert "prometheus" in results
        assert len(results["prometheus"]) > 0


# ============================================================================
# DYNAMIC STEADY-STATE CALCULATOR TESTS
# ============================================================================


class TestDynamicSteadyStateCalculator:
    """Test DynamicSteadyStateCalculator class."""

    @pytest.mark.unit
    def test_calculate_statistics(self, sample_metric_values) -> None:
        """Test statistical calculation."""
        stats = DynamicSteadyStateCalculator.calculate_statistics(sample_metric_values)

        assert stats["mean"] > 0
        assert stats["stddev"] > 0
        assert stats["min"] == 10.0
        assert stats["max"] == 32.0
        assert stats["p50"] > 0
        assert stats["p95"] > 0
        assert stats["p99"] > 0
        assert stats["data_points"] == 10

    @pytest.mark.unit
    def test_calculate_statistics_empty_list(self) -> None:
        """Test statistics calculation with empty list."""
        stats = DynamicSteadyStateCalculator.calculate_statistics([])

        assert stats["mean"] == 0.0
        assert stats["stddev"] == 0.0
        assert stats["data_points"] == 0

    @pytest.mark.unit
    def test_calculate_statistics_single_value(self) -> None:
        """Test statistics calculation with single value."""
        stats = DynamicSteadyStateCalculator.calculate_statistics([10.0])

        assert stats["mean"] == 10.0
        assert stats["stddev"] == 0.0
        assert stats["min"] == 10.0
        assert stats["max"] == 10.0

    @pytest.mark.unit
    def test_aggregate_sources_time_series(self) -> None:
        """Test aggregation from time-series sources."""
        source_data = {
            "grafana": [10.0, 12.0, 15.0],
            "prometheus": [18.0, 20.0],
            "database": [22.0, 25.0],
        }

        result = DynamicSteadyStateCalculator.aggregate_sources(
            source_data, "test_metric"
        )

        assert result["metric_name"] == "test_metric"
        assert result["data_points"] == 7
        assert "grafana" in result["sources"]
        assert "prometheus" in result["sources"]
        assert "database" in result["sources"]
        assert result["quality_score"] > 0

    @pytest.mark.unit
    def test_aggregate_sources_with_file_fallback(self) -> None:
        """Test aggregation with file source as fallback."""
        source_data = {
            "file": {
                "/path/to/file.json": {
                    "mean": 15.2,
                    "stddev": 3.8,
                    "min": 5.0,
                    "max": 32.1,
                }
            }
        }

        result = DynamicSteadyStateCalculator.aggregate_sources(
            source_data, "test_metric"
        )

        assert result["metric_name"] == "test_metric"
        assert result["data_points"] > 0
        assert "file" in result["sources"]

    @pytest.mark.unit
    def test_aggregate_sources_no_data(self) -> None:
        """Test aggregation with no data from any source."""
        source_data = {}

        result = DynamicSteadyStateCalculator.aggregate_sources(
            source_data, "test_metric"
        )

        assert result["metric_name"] == "test_metric"
        assert result["data_points"] == 0
        assert result["quality_score"] == 0

    @pytest.mark.unit
    def test_generate_steady_state_hypothesis(self) -> None:
        """Test steady-state-hypothesis generation."""
        metrics = [
            {
                "metric_name": "postgresql_commits_total",
                "mean": 15.2,
                "stddev": 3.8,
                "service_name": "postgres",
            }
        ]

        hypothesis = DynamicSteadyStateCalculator.generate_steady_state_hypothesis(
            metrics, threshold_sigma=2.0
        )

        assert hypothesis["title"] == "Dynamic steady-state based on historical metrics"
        assert len(hypothesis["probes"]) == 1
        assert hypothesis["probes"][0]["name"].startswith("check-")
        assert "tolerance" in hypothesis["probes"][0]

    @pytest.mark.unit
    def test_generate_steady_state_hypothesis_skips_invalid(self) -> None:
        """Test hypothesis generation skips invalid metrics."""
        metrics = [
            {
                "metric_name": "valid_metric",
                "mean": 15.2,
                "stddev": 3.8,
            },
            {
                "metric_name": "invalid_metric",
                "mean": 0,
                "stddev": 0,
            },
        ]

        hypothesis = DynamicSteadyStateCalculator.generate_steady_state_hypothesis(
            metrics
        )

        assert len(hypothesis["probes"]) == 1
        assert hypothesis["probes"][0]["name"] == "check-valid-metric"

    @pytest.mark.unit
    def test_percentile_calculation(self) -> None:
        """Test percentile calculation."""
        sorted_data = [10.0, 20.0, 30.0, 40.0, 50.0]

        p50 = DynamicSteadyStateCalculator._percentile(sorted_data, 50)
        p95 = DynamicSteadyStateCalculator._percentile(sorted_data, 95)
        p99 = DynamicSteadyStateCalculator._percentile(sorted_data, 99)

        assert p50 == 30.0
        assert p95 > 40.0
        assert p99 > 45.0

    @pytest.mark.unit
    def test_quality_score_calculation(self) -> None:
        """Test quality score calculation."""
        stats = {
            "data_points": 1000,
            "stddev": 5.0,
        }

        score = DynamicSteadyStateCalculator._calculate_quality_score(stats, 3)

        assert 0 <= score <= 100
        assert score > 50  # Should be high with 1000 points and 3 sources

    @pytest.mark.unit
    def test_quality_score_low_data_points(self) -> None:
        """Test quality score with low data points."""
        stats = {
            "data_points": 5,
            "stddev": 0.0,
        }

        score = DynamicSteadyStateCalculator._calculate_quality_score(stats, 1)

        assert score < 50  # Should be low with few points and 1 source


# ============================================================================
# STEADY-STATE FORMATTER TESTS
# ============================================================================


class TestSteadyStateFormatter:
    """Test SteadyStateFormatter class."""

    @pytest.mark.unit
    def test_format_metrics_table(self) -> None:
        """Test metrics table formatting."""
        metrics = [
            {
                "metric_name": "postgresql_commits_total",
                "mean": 15.2,
                "stddev": 3.8,
                "p95": 23.8,
                "p99": 28.9,
                "quality_score": 95,
            }
        ]

        output = SteadyStateFormatter.format_metrics_table(metrics)

        assert "DYNAMIC STEADY-STATE METRICS" in output
        assert "postgresql_commits_total" in output
        assert "15.20" in output
        assert "95" in output

    @pytest.mark.unit
    def test_format_metrics_table_empty(self) -> None:
        """Test formatting with empty metrics."""
        output = SteadyStateFormatter.format_metrics_table([])

        assert "No metrics calculated" in output

    @pytest.mark.unit
    def test_format_metrics_table_long_name(self) -> None:
        """Test formatting with long metric name."""
        metrics = [
            {
                "metric_name": "a" * 50,  # Very long name
                "mean": 15.2,
                "stddev": 3.8,
                "p95": 23.8,
                "p99": 28.9,
                "quality_score": 95,
            }
        ]

        output = SteadyStateFormatter.format_metrics_table(metrics)

        # Should truncate long names
        lines = output.split("\n")
        metric_line = [line for line in lines if "a" * 10 in line][0]
        assert len(metric_line.split()[0]) <= 40

    @pytest.mark.unit
    def test_format_summary(self) -> None:
        """Test summary formatting."""
        metrics = [
            {
                "metric_name": "test_metric",
                "quality_score": 90,
                "sources": ["grafana", "prometheus"],
            }
        ]

        output = SteadyStateFormatter.format_summary(metrics, "30d")

        assert "DYNAMIC STEADY-STATE SUMMARY" in output
        assert "30d" in output
        assert "1" in output  # Metrics count
        assert "90.0" in output  # Average quality

    @pytest.mark.unit
    def test_format_steady_state_hypothesis(self) -> None:
        """Test hypothesis formatting."""
        hypothesis = {
            "title": "Test hypothesis",
            "probes": [
                {
                    "name": "check-metric",
                    "tolerance": {"lower": 10.0, "upper": 20.0},
                }
            ],
        }

        output = SteadyStateFormatter.format_steady_state_hypothesis(hypothesis)

        assert "DYNAMIC STEADY-STATE HYPOTHESIS" in output
        assert "Test hypothesis" in output
        assert "check-metric" in output
        assert "10.00" in output
        assert "20.00" in output


# ============================================================================
# CONTROL HOOK TESTS
# ============================================================================


class TestDynamicSteadyStateControl:
    """Test DynamicSteadyStateControl."""

    @pytest.mark.unit
    def test_configure_control_enabled(self) -> None:
        """Test control configuration when enabled."""
        with patch.dict(os.environ, {"DYNAMIC_STEADY_STATE_ENABLED": "true"}):
            configure_control()

    @pytest.mark.unit
    def test_configure_control_disabled(self) -> None:
        """Test control configuration when disabled."""
        with patch.dict(os.environ, {"DYNAMIC_STEADY_STATE_ENABLED": "false"}):
            configure_control()

    @pytest.mark.unit
    def test_extract_metrics_from_explicit_config(self, sample_experiment) -> None:
        """Test metric extraction from explicit config."""
        metrics = _extract_metrics(
            sample_experiment, sample_experiment["dynamic_steady_state"]
        )

        assert "postgresql_commits_total" in metrics

    @pytest.mark.unit
    def test_extract_metrics_from_baseline_config(self) -> None:
        """Test metric extraction from baseline_config."""
        experiment = {
            "baseline_config": {
                "metrics": [
                    {"metric_name": "metric1"},
                    {"metric_name": "metric2"},
                ]
            }
        }

        metrics = _extract_metrics(experiment, {})

        assert "metric1" in metrics
        assert "metric2" in metrics

    @pytest.mark.unit
    def test_extract_metrics_from_probes(self) -> None:
        """Test metric extraction from steady-state-hypothesis probes."""
        experiment = {
            "steady-state-hypothesis": {
                "probes": [{"provider": {"arguments": {"metric_name": "probe_metric"}}}]
            }
        }

        metrics = _extract_metrics(experiment, {})

        assert "probe_metric" in metrics

    @pytest.mark.unit
    def test_extract_service_name_from_baseline_config(self) -> None:
        """Test service name extraction from baseline_config."""
        experiment = {"baseline_config": {"discovery": {"service_name": "postgres"}}}

        service_name = _extract_service_name(experiment)

        assert service_name == "postgres"

    @pytest.mark.unit
    def test_extract_service_name_from_title(self) -> None:
        """Test service name extraction from title."""
        experiment = {"title": "PostgreSQL Pool Exhaustion Test"}

        service_name = _extract_service_name(experiment)

        assert service_name == "postgres"

    @pytest.mark.unit
    def test_extract_service_name_default(self) -> None:
        """Test service name extraction defaults to unknown."""
        experiment = {"title": "Generic Test"}

        service_name = _extract_service_name(experiment)

        assert service_name == "unknown"

    @pytest.mark.unit
    @patch("chaosgeneric.control.dynamic_steady_state_control.DynamicMetricsFetcher")
    @patch(
        "chaosgeneric.control.dynamic_steady_state_control.DynamicSteadyStateCalculator"
    )
    @patch.dict(os.environ, {"DYNAMIC_STEADY_STATE_ENABLED": "true"})
    def test_before_experiment_start_success(
        self, mock_calculator, mock_fetcher, sample_experiment
    ):
        """Test successful before_experiment_start execution."""
        # Mock fetcher
        mock_fetcher_instance = MagicMock()
        mock_fetcher.return_value = mock_fetcher_instance
        mock_fetcher_instance.fetch_all.return_value = {
            "grafana": [10.0, 12.0, 15.0],
            "prometheus": [18.0, 20.0],
        }

        # Mock calculator
        mock_calculator.aggregate_sources.return_value = {
            "metric_name": "postgresql_commits_total",
            "mean": 15.2,
            "stddev": 3.8,
            "data_points": 5,
            "sources": ["grafana", "prometheus"],
            "quality_score": 90,
            "service_name": "postgres",
        }
        mock_calculator.generate_steady_state_hypothesis.return_value = {
            "title": "Dynamic steady-state",
            "probes": [],
        }

        context: dict[str, Any] = {}
        before_experiment_start(context, experiment=sample_experiment)

        assert "dynamic_steady_state" in context
        assert "postgresql_commits_total" in sample_experiment.get(
            "steady-state-hypothesis", {}
        ).get("title", "")

    @pytest.mark.unit
    @patch.dict(os.environ, {"DYNAMIC_STEADY_STATE_ENABLED": "false"})
    def test_before_experiment_start_disabled(self, sample_experiment) -> None:
        """Test before_experiment_start when disabled."""
        context: dict[str, Any] = {}
        before_experiment_start(context, experiment=sample_experiment)

        assert "dynamic_steady_state" not in context

    @pytest.mark.unit
    def test_before_experiment_start_no_experiment(self) -> None:
        """Test before_experiment_start with no experiment."""
        context: dict[str, Any] = {}
        before_experiment_start(context, experiment=None)

        # Should not raise exception
        assert True

    @pytest.mark.unit
    @patch("chaosgeneric.control.dynamic_steady_state_control.DynamicMetricsFetcher")
    @patch.dict(os.environ, {"DYNAMIC_STEADY_STATE_ENABLED": "true"})
    def test_before_experiment_start_no_metrics(
        self, mock_fetcher: Any, sample_experiment: dict[str, Any]
    ) -> None:
        """Test before_experiment_start with no metrics found."""
        # Remove metrics from experiment
        del sample_experiment["dynamic_steady_state"]["metrics"]
        del sample_experiment["baseline_config"]

        context: dict[str, Any] = {}
        before_experiment_start(context, experiment=sample_experiment)

        # Should handle gracefully
        assert True


# ============================================================================
# INTEGRATION TESTS
# ============================================================================


@pytest.mark.integration
class TestDynamicSteadyStateIntegration:
    """Integration tests for dynamic steady-state feature."""

    @pytest.mark.integration
    def test_end_to_end_flow(
        self,
        sample_experiment: dict[str, Any],
        tmp_path: Any,
        sample_baseline_file: str,
    ) -> None:
        """Test end-to-end flow from fetch to hypothesis generation."""
        # Setup
        with patch.dict(
            os.environ,
            {
                "DYNAMIC_STEADY_STATE_ENABLED": "true",
                "DYNAMIC_STEADY_STATE_BASELINE_FILES": sample_baseline_file,
            },
        ):
            # Mock external API calls
            with patch(
                "chaosgeneric.tools.dynamic_metrics_fetcher.requests.get"
            ) as mock_get:
                mock_get.return_value.status_code = 200
                mock_get.return_value.json.return_value = {
                    "status": "success",
                    "data": {"result": []},
                }
                mock_get.return_value.raise_for_status = Mock()

                # Execute
                context: dict[str, Any] = {}
                before_experiment_start(context, experiment=sample_experiment)

                # Verify
                assert "dynamic_steady_state" in context
                assert "metrics" in context["dynamic_steady_state"]
