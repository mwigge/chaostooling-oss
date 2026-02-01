"""
Integration tests for DynamicSteadyStateControl.

Tests control hook integration with Chaos Toolkit lifecycle.
"""

import os
from unittest.mock import Mock, patch

import pytest

from chaosgeneric.control.dynamic_steady_state_control import (
    before_experiment_start,
    configure_control,
)


class TestDynamicSteadyStateControl:
    """Test DynamicSteadyStateControl."""

    def test_configure_control_enabled(self):
        """Test control configuration when enabled."""
        with patch.dict(os.environ, {"DYNAMIC_STEADY_STATE_ENABLED": "true"}):
            configure_control()

    def test_configure_control_disabled(self):
        """Test control configuration when disabled."""
        with patch.dict(os.environ, {"DYNAMIC_STEADY_STATE_ENABLED": "false"}):
            configure_control()

    @patch("chaosgeneric.control.dynamic_steady_state_control.DynamicMetricsFetcher")
    @patch("chaosgeneric.control.dynamic_steady_state_control.DynamicSteadyStateCalculator")
    @patch("chaosgeneric.control.dynamic_steady_state_control._print_to_console")
    def test_before_experiment_start_success(
        self, mock_print, mock_calculator, mock_fetcher_class
    ):
        """Test successful steady-state calculation."""
        # Mock fetcher
        mock_fetcher = Mock()
        mock_fetcher.fetch_all.return_value = {
            "grafana": [10.0, 15.0, 20.0],
            "prometheus": [25.0, 30.0],
        }
        mock_fetcher_class.return_value = mock_fetcher

        # Mock calculator
        mock_calculator.aggregate_sources.return_value = {
            "metric_name": "test_metric",
            "mean": 20.0,
            "stddev": 5.0,
            "data_points": 5,
            "sources": ["grafana", "prometheus"],
            "quality_score": 90,
            "service_name": "test_service",
        }
        mock_calculator.generate_steady_state_hypothesis.return_value = {
            "title": "Dynamic steady-state",
            "probes": [],
        }

        experiment = {
            "title": "Test Experiment",
            "dynamic_steady_state": {
                "enabled": True,
                "period": "30d",
                "metrics": ["test_metric"],
            },
        }
        context = {}

        with patch.dict(os.environ, {"DYNAMIC_STEADY_STATE_ENABLED": "true"}):
            before_experiment_start(context, experiment)

        # Verify experiment was updated
        assert "steady-state-hypothesis" in experiment
        assert "dynamic_steady_state" in context

    def test_before_experiment_start_disabled(self):
        """Test when feature is disabled."""
        experiment = {"title": "Test Experiment"}
        context = {}

        with patch.dict(os.environ, {"DYNAMIC_STEADY_STATE_ENABLED": "false"}):
            before_experiment_start(context, experiment)

        # Should not modify experiment
        assert "steady-state-hypothesis" not in experiment or experiment.get(
            "steady-state-hypothesis"
        ) == {}

    def test_before_experiment_start_no_experiment(self):
        """Test when no experiment provided."""
        context = {}

        with patch.dict(os.environ, {"DYNAMIC_STEADY_STATE_ENABLED": "true"}):
            before_experiment_start(context, experiment=None)

        # Should not fail

    @patch("chaosgeneric.control.dynamic_steady_state_control._extract_metrics")
    def test_before_experiment_start_no_metrics(self, mock_extract):
        """Test when no metrics found."""
        mock_extract.return_value = []

        experiment = {"title": "Test Experiment"}
        context = {}

        with patch.dict(os.environ, {"DYNAMIC_STEADY_STATE_ENABLED": "true"}):
            before_experiment_start(context, experiment)

        # Should not modify experiment

    @patch("chaosgeneric.control.dynamic_steady_state_control.DynamicMetricsFetcher")
    def test_before_experiment_start_error_handling(self, mock_fetcher_class):
        """Test error handling during calculation."""
        mock_fetcher_class.side_effect = Exception("Fetcher error")

        experiment = {
            "title": "Test Experiment",
            "dynamic_steady_state": {"metrics": ["test_metric"]},
        }
        context = {}

        with patch.dict(os.environ, {"DYNAMIC_STEADY_STATE_ENABLED": "true"}):
            # Should not raise exception
            before_experiment_start(context, experiment)

    def test_extract_metrics_from_config(self):
        """Test metric extraction from dynamic_steady_state config."""
        from chaosgeneric.control.dynamic_steady_state_control import _extract_metrics

        experiment = {
            "dynamic_steady_state": {
                "metrics": ["metric1", "metric2"],
            }
        }

        metrics = _extract_metrics(experiment, experiment["dynamic_steady_state"])

        assert metrics == ["metric1", "metric2"]

    def test_extract_metrics_from_baseline_config(self):
        """Test metric extraction from baseline_config."""
        from chaosgeneric.control.dynamic_steady_state_control import _extract_metrics

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

    def test_extract_metrics_from_probes(self):
        """Test metric extraction from steady-state-hypothesis probes."""
        from chaosgeneric.control.dynamic_steady_state_control import _extract_metrics

        experiment = {
            "steady-state-hypothesis": {
                "probes": [
                    {
                        "provider": {
                            "arguments": {"metric_name": "probe_metric"}
                        }
                    }
                ]
            }
        }

        metrics = _extract_metrics(experiment, {})

        assert "probe_metric" in metrics

    def test_extract_service_name_from_baseline_config(self):
        """Test service name extraction from baseline_config."""
        from chaosgeneric.control.dynamic_steady_state_control import _extract_service_name

        experiment = {
            "baseline_config": {
                "discovery": {"service_name": "postgres"}
            }
        }

        service_name = _extract_service_name(experiment)

        assert service_name == "postgres"

    def test_extract_service_name_from_title(self):
        """Test service name extraction from experiment title."""
        from chaosgeneric.control.dynamic_steady_state_control import _extract_service_name

        experiment = {"title": "PostgreSQL Pool Exhaustion Test"}

        service_name = _extract_service_name(experiment)

        assert service_name == "postgres"

    def test_extract_service_name_default(self):
        """Test service name extraction default."""
        from chaosgeneric.control.dynamic_steady_state_control import _extract_service_name

        experiment = {"title": "Generic Test"}

        service_name = _extract_service_name(experiment)

        assert service_name == "unknown"
