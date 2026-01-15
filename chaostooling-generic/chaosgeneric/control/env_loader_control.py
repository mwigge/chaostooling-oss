"""
Chaos Toolkit control module for loading environment variables from .env files.

Automatically loads environment variables from a .env file matching the experiment name
(e.g., test-kafka-topic-saturation.env for test-kafka-topic-saturation.json).
"""

import logging
import os
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger("chaosgeneric.control.env_loader")

# Track if env vars were loaded
_env_loaded = False
_env_file_path: Optional[str] = None


def _parse_env_file(file_path: Path) -> dict[str, str]:
    """
    Parse a .env file and return a dictionary of key-value pairs.

    Supports:
    - KEY=value
    - KEY="value with spaces"
    - KEY='value with spaces'
    - Comments starting with #
    - Empty lines
    """
    env_vars = {}

    if not file_path.exists():
        return env_vars

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            for line in f:
                # Strip whitespace
                line = line.strip()

                # Skip empty lines and comments
                if not line or line.startswith("#"):
                    continue

                # Parse KEY=value
                if "=" in line:
                    # Split on first = only
                    key, value = line.split("=", 1)
                    key = key.strip()
                    value = value.strip()

                    # Remove quotes if present
                    if value.startswith('"') and value.endswith('"'):
                        value = value[1:-1]
                    elif value.startswith("'") and value.endswith("'"):
                        value = value[1:-1]

                    # Only set if not already in environment (env vars take precedence)
                    if key and key not in os.environ:
                        env_vars[key] = value
                    elif key in os.environ:
                        logger.debug(
                            f"Skipping {key} from .env file "
                            "(already set in environment)"
                        )

    except Exception as e:
        logger.warning(f"Failed to parse .env file {file_path}: {e}")

    return env_vars


def _find_env_file(experiment_path: Optional[str] = None) -> Optional[Path]:
    """
    Find the .env file for the experiment.

    Looks for:
    1. <experiment-name>.env in the same directory as the experiment file
    2. .env in the same directory as the experiment file
    3. .env in the current working directory

    Args:
        experiment_path: Path to the experiment JSON file (if available)

    Returns:
        Path to the .env file if found, None otherwise
    """
    # Try to find env file based on experiment path
    if experiment_path:
        exp_path = Path(experiment_path)
        if exp_path.exists():
            exp_dir = exp_path.parent
            exp_name = exp_path.stem  # filename without extension

            # Try <experiment-name>.env first
            candidate = exp_dir / f"{exp_name}.env"
            if candidate.exists():
                return candidate

            # Try .env in same directory
            candidate = exp_dir / ".env"
            if candidate.exists():
                return candidate

    # Try .env in current working directory
    cwd_env = Path.cwd() / ".env"
    if cwd_env.exists():
        return cwd_env

    return None


def configure_control(
    control: Any = None,
    experiment: Optional[dict[str, Any]] = None,
    configuration: Optional[dict[str, Any]] = None,
    **kwargs: Any,
) -> None:
    """
    Configure control - called once before experiment.
    """
    global _env_file_path

    config = configuration or {}

    # Get custom env file path from configuration if provided
    custom_env_file = config.get("env_file")
    if custom_env_file:
        _env_file_path = custom_env_file
        logger.info(f"Using custom env file: {custom_env_file}")
    else:
        # Try to get experiment path from kwargs or configuration
        experiment_path = kwargs.get("experiment_path") or config.get("experiment_path")
        _env_file_path = None

        if experiment_path:
            env_file = _find_env_file(experiment_path)
            if env_file:
                _env_file_path = str(env_file)
                logger.info(f"Found env file: {_env_file_path}")
            else:
                logger.debug("No .env file found for experiment")
        else:
            logger.debug(
                "No experiment path provided, will search in current directory"
            )

    logger.info("Environment loader control configured")


def before_experiment_control(
    context: Any,
    state: Any,
    experiment: dict[str, Any],
    **kwargs: Any,
) -> None:
    """
    Load environment variables from .env file before experiment begins.
    Called after configure_control and before steady-state hypothesis.
    """
    global _env_loaded, _env_file_path

    if _env_loaded:
        logger.debug("Environment variables already loaded, skipping")
        return

    # Find env file if not already found
    if not _env_file_path:
        # Try to get experiment path from various sources
        experiment_path = None

        # Check if experiment has a path attribute (Chaos Toolkit may set this)
        if hasattr(context, "experiment_path"):
            experiment_path = context.experiment_path
        elif isinstance(context, dict):
            experiment_path = context.get("experiment_path")

        # Try kwargs
        if not experiment_path:
            experiment_path = kwargs.get("experiment_path")

        env_file = _find_env_file(experiment_path)
        if env_file:
            _env_file_path = str(env_file)
        else:
            # Try current directory
            cwd_env = Path.cwd() / ".env"
            if cwd_env.exists():
                _env_file_path = str(cwd_env)

    if not _env_file_path:
        logger.debug("No .env file found, skipping environment variable loading")
        return

    env_file_path = Path(_env_file_path)
    if not env_file_path.exists():
        logger.warning(f"Env file not found: {env_file_path}")
        return

    try:
        logger.info(f"Loading environment variables from: {env_file_path}")
        env_vars = _parse_env_file(env_file_path)

        # Set environment variables
        vars_set = 0
        for key, value in env_vars.items():
            if key not in os.environ:
                os.environ[key] = value
                vars_set += 1
                logger.debug(f"Set {key}={value}")
            else:
                logger.debug(f"Skipped {key} (already in environment)")

        _env_loaded = True
        logger.info(
            f"Loaded {vars_set} environment variable(s) from {env_file_path}"
        )

        if vars_set == 0:
            logger.info(
                "No new environment variables were set "
                "(all already in environment)"
            )

    except Exception as e:
        logger.warning(
            f"Failed to load environment variables from {env_file_path}: {e}"
        )


def load_control(
    context: Any,
    experiment: dict[str, Any],
    configuration: dict[str, Any],
    **kwargs: Any,
) -> None:
    """
    Load control - called when control is loaded.
    This ensures the control is properly initialized.
    """
    logger.info("Environment loader control loaded")
    configure_control(
        control=None, experiment=experiment, configuration=configuration, **kwargs
    )


def unload_control(
    context: Any,
    experiment: dict[str, Any],
    configuration: dict[str, Any],
    **kwargs: Any,
) -> None:
    """
    Unload control - called when control is unloaded.
    """
    global _env_loaded, _env_file_path
    logger.info("Environment loader control unloaded")
    _env_loaded = False
    _env_file_path = None
