"""
LogCore - Structured logging interface for Loki.

Records:
- Action start/end events
- Probe execution results
- Errors and exceptions
- Compliance checks
- Custom events with audit trail
"""

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from opentelemetry.sdk._logs import LoggerProvider

logger = logging.getLogger("chaosotel.log_core")


def _handle_log_error(operation: str, error: Exception) -> None:
    """
    Standardized error handling for log operations.

    Args:
        operation: Description of the operation that failed
        error: The exception that occurred
    """
    if isinstance(error, (ValueError, AttributeError, TypeError)):
        logger.error(f"Invalid parameter for {operation}: {error}")
        raise
    else:
        logger.error(f"Unexpected error in {operation}: {error}", exc_info=True)
        raise RuntimeError(f"Failed to {operation}: {error}") from error


class LogCore:
    """
    Core logging interface for structured logs to Loki.

    Provides unified API for:
    - Action lifecycle logging (start/end)
    - Probe execution logging
    - Error logging with context
    - Compliance check logging
    - Custom event logging
    - Audit trail tracking
    """

    def __init__(self, logger_provider: LoggerProvider):
        """
        Initialize LogCore.

        Args:
            logger_provider: OpenTelemetry LoggerProvider
        """
        self.logger_provider = logger_provider
        self.logger = logger_provider.get_logger(__name__)

        # Audit trail for all logged events
        self._audit_trail: list = []

        logger.info("LogCore initialized")

    # ========================================================================
    # ACTION LOGGING
    # ========================================================================

    def log_action_start(
        self,
        action_name: str,
        action_type: Optional[str] = None,
        severity: Optional[str] = None,
        tags: Optional[Dict[str, str]] = None,
    ) -> None:
        """Log action start."""
        try:
            log_data = {
                "event": "action_start",
                "action_name": action_name,
                "action_type": action_type,
                "severity": severity,
                "timestamp": self._get_iso_timestamp(),
            }

            if tags:
                log_data["tags"] = tags  # type: ignore[assignment]

            log_data.update(self._get_trace_context())

            self._audit_trail.append({"event": "action_start", "data": log_data})

            logger.info(f"Action started: {action_name}", extra=log_data)
        except Exception as e:
            _handle_log_error("log action start", e)

    def log_action_end(
        self,
        action_name: str,
        success: bool = True,
        duration_ms: float = 0.0,
        result: Optional[Dict[str, Any]] = None,
        error: Optional[str] = None,
    ) -> None:
        """Log action end."""
        try:
            log_data = {
                "event": "action_end",
                "action_name": action_name,
                "success": success,
                "duration_ms": duration_ms,
                "timestamp": self._get_iso_timestamp(),
            }

            if result:
                log_data["result"] = result

            if error:
                log_data["error"] = error

            log_data.update(self._get_trace_context())

            self._audit_trail.append({"event": "action_end", "data": log_data})

            logger.log(
                logging.INFO if success else logging.ERROR,
                f"Action ended: {action_name}",
                extra=log_data,
            )
        except Exception as e:
            _handle_log_error("log action end", e)

    # ========================================================================
    # PROBE LOGGING
    # ========================================================================

    def log_probe_start(
        self,
        probe_name: str,
        target_type: Optional[str] = None,
        tags: Optional[Dict[str, str]] = None,
    ) -> None:
        """Log probe start."""
        try:
            log_data = {
                "event": "probe_start",
                "probe_name": probe_name,
                "target_type": target_type,
                "timestamp": self._get_iso_timestamp(),
            }

            if tags:
                log_data["tags"] = tags  # type: ignore[assignment]

            log_data.update(self._get_trace_context())

            self._audit_trail.append({"event": "probe_start", "data": log_data})

            logger.info(f"Probe started: {probe_name}", extra=log_data)
        except Exception as e:
            _handle_log_error("log probe start", e)

    def log_probe_end(
        self,
        probe_name: str,
        status: str = "success",
        duration_ms: float = 0.0,
        result: Optional[Dict[str, Any]] = None,
        error: Optional[str] = None,
    ) -> None:
        """Log probe end."""
        try:
            log_data = {
                "event": "probe_end",
                "probe_name": probe_name,
                "status": status,
                "duration_ms": duration_ms,
                "timestamp": self._get_iso_timestamp(),
            }

            if result:
                log_data["result"] = result

            if error:
                log_data["error"] = error

            log_data.update(self._get_trace_context())

            self._audit_trail.append({"event": "probe_end", "data": log_data})

            level = logging.INFO if status == "success" else logging.ERROR
            logger.log(level, f"Probe ended: {probe_name}", extra=log_data)
        except Exception as e:
            _handle_log_error("log probe end", e)

    # ========================================================================
    # ERROR LOGGING
    # ========================================================================

    def log_error(
        self,
        component: str,
        error_message: str,
        error_type: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Log structured error."""
        try:
            log_data = {
                "event": "error",
                "component": component,
                "error_message": error_message,
                "error_type": error_type,
                "timestamp": self._get_iso_timestamp(),
            }

            if context:
                log_data["context"] = context  # type: ignore[assignment]

            log_data.update(self._get_trace_context())

            self._audit_trail.append({"event": "error", "data": log_data})

            logger.error(f"Error in {component}: {error_message}", extra=log_data)
        except Exception as e:
            _handle_log_error("log error", e)

    # ========================================================================
    # COMPLIANCE LOGGING
    # ========================================================================

    def log_compliance_check(
        self,
        regulation: str,
        check_name: str,
        passed: bool = True,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Log compliance check result."""
        try:
            log_data = {
                "event": "compliance_check",
                "regulation": regulation,
                "check_name": check_name,
                "passed": passed,
                "timestamp": self._get_iso_timestamp(),
            }

            if details:
                log_data["details"] = details

            log_data.update(self._get_trace_context())

            self._audit_trail.append({"event": "compliance_check", "data": log_data})

            level = logging.INFO if passed else logging.WARNING
            logger.log(
                level,
                f"Compliance check: {regulation}/{check_name}",
                extra=log_data,
            )
        except Exception as e:
            _handle_log_error("log compliance check", e)

    # ========================================================================
    # EVENT LOGGING
    # ========================================================================

    def log_event(
        self,
        event_name: str,
        event_data: Optional[Dict[str, Any]] = None,
        severity: str = "info",
    ) -> None:
        """Log custom event."""
        try:
            log_data = {
                "event": event_name,
                "data": event_data or {},
                "severity": severity.upper(),
                "timestamp": self._get_iso_timestamp(),
            }

            log_data.update(self._get_trace_context())

            self._audit_trail.append({"event": event_name, "data": log_data})

            # Map severity to log level
            level_map = {
                "debug": logging.DEBUG,
                "info": logging.INFO,
                "warning": logging.WARNING,
                "error": logging.ERROR,
                "critical": logging.CRITICAL,
            }

            level = level_map.get(severity.lower(), logging.INFO)
            logger.log(level, f"Event: {event_name}", extra=log_data)
        except Exception as e:
            _handle_log_error("log event", e)

    # ========================================================================
    # AUDIT TRAIL
    # ========================================================================

    def get_audit_trail(self) -> List[Dict[str, Any]]:
        """Get audit trail."""
        return self._audit_trail.copy()

    def clear_audit_trail(self) -> None:
        """Clear audit trail."""
        self._audit_trail.clear()
        logger.info("Audit trail cleared")

    # ========================================================================
    # INTERNAL HELPERS
    # ========================================================================

    def _get_iso_timestamp(self) -> str:
        """Get ISO 8601 timestamp."""
        return datetime.now(timezone.utc).isoformat()

    def _get_trace_context(self) -> Dict[str, Any]:
        """Get trace context (trace_id, span_id)."""
        try:
            from opentelemetry import trace

            span = trace.get_current_span()
            ctx = span.get_span_context()

            return {
                "trace_id": format(ctx.trace_id, "032x"),
                "span_id": format(ctx.span_id, "016x"),
            }
        except Exception:
            return {
                "trace_id": "00000000000000000000000000000000",
                "span_id": "0000000000000000",
            }

    def _log_structured(self, level: str, log_data: Dict[str, Any]) -> None:
        """Log structured data."""
        try:
            if level == "DEBUG":
                logger.debug(log_data)
            elif level == "INFO":
                logger.info(log_data)
            elif level == "WARNING":
                logger.warning(log_data)
            elif level == "ERROR":
                logger.error(log_data)
            elif level == "CRITICAL":
                logger.critical(log_data)
        except Exception as e:
            _handle_log_error("structured logging", e)

    def shutdown(self) -> None:
        """Shutdown log core."""
        try:
            if hasattr(self.logger_provider, "shutdown"):
                self.logger_provider.shutdown()
            logger.info("LogCore shutdown complete")
        except Exception as e:
            _handle_log_error("LogCore shutdown", e)
