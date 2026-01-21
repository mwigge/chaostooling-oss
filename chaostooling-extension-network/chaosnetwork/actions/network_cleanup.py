import logging
import subprocess

from logzero import logger


def restore_network_conditions() -> bool:
    """
    Restore normal network conditions by deleting qdisc rules on eth0.
    """
    try:
        # Delete root qdisc on eth0 (clears netem delay/loss/corruption)
        subprocess.run(
            ["tc", "qdisc", "del", "dev", "eth0", "root"],
            capture_output=True,
            text=True,
            check=False,  # Don't raise if it fails (e.g. no qdisc exists)
        )
        logger.info("Restored network conditions (cleared tc qdisc)")
        return True
    except Exception as e:
        logger.error(f"Failed to restore network conditions: {e}")
        return False
