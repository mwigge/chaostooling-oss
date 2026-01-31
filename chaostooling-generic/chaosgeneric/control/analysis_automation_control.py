"""
Analysis Automation and Reporting

Automatically populates analysis_log with:
- Anomaly detection results
- Root cause analysis (RCA)
- Remediation recommendations
- DORA metrics evidence
"""

import logging
from datetime import datetime
from typing import Any

logger = logging.getLogger("chaosgeneric.control.analysis_automation")


class AnalysisAutomation:
    """Automatically generates analysis and populates analysis_log."""

    @staticmethod
    def detect_anomalies(baseline_validation: dict[str, Any]) -> list[dict[str, Any]]:
        """
        Extract detected anomalies from baseline validation.

        Returns:
            List of anomaly records
        """
        anomalies = []

        for anomaly in baseline_validation.get("anomalies", []):
            if anomaly.get("status") == "anomaly_detected":
                anomalies.append(
                    {
                        "metric": anomaly.get("metric"),
                        "severity": anomaly.get("severity"),
                        "value": anomaly.get("post_chaos_value"),
                        "baseline": anomaly.get("baseline_mean"),
                        "deviation_percent": anomaly.get("deviation_percent"),
                        "z_score": anomaly.get("z_score"),
                    }
                )

        return anomalies

    @staticmethod
    def perform_rca(
        anomalies: list[dict[str, Any]],
        experiment_actions: list[str],
        experiment_type: str,
    ) -> dict[str, Any]:
        """
        Perform Root Cause Analysis based on anomalies and experiment actions.

        Args:
            anomalies: Detected anomalies
            experiment_actions: Actions executed in experiment (cpu stress, latency, etc.)
            experiment_type: Type of experiment (compute, network, database, etc.)

        Returns:
            RCA findings
        """
        rca_findings = {
            "root_causes": [],
            "contributing_factors": [],
            "confidence_level": "medium",
        }

        if not anomalies:
            rca_findings["root_causes"].append("No detected anomalies")
            rca_findings["conclusion"] = (
                "System handled chaos injection without degradation"
            )
            return rca_findings

        # Match anomalies to actions
        for anomaly in anomalies:
            metric = anomaly.get("metric", "").lower()

            # CPU stress actions -> CPU/latency anomalies
            if "cpu_stress" in experiment_actions:
                if "cpu" in metric or "latency" in metric or "throughput" in metric:
                    rca_findings["root_causes"].append(
                        f"Direct: CPU stress injected by experiment caused {metric} degradation"
                    )
                    rca_findings["confidence_level"] = "high"

            # Memory stress -> Memory/latency anomalies
            if "memory_stress" in experiment_actions:
                if "memory" in metric or "latency" in metric or "gc_time" in metric:
                    rca_findings["root_causes"].append(
                        f"Direct: Memory stress caused {metric} degradation"
                    )
                    rca_findings["confidence_level"] = "high"

            # Disk I/O stress -> Disk/latency anomalies
            if "disk_io_stress" in experiment_actions:
                if "disk" in metric or "io" in metric or "latency" in metric:
                    rca_findings["root_causes"].append(
                        f"Direct: Disk I/O stress caused {metric} degradation"
                    )
                    rca_findings["confidence_level"] = "high"

            # Network chaos -> Latency/error anomalies
            if any(
                action in experiment_actions
                for action in ["inject_latency", "packet_loss", "bandwidth_limit"]
            ):
                if "latency" in metric or "error" in metric or "timeout" in metric:
                    rca_findings["root_causes"].append(
                        f"Direct: Network chaos caused {metric} degradation"
                    )
                    rca_findings["confidence_level"] = "high"

            # Database chaos -> Error/latency anomalies
            if any(
                action in experiment_actions
                for action in ["connection_pool", "lock_contention", "deadlock"]
            ):
                if "error" in metric or "latency" in metric or "connections" in metric:
                    rca_findings["root_causes"].append(
                        f"Direct: Database chaos caused {metric} degradation"
                    )
                    rca_findings["confidence_level"] = "high"

        # Contributing factors (cascading effects)
        if any("latency" in a.get("metric", "") for a in anomalies):
            rca_findings["contributing_factors"].append(
                "Increased latency cascading to dependent services"
            )

        if any("error" in a.get("metric", "") for a in anomalies):
            rca_findings["contributing_factors"].append(
                "Increased error rates potentially triggering timeouts/retries"
            )

        if any("cpu" in a.get("metric", "") for a in anomalies):
            rca_findings["contributing_factors"].append(
                "CPU saturation limiting throughput and increasing queuing delays"
            )

        if not rca_findings["root_causes"]:
            rca_findings["root_causes"].append(
                "Anomalies detected but not directly traceable to experiment actions"
            )
            rca_findings["confidence_level"] = "low"

        return rca_findings

    @staticmethod
    def generate_recommendations(
        anomalies: list[dict[str, Any]],
        rca: dict[str, Any],
        baseline_validation: dict[str, Any],
    ) -> list[str]:
        """
        Generate remediation recommendations based on findings.

        Args:
            anomalies: Detected anomalies
            rca: Root cause analysis
            baseline_validation: Baseline validation results

        Returns:
            List of recommendations
        """
        recommendations = []

        critical_count = sum(1 for a in anomalies if a.get("severity") == "CRITICAL")
        warning_count = sum(1 for a in anomalies if a.get("severity") == "WARNING")

        # Capacity recommendations
        for anomaly in anomalies:
            if anomaly.get("severity") == "CRITICAL":
                metric = anomaly.get("metric")
                if "cpu" in metric:
                    recommendations.append(
                        f"Upgrade CPU capacity or implement auto-scaling (current peak: {anomaly.get('value')})"
                    )
                elif "memory" in metric:
                    recommendations.append(
                        "Increase memory allocation or optimize memory usage patterns"
                    )
                elif "disk" in metric:
                    recommendations.append(
                        "Increase disk I/O capacity or implement caching strategy"
                    )
                elif "latency" in metric:
                    recommendations.append(
                        f"Optimize critical path latency - target < {anomaly.get('baseline')}ms"
                    )
                elif "error" in metric:
                    recommendations.append(
                        "Implement circuit breakers and graceful degradation"
                    )

        # Architecture recommendations
        if critical_count > 2:
            recommendations.append(
                "Consider microservices refactoring to isolate critical components"
            )
            recommendations.append("Implement bulkheads to limit cascade failures")

        if warning_count > 5:
            recommendations.append(
                "Implement comprehensive monitoring and alerting on key metrics"
            )

        # Resilience recommendations
        if any("timeout" in a.get("metric", "") for a in anomalies):
            recommendations.append("Implement exponential backoff and retry logic")

        if any("connection" in a.get("metric", "") for a in anomalies):
            recommendations.append("Implement connection pooling with proper tuning")
            recommendations.append("Set appropriate connection timeouts")

        # Testing recommendations
        if baseline_validation.get("overall_status") == "FAILED":
            recommendations.append("Increase chaos experiment intensity gradually")
            recommendations.append(
                "Focus on stabilizing system before running higher-intensity tests"
            )
        else:
            recommendations.append(
                "Current resilience is acceptable for chaos testing scope"
            )
            recommendations.append(
                "Consider increasing chaos intensity in next iteration"
            )

        # Monitoring recommendations
        recommendations.append("Add alerting for detected anomaly patterns")
        recommendations.append("Implement automated rollback for critical anomalies")

        return recommendations

    @staticmethod
    def generate_dora_evidence(
        baseline_validation: dict[str, Any], rca: dict[str, Any]
    ) -> dict[str, Any]:
        """
        Generate DORA (DevOps Research Assessment) evidence from analysis.

        DORA metrics:
        - Deployment frequency
        - Lead time for changes
        - Mean time to recovery (MTTR)
        - Change failure rate

        Returns:
            DORA evidence collected from experiment
        """
        return {
            "deployment_frequency": {
                "indicator": "Ability to experiment frequently",
                "evidence": "Chaos experiment executed successfully",
                "value": "✓ Can conduct chaos tests",
            },
            "lead_time": {
                "indicator": "System response to changes",
                "evidence": f"Recovery time: {baseline_validation.get('recovery_assessment', {}).get('reason')}",
                "value": "Tracked during experiment",
            },
            "mttr": {
                "indicator": "Recovery from failures",
                "evidence": "Post-chaos metrics validation",
                "status": baseline_validation.get("recovery_assessment", {}).get(
                    "status"
                ),
                "time_to_baseline": "Analyzed",
            },
            "change_failure_rate": {
                "indicator": "Impact of experiment",
                "anomalies_detected": baseline_validation.get(
                    "metrics_with_anomalies", 0
                ),
                "critical_anomalies": baseline_validation.get("critical_anomalies", 0),
                "failure_impact": "measured",
            },
        }

    @staticmethod
    def generate_analysis_report(
        run_id: int,
        service_name: str,
        baseline_validation: dict[str, Any],
        experiment_actions: list[str],
        experiment_type: str = "unknown",
    ) -> dict[str, Any]:
        """
        Generate comprehensive analysis report.

        Args:
            run_id: Experiment run ID
            service_name: Service name
            baseline_validation: Baseline validation results
            experiment_actions: List of chaos actions executed
            experiment_type: Type of experiment

        Returns:
            Complete analysis report
        """
        logger.info(f"Generating analysis report for run {run_id}")

        # Extract anomalies
        anomalies = AnalysisAutomation.detect_anomalies(baseline_validation)

        # Perform RCA
        rca = AnalysisAutomation.perform_rca(
            anomalies, experiment_actions, experiment_type
        )

        # Generate recommendations
        recommendations = AnalysisAutomation.generate_recommendations(
            anomalies, rca, baseline_validation
        )

        # Generate DORA evidence
        dora_evidence = AnalysisAutomation.generate_dora_evidence(
            baseline_validation, rca
        )

        report = {
            "analysis_date": datetime.utcnow().isoformat(),
            "run_id": run_id,
            "service": service_name,
            "experiment_type": experiment_type,
            "experiment_actions": experiment_actions,
            # Key findings
            "overall_assessment": baseline_validation.get("overall_status"),
            "metrics_validated": baseline_validation.get("metrics_validated", 0),
            "anomalies_detected": len(anomalies),
            "critical_anomalies": baseline_validation.get("critical_anomalies", 0),
            # Detailed analysis
            "anomalies": anomalies,
            "root_cause_analysis": rca,
            "recommendations": recommendations,
            "recovery_status": baseline_validation.get("recovery_assessment", {}),
            # Compliance/Metrics
            "dora_evidence": dora_evidence,
            "compliance_status": "PASS"
            if baseline_validation.get("overall_status") == "PASSED"
            else "REVIEW",
            # Summary
            "summary": {
                "findings": len(anomalies),
                "severity_distribution": {
                    "critical": baseline_validation.get("critical_anomalies", 0),
                    "warning": sum(
                        1 for a in anomalies if a.get("severity") == "WARNING"
                    ),
                    "notice": sum(
                        1 for a in anomalies if a.get("severity") == "NOTICE"
                    ),
                },
                "recommendations_count": len(recommendations),
                "conclusion": "Experiment completed with analysis generated",
            },
        }

        logger.info(f"Analysis report generated: {report['summary']}")

        return report


def analyze_experiment(
    context: dict[str, Any],
    baseline_validation: dict[str, Any],
    experiment: dict[str, Any],
) -> dict[str, Any]:
    """
    Main entry point for analysis automation.

    Can be called from after_experiment_control.

    Args:
        context: Chaos Toolkit context
        baseline_validation: Baseline validation results
        experiment: Experiment definition

    Returns:
        Complete analysis report
    """
    run_id = context.get("chaos_run_id")
    service_name = context.get("chaos_service_name", "unknown")

    # Extract experiment actions
    experiment_actions = []
    for method in experiment.get("method", []):
        experiment_actions.append(method.get("name", "unknown"))

    # Generate report
    report = AnalysisAutomation.generate_analysis_report(
        run_id,
        service_name,
        baseline_validation,
        experiment_actions,
        experiment_type=experiment.get("analysis_type", "unknown"),
    )

    # Store in context for other controls
    context["analysis_report"] = report

    return report
