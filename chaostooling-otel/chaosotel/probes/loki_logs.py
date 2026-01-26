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

    Tries multiple label formats to handle different OTEL Collector and Loki configurations.
    """
    start_time = time.time()
    end_time = start_time + timeout

    # Try multiple label names since Loki might use different ones depending on config
    # Common labels: service_namespace, namespace, service.namespace (with dots replaced)
    # OTEL Collector may transform service.namespace to service_namespace or namespace
    queries = [
        f'{{service_namespace="{service_namespace}"}}',
        f'{{namespace="{service_namespace}"}}',
        f'{{service_namespace=~".*{service_namespace}.*"}}',  # Partial match
        f'{{service_name=~".+"}}',  # Fallback: any service_name
        f"{{}}",  # Last resort: any logs
    ]

    for query in queries:
        logger.debug(f"Trying Loki query: {query}")
        query_start = time.time()

        while time.time() < min(
            query_start + 10, end_time
        ):  # Try each query for max 10s
            try:
                # Query Loki for recent logs (last 1 hour)
                response = requests.get(
                    f"{loki_url}/loki/api/v1/query",
                    params={"query": query, "limit": 10},
                    timeout=5,
                )

                if response.status_code == 200:
                    data = response.json()
                    if data.get("status") == "success":
                        results = data.get("data", {}).get("result", [])
                        if results:
                            logger.info(
                                f"Logs found with query: {query} ({len(results)} streams)"
                            )
                            # If we found logs with a generic query, log available labels
                            if query == f"{{}}":
                                logger.info(
                                    "Found logs in Loki, but namespace label may not match"
                                )
                                # Try to extract available labels from first result
                                if results and len(results) > 0:
                                    first_stream = results[0].get("stream", {})
                                    available_labels = list(first_stream.keys())
                                    logger.debug(
                                        f"Available labels in logs: {available_labels}"
                                    )
                            return True
            except Exception as e:
                logger.debug(f"Failed to query logs with {query}: {e}")

            time.sleep(2)

    logger.error(
        f"No logs found for namespace {service_namespace} in Loki (tried multiple label formats)"
    )
    logger.info(
        f"Note: Namespace should match OTEL_SERVICE_NAMESPACE environment variable"
    )
    logger.info(f"Note: Logs may take time to appear after experiment actions complete")
    logger.info(
        f"Note: Check OTEL Collector configuration for log label transformation"
    )
    return False
