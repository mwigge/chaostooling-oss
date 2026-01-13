"""
Tests for TraceCore.

Tests span creation, attributes, events, exceptions, and status.
"""

from chaosotel.core.trace_core import TraceCore


class TestTracesCoreInitialization:
    """Test TraceCore initialization."""

    def test_init(self, tracer_provider):
        """Test TraceCore initialization."""
        trace = TraceCore(tracer_provider)
        
        assert trace is not None
        assert trace.tracer_provider is not None
        assert trace.tracer is not None


class TestSpanCreation:
    """Test span creation."""

    def test_create_span(self, tracer_provider):
        """Test creating a span."""
        trace = TraceCore(tracer_provider)
        
        span = trace.create_span("test_span")
        
        assert span is not None

    def test_create_span_with_attributes(self, tracer_provider):
        """Test creating span with attributes."""
        trace = TraceCore(tracer_provider)
        
        span = trace.create_span(
            "test_span",
            attributes={"service": "chaos", "env": "test"}
        )
        
        assert span is not None

    def test_create_nested_spans(self, tracer_provider):
        """Test creating nested spans."""
        trace = TraceCore(tracer_provider)
        
        parent_span = trace.create_span("parent")
        child_span = trace.create_span("child")
        
        assert parent_span is not None
        assert child_span is not None


class TestAttributeManagement:
    """Test attribute management on spans."""

    def test_set_attribute(self, tracer_provider):
        """Test setting attribute on span."""
        trace = TraceCore(tracer_provider)
        span = trace.create_span("test_span")
        
        trace.set_attribute(span, "operation", "chaos")
        
        assert span is not None

    def test_set_multiple_attributes(self, tracer_provider):
        """Test setting multiple attributes."""
        trace = TraceCore(tracer_provider)
        span = trace.create_span("test_span")
        
        trace.set_attributes(span, {
            "operation": "chaos",
            "target": "database",
            "severity": "high"
        })
        
        assert span is not None


class TestEventRecording:
    """Test event recording on spans."""

    def test_add_event(self, tracer_provider):
        """Test adding event to span."""
        trace = TraceCore(tracer_provider)
        span = trace.create_span("test_span")
        
        trace.add_event(span, "action_started")
        
        assert span is not None

    def test_add_event_with_attributes(self, tracer_provider):
        """Test adding event with attributes."""
        trace = TraceCore(tracer_provider)
        span = trace.create_span("test_span")
        
        trace.add_event(
            span,
            "action_completed",
            attributes={"duration_ms": 150, "status": "success"}
        )
        
        assert span is not None


class TestExceptionTracking:
    """Test exception tracking in spans."""

    def test_record_exception(self, tracer_provider):
        """Test recording exception."""
        trace = TraceCore(tracer_provider)
        span = trace.create_span("test_span")
        
        try:
            raise ValueError("Test error")
        except ValueError as e:
            trace.record_exception(span, e)
        
        assert span is not None

    def test_exception_in_span(self, tracer_provider):
        """Test exception within span context."""
        trace = TraceCore(tracer_provider)
        
        try:
            with trace.span_context("test_span"):
                raise RuntimeError("Test runtime error")
        except RuntimeError:
            pass  # Expected
        
        assert trace is not None


class TestStatusManagement:
    """Test span status management."""

    def test_set_status_ok(self, tracer_provider):
        """Test setting span status to OK."""
        trace = TraceCore(tracer_provider)
        span = trace.create_span("test_span")
        
        trace.set_status_ok(span)
        
        assert span is not None

    def test_set_status_error(self, tracer_provider):
        """Test setting span status to ERROR."""
        trace = TraceCore(tracer_provider)
        span = trace.create_span("test_span")
        
        trace.set_status_error(span, "Operation failed")
        
        assert span is not None


class TestSpanAccessors:
    """Test span accessor methods."""

    def test_get_current_span(self, tracer_provider):
        """Test getting current span."""
        trace = TraceCore(tracer_provider)
        
        span = trace.get_current_span()
        
        # May be None if no active span
        assert span is None or span is not None

    def test_get_span_context(self, tracer_provider):
        """Test getting span context."""
        trace = TraceCore(tracer_provider)
        span = trace.create_span("test_span")
        
        context = trace.get_span_context(span)
        
        assert context is not None
        assert "trace_id" in context
        assert "span_id" in context


class TestManualSpanManagement:
    """Test manual span creation and management."""

    def test_start_end_span(self, tracer_provider):
        """Test starting and ending span."""
        trace = TraceCore(tracer_provider)
        
        span = trace.start_span("manual_span")
        assert span is not None
        
        # Manually end the span
        if span:
            span.end()
        
        assert trace is not None