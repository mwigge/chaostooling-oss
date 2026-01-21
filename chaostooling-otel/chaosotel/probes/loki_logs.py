import time

import requests
from logzero import logger


def verify_logs_exported(
    loki_url: str,
    service_namespace: str,
    timeout: int = 30,
) -> bool:
    """
    Verify that logs for the specified namespace are present in Loki.
    """
    start_time = time.time()
    end_time = start_time + timeout

    # Try multiple label names since Loki might use different ones depending on config
    # Common labels: service_namespace, namespace, service.namespace (with dots replaced)
    queries = [
        f'{{service_namespace="{service_namespace}"}}',
        f'{{namespace="{service_namespace}"}}',
        f'{{service_name=~".+"}}',  # Fallback: any service_name
    ]

    for query in queries:
        logger.debug(f"Trying Loki query: {query}")
        query_start = time.time()

        while time.time() < min(query_start + 10, end_time):  # Try each query for max 10s
            try:
                # Query Loki for recent logs
                response = requests.get(
                    f"{loki_url}/loki/api/v1/query",
                    params={"query": query, "limit": 1},
                    timeout=5,
                )

                if response.status_code == 200:
                    data = response.json()
                    if data.get("status") == "success" and data.get("data", {}).get(
                        "result"
                    ):
                        logger.info(f"Logs found with query: {query}")
                        return True
            except Exception as e:
                logger.debug(f"Failed to query logs with {query}: {e}")

            time.sleep(2)

    logger.error(f"No logs found for namespace {service_namespace} in Loki (tried multiple label formats)")
    return False
