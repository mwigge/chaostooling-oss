"""
ChaoSOTEL Calculator - Risk and complexity assessment.

Automatically calculates and exports:
- Experiment risk level (1-4)
- Experiment complexity score (0-100)
- Associated metrics to Prometheus
"""

import logging
from typing import Any, Dict, Optional

from chaosotel.otel import ensure_initialized, get_metrics_core

logger = logging.getLogger("chaosotel.calculator")


def calculate_risk_level(experiment: Dict[str, Any]) -> Dict[str, Any]:
    """
    Calculate experiment risk level.

    Risk Levels:
        1 = Low (simple single-system test)
        2 = Medium (multiple systems, basic chaos)
        3 = High (database failover, replication)
        4 = Critical (data loss, cascading failures)

    Risk Formula:
        Risk = (
            (Severity × 0.3) +
            (BlastRadius × 0.3) +
            (ProductionEnv × 0.2) +
            (NoRollback × 0.2)
        ) × 100

    Args:
        experiment: Experiment dict with structure:
            {
                "severity": "high",           # low, medium, high, critical
                "blast_radius": 0.4,          # 0.0-1.0 (% of infrastructure)
                "is_production": True,        # True/False
                "has_rollback": True,         # True/False
                "target_systems": 3,          # Number of systems
            }

    Returns:
        Dictionary with:
            - level (1-4)
            - level_name (Low, Medium, High, Critical)
            - score (0-100)
            - factors (breakdown of factors)

    Example:
        risk = calculate_risk_level({
            "severity": "high",
            "blast_radius": 0.4,
            "is_production": True,
            "has_rollback": True,
            "target_systems": 3
        })
        print(f"Risk: {risk['level_name']} ({risk['score']}/100)")
    """
    try:
        # Extract factors
        severity = experiment.get("severity", "medium").lower()
        blast_radius = float(experiment.get("blast_radius", 0.5))
        is_production = bool(experiment.get("is_production", False))
        has_rollback = bool(experiment.get("has_rollback", True))

        # Severity factor (0.0-1.0)
        severity_factor = {
            "low": 0.2,
            "medium": 0.5,
            "high": 0.9,
            "critical": 1.0,
        }.get(severity, 0.5)

        # Blast radius factor (already 0.0-1.0)
        blast_radius_factor = min(max(float(blast_radius), 0.0), 1.0)

        # Production env factor (0.0 or 1.0)
        production_factor = 1.0 if is_production else 0.3

        # No rollback factor (0.0 or 1.0)
        rollback_factor = 0.0 if has_rollback else 1.0

        # Calculate risk score
        risk_score = (
            (severity_factor * 0.3)
            + (blast_radius_factor * 0.3)
            + (production_factor * 0.2)
            + (rollback_factor * 0.2)
        ) * 100

        # Determine risk level
        if risk_score <= 25:
            risk_level = 1
            level_name = "Low"
        elif risk_score <= 50:
            risk_level = 2
            level_name = "Medium"
        elif risk_score <= 75:
            risk_level = 3
            level_name = "High"
        else:
            risk_level = 4
            level_name = "Critical"

        return {
            "level": risk_level,
            "level_name": level_name,
            "score": round(risk_score, 1),
            "factors": {
                "severity": round(severity_factor, 2),
                "blast_radius": round(blast_radius_factor, 2),
                "production_env": round(production_factor, 2),
                "rollback_available": round(1.0 - rollback_factor, 2),
            },
        }

    except Exception as e:
        logger.error(f"Error calculating risk level: {e}", exc_info=True)
        return {
            "level": 2,
            "level_name": "Medium",
            "score": 50.0,
            "factors": {},
            "error": str(e),
        }


def calculate_complexity_score(experiment: Dict[str, Any]) -> Dict[str, Any]:
    """
    Calculate experiment complexity score.

    Difficulty Levels:
        1-20   = Simple
        21-40  = Intermediate
        41-60  = Advanced
        61-80  = Expert
        81-100 = Master

    Complexity Formula:
        Score = (
            (NumSteps / MaxSteps × 0.25) +
            (NumProbes / MaxProbes × 0.25) +
            (TargetTypes / MaxTargets × 0.2) +
            (Duration / MaxDuration × 0.15) +
            (RollbackRatio × 0.15)
        ) × 100

    Args:
        experiment: Experiment dict with structure:
            {
                "num_steps": 15,              # Number of steps
                "num_probes": 8,              # Number of probes
                "num_rollbacks": 3,           # Number of rollbacks
                "duration_seconds": 3600,     # Total duration
                "target_types": ["db", "net"],# Types of targets
            }

    Returns:
        Dictionary with:
            - score (0-100)
            - difficulty (Simple to Master)
            - factors (breakdown)

    Example:
        complexity = calculate_complexity_score({
            "num_steps": 15,
            "num_probes": 8,
            "num_rollbacks": 3,
            "duration_seconds": 3600,
            "target_types": ["database", "network"]
        })
        print(f"Difficulty: {complexity['difficulty']}")
    """
    try:
        # Extract factors
        num_steps = int(experiment.get("num_steps", 5))
        num_probes = int(experiment.get("num_probes", 3))
        num_rollbacks = int(experiment.get("num_rollbacks", 1))
        duration_seconds = int(experiment.get("duration_seconds", 300))
        target_types = experiment.get("target_types", [])

        # Normalize to 0-1 scale
        max_steps = 50
        max_probes = 20
        max_targets = 5
        max_duration = 7200  # 2 hours

        steps_factor = min(float(num_steps) / max_steps, 1.0)
        probes_factor = min(float(num_probes) / max_probes, 1.0)
        targets_factor = min(float(len(target_types)) / max_targets, 1.0)
        duration_factor = min(float(duration_seconds) / max_duration, 1.0)

        # Rollback complexity
        total_steps = num_steps + num_probes
        rollback_ratio = float(num_rollbacks) / max(total_steps, 1)
        rollback_factor = min(rollback_ratio, 1.0)

        # Calculate complexity score
        complexity_score = (
            (steps_factor * 0.25)
            + (probes_factor * 0.25)
            + (targets_factor * 0.2)
            + (duration_factor * 0.15)
            + (rollback_factor * 0.15)
        ) * 100

        # Determine difficulty level
        if complexity_score <= 20:
            difficulty = "Simple"
        elif complexity_score <= 40:
            difficulty = "Intermediate"
        elif complexity_score <= 60:
            difficulty = "Advanced"
        elif complexity_score <= 80:
            difficulty = "Expert"
        else:
            difficulty = "Master"

        return {
            "score": round(complexity_score, 1),
            "difficulty": difficulty,
            "factors": {
                "num_steps": num_steps,
                "num_probes": num_probes,
                "num_rollbacks": num_rollbacks,
                "duration_hours": round(duration_seconds / 3600, 1),
                "target_types": len(target_types),
            },
        }

    except Exception as e:
        logger.error(f"Error calculating complexity: {e}", exc_info=True)
        return {
            "score": 50.0,
            "difficulty": "Intermediate",
            "factors": {},
            "error": str(e),
        }


def calculate_and_export_metrics(
    experiment_name: str,
    duration_seconds: float,
    success: bool,
    target_type: Optional[str] = None,
    severity: str = "medium",
    blast_radius: float = 0.5,
    is_production: bool = False,
    has_rollback: bool = True,
    num_steps: int = 5,
    num_probes: int = 3,
    num_rollbacks: int = 1,
    tags: Optional[Dict[str, str]] = None,
) -> Dict[str, Any]:
    """
    Calculate and export experiment metrics to Prometheus.

    Args:
        experiment_name: Name of experiment
        duration_seconds: Total experiment duration
        success: Whether experiment succeeded
        target_type: Type of target (database, network, etc.)
        severity: Experiment severity
        blast_radius: Blast radius (0.0-1.0)
        is_production: Whether production system
        has_rollback: Whether rollback plan exists
        num_steps: Number of steps
        num_probes: Number of probes
        num_rollbacks: Number of rollback actions
        tags: Additional tags

    Returns:
        Dictionary with risk, complexity, and metrics exported

    Example:
        result = calculate_and_export_metrics(
            experiment_name="test-postgres-failover",
            duration_seconds=300,
            success=True,
            target_type="database",
            severity="high",
            is_production=True
        )
        print(f"Risk: {result['risk']['level_name']}")
        print(f"Complexity: {result['complexity']['difficulty']}")
    """
    try:
        ensure_initialized()
        metrics = get_metrics_core()

        logger.info(f"Calculating metrics for experiment: {experiment_name}")

        # Build experiment dict
        experiment = {
            "name": experiment_name,
            "severity": severity,
            "blast_radius": blast_radius,
            "is_production": is_production,
            "has_rollback": has_rollback,
            "num_steps": num_steps,
            "num_probes": num_probes,
            "num_rollbacks": num_rollbacks,
            "duration_seconds": duration_seconds,
            "target_types": [target_type] if target_type else [],
        }

        # Calculate risk and complexity
        risk = calculate_risk_level(experiment)
        complexity = calculate_complexity_score(experiment)

        # Export to Prometheus
        metrics.record_custom_metric(
            "experiment.risk.level",
            value=float(risk["level"]),
            metric_type="gauge",
            tags={
                "experiment": experiment_name,
                "risk_level": risk["level_name"],
            },
        )

        metrics.record_custom_metric(
            "experiment.complexity.score",
            value=float(complexity["score"]),
            metric_type="gauge",
            tags={
                "experiment": experiment_name,
                "difficulty": complexity["difficulty"],
            },
        )

        metrics.record_custom_metric(
            "experiment.duration.seconds",
            value=float(duration_seconds),
            metric_type="gauge",
            unit="s",
        )

        metrics.record_custom_metric(
            "experiment.success",
            value=1.0 if success else 0.0,
            metric_type="gauge",
            tags={"experiment": experiment_name},
        )

        logger.info(
            f"Metrics exported: risk={risk['level_name']}, "
            f"complexity={complexity['difficulty']}"
        )

        return {
            "experiment_name": experiment_name,
            "risk": risk,
            "complexity": complexity,
            "metrics_exported": 4,
            "duration_seconds": duration_seconds,
            "success": success,
        }

    except Exception as e:
        logger.error(f"Error calculating and exporting metrics: {e}", exc_info=True)
        return {
            "experiment_name": experiment_name,
            "error": str(e),
            "metrics_exported": 0,
        }


def calculate_and_export_metrics_from_dict(
    experiment: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Calculate and export metrics from experiment dict.

    Args:
        experiment: Complete experiment dictionary

    Returns:
        Result dictionary with risk, complexity, and metrics
    """
    return calculate_and_export_metrics(
        experiment_name=experiment.get("name", "unknown"),
        duration_seconds=experiment.get("duration_seconds", 0),
        success=experiment.get("success", True),
        target_type=experiment.get("target_type"),
        severity=experiment.get("severity", "medium"),
        blast_radius=experiment.get("blast_radius", 0.5),
        is_production=experiment.get("is_production", False),
        has_rollback=experiment.get("has_rollback", True),
        num_steps=experiment.get("num_steps", 5),
        num_probes=experiment.get("num_probes", 3),
        num_rollbacks=experiment.get("num_rollbacks", 1),
        tags=experiment.get("tags"),
    )
