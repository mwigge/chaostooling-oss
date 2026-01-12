import time
import logging

logger = logging.getLogger("chaostoolkit")

def sleep(seconds: int = 1):
    """
    Sleep for a given number of seconds.
    
    :param seconds: Number of seconds to sleep
    """
    logger.info(f"Sleeping for {seconds} seconds...")
    time.sleep(seconds)
