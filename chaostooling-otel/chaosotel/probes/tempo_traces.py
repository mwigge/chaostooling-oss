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
    """
    start_time = time.time()
    end_time = start_time + timeout

    while time.time() < end_time:
        try:
            # Search for traces from the service in the last hour
            # Tempo search API: /api/search?q={service_name="..."}
            # Note: Tempo API might vary, using a common query pattern
            response = requests.get(
                f"{tempo_url}/api/search",
                params={"tags": f'service.name="{service_name}"', "limit": 1},
                timeout=5,
            )

            if response.status_code == 200:
                data = response.json()
                if data.get("traces"):
                    logger.info(f"Traces found for service: {service_name}")
                    return True
        except Exception as e:
            logger.debug(f"Failed to query traces: {e}")

        time.sleep(2)

    logger.error(f"No traces found for service {service_name} in Tempo")
    return False
