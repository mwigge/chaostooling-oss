"""
Chaos Toolkit actions for controlling background transaction load generator.

This allows Chaos Toolkit experiments to start/stop background transaction load
that simulates real-world distributed transactions across databases and messaging
systems.
"""

import logging
import os
from typing import Optional

import requests

logger = logging.getLogger("chaosgeneric.actions.load_generator")


def start_background_transaction_load(
    load_generator_url: Optional[str] = None,
    transactions_per_second: float = 2.0,
    timeout: int = 10,
) -> dict:
    """
    Start background transaction load generator.

    This starts continuous transaction generation that flows through:
    - App Server → Payment Service → RabbitMQ → PostgreSQL
    - App Server → Order Service → Kafka → MySQL
    - App Server → Inventory Service → MongoDB → Redis
    - Event-driven updates to MSSQL, Cassandra via messaging

    Args:
        load_generator_url: URL of the load generator service
            (default: http://transaction-load-generator:5001)
        transactions_per_second: Target transactions per second (default: 2.0)
        timeout: Request timeout in seconds (default: 10)

    Returns:
        Dict with status and TPS information
    """
    url = load_generator_url or os.getenv(
        "TRANSACTION_LOAD_GENERATOR_URL",
        "http://transaction-load-generator:5001",
    )

    try:
        response = requests.post(
            f"{url}/start", json={"tps": transactions_per_second}, timeout=timeout
        )
        response.raise_for_status()
        result = response.json()

        logger.info(
            f"Started background transaction load: {transactions_per_second} TPS",
            extra={"tps": transactions_per_second, "url": url},
        )

        return result
    except requests.exceptions.RequestException as e:
        logger.error(f"Failed to start load generator: {e}", extra={"url": url})
        raise


def stop_background_transaction_load(
    load_generator_url: Optional[str] = None, timeout: int = 10
) -> dict:
    """
    Stop background transaction load generator.

    Args:
        load_generator_url: URL of the load generator service
            (default: http://transaction-load-generator:5001)
        timeout: Request timeout in seconds (default: 10)

    Returns:
        Dict with status and statistics
    """
    url = load_generator_url or os.getenv(
        "TRANSACTION_LOAD_GENERATOR_URL",
        "http://transaction-load-generator:5001",
    )

    try:
        response = requests.post(f"{url}/stop", timeout=timeout)
        response.raise_for_status()
        result = response.json()

        logger.info(
            "Stopped background transaction load",
            extra={"stats": result.get("stats", {}), "url": url},
        )

        return result
    except requests.exceptions.RequestException as e:
        logger.error(f"Failed to stop load generator: {e}", extra={"url": url})
        raise


def get_background_load_stats(
    load_generator_url: Optional[str] = None, timeout: int = 10
) -> dict:
    """
    Get current background transaction load statistics.

    Args:
        load_generator_url: URL of the load generator service
            (default: http://transaction-load-generator:5001)
        timeout: Request timeout in seconds (default: 10)

    Returns:
        Dict with statistics (total, successful, failed, TPS, etc.)
    """
    url = load_generator_url or os.getenv(
        "TRANSACTION_LOAD_GENERATOR_URL",
        "http://transaction-load-generator:5001",
    )

    try:
        response = requests.get(f"{url}/stats", timeout=timeout)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        logger.error(f"Failed to get load stats: {e}", extra={"url": url})
        raise
