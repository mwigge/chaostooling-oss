# tests/test_core_logs.py

"""
Tests for LogCore class.
"""

import pytest
import json

from chaosotel.core import LogCore


class TestLogsCoreInitialization:
    """Test LogCore initialization."""
    
    def test_init(self, logger_provider):
        """Test LogCore initialization."""
        logs = LogCore(logger_provider)
        
        assert logs.logger_provider == logger_provider
        assert logs._audit_trail == []
    
    def test_init_empty_audit_trail(self, logger_provider):
        """Test that audit trail starts empty."""
        logs = LogCore(logger_provider)
        
        assert len(logs.get_audit_trail()) == 0


class TestActionLogging:
    """Test action lifecycle logging."""
    
    def test_log_action_start(self, logger_provider):
        """Test logging action start."""
        logs = LogCore(logger_provider)
        
        logs.log_action_start(
            action_name="test_action",
            action_type="database",
            severity="high"
        )
        
        assert len(logs.get_audit_trail()) > 0
    
    def test_log_action_end_success(self, logger_provider):
        """Test logging successful action end."""
        logs = LogCore(logger_provider)
        
        logs.log_action_end(
            action_name="test_action",
            success=True,
            duration_ms=1250.5
        )
        
        assert len(logs.get_audit_trail()) > 0
    
    def test_log_action_end_with_result(self, logger_provider):
        """Test logging action end with result."""
        logs = LogCore(logger_provider)
        
        logs.log_action_end(
            action_name="test_action",
            success=True,
            duration_ms=100.0,
            result={"status": "ok", "count": 5}
        )
        
        trail = logs.get_audit_trail()
        assert len(trail) > 0
    
    def test_log_action_error(self, logger_provider):
        """Test logging action error."""
        logs = LogCore(logger_provider)
        
        logs.log_action_end(
            action_name="failing_action",
            success=False,
            duration_ms=150.0,
            error="Connection timeout"
        )
        
        assert len(logs.get_audit_trail()) > 0


class TestProbeLogging:
    """Test probe logging."""
    
    def test_log_probe_start(self, logger_provider):
        """Test logging probe start."""
        logs = LogCore(logger_provider)
        
        logs.log_probe_start(
            probe_name="test_probe",
            target_type="database"
        )
        
        assert len(logs.get_audit_trail()) > 0
    
    def test_log_probe_end_success(self, logger_provider):
        """Test logging probe end success."""
        logs = LogCore(logger_provider)
        
        logs.log_probe_end(
            probe_name="test_probe",
            status="success",
            duration_ms=50.0,
            result={"connected": True}
        )
        
        assert len(logs.get_audit_trail()) > 0
    
    def test_log_probe_end_error(self, logger_provider):
        """Test logging probe end error."""
        logs = LogCore(logger_provider)
        
        logs.log_probe_end(
            probe_name="failing_probe",
            status="error",
            duration_ms=100.0,
            error="Connection refused"
        )
        
        assert len(logs.get_audit_trail()) > 0


class TestErrorLogging:
    """Test error logging."""
    
    def test_log_error(self, logger_provider):
        """Test logging structured error."""
        logs = LogCore(logger_provider)
        
        logs.log_error(
            component="database",
            error_message="Connection failed",
            error_type="ConnectionError"
        )
        
        assert len(logs.get_audit_trail()) > 0
    
    def test_log_error_with_context(self, logger_provider):
        """Test logging error with context."""
        logs = LogCore(logger_provider)
        
        logs.log_error(
            component="network",
            error_message="Timeout",
            error_type="TimeoutError",
            context={"host": "localhost", "port": 5432}
        )
        
        assert len(logs.get_audit_trail()) > 0


class TestComplianceLogging:
    """Test compliance check logging."""
    
    def test_log_compliance_check_pass(self, logger_provider):
        """Test logging passed compliance check."""
        logs = LogCore(logger_provider)
        
        logs.log_compliance_check(
            regulation="SOX",
            check_name="audit_trail",
            passed=True
        )
        
        assert len(logs.get_audit_trail()) > 0
    
    def test_log_compliance_check_fail(self, logger_provider):
        """Test logging failed compliance check."""
        logs = LogCore(logger_provider)
        
        logs.log_compliance_check(
            regulation="GDPR",
            check_name="data_retention",
            passed=False,
            details={"retained_days": 100}
        )
        
        assert len(logs.get_audit_trail()) > 0


class TestEventLogging:
    """Test event logging."""
    
    def test_log_event(self, logger_provider):
        """Test logging custom event."""
        logs = LogCore(logger_provider)
        
        logs.log_event(
            event_name="custom_event",
            event_data={"key": "value"}
        )
        
        assert len(logs.get_audit_trail()) > 0
    
    def test_log_event_with_severity(self, logger_provider):
        """Test logging event with severity."""
        logs = LogCore(logger_provider)
        
        logs.log_event(
            event_name="warning_event",
            event_data={"reason": "test"},
            severity="warning"
        )
        
        assert len(logs.get_audit_trail()) > 0


class TestAuditTrail:
    """Test audit trail functionality."""
    
    def test_get_audit_trail(self, logger_provider):
        """Test retrieving audit trail."""
        logs = LogCore(logger_provider)
        
        logs.log_action_start("action1")
        logs.log_action_end("action1", success=True, duration_ms=100.0)
        
        trail = logs.get_audit_trail()
        
        assert len(trail) == 2
    
    def test_clear_audit_trail(self, logger_provider):
        """Test clearing audit trail."""
        logs = LogCore(logger_provider)
        
        logs.log_action_start("action1")
        assert len(logs.get_audit_trail()) > 0
        
        logs.clear_audit_trail()
        
        assert len(logs.get_audit_trail()) == 0


class TestTraceContext:
    """Test trace context propagation."""
    
    def test_trace_context_in_logs(self, logger_provider):
        """Test that trace context is included in logs."""
        logs = LogCore(logger_provider)
        
        logs.log_action_start("test_action")
        
        trail = logs.get_audit_trail()
        log_entry = trail[0]["data"]
        
        # Should have trace context
        assert "trace_id" in log_entry
        assert "span_id" in log_entry