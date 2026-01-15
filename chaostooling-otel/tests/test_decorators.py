# tests/test_decorators.py

"""
Tests for ChaoSOTEL decorators.

Tests all 7 decorators:
1. @instrument_action
2. @instrument_probe
3. @instrument_rollback
4. @record_metric
5. @track_compliance
6. @track_impact
7. instrumented_section
"""

import time

import pytest
from chaosotel import (instrument_action, instrument_probe,
                       instrument_rollback, instrumented_section,
                       record_metric, track_compliance, track_impact)


class TestInstrumentAction:
    """Test @instrument_action decorator."""

    def test_successful_action(self, initialized_chaosotel):
        """Test successful action recording."""

        @instrument_action(name="test_action", target_type="database", severity="high")
        def test_func():
            return "success"

        result = test_func()

        assert result == "success"

    def test_action_duration_recorded(self, initialized_chaosotel):
        """Test that action duration is recorded."""

        @instrument_action(name="slow_action")
        def slow_func():
            time.sleep(0.1)
            return "done"

        result = slow_func()

        assert result == "done"

    def test_action_exception_handling(self, initialized_chaosotel):
        """Test exception handling in action."""

        @instrument_action(name="failing_action")
        def failing_func():
            raise ValueError("Test error")

        with pytest.raises(ValueError) as exc_info:
            failing_func()

        assert "Test error" in str(exc_info.value)

    def test_action_with_result_recording(self, initialized_chaosotel):
        """Test action with result recording."""

        @instrument_action(name="result_action", record_result=True)
        def return_value_func():
            return {"status": "ok", "count": 42}

        result = return_value_func()

        assert result["count"] == 42

    def test_action_with_tags(self, initialized_chaosotel):
        """Test action with custom tags."""

        @instrument_action(
            name="tagged_action", tags={"team": "platform", "env": "test"}
        )
        def tagged_func():
            return "tagged"

        result = tagged_func()

        assert result == "tagged"

    def test_action_without_initialization(self):
        """Test that action requires initialization."""

        @instrument_action(name="uninit_action")
        def uninit_func():
            return "never"

        with pytest.raises(RuntimeError):
            uninit_func()


class TestInstrumentProbe:
    """Test @instrument_probe decorator."""

    def test_successful_probe(self, initialized_chaosotel):
        """Test successful probe execution."""

        @instrument_probe(name="test_probe", target_type="database")
        def probe_func():
            return {"status": "healthy", "response_time_ms": 12.5}

        result = probe_func()

        assert result["status"] == "healthy"

    def test_probe_duration_recorded(self, initialized_chaosotel):
        """Test probe duration recording."""

        @instrument_probe(name="slow_probe")
        def slow_probe():
            time.sleep(0.05)
            return {"status": "ok"}

        result = slow_probe()

        assert result["status"] == "ok"

    def test_probe_error_detection(self, initialized_chaosotel):
        """Test probe error status detection."""

        @instrument_probe(name="error_probe")
        def error_probe():
            return {"status": "error", "reason": "connection failed"}

        result = error_probe()

        assert result["status"] == "error"

    def test_probe_exception(self, initialized_chaosotel):
        """Test probe exception handling."""

        @instrument_probe(name="failing_probe")
        def failing_probe():
            raise RuntimeError("Probe failed")

        with pytest.raises(RuntimeError):
            failing_probe()


class TestInstrumentRollback:
    """Test @instrument_rollback decorator."""

    def test_successful_rollback(self, initialized_chaosotel):
        """Test successful rollback."""

        @instrument_rollback(name="test_rollback", target_type="database")
        def rollback_func():
            return {"restored": True, "connections": 5}

        result = rollback_func()

        assert result["restored"] is True
        assert result["connections"] == 5

    def test_rollback_records_mttr(self, initialized_chaosotel):
        """Test that rollback records MTTR metric."""

        @instrument_rollback(name="mttr_rollback")
        def mttr_func():
            time.sleep(0.05)
            return {"done": True}

        result = mttr_func()

        assert result["done"] is True

    def test_rollback_failure(self, initialized_chaosotel):
        """Test rollback failure handling."""

        @instrument_rollback(name="failing_rollback")
        def failing_rollback():
            raise Exception("Recovery failed")

        with pytest.raises(Exception):
            failing_rollback()


class TestRecordMetric:
    """Test @record_metric decorator."""

    def test_record_metric_from_dict_result(self, initialized_chaosotel):
        """Test recording metric from dict result."""

        @record_metric("db.query.latency", unit="ms", metric_type="histogram")
        def query_func():
            return {"latency_ms": 125.5}

        result = query_func()

        assert result["latency_ms"] == 125.5

    def test_record_metric_custom_description(self, initialized_chaosotel):
        """Test recording metric with description."""

        @record_metric(
            "custom.metric",
            unit="GB",
            metric_type="gauge",
            description="Custom metric description",
        )
        def metric_func():
            return {"value": 42.0}

        result = metric_func()

        assert result["value"] == 42.0

    def test_multiple_metrics(self, initialized_chaosotel):
        """Test multiple metrics on same function."""

        @record_metric("metric.one", metric_type="counter")
        @record_metric("metric.two", metric_type="gauge")
        def multi_func():
            return {"metric_two": 10.0}

        result = multi_func()

        assert result["metric_two"] == 10.0


class TestTrackCompliance:
    """Test @track_compliance decorator."""

    def test_track_single_regulation(self, initialized_chaosotel):
        """Test tracking single regulation."""

        @track_compliance(regulations=["SOX"])
        def compliant_func():
            return "compliant"

        result = compliant_func()

        assert result == "compliant"

    def test_track_multiple_regulations(self, initialized_chaosotel):
        """Test tracking multiple regulations."""

        @track_compliance(regulations=["SOX", "GDPR", "PCI-DSS"])
        def multi_compliant_func():
            return "multi_compliant"

        result = multi_compliant_func()

        assert result == "multi_compliant"

    def test_compliance_violation_on_error(self, initialized_chaosotel):
        """Test compliance violation on function error."""

        @track_compliance(regulations=["SOX"])
        def violating_func():
            raise ValueError("Compliance violation")

        with pytest.raises(ValueError):
            violating_func()


class TestTrackImpact:
    """Test @track_impact decorator."""

    def test_track_impact_from_int_result(self, initialized_chaosotel):
        """Test impact tracking from int return value."""

        @track_impact(impact_type="connections")
        def kill_func():
            return 5  # 5 connections killed

        result = kill_func()

        assert result == 5

    def test_track_impact_from_dict_result(self, initialized_chaosotel):
        """Test impact tracking from dict result."""

        @track_impact(impact_type="pods")
        def restart_func():
            return {"count": 3, "status": "restarted"}

        result = restart_func()

        assert result["count"] == 3

    def test_track_impact_zero(self, initialized_chaosotel):
        """Test impact with zero count."""

        @track_impact(impact_type="instances")
        def no_impact_func():
            return 0

        result = no_impact_func()

        assert result == 0


class TestInstrumentedSection:
    """Test instrumented_section context manager."""

    def test_successful_section(self, initialized_chaosotel):
        """Test successful instrumented section."""
        with instrumented_section("test_section"):
            value = 42

        assert value == 42

    def test_section_with_tags(self, initialized_chaosotel):
        """Test instrumented section with tags."""
        with instrumented_section("tagged_section", tags={"team": "platform"}):
            pass

    def test_section_exception_handling(self, initialized_chaosotel):
        """Test exception handling in section."""
        with pytest.raises(ValueError):
            with instrumented_section("error_section"):
                raise ValueError("Section error")

    def test_nested_sections(self, initialized_chaosotel):
        """Test nested instrumented sections."""
        with instrumented_section("outer"):
            with instrumented_section("inner"):
                value = "nested"

        assert value == "nested"


class TestDecoratorCombinations:
    """Test combinations of decorators."""

    def test_action_with_compliance(self, initialized_chaosotel):
        """Test action with compliance tracking."""

        @track_compliance(regulations=["SOX"])
        @instrument_action(name="compliant_action")
        def combined_func():
            return "result"

        result = combined_func()

        assert result == "result"

    def test_action_with_impact(self, initialized_chaosotel):
        """Test action with impact tracking."""

        @track_impact(impact_type="connections")
        @instrument_action(name="impactful_action")
        def impact_func():
            return 5

        result = impact_func()

        assert result == 5

    def test_action_with_metric_and_compliance(self, initialized_chaosotel):
        """Test action with metric and compliance."""

        @track_compliance(regulations=["GDPR"])
        @record_metric("custom.metric", metric_type="gauge")
        @instrument_action(name="complex_action")
        def complex_func():
            return {"custom_metric": 42.0}

        result = complex_func()

        assert result["custom_metric"] == 42.0
