import time

import requests
from logzero import logger


def verify_metrics_exported(
    prometheus_url: str,
    required_metrics: list[str],
    timeout: int = 30,
) -> bool:
    """
    Verify that the specified metrics are present in Prometheus.

    Handles OpenTelemetry metric name prefixes that may be added by OTEL Collector.
    Common prefixes: chaosotel_, chaos_, or meter name prefixes.
    """
    start_time = time.time()
    end_time = start_time + timeout

    missing_metrics = set(required_metrics)

    while time.time() < end_time and missing_metrics:
        for metric in list(missing_metrics):
            try:
                # Try the metric name as-is first
                response = requests.get(
                    f"{prometheus_url}/api/v1/query",
                    params={"query": metric},
                    timeout=5,
                )
                if response.status_code == 200:
                    data = response.json()
                    if data.get("status") == "success" and data.get("data", {}).get(
                        "result"
                    ):
                        logger.info(f"Metric found: {metric}")
                        missing_metrics.remove(metric)
                        continue

                # If not found, try common OTEL prefixes
                # OTEL Collector may prefix metrics with meter name or service name
                prefixes = ["chaosotel_", "chaos_", "otel_"]
                found = False
                for prefix in prefixes:
                    prefixed_metric = f"{prefix}{metric}"
                    response = requests.get(
                        f"{prometheus_url}/api/v1/query",
                        params={"query": prefixed_metric},
                        timeout=5,
                    )
                    if response.status_code == 200:
                        data = response.json()
                        if data.get("status") == "success" and data.get("data", {}).get(
                            "result"
                        ):
                            logger.info(
                                f"Metric found with prefix: {prefixed_metric} (searched for: {metric})"
                            )
                            missing_metrics.remove(metric)
                            found = True
                            break

                if not found:
                    # Try querying all metrics to see what's available
                    response = requests.get(
                        f"{prometheus_url}/api/v1/label/__name__/values",
                        timeout=5,
                    )
                    if response.status_code == 200:
                        data = response.json()
                        available_metrics = data.get("data", [])
                        # Check if any available metric contains our metric name
                        matching = [m for m in available_metrics if metric in m]
                        if matching:
                            logger.debug(f"Found similar metrics: {matching[:5]}")
            except Exception as e:
                logger.debug(f"Failed to query metric {metric}: {e}")

        if missing_metrics:
            time.sleep(2)

    if missing_metrics:
        logger.error(f"Missing metrics in Prometheus: {missing_metrics}")
        logger.info(
            "Note: Metrics may be prefixed by OTEL Collector (e.g., chaosotel_chaos_experiment_success_ratio)"
        )
        logger.info(
            "Note: Some metrics (like chaos_experiment_success_ratio) are only recorded after experiment completion"
        )
        return False

    logger.info("All required metrics found in Prometheus")
    return True
