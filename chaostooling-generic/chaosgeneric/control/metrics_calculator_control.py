# chaostooling-generic/chaosgeneric/control/metrics_calculator_control.py

"""
Metrics Calculator Control - Calculates experiment risk/complexity/test scores.

This control runs for every experiment and:
1. Analyzes the experiment configuration to extract test metrics
2. Calculates risk score (based on chaos targets and scope)
3. Calculates complexity score (based on number of targets and phases)
4. Calculates test score (based on metric count and criticality)
5. Inserts/updates experiment_runs and experiment_test_metrics tables

Runs on: before_experiment_start (to record metrics being tested)
         after_experiment_end (to finalize scores if needed)
"""

import json
import logging
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from chaosgeneric.data.chaos_db import ChaosDb

logger = logging.getLogger("chaosgeneric.control.metrics_calculator")


class MetricsCalculator:
    """Calculate experiment metrics and scores."""

    def __init__(self, db: Optional[ChaosDb] = None):
        """Initialize with optional database connection."""
        self.db = db

    def calculate_risk_score(self, experiment: Dict[str, Any]) -> int:
        """
        Calculate risk score based on experiment configuration.

        Risk factors:
        - Number of chaos actions (weight: 10 points each, max 100)
        - Chaos target scope (low=10, medium=30, high=50)
        - Duration of actions (weight: 1 point per 60 seconds, max 50)

        Range: 0-255 (capped)

        Args:
            experiment: Full experiment configuration dict

        Returns:
            Risk score (0-255)
        """
        score = 0

        # Count chaos actions in method
        method = experiment.get("method", [])
        action_count = len([a for a in method if a.get("type") == "action"])
        score += min(action_count * 10, 100)  # 10 points per action, max 100

        # Estimate scope from targets mentioned in experiment
        experiment_str = json.dumps(experiment).lower()
        if "connection" in experiment_str or "pool" in experiment_str:
            score += 30  # Connection tests are medium risk
        if "kill" in experiment_str or "network" in experiment_str:
            score += 50  # Disruptive actions are high risk
        if "shutdown" in experiment_str or "crash" in experiment_str:
            score += 70  # Severe disruptions are very high risk

        # Duration: estimate from longest action timeout
        for action in method:
            if action.get("type") == "action":
                timeout = action.get("arguments", {}).get("timeout", 0)
                if isinstance(timeout, str):
                    # Parse duration strings like "30s", "2m", etc.
                    timeout = self._parse_duration(timeout)
                score += int(timeout / 60)  # 1 point per 60 seconds

        return min(score, 255)

    def calculate_complexity_score(self, experiment: Dict[str, Any]) -> int:
        """
        Calculate complexity score based on experiment structure.

        Complexity factors:
        - Probe count (weight: 5 points each, max 50)
        - Rollback action count (weight: 10 points each, max 50)
        - Phase count (phases: before/method/rollback/after)
        - Nested conditions and tolerances (weight: 15 points per probe)

        Range: 0-255

        Args:
            experiment: Full experiment configuration dict

        Returns:
            Complexity score (0-255)
        """
        score = 0

        # Count steady-state hypothesis probes
        ssh = experiment.get("steady-state-hypothesis", {})
        probes = ssh.get("probes", [])
        score += min(len(probes) * 5, 50)  # 5 points per probe, max 50

        # Count rollback actions
        rollbacks = experiment.get("rollbacks", [])
        score += min(len(rollbacks) * 10, 50)  # 10 points per rollback, max 50

        # Count phases (max 4: before, method, rollback, after)
        phase_count = 0
        if experiment.get("method"):
            phase_count += 1
        if experiment.get("rollbacks"):
            phase_count += 1
        score += phase_count * 20  # 20 points per major phase

        # Add points for tolerance/conditional logic
        for probe in probes:
            if "tolerance" in probe:
                score += 15
            if "conditions" in probe:
                score += 10

        return min(score, 255)

    def calculate_test_score(self, metrics: List[str]) -> int:
        """
        Calculate test score based on metrics being tested.

        Test factors:
        - Metric count (weight: 5 points each, max 100)
        - Metric criticality (low=1, medium=3, high=5, critical=10)

        Range: 0-255

        Args:
            metrics: List of metric names being tested

        Returns:
            Test score (0-255)
        """
        score = 0

        # Count metrics
        score += min(len(metrics) * 5, 100)  # 5 points per metric, max 100

        # Apply criticality multipliers
        criticality_keywords = {
            "critical": ["error", "failure", "down", "crash"],
            "high": ["latency", "throughput", "connection", "memory", "cpu"],
            "medium": ["cache", "queue", "replications", "lock"],
            "low": ["checkpoint", "vacuum", "cleanup"],
        }

        critical_count = 0
        high_count = 0

        for metric in metrics:
            metric_lower = metric.lower()
            for keyword in criticality_keywords["critical"]:
                if keyword in metric_lower:
                    critical_count += 1
                    break
            else:
                for keyword in criticality_keywords["high"]:
                    if keyword in metric_lower:
                        high_count += 1
                        break

        score += critical_count * 10  # 10 points per critical metric
        score += high_count * 5  # 5 points per high metric

        return min(score, 255)

    def determine_risk_level(self, risk_score: int) -> str:
        """
        Determine risk level based on score.

        Args:
            risk_score: Calculated risk score

        Returns:
            Risk level: 'low' | 'medium' | 'high' | 'critical'
        """
        if risk_score < 50:
            return "low"
        elif risk_score < 120:
            return "medium"
        elif risk_score < 200:
            return "high"
        else:
            return "critical"

    def extract_test_metrics(self, experiment: Dict[str, Any]) -> List[Dict[str, str]]:
        """
        Extract metrics being tested from experiment JSON.

        Looks for:
        - metric_name in probes
        - metrics list in actions
        - metric_query in actions

        Returns:
            List of dicts: {metric_name, metric_query, criticality}
        """
        metrics = []

        # From steady-state probes
        ssh = experiment.get("steady-state-hypothesis", {})
        for probe in ssh.get("probes", []):
            metric_name = probe.get("arguments", {}).get("metric_name")
            if metric_name:
                metrics.append(
                    {
                        "metric_name": metric_name,
                        "metric_query": f"baseline metric: {metric_name}",
                        "criticality": self._determine_probe_criticality(probe),
                    }
                )

        # From method actions
        for action in experiment.get("method", []):
            arguments = action.get("arguments", {})

            # Single metric_name
            if "metric_name" in arguments:
                metrics.append(
                    {
                        "metric_name": arguments["metric_name"],
                        "metric_query": arguments.get("metric_query", ""),
                        "criticality": "high",
                    }
                )

            # Multiple metrics list
            if "metrics" in arguments:
                metrics_list = arguments["metrics"]
                if isinstance(metrics_list, list):
                    for m in metrics_list:
                        metrics.append(
                            {
                                "metric_name": m
                                if isinstance(m, str)
                                else m.get("name", "unknown"),
                                "metric_query": m
                                if isinstance(m, str)
                                else m.get("query", ""),
                                "criticality": "high",
                            }
                        )

        # From post-experiment analysis
        analysis = experiment.get("post-experiment-analysis", {})
        if "arguments" in analysis:
            if "metrics" in analysis["arguments"]:
                for m in analysis["arguments"]["metrics"]:
                    if m not in metrics:
                        metrics.append(
                            {
                                "metric_name": m,
                                "metric_query": "",
                                "criticality": "medium",
                            }
                        )

        return metrics

    def _determine_probe_criticality(self, probe: Dict[str, Any]) -> str:
        """Determine criticality of a probe based on tolerance/description."""
        tolerance = probe.get("tolerance", False)
        description = probe.get("description", "").lower()

        if "error" in description or "fail" in description:
            return "critical"
        elif "connection" in description or "latency" in description:
            return "high"
        else:
            return "medium"

    def _parse_duration(self, duration_str: str) -> float:
        """Parse duration string like '30s', '2m', '1h' to seconds."""
        duration_str = str(duration_str).strip()
        if duration_str.endswith("s"):
            return float(duration_str[:-1])
        elif duration_str.endswith("m"):
            return float(duration_str[:-1]) * 60
        elif duration_str.endswith("h"):
            return float(duration_str[:-1]) * 3600
        else:
            try:
                return float(duration_str)
            except ValueError:
                return 0

    def save_experiment_metrics(
        self,
        run_id: str,
        experiment: Dict[str, Any],
        risk_score: int,
        complexity_score: int,
        test_score: int,
        risk_level: str,
    ) -> bool:
        """
        Save calculated metrics to database.

        Args:
            run_id: Experiment run ID (UUID)
            experiment: Full experiment configuration
            risk_score: Calculated risk score
            complexity_score: Calculated complexity score
            test_score: Calculated test score
            risk_level: Determined risk level

        Returns:
            True if successful, False otherwise
        """
        if not self.db:
            logger.warning("Database not configured, skipping metrics save")
            return False

        try:
            # Update experiment_runs with scores
            self.db.execute(
                """
                UPDATE experiment_runs
                SET risk_score = %s,
                    complexity_score = %s,
                    test_score = %s,
                    risk_level = %s
                WHERE run_id = %s
                """,
                (risk_score, complexity_score, test_score, risk_level, run_id),
            )

            # Extract and insert test metrics
            metrics = self.extract_test_metrics(experiment)

            # Get run_id (internal id)
            run_record = self.db.execute_fetch_one(
                "SELECT id FROM experiment_runs WHERE run_id = %s", (run_id,)
            )

            if not run_record:
                logger.error(f"Run not found: {run_id}")
                return False

            run_internal_id = run_record[0]

            # Insert test metrics
            for metric in metrics:
                self.db.execute(
                    """
                    INSERT INTO experiment_test_metrics
                    (run_id, metric_name, metric_query, criticality, created_at)
                    VALUES (%s, %s, %s, %s, %s)
                    """,
                    (
                        run_internal_id,
                        metric["metric_name"],
                        metric["metric_query"],
                        metric["criticality"],
                        datetime.utcnow(),
                    ),
                )

            logger.info(
                f"Saved metrics for run {run_id}: "
                f"risk={risk_score}, complexity={complexity_score}, test={test_score}"
            )
            return True

        except Exception as e:
            logger.error(f"Error saving experiment metrics: {e}")
            return False


# Control provider functions


def configure_control():
    """Configure the metrics calculator control."""
    logger.info("Metrics calculator control configured")


# Control provider functions that ChaosToolkit calls
# These are the proper hooks into the ChaosToolkit lifecycle


def before_experiment_start(context: Dict[str, Any], **kwargs) -> None:
    """
    Entry point called by ChaosToolkit before experiment starts.

    This is the standard ChaosToolkit control hook signature.
    ChaosToolkit passes:
    - context: Dict that may have various keys depending on lifecycle
    - kwargs: Additional arguments (may include run_id, experiment, etc.)
    """
    try:
        # Get experiment from multiple possible locations
        # ChaosToolkit can put it in context, kwargs, or as top-level argument
        experiment = context.get("experiment") or kwargs.get("experiment")

        if not experiment:
            logger.debug(
                f"No experiment in context/kwargs. Context keys: {context.keys() if context else 'None'}"
            )
            logger.debug(f"Kwargs keys: {kwargs.keys() if kwargs else 'None'}")
            # Don't fail, just log and return - control still successful
            return

        # Try to get run_id from various sources
        run_id = kwargs.get("run_id") or context.get("run_id")

        if not run_id:
            # Generate run_id if not provided
            run_id = str(uuid.uuid4())
            logger.info(f"Generated run_id: {run_id}")

        logger.info(
            f"Calculating metrics for experiment: {experiment.get('title', 'unknown')}"
        )

        # Initialize calculator
        db = ChaosDb()
        calculator = MetricsCalculator(db=db)

        # Calculate scores
        risk_score = calculator.calculate_risk_score(experiment)
        complexity_score = calculator.calculate_complexity_score(experiment)
        metrics = calculator.extract_test_metrics(experiment)
        test_score = calculator.calculate_test_score(
            [m["metric_name"] for m in metrics]
        )
        risk_level = calculator.determine_risk_level(risk_score)

        # Save to database
        calculator.save_experiment_metrics(
            run_id=run_id,
            experiment=experiment,
            risk_score=risk_score,
            complexity_score=complexity_score,
            test_score=test_score,
            risk_level=risk_level,
        )

        logger.info(
            f"Experiment metrics calculated: "
            f"risk={risk_score} ({risk_level}), "
            f"complexity={complexity_score}, "
            f"test={test_score}, "
            f"metrics={len(metrics)}"
        )

    except Exception as e:
        logger.error(f"Error in metrics calculator control: {e}", exc_info=True)
        # Don't raise - this shouldn't block experiment execution


# Alias for backwards compatibility
before_experiment_control = before_experiment_start
