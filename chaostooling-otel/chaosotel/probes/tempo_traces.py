import time

import requests
from logzero import logger


def verify_traces_exported(
    tempo_url: str,
    service_name: str,
    timeout: int = 30,
) -> bool:
    """
    Verify that traces for the specified service are present in Tempo.

    Tries multiple query formats to handle different Tempo API versions and label formats.
    """
    start_time = time.time()
    end_time = start_time + timeout

    # Try multiple query formats
    query_formats = [
        f'service.name="{service_name}"',
        f'service_name="{service_name}"',
        f'resource.service.name="{service_name}"',
        f'name="{service_name}"',
    ]

    while time.time() < end_time:
        for query_tag in query_formats:
            try:
                # Try Tempo search API with tags parameter
                response = requests.get(
                    f"{tempo_url}/api/search",
                    params={"tags": query_tag, "limit": 1},
                    timeout=5,
                )

                if response.status_code == 200:
                    data = response.json()
                    # Tempo API may return traces in different formats
                    traces = data.get("traces") or data.get("data", {}).get(
                        "traces", []
                    )
                    if traces:
                        logger.info(
                            f"Traces found for service: {service_name} (using query: {query_tag})"
                        )
                        return True

                # Try alternative API format (some Tempo versions use 'q' parameter)
                response = requests.get(
                    f"{tempo_url}/api/search",
                    params={"q": query_tag, "limit": 1},
                    timeout=5,
                )

                if response.status_code == 200:
                    data = response.json()
                    traces = data.get("traces") or data.get("data", {}).get(
                        "traces", []
                    )
                    if traces:
                        logger.info(
                            f"Traces found for service: {service_name} (using q parameter)"
                        )
                        return True
            except Exception as e:
                logger.debug(f"Failed to query traces with {query_tag}: {e}")

        time.sleep(2)

    logger.error(f"No traces found for service {service_name} in Tempo")
    logger.info(
        f"Note: Service name should match OTEL_SERVICE_NAME environment variable"
    )
    logger.info(
        f"Note: Traces may take time to appear after experiment actions complete"
    )
    return False
