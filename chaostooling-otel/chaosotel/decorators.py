"""
ChaoSOTEL Decorators - Zero-boilerplate automatic instrumentation.

Seven decorators for automatic metrics, logs, traces, and compliance tracking:
1. @instrument_action - Action execution tracking
2. @instrument_probe - Probe execution tracking
3. @instrument_rollback - Recovery/rollback tracking
4. @record_metric - Custom metric recording
5. @track_compliance - Compliance violation detection
6. @track_impact - Impact scope measurement
7. instrumented_section - Context manager for code blocks

All decorators automatically use MetricsCore, LogCore, TraceCore, ComplianceCore.
"""

import functools
import logging
import time
from typing import Any, Callable, Dict, List, Optional

from chaosotel.otel import (
    ensure_initialized,
    get_compliance_core,
    get_log_core,
    get_metrics_core,
    get_trace_core,
)

logger = logging.getLogger("chaosotel.decorators")


# ============================================================================
# 1. @instrument_action
# ============================================================================


def instrument_action(
    name: str,
    target_type: Optional[str] = None,
    severity: str = "medium",
    record_result: bool = False,
    tags: Optional[Dict[str, str]] = None,
) -> Callable:
    """
    Decorator to automatically instrument chaos actions.

    Records:
    - Action start/end (logs)
    - Duration (metrics histogram)
    - Success/failure (metrics counters)
    - Exceptions (traces)
    - Compliance impact

    Args:
        name: Action name (e.g., "kill_connections")
        target_type: Target type (database, network, compute)
        severity: Severity level (low, medium, high, critical)
        record_result: Whether to record function return value
        tags: Additional tags

    Example:
        @instrument_action(
            name="kill_active_connections",
            target_type="database",
            severity="high"
        )
        def kill_connections():
            return 5
    """

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            ensure_initialized()

            logs = get_log_core()
            metrics = get_metrics_core()
            traces = get_trace_core()

            start_time = time.time()

            # Log action start
            logs.log_action_start(
                action_name=name,
                action_type=target_type,
                severity=severity,
                tags=tags,
            )

            # Create trace span
            span_attrs = {
                "action.name": name,
                "action.type": target_type or "unknown",
                "action.severity": severity,
            }
            if tags:
                span_attrs.update({f"tag.{k}": str(v) for k, v in tags.items()})

            try:
                with traces.create_span(
                    f"action-{name}", attributes=span_attrs
                ):
                    # Execute action
                    result = func(*args, **kwargs)

                    # Record success
                    duration_ms = (time.time() - start_time) * 1000

                    metrics.record_action_duration(
                        name=name,
                        duration_ms=duration_ms,
                        status="success",
                        severity=severity,
                        target_type=target_type,
                        tags=tags,
                    )

                    metrics.record_action_count(
                        name=name,
                        status="success",
                        severity=severity,
                        target_type=target_type,
                    )

                    # Log action end
                    logs.log_action_end(
                        action_name=name,
                        success=True,
                        duration_ms=duration_ms,
                        result={"value": result} if record_result else None,
                    )

                    logger.debug(
                        f"Action completed: {name} ({duration_ms:.1f}ms)"
                    )

                    return result

            except Exception as e:
                # Record failure
                duration_ms = (time.time() - start_time) * 1000

                metrics.record_action_duration(
                    name=name,
                    duration_ms=duration_ms,
                    status="error",
                    severity=severity,
                    target_type=target_type,
                    tags=tags,
                )

                metrics.record_action_count(
                    name=name,
                    status="error",
                    severity=severity,
                    target_type=target_type,
                )

                # Log action error
                logs.log_action_end(
                    action_name=name,
                    success=False,
                    duration_ms=duration_ms,
                    error=str(e),
                )

                logger.error(f"Action failed: {name} - {e}", exc_info=True)

                raise

        return wrapper

    return decorator


# ============================================================================
# 2. @instrument_probe
# ============================================================================


def instrument_probe(
    name: str,
    target_type: Optional[str] = None,
    record_args: bool = False,
    tags: Optional[Dict[str, str]] = None,
) -> Callable:
    """
    Decorator to automatically instrument probes.

    Records:
    - Probe start/end (logs)
    - Duration (metrics histogram)
    - Result status and value
    - Exceptions (traces)

    Args:
        name: Probe name
        target_type: Target type
        record_args: Whether to record function arguments
        tags: Additional tags

    Example:
        @instrument_probe(
            name="check_postgres_connectivity",
            target_type="database"
        )
        def check_postgres_connectivity():
            return {"connected": True, "status": "healthy"}
    """

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            ensure_initialized()

            logs = get_log_core()
            metrics = get_metrics_core()
            traces = get_trace_core()

            start_time = time.time()

            # Log probe start
            logs.log_probe_start(
                probe_name=name, target_type=target_type, tags=tags
            )

            # Create trace span
            span_attrs = {
                "probe.name": name,
                "probe.type": target_type or "unknown",
            }

            try:
                with traces.create_span(f"probe-{name}", attributes=span_attrs):
                    result = func(*args, **kwargs)

                    duration_ms = (time.time() - start_time) * 1000

                    # Determine status from result
                    status = "success"
                    if (
                        isinstance(result, dict)
                        and result.get("status") == "error"
                    ):
                        status = "error"

                    # Record metrics
                    metrics.record_probe_duration(
                        name=name,
                        duration_ms=duration_ms,
                        status=status,
                        target_type=target_type,
                        tags=tags,
                    )

                    metrics.record_probe_count(
                        name=name, status=status, target_type=target_type
                    )

                    # Log probe end
                    logs.log_probe_end(
                        probe_name=name,
                        status=status,
                        duration_ms=duration_ms,
                        result=result,
                    )

                    logger.debug(
                        f"Probe completed: {name} ({duration_ms:.1f}ms)"
                    )

                    return result

            except Exception as e:
                duration_ms = (time.time() - start_time) * 1000

                metrics.record_probe_duration(
                    name=name,
                    duration_ms=duration_ms,
                    status="error",
                    target_type=target_type,
                )

                metrics.record_probe_count(
                    name=name, status="error", target_type=target_type
                )

                logs.log_probe_end(
                    probe_name=name,
                    status="error",
                    duration_ms=duration_ms,
                    error=str(e),
                )

                logger.error(f"Probe failed: {name} - {e}", exc_info=True)
                raise

        return wrapper

    return decorator


# ============================================================================
# 3. @instrument_rollback
# ============================================================================


def instrument_rollback(
    name: str,
    target_type: Optional[str] = None,
    tags: Optional[Dict[str, str]] = None,
) -> Callable:
    """
    Decorator to instrument recovery/rollback actions.

    Critical for MTTR (Mean Time To Recovery) tracking.

    Records:
    - Recovery start/end (logs)
    - Recovery duration (metrics histogram - MTTR)
    - Success/failure
    - Compliance impact

    Args:
        name: Rollback action name
        target_type: Target type
        tags: Additional tags

    Example:
        @instrument_rollback(
            name="restart_connections",
            target_type="database"
        )
        def restart_connections():
            pass
    """

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            ensure_initialized()

            logs = get_log_core()
            metrics = get_metrics_core()
            traces = get_trace_core()

            start_time = time.time()

            logs.log_event(
                "recovery_start",
                event_data={"action": name, "target_type": target_type},
            )

            try:
                with traces.create_span(f"rollback-{name}"):
                    result = func(*args, **kwargs)

                    duration_ms = (time.time() - start_time) * 1000

                    # Record MTTR (critical for compliance)
                    metrics.record_recovery_time(
                        name=name,
                        duration_ms=duration_ms,
                        success=True,
                        target_type=target_type,
                    )

                    logs.log_event(
                        "recovery_complete",
                        event_data={
                            "action": name,
                            "success": True,
                            "duration_ms": duration_ms,
                        },
                    )

                    logger.info(
                        f"Recovery completed: {name} ({duration_ms:.1f}ms)"
                    )

                    return result

            except Exception as e:
                duration_ms = (time.time() - start_time) * 1000

                metrics.record_recovery_time(
                    name=name,
                    duration_ms=duration_ms,
                    success=False,
                    target_type=target_type,
                )

                logs.log_event(
                    "recovery_failed",
                    event_data={
                        "action": name,
                        "success": False,
                        "duration_ms": duration_ms,
                        "error": str(e),
                    },
                    severity="error",
                )

                logger.error(f"Recovery failed: {name} - {e}", exc_info=True)
                raise

        return wrapper

    return decorator


# ============================================================================
# 4. @record_metric
# ============================================================================


def record_metric(
    name: str,
    unit: str = "1",
    metric_type: str = "gauge",
    description: Optional[str] = None,
) -> Callable:
    """
    Decorator to record custom domain-specific metrics.

    Args:
        name: Metric name (e.g., "db.query.latency")
        unit: Unit (ms, GB, %, etc.)
        metric_type: "gauge", "counter", or "histogram"
        description: Metric description

    Example:
        @record_metric(
            "db.query.latency",
            unit="ms",
            metric_type="histogram"
        )
        @instrument_action(name="query_test")
        def test_query():
            return {"latency_ms": 125.5}
    """

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            ensure_initialized()

            metrics = get_metrics_core()

            result = func(*args, **kwargs)

            # Try to extract metric value from result
            if isinstance(result, dict):
                # Look for common value keys
                metric_value = None
                for key in [name.split(".")[-1], "value", "result"]:
                    if key in result:
                        try:
                            metric_value = float(result[key])
                            break
                        except (ValueError, TypeError):
                            pass

                if metric_value is not None:
                    metrics.record_custom_metric(
                        name=name,
                        value=metric_value,
                        metric_type=metric_type,
                        unit=unit,
                        description=description,
                    )

            return result

        return wrapper

    return decorator


# ============================================================================
# 5. @track_compliance
# ============================================================================


def track_compliance(regulations: List[str]) -> Callable:
    """
    Decorator to track compliance violations.

    Args:
        regulations: List of regulations (SOX, GDPR, PCI-DSS, HIPAA)

    Example:
        @track_compliance(regulations=["SOX", "PCI-DSS"])
        @instrument_action(name="corrupt_data")
        def corrupt_table_data():
            pass
    """

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            ensure_initialized()

            compliance = get_compliance_core()
            logs = get_log_core()

            try:
                result = func(*args, **kwargs)

                # Track compliance for each regulation
                for regulation in regulations:
                    compliance.track_action_execution(
                        action_name=func.__name__,
                        regulation=regulation,
                        status="success",
                        duration_ms=0,
                    )

                    logs.log_compliance_check(
                        regulation=regulation,
                        check_name=func.__name__,
                        passed=True,
                    )

                return result

            except Exception as e:
                # Track compliance violations
                for regulation in regulations:
                    compliance.track_action_execution(
                        action_name=func.__name__,
                        regulation=regulation,
                        status="error",
                        duration_ms=0,
                    )

                    logs.log_compliance_check(
                        regulation=regulation,
                        check_name=func.__name__,
                        passed=False,
                        details={"error": str(e)},
                    )

                raise

        return wrapper

    return decorator


# ============================================================================
# 6. @track_impact
# ============================================================================


def track_impact(impact_type: str) -> Callable:
    """
    Decorator to measure resource impact.

    Args:
        impact_type: Type of impact (connections, pods, instances, etc.)

    Example:
        @track_impact(impact_type="connections")
        @instrument_action(name="kill_connections")
        def kill_active_connections():
            return 5  # Returns impact count
    """

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            ensure_initialized()

            metrics = get_metrics_core()

            result = func(*args, **kwargs)

            # Try to extract impact count from result
            impact_count = 0

            if isinstance(result, int):
                impact_count = result
            elif isinstance(result, dict) and "count" in result:
                try:
                    impact_count = int(result["count"])
                except (ValueError, TypeError):
                    pass

            if impact_count > 0:
                metrics.record_impact_scope(
                    action_name=func.__name__,
                    impact_type=impact_type,
                    count=impact_count,
                )

            return result

        return wrapper

    return decorator


# ============================================================================
# 7. instrumented_section - Context manager
# ============================================================================


class instrumented_section:
    """
    Context manager for instrumenting arbitrary code sections.

    Example:
        from chaosotel import instrumented_section

        with instrumented_section("backup_validation"):
            validate_backup()
            check_integrity()
    """

    def __init__(self, name: str, tags: Optional[Dict[str, str]] = None):
        """
        Initialize instrumented section.

        Args:
            name: Section name
            tags: Additional tags
        """
        self.name = name
        self.tags = tags
        self.trace_core = None
        self.log_core = None
        self.span = None

    def __enter__(self):
        """Enter instrumented section."""
        try:
            ensure_initialized()
            self.trace_core = get_trace_core()
            self.log_core = get_log_core()

            self.log_core.log_event(
                f"{self.name}_start", event_data=self.tags or {}
            )

            span_attrs = {"section.name": self.name}
            if self.tags:
                span_attrs.update(
                    {f"tag.{k}": str(v) for k, v in self.tags.items()}
                )

            self.span = self.trace_core.start_span(f"section-{self.name}")
            if self.span:
                for key, value in span_attrs.items():
                    self.span.set_attribute(key, value)

            logger.debug(f"Instrumented section started: {self.name}")

        except Exception as e:
            logger.error(
                f"Error entering instrumented section: {e}", exc_info=True
            )

        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Exit instrumented section."""
        try:
            if self.log_core:
                self.log_core.log_event(
                    f"{self.name}_end", event_data={"success": exc_type is None}
                )

            if self.span:
                if exc_type:
                    self.span.set_attribute("error", str(exc_val))
                self.trace_core.end_span(self.span)

            logger.debug(f"Instrumented section completed: {self.name}")

        except Exception as e:
            logger.error(
                f"Error exiting instrumented section: {e}", exc_info=True
            )

        return False  # Don't suppress exceptions


# ============================================================================
# Helper for initialization
# ============================================================================


def init_cores() -> tuple:
    """
    Get all core instances.

    Returns:
        Tuple of (MetricsCore, LogCore, TraceCore, ComplianceCore)
    """
    ensure_initialized()
    return (
        get_metrics_core(),
        get_log_core(),
        get_trace_core(),
        get_compliance_core(),
    )
