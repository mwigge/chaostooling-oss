"""
Tests for MetricsCore.

Tests action, probe, recovery, compliance, and custom metrics.
"""

import pytest
from chaosotel.core.metrics_core import MetricsCore


class TestMetricsCoreInitialization:
    """Test MetricsCore initialization."""

    def test_init(self, meter_provider):
        """Test MetricsCore initialization."""
        metrics = MetricsCore(meter_provider)
        
        assert metrics is not None
        assert metrics.meter_provider is not None
        assert metrics._metric_count == 0

    def test_init_with_custom_name(self, meter_provider):
        """Test MetricsCore initialization with custom name."""
        metrics = MetricsCore(meter_provider, name="custom_meter")
        
        assert metrics is not None


class TestActionMetrics:
    """Test action metrics."""

    def test_record_action_duration(self, meter_provider):
        """Test recording action duration."""
        metrics = MetricsCore(meter_provider)
        initial_count = metrics._metric_count
        
        metrics.record_action_duration(
            name="test_action",
            duration_ms=150.5,
            status="success"
        )
        
        assert metrics._metric_count > initial_count

    def test_record_action_count(self, meter_provider):
        """Test recording action count."""
        metrics = MetricsCore(meter_provider)
        initial_count = metrics._metric_count
        
        metrics.record_action_count(
            name="test_action",
            status="success"
        )
        
        assert metrics._metric_count > initial_count

    def test_record_action_success_vs_error(self, meter_provider):
        """Test recording success vs error actions."""
        metrics = MetricsCore(meter_provider)
        
        metrics.record_action_count(name="action1", status="success")
        metrics.record_action_count(name="action1", status="error")
        
        assert metrics._metric_count >= 2


class TestProbeMetrics:
    """Test probe metrics."""

    def test_record_probe_duration(self, meter_provider):
        """Test recording probe duration."""
        metrics = MetricsCore(meter_provider)
        initial_count = metrics._metric_count
        
        metrics.record_probe_duration(
            name="test_probe",
            duration_ms=250.0,
            status="success"
        )
        
        assert metrics._metric_count > initial_count

    def test_record_probe_count(self, meter_provider):
        """Test recording probe count."""
        metrics = MetricsCore(meter_provider)
        initial_count = metrics._metric_count
        
        metrics.record_probe_count(
            name="test_probe",
            status="success"
        )
        
        assert metrics._metric_count > initial_count


class TestRecoveryMetrics:
    """Test recovery metrics (MTTR)."""

    def test_record_recovery_time_success(self, meter_provider):
        """Test recording successful recovery time."""
        metrics = MetricsCore(meter_provider)
        initial_count = metrics._metric_count
        
        metrics.record_recovery_time(
            name="rollback_db",
            duration_ms=500.0,
            success=True
        )
        
        assert metrics._metric_count > initial_count

    def test_record_recovery_time_failure(self, meter_provider):
        """Test recording failed recovery time."""
        metrics = MetricsCore(meter_provider)
        initial_count = metrics._metric_count
        
        metrics.record_recovery_time(
            name="rollback_db",
            duration_ms=2000.0,
            success=False
        )
        
        assert metrics._metric_count > initial_count


class TestComplianceMetrics:
    """Test compliance metrics."""

    def test_record_compliance_score(self, meter_provider):
        """Test recording compliance score."""
        metrics = MetricsCore(meter_provider)
        
        # Gauges work differently, just ensure no error
        metrics.record_compliance_score(
            regulation="SOX",
            score=95.0
        )
        
        assert metrics is not None

    def test_record_compliance_violation(self, meter_provider):
        """Test recording compliance violation."""
        metrics = MetricsCore(meter_provider)
        initial_count = metrics._metric_count
        
        metrics.record_compliance_violation(
            regulation="GDPR",
            violation="data_exposure",
            severity="critical"
        )
        
        assert metrics._metric_count > initial_count


class TestImpactMetrics:
    """Test impact metrics."""

    def test_record_impact_scope(self, meter_provider):
        """Test recording impact scope."""
        metrics = MetricsCore(meter_provider)
        initial_count = metrics._metric_count
        
        metrics.record_impact_scope(
            action_name="kill_pod",
            impact_type="pods_killed",
            count=5,
            percentage=25.0
        )
        
        assert metrics._metric_count > initial_count


class TestCustomMetrics:
    """Test custom metric recording."""

    def test_record_gauge_metric(self, meter_provider):
        """Test recording gauge metric."""
        metrics = MetricsCore(meter_provider)
        
        # Gauges work differently - just ensure no error
        metrics.record_custom_metric(
            name="cpu.usage",
            value=45.5,
            metric_type="gauge",
            unit="%"
        )
        
        assert metrics is not None

    def test_record_counter_metric(self, meter_provider):
        """Test recording counter metric."""
        metrics = MetricsCore(meter_provider)
        initial_count = metrics._metric_count
        
        metrics.record_custom_metric(
            name="requests.total",
            value=100,
            metric_type="counter"
        )
        
        assert metrics._metric_count > initial_count

    def test_record_histogram_metric(self, meter_provider):
        """Test recording histogram metric."""
        metrics = MetricsCore(meter_provider)
        initial_count = metrics._metric_count
        
        metrics.record_custom_metric(
            name="response.time",
            value=125.5,
            metric_type="histogram",
            unit="ms"
        )
        
        assert metrics._metric_count > initial_count

    def test_record_metric_with_tags(self, meter_provider):
        """Test recording metric with tags."""
        metrics = MetricsCore(meter_provider)
        
        metrics.record_custom_metric(
            name="custom.metric",
            value=42.0,
            metric_type="gauge",
            tags={"service": "chaos", "env": "prod"}
        )
        
        assert metrics is not None

    def test_record_metric_with_description(self, meter_provider):
        """Test recording metric with description."""
        metrics = MetricsCore(meter_provider)
        
        metrics.record_custom_metric(
            name="described.metric",
            value=10.0,
            metric_type="gauge",
            description="Custom metric description"
        )
        
        assert metrics is not None


class TestMetricsInstrumentation:
    """Test metrics instrumentation."""

    def test_instrument_reuse(self, meter_provider):
        """Test instrument reuse from cache."""
        metrics = MetricsCore(meter_provider)
        
        # Record same metric twice - should reuse instrument
        metrics.record_action_duration("action1", 100.0)
        initial_instruments = len(metrics._instruments)
        
        metrics.record_action_duration("action1", 200.0)
        
        # Should still have same number of instruments (reused)
        assert len(metrics._instruments) == initial_instruments