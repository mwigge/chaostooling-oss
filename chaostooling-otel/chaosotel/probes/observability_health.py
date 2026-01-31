import time

import requests
from logzero import logger


def check_prometheus_health(
    prometheus_url: str, retries: int = 5, delay: int = 2
) -> bool:
    """
    Checks if Prometheus is healthy by querying its health endpoint.
    """
    url = f"{prometheus_url}/-/healthy"
    for i in range(retries):
        try:
            response = requests.get(url, timeout=5)
            if response.status_code == 200:
                logger.info(f"Prometheus at {prometheus_url} is healthy.")
                return True
            else:
                logger.warning(
                    f"Prometheus at {prometheus_url} returned status {response.status_code}: {response.text}. Retrying ({i + 1}/{retries})..."
                )
        except requests.RequestException as e:
            logger.warning(
                f"Failed to connect to Prometheus at {prometheus_url}: {e}. Retrying ({i + 1}/{retries})..."
            )

        time.sleep(delay)

    logger.error(
        f"Prometheus at {prometheus_url} is not healthy after {retries} retries."
    )
    return False


def check_tempo_health(tempo_url: str, retries: int = 10, delay: int = 3) -> bool:
    """
    Checks if Tempo is healthy by querying its ready endpoint.
    """
    url = f"{tempo_url}/ready"
    for i in range(retries):
        try:
            response = requests.get(url, timeout=5)
            if response.status_code == 200:
                logger.info(f"Tempo at {tempo_url} is ready.")
                return True
            else:
                logger.warning(
                    f"Tempo at {tempo_url} returned status {response.status_code}: {response.text}. Retrying ({i + 1}/{retries})..."
                )
        except requests.RequestException as e:
            logger.warning(
                f"Failed to connect to Tempo at {tempo_url}: {e}. Retrying ({i + 1}/{retries})..."
            )

        time.sleep(delay)

    logger.error(f"Tempo at {tempo_url} is not ready after {retries} retries.")
    return False


def check_loki_health(loki_url: str, retries: int = 15, delay: int = 3) -> bool:
    """
    Checks if Loki is healthy by querying its ready endpoint.
    """
    url = f"{loki_url}/ready"
    for i in range(retries):
        try:
            response = requests.get(url, timeout=5)
            if response.status_code == 200:
                logger.info(f"Loki at {loki_url} is ready.")
                return True
            else:
                logger.warning(
                    f"Loki at {loki_url} returned status {response.status_code}: {response.text}. Retrying ({i + 1}/{retries})..."
                )
        except requests.RequestException as e:
            logger.warning(
                f"Failed to connect to Loki at {loki_url}: {e}. Retrying ({i + 1}/{retries})..."
            )

        time.sleep(delay)

    logger.error(f"Loki at {loki_url} is not ready after {retries} retries.")
    return False
