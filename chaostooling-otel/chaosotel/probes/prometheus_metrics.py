import time
from typing import List

import requests
from logzero import logger


def verify_metrics_exported(
    prometheus_url: str,
    required_metrics: List[str],
    timeout: int = 30,
) -> bool:
    """
    Verify that the specified metrics are present in Prometheus.
    """
    start_time = time.time()
    end_time = start_time + timeout

    missing_metrics = set(required_metrics)

    while time.time() < end_time and missing_metrics:
        for metric in list(missing_metrics):
            try:
                # Query for the metric existence
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
            except Exception as e:
                logger.debug(f"Failed to query metric {metric}: {e}")

        if missing_metrics:
            time.sleep(2)

    if missing_metrics:
        logger.error(f"Missing metrics in Prometheus: {missing_metrics}")
        return False

    logger.info("All required metrics found in Prometheus")
    return True
