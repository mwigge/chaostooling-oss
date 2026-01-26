"""
Input validation utilities for chaosdb extension.

Provides validation functions for database connection parameters,
ports, timeouts, and other common inputs.
"""

import logging
from typing import Optional, Union

logger = logging.getLogger(__name__)


def validate_port(
    port: Optional[Union[int, str]], default: int, name: str = "port"
) -> int:
    """
    Validate and return a valid port number.

    Args:
        port: Port number to validate (can be None, int, or str)
        default: Default port if port is None or invalid
        name: Name of the parameter for error messages

    Returns:
        Valid port number (1-65535)

    Raises:
        ValueError: If port is out of valid range
    """
    if port is None:
        return default

    # Handle string input from Chaos Toolkit configuration
    if isinstance(port, str):
        try:
            port = int(port)
        except ValueError:
            logger.warning(f"Invalid {name} '{port}', using default {default}")
            return default

    if not isinstance(port, int) or port < 1 or port > 65535:
        logger.warning(f"Invalid {name} {port}, using default {default}")
        return default

    return port


def validate_host(host: Optional[str], default: str, name: str = "host") -> str:
    """
    Validate and return a valid hostname or IP address.

    Args:
        host: Hostname or IP address to validate
        default: Default host if host is None or empty
        name: Name of the parameter for error messages

    Returns:
        Valid hostname or IP address
    """
    if not host or not host.strip():
        return default

    return host.strip()


def validate_database_name(
    database: Optional[str], default: str, name: str = "database"
) -> str:
    """
    Validate and return a valid database name.

    Args:
        database: Database name to validate
        default: Default database name if database is None or empty
        name: Name of the parameter for error messages

    Returns:
        Valid database name
    """
    if not database or not database.strip():
        return default

    db_name = database.strip()
    # Basic validation: database names should not contain certain characters
    if any(char in db_name for char in ['"', "'", ";", "--"]):
        logger.warning(
            f"Potentially unsafe {name} '{db_name}', using default {default}"
        )
        return default

    return db_name


def validate_timeout(
    timeout: Optional[Union[int, str]],
    default: int,
    min_value: int = 1,
    max_value: int = 3600,
) -> int:
    """
    Validate and return a valid timeout value in seconds.

    Args:
        timeout: Timeout value to validate (can be None, int, or str)
        default: Default timeout if timeout is None or invalid
        min_value: Minimum allowed timeout
        max_value: Maximum allowed timeout

    Returns:
        Valid timeout value
    """
    if timeout is None:
        return default

    # Handle string input from Chaos Toolkit configuration
    if isinstance(timeout, str):
        try:
            timeout = int(timeout)
        except ValueError:
            logger.warning(f"Invalid timeout '{timeout}', using default {default}")
            return default

    if not isinstance(timeout, int) or timeout < min_value or timeout > max_value:
        logger.warning(
            f"Timeout {timeout} out of range [{min_value}, {max_value}], "
            f"using default {default}"
        )
        return default

    return timeout


def validate_positive_int(
    value: Optional[Union[int, str]],
    default: int,
    name: str = "value",
    min_value: int = 1,
) -> int:
    """
    Validate and return a positive integer.

    Args:
        value: Value to validate (can be None, int, or str)
        default: Default value if value is None or invalid
        name: Name of the parameter for error messages
        min_value: Minimum allowed value

    Returns:
        Valid positive integer
    """
    if value is None:
        return default

    # Handle string input from Chaos Toolkit configuration
    if isinstance(value, str):
        try:
            value = int(value)
        except ValueError:
            logger.warning(f"Invalid {name} '{value}', using default {default}")
            return default

    if not isinstance(value, int) or value < min_value:
        logger.warning(
            f"Invalid {name} {value} (must be >= {min_value}), using default {default}"
        )
        return default

    return value
