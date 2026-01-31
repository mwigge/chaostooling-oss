"""
Baseline Validation and Anomaly Detection

Automatically validates experiment metrics against baseline on completion.
Detects anomalies and assesses impact using statistical analysis.
"""

import logging
import json
from typing import Dict, Any, List, Optional
from datetime import datetime

logger = logging.getLogger("chaosgeneric.control.baseline_validation")


class BaselineValidator:
    """Validates metrics against baselines using statistical analysis."""

    @staticmethod
    def get_sigma_bounds(
        mean: float, stddev: float, sigma_level: int = 2
    ) -> Dict[str, float]:
        """
        Calculate sigma bounds for anomaly detection.

        Args:
            mean: Mean value from baseline
            stddev: Standard deviation from baseline
            sigma_level: Number of standard deviations (2 or 3)

        Returns:
            Dict with lower and upper bounds
        """
        return {
            "lower_bound": mean - (sigma_level * stddev),
            "upper_bound": mean + (sigma_level * stddev),
            "sigma_level": sigma_level,
        }

    @staticmethod
    def check_anomaly(
        value: float, baseline: Dict[str, Any], sigma_level: int = 2
    ) -> Dict[str, Any]:
        """
        Check if metric value is anomalous compared to baseline.

        Args:
            value: Current metric value
            baseline: Baseline stats (mean, stddev, p95, p99)
            sigma_level: Sigma threshold for anomaly (2 or 3)

        Returns:
            Dict with anomaly detection results
        """
        mean = baseline.get("mean", 0)
        stddev = baseline.get("stddev", 0)

        if stddev == 0:
            # If no variance, any change is anomalous
            return {
                "is_anomaly": value != mean,
                "reason": "no_baseline_variance",
                "value": value,
                "baseline_mean": mean,
            }

        # Calculate z-score
        z_score = abs((value - mean) / stddev)

        bounds = BaselineValidator.get_sigma_bounds(mean, stddev, sigma_level)

        is_anomaly = value < bounds["lower_bound"] or value > bounds["upper_bound"]

        # Categorize severity
        if z_score > 3:
            severity = "CRITICAL"
        elif z_score > 2:
            severity = "WARNING"
        elif z_score > 1:
            severity = "NOTICE"
        else:
            severity = "NORMAL"

        return {
            "is_anomaly": is_anomaly,
            "severity": severity,
            "value": value,
            "baseline_mean": mean,
            "baseline_stddev": stddev,
            "z_score": round(z_score, 2),
            "bounds": bounds,
            "deviation_percent": round((abs(value - mean) / max(mean, 1)) * 100, 2),
        }

    @staticmethod
    def validate_experiment_metrics(
        run_id: int,
        service_name: str,
        post_chaos_metrics: Dict[str, float],
        baselines: Dict[str, Dict[str, float]],
        sigma_level: int = 2,
    ) -> Dict[str, Any]:
        """
        Validate all experiment metrics against baselines.

        Args:
            run_id: Experiment run ID
            service_name: Service being tested
            post_chaos_metrics: Metrics after chaos (dict of metric_name: value)
            baselines: Baseline stats (dict of metric_name: baseline_stats)
            sigma_level: Sigma threshold for anomaly

        Returns:
            Validation report with anomalies and recommendations
        """
        logger.info(f"Validating {len(post_chaos_metrics)} metrics for run {run_id}")

        validation_results = {
            "run_id": run_id,
            "service": service_name,
            "validation_date": datetime.utcnow().isoformat(),
            "metrics_validated": len(post_chaos_metrics),
            "metrics_with_anomalies": 0,
            "critical_anomalies": 0,
            "anomalies": [],
            "recovery_assessment": {},
            "recommendations": [],
        }

        for metric_name, post_value in post_chaos_metrics.items():
            baseline = baselines.get(metric_name, {})

            if not baseline:
                logger.warning(f"No baseline for metric: {metric_name}")
                validation_results["anomalies"].append(
                    {
                        "metric": metric_name,
                        "status": "no_baseline",
                        "value": post_value,
                    }
                )
                continue

            # Check for anomaly
            check = BaselineValidator.check_anomaly(post_value, baseline, sigma_level)

            if check["is_anomaly"]:
                validation_results["metrics_with_anomalies"] += 1

                if check["severity"] == "CRITICAL":
                    validation_results["critical_anomalies"] += 1

                anomaly_record = {
                    "metric": metric_name,
                    "status": "anomaly_detected",
                    "severity": check["severity"],
                    "post_chaos_value": post_value,
                    "baseline_mean": check["baseline_mean"],
                    "deviation_percent": check["deviation_percent"],
                    "z_score": check["z_score"],
                }

                validation_results["anomalies"].append(anomaly_record)
                logger.warning(
                    f"Anomaly: {metric_name} = {post_value} "
                    f"(baseline: {check['baseline_mean']}, "
                    f"deviation: {check['deviation_percent']}%, "
                    f"severity: {check['severity']})"
                )
            else:
                logger.info(
                    f"Normal: {metric_name} = {post_value} "
                    f"(baseline: {check['baseline_mean']}, "
                    f"deviation: {check['deviation_percent']}%)"
                )

        # Assessment and recommendations
        if validation_results["critical_anomalies"] > 0:
            validation_results["overall_status"] = "FAILED"
            validation_results["recovery_assessment"]["status"] = "incomplete"
            validation_results["recovery_assessment"]["reason"] = (
                f"{validation_results['critical_anomalies']} critical anomalies detected"
            )
            validation_results["recommendations"].append(
                "Critical anomalies detected. Investigate root cause before re-running."
            )
            validation_results["recommendations"].append(
                "Consider scaling resources or optimizing slow operations."
            )
        elif validation_results["metrics_with_anomalies"] > 0:
            validation_results["overall_status"] = "WARNING"
            validation_results["recovery_assessment"]["status"] = "partial"
            validation_results["recovery_assessment"]["reason"] = (
                f"{validation_results['metrics_with_anomalies']} anomalies detected"
            )
            validation_results["recommendations"].append(
                "Some metrics show anomalies but within warning threshold. Monitor recovery."
            )
            validation_results["recommendations"].append(
                "Consider increasing baseline analysis window for more accurate bounds."
            )
        else:
            validation_results["overall_status"] = "PASSED"
            validation_results["recovery_assessment"]["status"] = "complete"
            validation_results["recovery_assessment"]["reason"] = (
                "All metrics within baseline bounds"
            )
            validation_results["recommendations"].append(
                "Experiment completed successfully. System recovered within expected parameters."
            )

        logger.info(
            f"Validation complete: {validation_results['overall_status']} "
            f"({validation_results['metrics_with_anomalies']} anomalies, "
            f"{validation_results['critical_anomalies']} critical)"
        )

        return validation_results


def validate_baseline(
    context: Dict[str, Any],
    baseline_metrics: Dict[str, Dict[str, float]],
    post_chaos_metrics: Dict[str, float],
) -> Dict[str, Any]:
    """
    Chaos Toolkit hook: Validate baseline on experiment completion.

    Can be called from after_experiment_control or in probes.

    Args:
        context: Chaos Toolkit context with run_id and service info
        baseline_metrics: Baseline stats from database
        post_chaos_metrics: Metrics collected after chaos

    Returns:
        Validation report
    """
    validator = BaselineValidator()

    run_id = context.get("chaos_run_id")
    service_name = context.get("chaos_service_name", "unknown")

    result = validator.validate_experiment_metrics(
        run_id, service_name, post_chaos_metrics, baseline_metrics, sigma_level=2
    )

    # Store validation in context for other controls
    context["baseline_validation"] = result

    return result


def print_baseline_summary() -> None:
    """Print summary of baseline data usage after steady-state hypothesis."""
    logger.info("")
    logger.info(
        "╔══════════════════════════════════════════════════════════════════════╗"
    )
    logger.info(
        "║              BASELINE DATA VALIDATION SUMMARY                        ║"
    )
    logger.info(
        "╚══════════════════════════════════════════════════════════════════════╝"
    )
    logger.info("")
    logger.info("📊 BASELINE DATA USAGE:")
    logger.info("")
    logger.info("   ✓ Using real metrics from DATABASE:")
    logger.info("     Probes with actual baseline data are comparing against REAL")
    logger.info("     historical metrics. System steady-state is VALIDATED.")
    logger.info("")
    logger.info("   ✓ Using metrics from FILE (fallback):")
    logger.info("     Database was unavailable, using JSON file baseline instead.")
    logger.info("     System steady-state is VALIDATED.")
    logger.info("")
    logger.info("   ⚠️  Tolerance bypass (NO baseline data):")
    logger.info("     Probe passed WITHOUT validating actual metrics because")
    logger.info("     tolerance=true and no baseline was found. This is expected")
    logger.info("     on FIRST RUN when no baselines exist yet.")
    logger.info("")
    logger.info("💡 INTERPRETATION:")
    logger.info("")
    logger.info("   First run (NEW EXPERIMENT):")
    logger.info("   • All probes will PASS due to tolerance=true (no baseline exists)")
    logger.info("   • This establishes baseline data in the database")
    logger.info("   • Next runs will use REAL baseline comparison")
    logger.info("")
    logger.info("   Subsequent runs (WITH BASELINE):")
    logger.info("   • Probes will FAIL if metrics deviate >2σ from baseline")
    logger.info("   • Shows system degradation during chaos scenarios")
    logger.info("")
    logger.info(
        "╔══════════════════════════════════════════════════════════════════════╗"
    )
    logger.info(
        "║        Steady-state hypothesis validation complete ✓                 ║"
    )
    logger.info(
        "╚══════════════════════════════════════════════════════════════════════╝"
    )
    logger.info("")
