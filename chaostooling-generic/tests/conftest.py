"""
Shared test fixtures and configuration for chaostooling baseline testing.

This module provides:
- Database fixtures for chaos_platform connectivity
- Sample baseline data fixtures
- Mock client fixtures for external dependencies
- Test configuration and markers
"""

import json
import os
from datetime import datetime, timedelta

import psycopg2
import pytest
from psycopg2.extras import DictCursor

# ============================================================================
# TEST MARKERS & CONFIGURATION
# ============================================================================


def pytest_configure(config):
    """Register custom markers for test categorization."""
    config.addinivalue_line(
        "markers", "unit: Unit tests (fast, no external dependencies)"
    )
    config.addinivalue_line(
        "markers", "integration: Integration tests (require database/external services)"
    )
    config.addinivalue_line(
        "markers", "e2e: End-to-end tests (full workflow from discover to audit)"
    )
    config.addinivalue_line("markers", "slow: Tests that take >1 second to run")
    config.addinivalue_line("markers", "db: Tests that require database connectivity")
    config.addinivalue_line(
        "markers", "flaky: Tests known to be flaky and need investigation"
    )


# ============================================================================
# DATABASE FIXTURES
# ============================================================================


@pytest.fixture(scope="session")
def db_config() -> dict[str, str]:
    """Database configuration from environment or defaults."""
    return {
        "host": os.getenv("CHAOS_DB_HOST", "localhost"),
        "port": int(os.getenv("CHAOS_DB_PORT", "5434")),
        "database": os.getenv("CHAOS_DB_NAME", "chaos_platform"),
        "user": os.getenv("CHAOS_DB_USER", "chaos_user"),
        "password": os.getenv("CHAOS_DB_PASSWORD", "chaos_password"),
    }


@pytest.fixture(scope="session")
def db_connection(db_config):
    """Session-scoped database connection for test setup."""
    try:
        conn = psycopg2.connect(**db_config)
        conn.autocommit = True
        yield conn
        conn.close()
    except psycopg2.OperationalError as e:
        pytest.skip(f"Cannot connect to database: {e}")


@pytest.fixture
def db_cursor(db_connection):
    """Function-scoped database cursor with transaction rollback after test."""
    cursor = db_connection.cursor(cursor_factory=DictCursor)
    yield cursor
    # Rollback any changes made during test
    try:
        db_connection.rollback()
    except Exception:
        pass
    cursor.close()


@pytest.fixture(autouse=True)
def db_transaction_rollback(db_connection):
    """Automatic transaction rollback after each test to maintain clean state."""
    yield
    try:
        db_connection.rollback()
    except Exception:
        pass


# ============================================================================
# BASELINE DATA FIXTURES
# ============================================================================


@pytest.fixture
def baseline_metric_factory():
    """Factory for creating BaselineMetric instances."""
    from chaosgeneric.tools.baseline_loader import BaselineMetric

    def _create_metric(
        metric_name: str = "cpu_usage",
        system_name: str = "api-server",
        service_name: str = "api-service",
        mean: float = 45.5,
        stdev: float = 5.2,
        p50: float = 44.0,
        p95: float = 58.0,
        p99: float = 62.0,
        min_val: float = 10.0,
        max_val: float = 95.0,
        count: int = 1000,
        baseline_window_hours: int = 24,
        thresholds: dict = None,
        sample_time: datetime = None,
        valid: bool = True,
        quality_score: float = 0.95,
        **kwargs,
    ) -> BaselineMetric:
        """Create a BaselineMetric with sensible defaults."""
        if sample_time is None:
            sample_time = datetime.utcnow()

        if thresholds is None:
            thresholds = {
                "warn": mean + (2 * stdev),
                "critical": mean + (3 * stdev),
                "min": max(0, min_val - (stdev / 2)),
            }

        return BaselineMetric(
            metric_name=metric_name,
            system_name=system_name,
            service_name=service_name,
            mean=mean,
            stdev=stdev,
            p50=p50,
            p95=p95,
            p99=p99,
            min_val=min_val,
            max_val=max_val,
            count=count,
            baseline_window_hours=baseline_window_hours,
            thresholds=thresholds,
            sample_time=sample_time,
            valid=valid,
            quality_score=quality_score,
            **kwargs,
        )

    return _create_metric


@pytest.fixture
def sample_baselines(baseline_metric_factory) -> dict[str, object]:
    """Sample baseline metrics covering various scenarios."""
    return {
        # Normal baselines
        "cpu_usage": baseline_metric_factory(
            metric_name="cpu_usage",
            system_name="api-server",
            service_name="api-service",
            mean=45.5,
            stdev=5.2,
        ),
        "memory_usage": baseline_metric_factory(
            metric_name="memory_usage",
            system_name="api-server",
            service_name="api-service",
            mean=70.0,
            stdev=8.0,
        ),
        "latency_p99": baseline_metric_factory(
            metric_name="latency_p99",
            system_name="api-server",
            service_name="api-service",
            mean=150.0,
            stdev=25.0,
        ),
        # Edge case: zero stdev (constant metric)
        "constant_metric": baseline_metric_factory(
            metric_name="constant_metric",
            system_name="db-server",
            service_name="postgres",
            mean=100.0,
            stdev=0.0,
            p50=100.0,
            p95=100.0,
            p99=100.0,
        ),
        # Edge case: very high variance
        "high_variance": baseline_metric_factory(
            metric_name="high_variance",
            system_name="cache-server",
            service_name="redis",
            mean=50.0,
            stdev=40.0,
        ),
        # Edge case: low quality
        "low_quality": baseline_metric_factory(
            metric_name="low_quality",
            system_name="queue-server",
            service_name="kafka",
            quality_score=0.45,
        ),
        # Invalid baseline
        "invalid_baseline": baseline_metric_factory(
            metric_name="invalid_baseline",
            system_name="unknown",
            service_name="unknown",
            valid=False,
        ),
    }


@pytest.fixture
def sample_experiment_configs() -> dict[str, dict]:
    """Sample chaos toolkit experiment configurations."""
    return {
        "postgres_pool_exhaustion": {
            "version": "1.0.0",
            "title": "PostgreSQL Pool Exhaustion",
            "description": "Test pool exhaustion behavior",
            "steady-state-hypothesis": {
                "title": "Connections remain within limits",
                "probes": [
                    {
                        "type": "probe",
                        "name": "check-connection-count",
                        "module": "chaosgeneric.probes.baseline",
                        "function": "check_baseline_metric",
                        "arguments": {
                            "metric_name": "postgres_connections",
                            "system_name": "postgres-primary",
                            "threshold_type": "p99",
                        },
                    }
                ],
            },
            "method": [
                {
                    "type": "action",
                    "name": "exhaust-connections",
                    "module": "chaosgeneric.actions.db",
                    "function": "exhaust_postgres_pool",
                }
            ],
        },
        "cpu_stress_test": {
            "version": "1.0.0",
            "title": "CPU Stress Test",
            "description": "Test application behavior under CPU stress",
            "steady-state-hypothesis": {
                "title": "Application responds within baseline",
                "probes": [
                    {
                        "type": "probe",
                        "name": "check-cpu",
                        "module": "chaosgeneric.probes.baseline",
                        "function": "check_baseline_metric",
                        "arguments": {
                            "metric_name": "cpu_usage",
                            "system_name": "api-server",
                            "threshold_type": "p95",
                        },
                    }
                ],
            },
        },
    }


# ============================================================================
# MOCK FIXTURES
# ============================================================================


@pytest.fixture
def mock_grafana_client(mocker):
    """Mock Grafana client for testing baseline discovery."""
    mock = mocker.MagicMock()
    mock.get_metrics_by_system.return_value = [
        {"metric": "cpu_usage", "system": "api-server"},
        {"metric": "memory_usage", "system": "api-server"},
        {"metric": "latency_p99", "system": "api-server"},
    ]
    mock.get_metrics_by_service.return_value = [
        {"metric": "postgres_connections", "service": "postgres"},
        {"metric": "postgres_active_queries", "service": "postgres"},
    ]
    return mock


@pytest.fixture
def mock_db_client(mocker):
    """Mock ChaosDb client for testing database operations."""
    mock = mocker.MagicMock()
    mock.get_baselines_for_system.return_value = [
        {"metric_name": "cpu_usage", "mean": 45.5, "stdev": 5.2},
        {"metric_name": "memory_usage", "mean": 70.0, "stdev": 8.0},
    ]
    mock.insert_baseline_experiment_mapping.return_value = True
    mock.get_baseline_versions.return_value = [
        {"version_id": 1, "created_at": datetime.utcnow()},
        {"version_id": 2, "created_at": datetime.utcnow()},
    ]
    return mock


@pytest.fixture
def mock_metrics_client(mocker):
    """Mock metrics client for testing baseline calculations."""
    mock = mocker.MagicMock()
    mock.query_metric.return_value = {
        "values": [45.5, 46.2, 44.8, 47.1, 45.3] * 200,  # 1000 values
        "timestamps": [datetime.utcnow() - timedelta(minutes=i) for i in range(1000)],
    }
    return mock


# ============================================================================
# CLEANUP & TEARDOWN FIXTURES
# ============================================================================


@pytest.fixture(autouse=True)
def cleanup_test_data(db_cursor):
    """Clean up test data after each test."""
    yield
    # Tables to clean in order of foreign key dependencies
    tables = [
        "baseline_experiment_mapping",
        "baseline_versions",
        "baseline_metrics",
    ]

    for table in tables:
        try:
            db_cursor.execute(f"DELETE FROM {table};")
        except Exception:
            pass


# ============================================================================
# TEST PARAMETRIZATION FIXTURES
# ============================================================================


@pytest.fixture(
    params=[
        "cpu_usage",
        "memory_usage",
        "latency_p99",
        "disk_io",
        "network_throughput",
    ]
)
def metric_names(request):
    """Parameterized fixture for various metric names."""
    return request.param


@pytest.fixture(
    params=[
        "api-server",
        "db-server",
        "cache-server",
        "queue-server",
    ]
)
def system_names(request):
    """Parameterized fixture for various system names."""
    return request.param


@pytest.fixture(
    params=[
        ("p50", 0.50),
        ("p95", 0.95),
        ("p99", 0.99),
    ]
)
def percentile_thresholds(request):
    """Parameterized fixture for percentile thresholds."""
    return request.param


# ============================================================================
# UTILITY FIXTURES
# ============================================================================


@pytest.fixture
def temp_baseline_file(tmp_path):
    """Create temporary baseline JSON file for testing."""
    baseline_data = {
        "version": "1.0.0",
        "baselines": {
            "cpu_usage": {
                "mean": 45.5,
                "stdev": 5.2,
                "p95": 58.0,
                "p99": 62.0,
            },
            "memory_usage": {
                "mean": 70.0,
                "stdev": 8.0,
                "p95": 85.0,
                "p99": 90.0,
            },
        },
    }

    file_path = tmp_path / "baselines.json"
    file_path.write_text(json.dumps(baseline_data, indent=2))
    return file_path


@pytest.fixture
def test_audit_log_entry() -> dict:
    """Sample audit log entry for testing."""
    return {
        "log_id": 1,
        "action": "baseline_discovered",
        "entity_type": "baseline_metric",
        "entity_id": "cpu_usage_api-server",
        "actor": "test_user",
        "details": {
            "metric_name": "cpu_usage",
            "system_name": "api-server",
            "mean": 45.5,
            "stdev": 5.2,
        },
        "action_timestamp": datetime.utcnow(),
    }
