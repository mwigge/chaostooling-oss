"""
DEPRECATED: This module has been merged into baseline_manager.py

Please use baseline_manager.py instead:
    python tools/baseline_manager.py analyze --period 14d --output-dir ./analysis

This file is kept for backward compatibility and will be removed in a future release.

Legacy documentation:
Steady State Analyzer - Step 1 of Chaos Engineering Workflow

This module analyzes historical observability data to establish:
1. Service baselines (metrics, latency, throughput, error rates)
2. SLO targets
3. Service topology and dependencies
4. Anomaly detection thresholds
5. Cyclical patterns (daily, weekly)

Used to initialize the chaos platform and detect deviations during experiments.
"""

import logging
import statistics
import warnings
from datetime import datetime, timedelta

import requests

logger = logging.getLogger(__name__)

# Show deprecation warning
warnings.warn(
    "steady_state_analyzer.py is deprecated. Use 'tools/baseline_manager.py analyze' instead.",
    DeprecationWarning,
    stacklevel=2,
)


class SteadyStateAnalyzer:
    """
    Analyze historical data to define system steady state.

    This is Step 1 of the chaos engineering workflow.
    Outputs:
    - baseline_metrics.json (per-service metric statistics)
    - slo_targets.json (SLO definitions)
    - service_topology.json (dependencies, SPOFs)
    - anomaly_detection_model.json (thresholds)
    """

    def __init__(
        self,
        prometheus_url: str,
        tempo_url: str,
        loki_url: str,
        analysis_period_days: int = 14,
    ):
        self.prometheus_url = prometheus_url
        self.tempo_url = tempo_url
        self.loki_url = loki_url
        self.analysis_period_days = analysis_period_days
        self.analysis_end_time = datetime.utcnow()
        self.analysis_start_time = self.analysis_end_time - timedelta(
            days=analysis_period_days
        )

    def analyze(self) -> dict:
        """
        Execute full steady state analysis.

        Returns:
            Dictionary containing:
            - baseline_metrics
            - slo_targets
            - service_topology
            - anomaly_thresholds
            - analysis_report
        """
        logger.info(
            f"Starting steady state analysis for {self.analysis_period_days} days"
        )
        logger.info(f"Period: {self.analysis_start_time} to {self.analysis_end_time}")

        # Phase 1: Collect and normalize data
        metrics_data = self._collect_metrics()
        trace_data = self._collect_traces()
        self._collect_logs()

        # Phase 2: Calculate baselines
        baselines = self._calculate_baselines(metrics_data)
        slos = self._generate_slos(baselines)
        topology = self._analyze_service_topology(trace_data)
        anomaly_thresholds = self._calculate_anomaly_thresholds(baselines)

        # Phase 3: Generate report
        report = self._generate_report(baselines, slos, topology, anomaly_thresholds)

        return {
            "baseline_metrics": baselines,
            "slo_targets": slos,
            "service_topology": topology,
            "anomaly_thresholds": anomaly_thresholds,
            "analysis_report": report,
            "analysis_period": {
                "start": self.analysis_start_time.isoformat(),
                "end": self.analysis_end_time.isoformat(),
                "days": self.analysis_period_days,
            },
        }

    def _collect_metrics(self) -> dict:
        """Collect raw metrics from Prometheus"""
        logger.info("Collecting metrics from Prometheus...")

        metrics_to_collect = [
            'http_request_duration_seconds_bucket{le="+Inf"}',
            "http_requests_total",
            "http_request_errors_total",
            "http_request_duration_seconds",
            "process_resident_memory_bytes",
            "process_cpu_seconds_total",
            "go_goroutines",
        ]

        collected = {}

        for metric in metrics_to_collect:
            try:
                data = self._query_prometheus_range(metric)
                if data.get("status") == "success":
                    collected[metric] = data.get("data", {})
                    logger.info(f"  ✓ Collected: {metric}")
                else:
                    logger.warning(f"  ✗ Failed to collect: {metric}")
            except Exception as e:
                logger.warning(f"  ✗ Error collecting {metric}: {e}")

        return collected

    def _collect_traces(self) -> dict:
        """Collect trace data from Tempo"""
        logger.info("Collecting traces from Tempo...")

        try:
            response = requests.get(
                f"{self.tempo_url}/api/search",
                params={
                    "start": int(self.analysis_start_time.timestamp() * 1e9),
                    "end": int(self.analysis_end_time.timestamp() * 1e9),
                    "limit": 10000,
                },
                timeout=60,
            )
            response.raise_for_status()
            traces = response.json()
            logger.info(f"  ✓ Collected {len(traces.get('traces', []))} traces")
            return traces
        except Exception as e:
            logger.warning(f"  ✗ Error collecting traces: {e}")
            return {"traces": []}

    def _collect_logs(self) -> dict:
        """Collect logs from Loki"""
        logger.info("Collecting logs from Loki...")

        try:
            response = requests.get(
                f"{self.loki_url}/loki/api/v1/query_range",
                params={
                    "query": '{severity="ERROR"} or {severity="WARN"}',
                    "start": int(self.analysis_start_time.timestamp() * 1e9),
                    "end": int(self.analysis_end_time.timestamp() * 1e9),
                    "limit": 50000,
                },
                timeout=60,
            )
            response.raise_for_status()
            logs = response.json()
            logger.info("  ✓ Collected logs from Loki")
            return logs
        except Exception as e:
            logger.warning(f"  ✗ Error collecting logs: {e}")
            return {"data": {"result": []}}

    def _calculate_baselines(self, metrics_data: dict) -> dict:
        """
        Calculate baseline statistics for each metric and service.

        For each metric:
        - Mean (μ)
        - Standard deviation (σ)
        - Percentiles (P50, P95, P99)
        - Min/max
        """
        logger.info("Calculating metric baselines...")

        baselines = {}

        for metric_name, metric_data in metrics_data.items():
            services_data = {}

            # Extract values per service
            if isinstance(metric_data, dict) and "result" in metric_data:
                for result in metric_data.get("result", []):
                    labels = result.get("metric", {})
                    service = labels.get("service", labels.get("job", "unknown"))
                    values = [float(v[1]) for v in result.get("values", [])]

                    if values:
                        services_data[service] = {
                            "mean": statistics.mean(values),
                            "median": statistics.median(values),
                            "stdev": (
                                statistics.stdev(values) if len(values) > 1 else 0
                            ),
                            "min": min(values),
                            "max": max(values),
                            "p50": self._percentile(values, 50),
                            "p95": self._percentile(values, 95),
                            "p99": self._percentile(values, 99),
                            "count": len(values),
                        }

            baselines[metric_name] = services_data
            logger.info(f"  ✓ Calculated baseline for {metric_name}")

        return baselines

    def _generate_slos(self, baselines: dict) -> dict:
        """Generate SLO targets based on baselines"""
        logger.info("Generating SLO targets...")

        slos = {}

        # Latency SLOs (p99 + margin)
        latency_metric = "http_request_duration_seconds"
        if latency_metric in baselines:
            slos["latency"] = {}
            for service, stats in baselines[latency_metric].items():
                # SLO: P99 + 10% margin
                target = stats["p99"] * 1.1
                slos["latency"][service] = {
                    "p99_ms": stats["p99"] * 1000,
                    "slo_target_ms": target * 1000,
                    "unit": "milliseconds",
                }

        # Throughput SLOs (mean - margin)
        throughput_metric = "http_requests_total"
        if throughput_metric in baselines:
            slos["throughput"] = {}
            for service, stats in baselines[throughput_metric].items():
                # SLO: Mean - 10%
                target = stats["mean"] * 0.9
                slos["throughput"][service] = {
                    "baseline_rps": stats["mean"],
                    "slo_target_rps": target,
                    "unit": "requests_per_second",
                }

        # Error Rate SLOs (< 0.5%)
        error_metric = "http_request_errors_total"
        if error_metric in baselines:
            slos["error_rate"] = {}
            for service, stats in baselines[error_metric].items():
                slos["error_rate"][service] = {
                    "baseline_errors": stats["mean"],
                    "slo_max_percent": 0.5,
                    "unit": "percent",
                }

        logger.info(f"  ✓ Generated SLOs for {len(slos)} categories")
        return slos

    def _analyze_service_topology(self, trace_data: dict) -> dict:
        """
        Analyze service topology from traces.

        Identifies:
        - Service call graph
        - Critical paths
        - Single points of failure (SPOF)
        """
        logger.info("Analyzing service topology...")

        service_calls = {}  # From→To relationships
        service_latencies = {}  # Latencies per hop

        for trace in trace_data.get("traces", []):
            trace.get("traceID", "unknown")
            # This would need full trace parsing
            # For now, simplified version

        # Build graph from call relationships
        graph = {
            "nodes": list(set(list(service_calls.keys()))),
            "edges": [
                {"from": src, "to": dst, "avg_latency_ms": latency}
                for (src, dst), latency in service_latencies.items()
            ],
            "critical_paths": self._identify_critical_paths(service_calls),
            "single_points_of_failure": self._identify_spofs(service_calls),
        }

        logger.info(f"  ✓ Identified {len(graph['nodes'])} services")
        return graph

    def _calculate_anomaly_thresholds(self, baselines: dict) -> dict:
        """
        Calculate dynamic anomaly detection thresholds.

        Using: mean ± (2 * stdev) for each metric
        """
        logger.info("Calculating anomaly thresholds...")

        thresholds = {}

        for metric_name, services_data in baselines.items():
            thresholds[metric_name] = {}
            for service, stats in services_data.items():
                mean = stats["mean"]
                stdev = stats["stdev"]

                thresholds[metric_name][service] = {
                    "lower_bound": mean - (2 * stdev),
                    "upper_bound": mean + (2 * stdev),
                    "critical_upper": mean + (3 * stdev),
                    "mean": mean,
                    "stdev": stdev,
                }

        logger.info(f"  ✓ Calculated thresholds for {len(thresholds)} metrics")
        return thresholds

    def _generate_report(
        self, baselines: dict, slos: dict, topology: dict, thresholds: dict
    ) -> dict:
        """Generate human-readable analysis report"""

        return {
            "summary": {
                "analysis_period_days": self.analysis_period_days,
                "services_analyzed": len(topology.get("nodes", [])),
                "critical_paths": len(topology.get("critical_paths", [])),
                "spofs": len(topology.get("single_points_of_failure", [])),
            },
            "key_findings": self._extract_key_findings(baselines, topology),
            "recommendations": self._generate_recommendations(baselines, topology),
            "data_completeness": self._estimate_data_quality(baselines),
        }

    def _extract_key_findings(self, baselines: dict, topology: dict) -> list[str]:
        """Extract key findings from analysis"""
        findings = []

        # Find slowest services
        if "http_request_duration_seconds" in baselines:
            latency_data = baselines["http_request_duration_seconds"]
            slowest = max(
                latency_data.items(),
                key=lambda x: x[1].get("p99", 0),
                default=("unknown", {}),
            )
            if slowest[0] != "unknown":
                findings.append(
                    f"Slowest service: {slowest[0]} "
                    f"(P99: {slowest[1].get('p99', 0):.0f}ms)"
                )

        # Find services with highest error rates
        if "http_request_errors_total" in baselines:
            error_data = baselines["http_request_errors_total"]
            highest_errors = max(
                error_data.items(),
                key=lambda x: x[1].get("mean", 0),
                default=("unknown", {}),
            )
            if highest_errors[0] != "unknown":
                findings.append(
                    f"Highest error rate: {highest_errors[0]} "
                    f"({highest_errors[1].get('mean', 0):.2f}%)"
                )

        # Identify SPOFs
        spofs = topology.get("single_points_of_failure", [])
        if spofs:
            findings.append(f"Identified {len(spofs)} single points of failure")

        return findings

    def _generate_recommendations(self, baselines: dict, topology: dict) -> list[str]:
        """Generate improvement recommendations"""
        recommendations = []

        # Check for services with high latency variance
        if "http_request_duration_seconds" in baselines:
            latency_data = baselines["http_request_duration_seconds"]
            for service, stats in latency_data.items():
                if stats["stdev"] > stats["mean"] * 0.5:  # High variance
                    recommendations.append(
                        f"Service {service} has high latency variance. "
                        "Consider investigating root causes or adding caching."
                    )

        # Recommend testing for SPOFs
        spofs = topology.get("single_points_of_failure", [])
        if spofs:
            recommendations.append(
                f"Run chaos tests for identified SPOFs: {', '.join(spofs)}"
            )

        return recommendations

    def _estimate_data_quality(self, baselines: dict) -> dict:
        """Estimate quality of collected data"""
        total_metrics = sum(
            sum(1 for _ in services.values()) for services in baselines.values()
        )

        return {
            "total_metric_series": total_metrics,
            "estimated_completeness_percent": (
                min(total_metrics / 50, 1.0) * 100
            ),  # Heuristic
            "recommended_analysis_period": "14 days minimum",
        }

    def _query_prometheus_range(self, query: str) -> dict:
        """Query Prometheus range query"""
        try:
            response = requests.get(
                f"{self.prometheus_url}/api/v1/query_range",
                params={
                    "query": query,
                    "start": int(self.analysis_start_time.timestamp()),
                    "end": int(self.analysis_end_time.timestamp()),
                    "step": "60",
                },
                timeout=30,
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Prometheus query failed: {e}")
            return {"status": "error"}

    @staticmethod
    def _percentile(data: list[float], percentile: int) -> float:
        """Calculate percentile of a dataset"""
        sorted_data = sorted(data)
        index = (percentile / 100) * len(sorted_data)
        if index.is_integer():
            return sorted_data[int(index) - 1]
        else:
            return sorted_data[int(index)]

    @staticmethod
    def _identify_critical_paths(service_calls: dict) -> list[list[str]]:
        """Identify critical paths through service topology"""
        # Simplified: return empty for now
        return []

    @staticmethod
    def _identify_spofs(service_calls: dict) -> list[str]:
        """Identify single points of failure"""
        # Simplified: return empty for now
        return []


def create_steady_state_analyzer(
    prometheus_url: str = "http://localhost:9090",
    tempo_url: str = "http://localhost:3100",
    loki_url: str = "http://localhost:3100",
    analysis_period_days: int = 14,
) -> SteadyStateAnalyzer:
    """Factory function to create analyzer"""
    return SteadyStateAnalyzer(
        prometheus_url=prometheus_url,
        tempo_url=tempo_url,
        loki_url=loki_url,
        analysis_period_days=analysis_period_days,
    )
