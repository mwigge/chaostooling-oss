"""
Chaos Toolkit control module for ChaoSOTEL.

Wires Chaos Toolkit lifecycle hooks directly to the chaosotel
metrics/logs/traces cores.
"""

import logging
from typing import Any, Optional

from .calculator import calculate_complexity_score, calculate_risk_level
from .otel import (
    ensure_initialized,
    flush,
    get_log_core,
    get_metric_tags,
    get_metrics_core,
    get_tracer,
    initialize,
)

logger = logging.getLogger("chaosotel.control")

# Global storage for experiment root span and context token
_experiment_root_span = None
_experiment_context_token = None
_experiment_start_time = None
_activity_infra_snapshots: dict[str, dict[str, Any]] = {}

try:
    import psutil  # type: ignore
except ImportError:  # pragma: no cover - optional dependency
    psutil = None


def _snapshot_host_resources() -> dict[str, float]:
    """
    Take a lightweight snapshot of host-level CPU and memory usage.

    Returns a dict with at least cpu_percent and mem_percent when psutil is available.
    """
    if psutil is None:
        return {}

    try:
        cpu_percent = psutil.cpu_percent(interval=None)
        import psutil as _ps  # local alias to satisfy type checkers

        mem = _ps.virtual_memory()
        return {
            "cpu_percent": float(cpu_percent),
            "mem_percent": float(mem.percent),
        }
    except Exception as exc:  # pragma: no cover - safety
        logger.warning(f"Failed to snapshot host resources: {exc}")
        return {}


def _infer_target_type(activity: dict[str, Any]) -> str:
    """
    Best-effort inference of target type (db, network, compute, app, etc.) from activity metadata.
    """
    provider = activity.get("provider") or {}
    module_path = provider.get("module", "") or ""

    if module_path.startswith("chaosdb."):
        return "database"
    if module_path.startswith("chaosnetwork."):
        return "network"
    if module_path.startswith("chaoscompute."):
        return "compute"
    if module_path.startswith("chaosapp."):
        return "application"

    return "unknown"


def _init_once(config: Optional[dict[str, Any]]) -> None:
    """Initialize chaosotel if not already initialized."""
    target_type = (config or {}).get("target_type", "unknown")
    service_version = (config or {}).get("service_version", "1.0.0")

    try:
        initialize(target_type=target_type, service_version=service_version)
    except Exception as exc:  # pragma: no cover - defensive guard
        logger.error("Failed to initialize chaosotel control: %s", exc)
        raise


def _start_and_end_span(
    name: str,
    attributes: Optional[dict[str, Any]] = None,
    success: bool = True,
    error: Optional[str] = None,
) -> None:
    """Create a span, optionally mark status, and end it."""
    tracer = get_tracer()
    from opentelemetry.trace import StatusCode

    with tracer.start_as_current_span(name) as span:  # type: ignore[attr-defined]
        if attributes:
            for key, value in attributes.items():
                if value is not None:
                    span.set_attribute(key, str(value))

        if success:
            span.set_status(StatusCode.OK)
        else:
            span.set_status(StatusCode.ERROR, description=error or "Unknown error")


def _emit_risk_and_complexity_metrics(
    experiment: dict[str, Any],
    tags: dict[str, str],
) -> None:
    """Compute and emit risk/complexity gauges for the experiment."""
    metrics = get_metrics_core()

    # Risk is best-effort; falls back to defaults if keys are missing
    risk = calculate_risk_level(experiment or {})
    metrics.record_custom_metric(
        "chaos.experiment.risk.score",
        risk.get("score", 0),
        metric_type="gauge",
        tags=tags,
        description="Calculated risk score (0-100)",
    )
    metrics.record_custom_metric(
        "chaos.experiment.risk.level",
        risk.get("level", 0),
        metric_type="gauge",
        tags=tags,
        description="Calculated risk level (1-4)",
    )

    complexity_input = {
        "num_steps": len(experiment.get("method", []) or []),
        "num_probes": len(
            (experiment.get("steady-state-hypothesis") or {}).get("probes", [])
        ),
        "num_rollbacks": len(experiment.get("rollbacks", []) or []),
        "duration_seconds": experiment.get("duration_seconds", 0),
        "target_types": experiment.get("tags", []),
    }
    complexity = calculate_complexity_score(complexity_input)
    metrics.record_custom_metric(
        "chaos.experiment.complexity.score",
        complexity.get("score", 0),
        metric_type="gauge",
        tags=tags,
        description="Calculated complexity score (0-100)",
    )


# ============================================================================
# Chaos Toolkit control hooks
# ============================================================================


def configure_control(
    control: Any = None,
    experiment: Optional[dict[str, Any]] = None,
    configuration: Optional[dict[str, Any]] = None,
    secrets: Optional[dict[str, Any]] = None,
    settings: Optional[dict[str, Any]] = None,
    **kwargs: Any,
) -> None:
    """
    Chaos Toolkit entry point. Called once before other hooks.
    """
    _init_once(configuration or {})

    tags = get_metric_tags(
        experiment_title=(experiment or {}).get("title"),
        experiment_version=(experiment or {}).get("version"),
    )

    # Record initialization and risk/complexity upfront
    metrics = get_metrics_core()
    metrics.record_custom_metric(
        "chaos.experiment.initialized",
        1,
        metric_type="counter",
        tags=tags,
        description="Experiment initialization count",
    )

    _emit_risk_and_complexity_metrics(experiment or {}, tags)

    log_core = get_log_core()
    log_core.log_event(
        "experiment_initialized",
        event_data={"title": (experiment or {}).get("title")},
        severity="info",
    )


def before_experiment_control(
    context: Any, state: Any, experiment: dict[str, Any], **kwargs: Any
) -> None:
    """Create root experiment span that stays active for the entire experiment."""
    global _experiment_root_span, _experiment_context_token, _experiment_start_time
    import time

    ensure_initialized()
    tags = get_metric_tags(
        experiment_title=experiment.get("title"),
        experiment_version=experiment.get("version"),
    )

    # Record experiment start time for duration calculation
    _experiment_start_time = time.time()

    # Create root experiment span that will be the parent of all activity spans
    tracer = get_tracer()
    experiment_title = experiment.get("title", "unknown")

    # Start root span and make it current (so all child spans link to it)
    from opentelemetry import trace

    # Create the root span and make it current using use_span context manager
    # This ensures the span stays in context across function calls
    from opentelemetry.trace import SpanKind

    root_span = tracer.start_span(  # type: ignore[attr-defined]
        f"chaos.experiment.{experiment_title}",
        kind=SpanKind.SERVER,  # SERVER kind for root span
    )

    # Set experiment attributes
    root_span.set_attribute("experiment.title", experiment_title)
    root_span.set_attribute("experiment.version", experiment.get("version", "unknown"))
    root_span.set_attribute("chaos.experiment.type", "chaos_engineering")

    # Extract experiment metadata for metrics
    method_steps = experiment.get("method", []) or []
    steady_state_probes = (experiment.get("steady-state-hypothesis") or {}).get(
        "probes", []
    ) or []
    rollbacks = experiment.get("rollbacks", []) or []

    root_span.set_attribute("experiment.num_steps", len(method_steps))
    root_span.set_attribute("experiment.num_probes", len(steady_state_probes))
    root_span.set_attribute("experiment.num_rollbacks", len(rollbacks))

    # Count scenarios (method steps that are scenarios)
    scenarios = [
        step for step in method_steps if step.get("name", "").startswith("SCENARIO-")
    ]
    num_scenarios = len(scenarios)

    # Count total activities (all method steps including scenarios and their actions)
    total_activities = len(method_steps)

    # Record experiment metadata metrics for dashboard panels
    metrics = get_metrics_core()
    try:
        # Record scenarios count
        metrics.record_custom_metric(
            "chaos_experiment_scenarios_total",
            num_scenarios,
            metric_type="gauge",
            tags=tags,
            description="Total number of scenarios in experiment",
        )
        # Record total activities count
        metrics.record_custom_metric(
            "chaos_experiment_activities_total",
            total_activities,
            metric_type="gauge",
            tags=tags,
            description="Total number of activities in experiment",
        )
        # Record validation probes count
        metrics.record_custom_metric(
            "chaos_experiment_probes_total",
            len(steady_state_probes),
            metric_type="gauge",
            tags=tags,
            description="Total number of validation probes in experiment",
        )
        logger.debug(
            f"Recorded experiment metrics: {num_scenarios} scenarios, {total_activities} activities, {len(steady_state_probes)} probes"
        )
    except Exception as e:
        logger.warning(
            f"Failed to record experiment metadata metrics: {e}", exc_info=True
        )

    # Use use_span to make this span current and keep it in context
    # Store the context token to keep it active
    _experiment_context_token = trace.context_api.attach(
        trace.set_span_in_context(root_span)
    )
    _experiment_root_span = root_span

    # Record risk and complexity metrics at start
    _emit_risk_and_complexity_metrics(experiment, tags)

    get_log_core().log_event(
        "experiment_start",
        {
            "title": experiment_title,
            "num_steps": len(method_steps),
            "num_probes": len(steady_state_probes),
            "num_rollbacks": len(rollbacks),
        },
    )
    get_metrics_core().record_custom_metric(
        "chaos.experiment.start",
        1,
        metric_type="counter",
        tags=tags,
        description="Experiment start events",
    )

    logger.info(
        f"Started root experiment span: {experiment_title} (trace_id: {format(root_span.get_span_context().trace_id, '032x')})"
    )


def after_experiment_control(
    context: Any, state: Any, experiment: dict[str, Any], **kwargs: Any
) -> None:
    """End root experiment span, record experiment metrics, and flush telemetry."""
    global _experiment_root_span, _experiment_context_token, _experiment_start_time
    import time

    from .calculator import calculate_and_export_metrics

    ensure_initialized()
    tags = get_metric_tags(
        experiment_title=experiment.get("title"),
        experiment_version=experiment.get("version"),
    )

    # End the root experiment span
    from opentelemetry import trace
    from opentelemetry.trace import StatusCode

    experiment_title = experiment.get("title", "unknown")

    # Calculate experiment duration
    duration_seconds = 0.0
    if _experiment_start_time:
        duration_seconds = time.time() - _experiment_start_time

    # Determine experiment success from state
    # Chaos Toolkit state typically has 'status' field: 'completed', 'failed', 'interrupted'
    experiment_status = (
        getattr(state, "status", None) if hasattr(state, "status") else None
    )
    if experiment_status is None and hasattr(state, "__dict__"):
        experiment_status = state.__dict__.get("status", None)

    # Default to success if we can't determine
    experiment_success = experiment_status != "failed" if experiment_status else True

    # Extract experiment metadata
    method_steps = experiment.get("method", []) or []
    steady_state_probes = (experiment.get("steady-state-hypothesis") or {}).get(
        "probes", []
    ) or []
    rollbacks = experiment.get("rollbacks", []) or []
    target_types = experiment.get("tags", []) or []

    # Detach context and end the root span
    if _experiment_root_span:
        root_span = _experiment_root_span
        root_span.set_attribute("experiment.status", experiment_status or "completed")
        root_span.set_attribute("experiment.success", experiment_success)
        root_span.set_attribute("experiment.duration_seconds", duration_seconds)
        root_span.set_status(StatusCode.OK if experiment_success else StatusCode.ERROR)
        root_span.end()
        logger.info(
            f"Ended root experiment span: {experiment_title} (success={experiment_success}, duration={duration_seconds:.2f}s)"
        )

        # Detach context after ending span
        if _experiment_context_token:
            try:
                trace.context_api.detach(_experiment_context_token)
            except Exception as e:
                logger.warning(f"Failed to detach context: {e}")

        _experiment_root_span = None
        _experiment_context_token = None

    # Record comprehensive experiment metrics
    metrics = get_metrics_core()

    # Record experiment completion
    get_log_core().log_event(
        "experiment_end",
        {
            "title": experiment_title,
            "status": experiment_status or "completed",
            "success": experiment_success,
            "duration_seconds": duration_seconds,
        },
    )

    metrics.record_custom_metric(
        "chaos.experiment.end",
        1,
        metric_type="counter",
        tags=tags,
        description="Experiment completion events",
    )

    # Record experiment success/failure
    # Record experiment success/failed metrics (using underscores for Prometheus compatibility)
    metrics.record_custom_metric(
        "chaos_experiment_success_ratio",
        1.0 if experiment_success else 0.0,
        metric_type="gauge",
        tags={**tags, "status": experiment_status or "completed"},
        description="Experiment success ratio (1.0 = success, 0.0 = failed)",
    )

    metrics.record_custom_metric(
        "chaos_experiment_failed_ratio",
        1.0 if not experiment_success else 0.0,
        metric_type="gauge",
        tags={**tags, "status": experiment_status or "completed"},
        description="Experiment failure ratio (1.0 = failed, 0.0 = success)",
    )

    # Record experiment duration
    metrics.record_custom_metric(
        "chaos.experiment.duration_seconds",
        duration_seconds,
        metric_type="histogram",
        unit="s",
        tags=tags,
        description="Experiment duration in seconds",
    )

    # Calculate and export risk/complexity metrics
    try:
        # Extract severity and blast_radius from experiment if available
        severity = experiment.get("severity", "medium")
        blast_radius = experiment.get("blast_radius", 0.5)
        is_production = experiment.get("is_production", False)
        has_rollback = len(rollbacks) > 0

        calculate_and_export_metrics(
            experiment_name=experiment_title,
            duration_seconds=duration_seconds,
            success=experiment_success,
            target_type=target_types[0] if target_types else None,
            severity=severity,
            blast_radius=blast_radius,
            is_production=is_production,
            has_rollback=has_rollback,
            num_steps=len(method_steps),
            num_probes=len(steady_state_probes),
            num_rollbacks=len(rollbacks),
            tags=tags,
        )
        logger.info(
            f"Exported experiment metrics: {experiment_title} (risk/complexity calculated)"
        )
    except Exception as e:
        logger.warning(f"Failed to calculate experiment metrics: {e}", exc_info=True)

    flush()
    _experiment_start_time = None


def before_hypothesis_control(
    context: Any, state: Any, experiment: dict[str, Any], **kwargs: Any
) -> None:
    ensure_initialized()
    _start_and_end_span(
        "chaos.hypothesis.start", {"experiment.title": experiment.get("title")}
    )
    get_log_core().log_event("hypothesis_start", {"title": experiment.get("title")})


def after_hypothesis_control(
    context: Any, state: Any, experiment: dict[str, Any], **kwargs: Any
) -> None:
    ensure_initialized()
    _start_and_end_span(
        "chaos.hypothesis.end", {"experiment.title": experiment.get("title")}
    )
    get_log_core().log_event("hypothesis_end", {"title": experiment.get("title")})


def before_method_control(
    context: Any, state: Any, experiment: dict[str, Any], **kwargs: Any
) -> None:
    ensure_initialized()
    _start_and_end_span(
        "chaos.method.start", {"experiment.title": experiment.get("title")}
    )


def after_method_control(
    context: Any, state: Any, experiment: dict[str, Any], **kwargs: Any
) -> None:
    ensure_initialized()
    _start_and_end_span(
        "chaos.method.end", {"experiment.title": experiment.get("title")}
    )


def before_activity_control(
    context: dict[str, Any],
    state: Any,
    experiment: dict[str, Any],
    **kwargs: Any,
) -> None:
    """Create activity span as child of root experiment span."""
    ensure_initialized()
    metrics = get_metrics_core()

    activity = context or {}

    activity_name = activity.get("name")
    if not activity_name:
        provider = activity.get("provider", {})
        func = provider.get("func")
        if func:
            activity_name = func
        else:
            activity_name = "unknown"

    activity_type = activity.get("type", "unknown")
    target_type = _infer_target_type(activity)

    # Capture infra snapshot at start of activity
    activity_key = f"{activity_name}:{id(context) if context is not None else 'none'}"
    _activity_infra_snapshots[activity_key] = {
        "start": _snapshot_host_resources(),
        "meta": {
            "experiment_title": experiment.get("title"),
            "experiment_version": experiment.get("version"),
            "phase_name": activity_name,
            "phase_type": activity_type,
            "target_type": target_type,
        },
    }

    # Create activity span - will automatically be child of current (root experiment) span
    from opentelemetry import trace
    from opentelemetry.trace import SpanKind

    tracer = get_tracer()
    # Use start_span and manually set as current (similar to root span pattern)
    activity_span = tracer.start_span(  # type: ignore[attr-defined]
        f"chaos.activity.{activity_name}",
        kind=SpanKind.SERVER,  # SERVER kind
    )

    # Set activity attributes
    activity_span.set_attribute("activity.name", activity_name)
    activity_span.set_attribute("activity.type", activity_type)
    activity_span.set_attribute("experiment.title", experiment.get("title", "unknown"))

    # Make the activity span current and store the context token
    activity_context_token = trace.context_api.attach(
        trace.set_span_in_context(activity_span)
    )

    # Store the span and token in context for cleanup in after_activity_control
    if "_activity_spans" not in context:
        context["_activity_spans"] = []
    context["_activity_spans"].append(
        {"span": activity_span, "token": activity_context_token}
    )

    # Record current phase metric so dashboards can show the active experiment phase
    phase_tags = get_metric_tags(
        experiment_title=experiment.get("title"),
        experiment_version=experiment.get("version"),
        phase_name=activity_name,
        phase_type=activity_type,
    )
    try:
        metrics.record_custom_metric(
            "chaos.experiment.phase",
            1.0,
            metric_type="gauge",
            tags=phase_tags,
            description="Current active experiment phase (1.0=active, 0.0=inactive)",
        )
    except Exception as exc:
        logger.warning(
            f"Failed to record experiment phase metric for {activity_name}: {exc}"
        )

    get_log_core().log_event(
        "activity_start",
        {
            "name": activity_name,
            "type": activity_type,
        },
    )


def after_activity_control(
    context: dict[str, Any],
    state: Any,
    experiment: dict[str, Any],
    **kwargs: Any,
) -> None:
    """End activity span and return to parent (experiment) span."""
    ensure_initialized()
    metrics = get_metrics_core()
    from opentelemetry import trace
    from opentelemetry.trace import StatusCode

    activity = (context or {}).get("activity", {})
    activity_name = activity.get("name", "unknown")
    activity_type = activity.get("type", "unknown")

    # Compute infra "cost" for this activity from host-level snapshots
    activity_key = f"{activity_name}:{id(context) if context is not None else 'none'}"
    snapshot = _activity_infra_snapshots.pop(activity_key, None)
    if snapshot and snapshot.get("start"):
        start = snapshot["start"]
        end = _snapshot_host_resources()
        meta = snapshot.get("meta", {})

        if end:
            try:
                cpu_values = [
                    v
                    for v in [start.get("cpu_percent"), end.get("cpu_percent")]
                    if v is not None
                ]
                mem_values = [
                    v
                    for v in [start.get("mem_percent"), end.get("mem_percent")]
                    if v is not None
                ]

                cpu_avg = sum(cpu_values) / len(cpu_values) if cpu_values else None
                mem_avg = sum(mem_values) / len(mem_values) if mem_values else None

                cost_tags = get_metric_tags(
                    experiment_title=meta.get("experiment_title"),
                    experiment_version=meta.get("experiment_version"),
                    phase_name=meta.get("phase_name"),
                    phase_type=meta.get("phase_type"),
                    target_type=meta.get("target_type"),
                )

                if cpu_avg is not None:
                    metrics.record_custom_metric(
                        "chaos.action.infra.cpu.percent",
                        float(cpu_avg),
                        metric_type="gauge",
                        unit="percent",
                        tags=cost_tags,
                        description="Approximate CPU usage during activity (host-level)",
                    )

                if mem_avg is not None:
                    metrics.record_custom_metric(
                        "chaos.action.infra.memory.percent",
                        float(mem_avg),
                        metric_type="gauge",
                        unit="percent",
                        tags=cost_tags,
                        description="Approximate memory usage during activity (host-level)",
                    )
            except Exception as exc:  # pragma: no cover - defensive
                logger.warning(
                    f"Failed to record infra cost metrics for activity {activity_name}: {exc}"
                )

    # Mark phase as inactive (0.0) for this activity
    phase_tags = get_metric_tags(
        experiment_title=experiment.get("title"),
        experiment_version=experiment.get("version"),
        phase_name=activity_name,
        phase_type=activity_type,
    )
    try:
        metrics.record_custom_metric(
            "chaos.experiment.phase",
            0.0,
            metric_type="gauge",
            tags=phase_tags,
            description="Current active experiment phase (1.0=active, 0.0=inactive)",
        )
    except Exception as exc:
        logger.warning(
            f"Failed to record experiment phase completion metric for {activity_name}: {exc}"
        )

    # Get and clean up the stored activity span
    activity_spans = context.get("_activity_spans", [])

    # Record operation metrics (success/error counters) for dashboard visibility
    try:
        target_type = _infer_target_type(activity)

        if activity_spans:
            last_span_data = activity_spans[-1]
            span = last_span_data.get("span")
            if span:
                span_status = span.status
                is_success = (
                    span_status.status_code == StatusCode.OK if span_status else True
                )

                if activity_type == "probe":
                    # Record probe execution
                    metrics.record_probe_count(
                        name=activity_name,
                        status="success" if is_success else "error",
                        target_type=target_type,
                    )
                else:
                    # Record action/operation count
                    metrics.record_action_count(
                        name=activity_name,
                        status="success" if is_success else "error",
                        target_type=target_type,
                    )
    except Exception as exc:
        logger.warning(
            f"Failed to record operation metrics for activity {activity_name}: {exc}"
        )
    if activity_spans:
        activity_data = (
            activity_spans.pop()
        )  # Remove the last one (should be this activity)
        activity_span = activity_data.get("span")
        activity_token = activity_data.get("token")

        if activity_span:
            # Set status and end the span
            activity_span.set_status(StatusCode.OK)
            activity_span.end()

        # Detach the context token to return to parent span
        if activity_token is not None:
            trace.context_api.detach(activity_token)

    get_log_core().log_event(
        "activity_end",
        {
            "name": activity_name,
            "type": activity.get("type"),
        },
    )


def cleanup_control(
    control: Any = None,
    experiment: Optional[dict[str, Any]] = None,
    **kwargs: Any,
) -> None:
    """Flush telemetry after the run."""
    try:
        flush()
    except Exception as exc:  # pragma: no cover - safety
        logger.warning("Cleanup flush failed: %s", exc)
