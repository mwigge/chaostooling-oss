import logging
import time
from typing import Union

logger = logging.getLogger("chaostoolkit")


def sleep(seconds: Union[int, str] = 1):
    """
    Sleep for a given number of seconds.

    :param seconds: Number of seconds to sleep (can be int or string from env vars)
    """
    # Handle string input from Chaos Toolkit configuration
    if isinstance(seconds, str):
        seconds = int(seconds)

    logger.info(f"Sleeping for {seconds} seconds...")
    time.sleep(seconds)
