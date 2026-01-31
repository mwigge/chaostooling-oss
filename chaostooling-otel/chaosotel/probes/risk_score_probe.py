"""
Risk Score Analysis Probe

Investigates the risk score calculation mismatch between:
- Manual risk_score (audit_log-based, typically ~92)
- Grafana metrics (multiple datasources: Prometheus, Loki, Tempo, etc.)

Grafana provides a unified interface for fetching metrics from multiple datasources.

Architecture:
    Manual Assessment → Experiment definition (criticality, blast radius, etc.)
    Grafana Metrics ← Unified datasource interface (Prometheus, Loki, Tempo, Elasticsearch, etc.)
    Risk Score ← Comparison and analysis
"""

import json
import logging
from typing import Dict, Any, Optional, List
import requests
from datetime import datetime, timedelta

logger = logging.getLogger("chaosotel.probes.risk_score")


class GrafanaMetricsClient:
    """
    Unified metrics client that queries Grafana, which handles multiple datasources.

    Advantages:
    - Single interface for all datasources (Prometheus, Loki, Tempo, Elasticsearch, etc.)
    - Datasource abstraction - can swap backends without changing queries
    - Grafana alerting rules and annotations
    - Multi-datasource dashboard support
    """

    def __init__(self, grafana_url: str = "http://grafana:3000", api_key: str = None):
        """
        Initialize Grafana client.

        Args:
            grafana_url: Grafana server URL
            api_key: Grafana API key (optional, uses default user if not provided)
        """
        self.grafana_url = grafana_url.rstrip("/")
        self.api_key = api_key
        self.headers = {}
        if api_key:
            self.headers["Authorization"] = f"Bearer {api_key}"
        self.headers["Content-Type"] = "application/json"

    def list_datasources(self) -> List[Dict[str, Any]]:
        """
        List all available datasources in Grafana.

        Returns:
            List of datasource configurations
        """
        try:
            response = requests.get(
                f"{self.grafana_url}/api/datasources", headers=self.headers, timeout=10
            )
            if response.status_code == 200:
                return response.json()
        except Exception as e:
            logger.warning(f"Failed to list Grafana datasources: {e}")
        return []

    def get_datasource_by_name(self, name: str) -> Optional[Dict[str, Any]]:
        """
        Get datasource by name.

        Args:
            name: Datasource name (e.g., 'Prometheus', 'Loki')

        Returns:
            Datasource config or None
        """
        try:
            response = requests.get(
                f"{self.grafana_url}/api/datasources/name/{name}",
                headers=self.headers,
                timeout=10,
            )
            if response.status_code == 200:
                return response.json()
        except Exception as e:
            logger.warning(f"Failed to get Grafana datasource {name}: {e}")
        return None

    def query_metric(
        self, query: str, datasource_name: str = "Prometheus", time_range: str = "1h"
    ) -> Optional[float]:
        """
        Query metric from any Grafana datasource.

        Args:
            query: Query string (PromQL for Prometheus, LogQL for Loki, etc.)
            datasource_name: Name of the datasource in Grafana
            time_range: Time range (1h, 5m, etc.)

        Returns:
            Latest metric value or None
        """
        try:
            datasource = self.get_datasource_by_name(datasource_name)
            if not datasource:
                logger.warning(f"Datasource {datasource_name} not found")
                return None

            datasource_id = datasource.get("id")

            # Calculate time range in milliseconds
            now = int(datetime.utcnow().timestamp() * 1000)
            if time_range == "1h":
                since = now - (3600 * 1000)
            elif time_range == "5m":
                since = now - (5 * 60 * 1000)
            else:
                since = now - (3600 * 1000)  # Default to 1h

            # Build query for tsdb endpoint (works with Prometheus and similar)
            payload = {
                "queries": [
                    {
                        "refId": "A",
                        "datasourceId": datasource_id,
                        "targets": [
                            {"expr": query, "refId": "A", "format": "time_series"}
                        ],
                        "range": {"from": since, "to": now},
                    }
                ]
            }

            response = requests.post(
                f"{self.grafana_url}/api/tsdb/query",
                json=payload,
                headers=self.headers,
                timeout=10,
            )

            if response.status_code == 200:
                data = response.json()
                if data.get("results"):
                    result = data["results"][0]
                    if result.get("series"):
                        # Extract last value from time series
                        last_series = result["series"][-1]
                        if last_series.get("points"):
                            last_point = last_series["points"][-1]
                            # points are [timestamp, value]
                            return float(last_point[0])
        except Exception as e:
            logger.warning(f"Failed to query Grafana metric: {e}")

        return None


def calculate_manual_risk_score(experiment_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Calculate risk score based on manual assessment.

    Factors:
    - Service criticality (1-10)
    - Blast radius (1-10)
    - Recovery difficulty (1-10)
    - Team expertise (1-10, inverse)
    - Time of execution (business hours vs off-hours)

    Formula: (criticality + blast_radius + recovery + expertise_inverse + time_factor) / 5 * 10

    Returns:
        Dict with calculation breakdown
    """
    criticality = experiment_data.get("service_criticality", 5)  # 1-10
    blast_radius = experiment_data.get(
        "blast_radius", 5
    )  # 1-10 (how many services affected)
    recovery_difficulty = experiment_data.get("recovery_difficulty", 5)  # 1-10
    team_expertise = 10 - experiment_data.get(
        "team_expertise_level", 5
    )  # Inverse (1-10)
    time_factor = 10 if experiment_data.get("is_business_hours", False) else 5

    # Weighted calculation
    weighted_sum = (
        criticality * 0.25
        + blast_radius * 0.25
        + recovery_difficulty * 0.2
        + team_expertise * 0.15
        + (time_factor / 10) * 0.15
    ) * 10

    return {
        "approach": "Manual Assessment",
        "factors": {
            "service_criticality": criticality,
            "blast_radius": blast_radius,
            "recovery_difficulty": recovery_difficulty,
            "team_expertise_level": 10 - team_expertise,
            "is_business_hours": experiment_data.get("is_business_hours", False),
            "time_factor": time_factor,
        },
        "calculation": {
            "formula": "(criticality*0.25 + blast_radius*0.25 + recovery*0.2 + expertise*0.15 + time*0.15) * 10",
            "step1_sum": (
                criticality * 0.25
                + blast_radius * 0.25
                + recovery_difficulty * 0.2
                + team_expertise * 0.15
                + (time_factor / 10) * 0.15
            ),
            "result": round(weighted_sum, 2),
        },
    }


def calculate_grafana_metrics_risk_score(
    service_name: str, grafana_url: str = "http://grafana:3000", api_key: str = None
) -> Dict[str, Any]:
    """
    Calculate risk score based on Grafana metrics from any datasource.

    Factors:
    - Error rate (% errors increase risk)
    - Latency (ms, p99)
    - Resource utilization (CPU, memory %)
    - Traffic rate (requests/sec)

    Grafana provides unified access to multiple datasources:
    - Prometheus (for application and system metrics)
    - Loki (for logs and log-based metrics)
    - Tempo (for distributed tracing and latency)
    - Elasticsearch (for application events)
    - CloudWatch/Datadog/New Relic (for cloud metrics)

    Formula: Weighted combination of normalized metrics

    Returns:
        Dict with calculation breakdown
    """
    client = GrafanaMetricsClient(grafana_url, api_key)
    metrics = {}

    # Query key metrics from Grafana (datasource-agnostic)
    error_rate = (
        client.query_metric(
            f'increase(chaos_errors_total{{service="{service_name}"}}[5m]) / increase(chaos_requests_total{{service="{service_name}"}}[5m]) * 100',
            datasource_name="Prometheus",
        )
        or 0
    )

    latency_p99 = (
        client.query_metric(
            f'histogram_quantile(0.99, rate(chaos_request_duration_ms_bucket{{service="{service_name}"}}[5m]))',
            datasource_name="Prometheus",
        )
        or 0
    )

    cpu_percent = (
        client.query_metric(
            f'avg(rate(container_cpu_usage_seconds_total{{pod=~"{service_name}.*"}}[5m])) * 100',
            datasource_name="Prometheus",
        )
        or 0
    )

    memory_percent = (
        client.query_metric(
            f'avg(container_memory_working_set_bytes{{pod=~"{service_name}.*"}}) / avg(container_spec_memory_limit_bytes{{pod=~"{service_name}.*"}}) * 100',
            datasource_name="Prometheus",
        )
        or 0
    )

    traffic_rps = (
        client.query_metric(
            f'sum(rate(chaos_requests_total{{service="{service_name}"}}[5m]))',
            datasource_name="Prometheus",
        )
        or 0
    )

    metrics = {
        "error_rate_percent": round(error_rate, 2),
        "latency_p99_ms": round(latency_p99, 2),
        "cpu_percent": round(cpu_percent, 2),
        "memory_percent": round(memory_percent, 2),
        "traffic_rps": round(traffic_rps, 2),
    }

    # Normalize and weight
    error_score = min(
        error_rate / 10, 10
    )  # 0-10 (1% error = 0.1, 10% = 1.0, 100% = 10)
    latency_score = min(latency_p99 / 1000, 10)  # 0-10 (1000ms = 1.0, 10000ms = 10)
    cpu_score = min(cpu_percent / 10, 10)  # 0-10 (80% = 8.0)
    memory_score = min(memory_percent / 10, 10)  # 0-10
    traffic_score = min(traffic_rps / 1000, 10)  # 0-10 (1000 rps = 1.0)

    # Weighted calculation
    grafana_score = (
        error_score * 0.3
        + latency_score * 0.25
        + cpu_score * 0.2
        + memory_score * 0.15
        + traffic_score * 0.1
    )

    return {
        "approach": "Grafana Metrics (Multi-Datasource)",
        "metrics": metrics,
        "normalized_scores": {
            "error_score": round(error_score, 2),
            "latency_score": round(latency_score, 2),
            "cpu_score": round(cpu_score, 2),
            "memory_score": round(memory_score, 2),
            "traffic_score": round(traffic_score, 2),
        },
        "calculation": {
            "formula": "error*0.3 + latency*0.25 + cpu*0.2 + memory*0.15 + traffic*0.1",
            "result": round(grafana_score, 2),
        },
    }


def analyze_risk_score_mismatch(
    service_name: str,
    experiment_data: Dict[str, Any],
    grafana_url: str = "http://grafana:3000",
    api_key: str = None,
) -> Dict[str, Any]:
    """
    Analyze the difference between manual and Grafana metrics risk scores.

    Manual score comes from experiment definition (criticality, blast radius, etc.)
    Grafana metrics score comes from actual system metrics (Prometheus, Loki, etc.)

    Usage in experiment:
        {
            "type": "probe",
            "name": "Analyze Risk Score",
            "provider": {
                "type": "python",
                "module": "chaosotel.probes.risk_score_probe",
                "func": "analyze_risk_score_mismatch",
                "arguments": {
                    "service_name": "postgres",
                    "experiment_data": {
                        "service_criticality": 9,
                        "blast_radius": 8,
                        "recovery_difficulty": 7,
                        "team_expertise_level": 8,
                        "is_business_hours": false
                    }
                }
            }
        }

    Returns:
        Dict with analysis and explanation
    """
    logger.info(f"Analyzing risk score for {service_name}")

    # Calculate both scores
    manual = calculate_manual_risk_score(experiment_data)
    grafana = calculate_grafana_metrics_risk_score(service_name, grafana_url, api_key)

    manual_score = manual["calculation"]["result"]
    grafana_score = grafana["calculation"]["result"]
    diff = abs(manual_score - grafana_score)
    diff_percent = (diff / max(manual_score, grafana_score, 1)) * 100

    # Generate explanation
    explanation = []

    explanation.append(
        f"Manual Risk Score: {manual_score}/10.0 "
        f"(based on criticality, blast radius, recovery difficulty, expertise, timing)"
    )
    explanation.append(
        f"Grafana Metrics Risk Score: {grafana_score}/10.0 "
        f"(based on live metrics: errors, latency, CPU, memory, traffic from Prometheus/Loki/Tempo)"
    )
    explanation.append(f"Difference: {diff:.2f} points ({diff_percent:.1f}%)")

    if diff_percent > 50:
        explanation.append("")
        explanation.append("SIGNIFICANT MISMATCH - Likely Causes:")

        if manual_score > grafana_score:
            explanation.append(
                f"• Manual assessment assumes high risk ({manual_score}), "
                f"but system is performing well ({grafana_score})"
            )
            explanation.append(
                "• Possible: System has good redundancy/failover built in"
            )
            explanation.append(
                "• Possible: Conservative assessment (better safe than sorry)"
            )
            explanation.append(
                "• Possible: Pre-chaos metrics don't reflect chaos impact"
            )
        else:
            explanation.append(
                f"• Grafana metrics show high risk ({grafana_score}), "
                f"but manual assessment is lower ({manual_score})"
            )
            explanation.append(
                "• Possible: System already degraded before chaos experiment"
            )
            explanation.append(
                "• Possible: Metrics include unavoidable baseline spikes"
            )
            explanation.append("• Possible: Manual assessment underestimates impact")
    else:
        explanation.append("Scores are well-aligned. Assessment is consistent.")

    # Recommendations
    recommendations = []

    if diff_percent > 50:
        recommendations.append("Review manual assessment criteria with the team")
        recommendations.append(
            "Validate Grafana metrics accuracy and datasource configuration"
        )
        recommendations.append("Adjust risk weighting in either approach")
        recommendations.append(
            "Monitor actual incident response time vs. estimated recovery difficulty"
        )

    if grafana_score > 8:
        recommendations.append("System showing high-risk metrics even before chaos")
        recommendations.append("Consider baseline optimization before chaos testing")

    if manual_score > 8:
        recommendations.append("High-risk experiment - ensure proper safety controls")
        recommendations.append("Consider running in staging environment first")

    logger.info(
        f"Risk score analysis: Manual={manual_score}, Grafana={grafana_score}, Diff={diff:.2f}"
    )

    return {
        "timestamp": datetime.utcnow().isoformat(),
        "service": service_name,
        "manual_assessment": manual,
        "grafana_metrics": grafana,
        "comparison": {
            "manual_score": manual_score,
            "grafana_metrics_score": grafana_score,
            "absolute_difference": round(diff, 2),
            "percent_difference": round(diff_percent, 1),
            "aligned": diff_percent <= 50,
        },
        "explanation": explanation,
        "recommendations": recommendations,
        "remediation_priority": "HIGH" if diff_percent > 50 else "MEDIUM",
    }


def probe_risk_score(
    service_name: str, grafana_url: str = "http://grafana:3000", api_key: str = None
) -> Dict[str, Any]:
    """
    Lightweight probe to get current risk score from Grafana metrics.

    Returns:
        Current Grafana metrics risk score
    """
    logger.info(f"Probing risk score for {service_name}")

    result = calculate_grafana_metrics_risk_score(service_name, grafana_url, api_key)

    return {
        "service": service_name,
        "grafana_metrics_risk_score": result["calculation"]["result"],
        "metrics": result["metrics"],
        "timestamp": datetime.utcnow().isoformat(),
    }
