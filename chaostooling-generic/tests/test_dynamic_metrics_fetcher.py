"""
Unit tests for DynamicMetricsFetcher.

Tests metric fetching from Grafana, Prometheus, database, and files.
"""

import json
import os
from datetime import datetime, timedelta
from unittest.mock import MagicMock, Mock, patch

import pytest

from chaosgeneric.tools.dynamic_metrics_fetcher import DynamicMetricsFetcher


class TestDynamicMetricsFetcher:
    """Test DynamicMetricsFetcher class."""

    def test_init_defaults(self):
        """Test initialization with default values."""
        with patch.dict(os.environ, {}, clear=True):
            fetcher = DynamicMetricsFetcher()
            assert fetcher.grafana_url == "http://grafana:3000"
            assert fetcher.prometheus_url == "http://prometheus:9090"
            assert fetcher.db_host == "chaos-platform-db"
            assert fetcher.db_port == 5432
            assert fetcher.timeout == 5

    def test_init_custom(self):
        """Test initialization with custom values."""
        fetcher = DynamicMetricsFetcher(
            grafana_url="http://custom-grafana:3000",
            prometheus_url="http://custom-prom:9090",
            db_host="custom-db",
            db_port=5433,
            timeout=10,
        )
        assert fetcher.grafana_url == "http://custom-grafana:3000"
        assert fetcher.prometheus_url == "http://custom-prom:9090"
        assert fetcher.db_host == "custom-db"
        assert fetcher.db_port == 5433
        assert fetcher.timeout == 10

    @patch("chaosgeneric.tools.dynamic_metrics_fetcher.requests.get")
    def test_fetch_from_grafana_success(self, mock_get):
        """Test successful fetch from Grafana."""
        # Mock response
        mock_response = Mock()
        mock_response.json.return_value = {
            "status": "success",
            "data": {
                "result": [
                    {
                        "values": [
                            [1000, "10.5"],
                            [2000, "15.2"],
                            [3000, "12.8"],
                        ]
                    }
                ]
            },
        }
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response

        fetcher = DynamicMetricsFetcher(grafana_url="http://grafana:3000")
        values = fetcher.fetch_from_grafana("test_metric", "24h")

        assert len(values) == 3
        assert values == [10.5, 15.2, 12.8]
        mock_get.assert_called_once()

    @patch("chaosgeneric.tools.dynamic_metrics_fetcher.requests.get")
    def test_fetch_from_grafana_failure(self, mock_get):
        """Test Grafana fetch failure handling."""
        mock_get.side_effect = Exception("Connection error")

        fetcher = DynamicMetricsFetcher()
        values = fetcher.fetch_from_grafana("test_metric", "24h")

        assert values == []

    @patch("chaosgeneric.tools.dynamic_metrics_fetcher.requests.get")
    def test_fetch_from_prometheus_success(self, mock_get):
        """Test successful fetch from Prometheus."""
        mock_response = Mock()
        mock_response.json.return_value = {
            "status": "success",
            "data": {
                "result": [
                    {
                        "values": [
                            [1000, "20.1"],
                            [2000, "25.3"],
                        ]
                    }
                ]
            },
        }
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response

        fetcher = DynamicMetricsFetcher(prometheus_url="http://prometheus:9090")
        values = fetcher.fetch_from_prometheus("test_metric", "24h")

        assert len(values) == 2
        assert values == [20.1, 25.3]

    @patch("chaosgeneric.tools.dynamic_metrics_fetcher.requests.get")
    def test_fetch_from_prometheus_failure(self, mock_get):
        """Test Prometheus fetch failure handling."""
        mock_get.side_effect = Exception("Timeout")

        fetcher = DynamicMetricsFetcher()
        values = fetcher.fetch_from_prometheus("test_metric", "24h")

        assert values == []

    def test_fetch_from_file_success(self, tmp_path):
        """Test successful fetch from file."""
        # Create test baseline file
        baseline_file = tmp_path / "baseline.json"
        baseline_data = {
            "baseline_config": {
                "metrics": [
                    {
                        "metric_name": "test_metric",
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
        baseline_file.write_text(json.dumps(baseline_data))

        fetcher = DynamicMetricsFetcher()
        result = fetcher.fetch_from_file("test_metric", str(baseline_file))

        assert result["mean"] == 15.2
        assert result["stddev"] == 3.8
        assert result["min"] == 5.0
        assert result["max"] == 32.1

    def test_fetch_from_file_not_found(self):
        """Test file fetch when file doesn't exist."""
        fetcher = DynamicMetricsFetcher()
        result = fetcher.fetch_from_file("test_metric", "/nonexistent/file.json")

        assert result == {}

    def test_fetch_from_file_metric_not_found(self, tmp_path):
        """Test file fetch when metric not in file."""
        baseline_file = tmp_path / "baseline.json"
        baseline_data = {"baseline_config": {"metrics": []}}
        baseline_file.write_text(json.dumps(baseline_data))

        fetcher = DynamicMetricsFetcher()
        result = fetcher.fetch_from_file("nonexistent_metric", str(baseline_file))

        assert result == {}

    @patch("chaosgeneric.tools.dynamic_metrics_fetcher.ChaosDb")
    def test_fetch_from_database_success(self, mock_chaos_db_class):
        """Test successful fetch from database."""
        # Mock database connection and cursor
        mock_db = Mock()
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_conn.__enter__ = Mock(return_value=mock_conn)
        mock_conn.__exit__ = Mock(return_value=None)
        mock_conn.cursor.return_value.__enter__ = Mock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = Mock(return_value=None)

        # Mock query results
        mock_cursor.fetchall.return_value = [
            (json.dumps({"values": [[1000, "10.5"], [2000, "15.2"]]}),),
        ]

        mock_db._get_connection.return_value.__enter__ = Mock(return_value=mock_conn)
        mock_db._get_connection.return_value.__exit__ = Mock(return_value=None)
        mock_chaos_db_class.return_value = mock_db

        fetcher = DynamicMetricsFetcher()
        values = fetcher.fetch_from_database("test_metric", "test_service", "24h")

        assert len(values) == 2
        assert values == [10.5, 15.2]

    @patch("chaosgeneric.tools.dynamic_metrics_fetcher.ChaosDb")
    def test_fetch_from_database_failure(self, mock_chaos_db_class):
        """Test database fetch failure handling."""
        mock_chaos_db_class.side_effect = Exception("Database error")

        fetcher = DynamicMetricsFetcher()
        values = fetcher.fetch_from_database("test_metric", "test_service", "24h")

        assert values == []

    @patch("chaosgeneric.tools.dynamic_metrics_fetcher.DynamicMetricsFetcher.fetch_from_grafana")
    @patch("chaosgeneric.tools.dynamic_metrics_fetcher.DynamicMetricsFetcher.fetch_from_prometheus")
    @patch("chaosgeneric.tools.dynamic_metrics_fetcher.DynamicMetricsFetcher.fetch_from_database")
    def test_fetch_all_parallel(self, mock_db, mock_prom, mock_grafana):
        """Test fetch_all with parallel execution."""
        mock_grafana.return_value = [10.0, 15.0]
        mock_prom.return_value = [20.0, 25.0]
        mock_db.return_value = [30.0, 35.0]

        fetcher = DynamicMetricsFetcher()
        result = fetcher.fetch_all(
            "test_metric", "test_service", "24h", sources=["grafana", "prometheus", "database"]
        )

        assert "grafana" in result
        assert "prometheus" in result
        assert "database" in result
        assert result["grafana"] == [10.0, 15.0]
        assert result["prometheus"] == [20.0, 25.0]
        assert result["database"] == [30.0, 35.0]

    def test_parse_time_range_hours(self):
        """Test time range parsing for hours."""
        end_time = datetime(2026, 1, 31, 12, 0, 0)
        start_time = DynamicMetricsFetcher._parse_time_range("24h", end_time)

        expected = end_time - timedelta(hours=24)
        assert start_time == expected

    def test_parse_time_range_days(self):
        """Test time range parsing for days."""
        end_time = datetime(2026, 1, 31, 12, 0, 0)
        start_time = DynamicMetricsFetcher._parse_time_range("30d", end_time)

        expected = end_time - timedelta(days=30)
        assert start_time == expected

    def test_parse_time_range_minutes(self):
        """Test time range parsing for minutes."""
        end_time = datetime(2026, 1, 31, 12, 0, 0)
        start_time = DynamicMetricsFetcher._parse_time_range("60m", end_time)

        expected = end_time - timedelta(minutes=60)
        assert start_time == expected

    def test_parse_time_range_invalid(self):
        """Test time range parsing with invalid format."""
        end_time = datetime(2026, 1, 31, 12, 0, 0)
        start_time = DynamicMetricsFetcher._parse_time_range("invalid", end_time)

        # Should default to 24h
        expected = end_time - timedelta(hours=24)
        assert start_time == expected
