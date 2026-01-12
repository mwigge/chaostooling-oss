"""
TraceCore - Distributed tracing interface for Tempo/Jaeger.

Records:
- Span creation and lifecycle
- Span attributes
- Events within spans
- Exception tracking
- Span status
"""

import logging
from typing import Any, Dict, Optional

from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.trace import Status, StatusCode

logger = logging.getLogger("chaosotel.trace_core")


class TraceCore:
    """
    Core tracing interface for Tempo/Jaeger.

    Provides unified API for:
    - Span creation and management
    - Attribute tracking
    - Event recording
    - Exception tracking
    - Status management
    """

    def __init__(self, tracer_provider: TracerProvider):
        """
        Initialize TraceCore.

        Args:
            tracer_provider: OpenTelemetry TracerProvider
        """
        self.tracer_provider = tracer_provider
        self.tracer = tracer_provider.get_tracer(__name__)

        logger.info("TraceCore initialized")

    # ========================================================================
    # SPAN CREATION & MANAGEMENT
    # ========================================================================

    def create_span(
        self, name: str, attributes: Optional[Dict[str, Any]] = None
    ) -> Any:
        """Create a new span."""
        try:
            span = self.tracer.start_span(name)

            if attributes:
                for key, value in attributes.items():
                    span.set_attribute(key, value)

            logger.debug(f"Created span: {name}")
            return span
        except Exception as e:
            logger.error(f"Error creating span: {e}")
            return None

    def start_span(
        self, name: str, attributes: Optional[Dict[str, Any]] = None
    ) -> Any:
        """Start a span manually."""
        try:
            span = self.tracer.start_span(name)
            if attributes:
                for key, value in attributes.items():
                    span.set_attribute(key, value)
            return span
        except Exception as e:
            logger.error(f"Error starting span: {e}")
            return None

    # ========================================================================
    # ATTRIBUTE MANAGEMENT
    # ========================================================================

    def set_attribute(self, span: Any, key: str, value: Any) -> None:
        """Set attribute on span."""
        try:
            if span:
                span.set_attribute(key, value)
            logger.debug(f"Set attribute {key}={value}")
        except Exception as e:
            logger.error(f"Error setting attribute: {e}")

    def set_attributes(self, span: Any, attributes: Dict[str, Any]) -> None:
        """Set multiple attributes on span."""
        try:
            if span and attributes:
                for key, value in attributes.items():
                    span.set_attribute(key, value)
            logger.debug(f"Set {len(attributes or {})} attributes")
        except Exception as e:
            logger.error(f"Error setting attributes: {e}")

    # ========================================================================
    # EVENT RECORDING
    # ========================================================================

    def add_event(
        self, span: Any, name: str, attributes: Optional[Dict[str, Any]] = None
    ) -> None:
        """Add event to span."""
        try:
            if span:
                span.add_event(name, attributes=attributes)
            logger.debug(f"Added event: {name}")
        except Exception as e:
            logger.error(f"Error adding event: {e}")

    # ========================================================================
    # EXCEPTION TRACKING
    # ========================================================================

    def record_exception(
        self, span: Any, exception: Exception, escaped: bool = False
    ) -> None:
        """Record exception in span."""
        try:
            if span:
                span.record_exception(exception, escaped=escaped)
            logger.error(f"Recorded exception: {str(exception)}")
        except Exception as e:
            logger.error(f"Error recording exception: {e}")

    # ========================================================================
    # STATUS MANAGEMENT
    # ========================================================================

    def set_status_ok(self, span: Any) -> None:
        """Set span status to OK."""
        try:
            if span:
                span.set_status(Status(StatusCode.OK))
            logger.debug("Set span status to OK")
        except Exception as e:
            logger.error(f"Error setting status OK: {e}")

    def set_status_error(
        self, span: Any, description: Optional[str] = None
    ) -> None:
        """Set span status to ERROR."""
        try:
            if span:
                span.set_status(
                    Status(StatusCode.ERROR, description=description)
                )
            logger.debug(f"Set span status to ERROR: {description}")
        except Exception as e:
            logger.error(f"Error setting status ERROR: {e}")

    def set_status_unset(self, span: Any) -> None:
        """Set span status to UNSET."""
        try:
            if span:
                span.set_status(Status(StatusCode.UNSET))
            logger.debug("Set span status to UNSET")
        except Exception as e:
            logger.error(f"Error setting status UNSET: {e}")

    # ========================================================================
    # SPAN ACCESSORS
    # ========================================================================

    def get_current_span(self) -> Any:
        """Get current active span."""
        try:
            from opentelemetry import trace

            return trace.get_current_span()
        except Exception as e:
            logger.error(f"Error getting current span: {e}")
            return None

    def get_span_context(self, span: Optional[Any] = None) -> Dict[str, Any]:
        """Get span context (trace_id, span_id)."""
        try:
            target_span = span or self.get_current_span()

            if target_span:
                context = target_span.get_span_context()
                return {
                    "trace_id": format(context.trace_id, "032x"),
                    "span_id": format(context.span_id, "016x"),
                    "is_valid": context.is_valid,
                    "is_recording": context.is_recording,
                }

            return {
                "trace_id": "00000000000000000000000000000000",
                "span_id": "0000000000000000",
                "is_valid": False,
                "is_recording": False,
            }
        except Exception as e:
            logger.error(f"Error getting span context: {e}")
            return {
                "trace_id": "00000000000000000000000000000000",
                "span_id": "0000000000000000",
                "is_valid": False,
                "is_recording": False,
            }

    # ========================================================================
    # CONTEXT MANAGERS
    # ========================================================================

    def span_context(
        self, name: str, attributes: Optional[Dict[str, Any]] = None
    ):
        """Context manager for span creation."""
        try:
            span = self.create_span(name, attributes)
            return _SpanContextManager(span, self)
        except Exception as e:
            logger.error(f"Error creating span context: {e}")
            return _NullContextManager()

    # ========================================================================
    # SHUTDOWN
    # ========================================================================

    def shutdown(self) -> None:
        """Shutdown trace core."""
        try:
            if hasattr(self.tracer_provider, "shutdown"):
                self.tracer_provider.shutdown()
            logger.info("TraceCore shutdown complete")
        except Exception as e:
            logger.error(f"Error during TraceCore shutdown: {e}")


class _SpanContextManager:
    """Context manager for spans."""

    def __init__(self, span: Any, trace_core: TraceCore):
        self.span = span
        self.trace_core = trace_core

    def __enter__(self):
        return self.span

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type:
            self.trace_core.record_exception(self.span, exc_val)
            self.trace_core.set_status_error(self.span, str(exc_val))
        else:
            self.trace_core.set_status_ok(self.span)

        if self.span:
            self.span.end()


class _NullContextManager:
    """Null context manager for error cases."""

    def __enter__(self):
        return None

    def __exit__(self, exc_type, exc_val, exc_tb):
        pass
