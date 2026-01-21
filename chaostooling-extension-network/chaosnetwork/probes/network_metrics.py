from typing import Optional

from chaosnetwork.probes.network_latency import probe_network_latency
from logzero import logger


def check_network_latency(
    target_host: str,
    max_latency_ms: Optional[float] = None,
) -> float:
    """
    Check network latency to the target host.
    Returns the average latency in milliseconds.
    """
    # Default count and timeout as per original probe defaults or sensible values
    result = probe_network_latency(target_host, count=5, timeout=5)
    avg_latency = result.get("latency_avg_ms", 0.0)

    if max_latency_ms is not None and avg_latency > max_latency_ms:
        logger.warning(
            f"Network latency {avg_latency}ms exceeds threshold {max_latency_ms}ms"
        )

    return float(avg_latency)
