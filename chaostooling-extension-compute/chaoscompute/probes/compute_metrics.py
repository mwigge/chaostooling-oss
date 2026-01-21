from typing import Optional

from chaoscompute.probes.compute_system import get_cpu_usage
from logzero import logger


def check_cpu_usage(max_cpu_percent: Optional[float] = None) -> float:
    """
    Check the current CPU usage percentage.
    If max_cpu_percent is provided, it logs a warning if usage exceeds it,
    but the return value is always the actual usage.
    """
    usage = get_cpu_usage()
    if max_cpu_percent is not None and usage > max_cpu_percent:
        logger.warning(f"CPU usage {usage}% exceeds threshold {max_cpu_percent}%")

    return usage
