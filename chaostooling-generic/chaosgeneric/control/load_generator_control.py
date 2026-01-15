"""
Chaos Toolkit control module for background transaction load generator.

Automatically starts load generator before experiment and stops it after.
"""

import logging
from typing import Any, Optional

from ..actions.load_generator.transaction_load_generator import (
    start_background_transaction_load,
    stop_background_transaction_load,
)

logger = logging.getLogger("chaosgeneric.control.load_generator")

# Global state
_load_generator_started = False
_load_generator_config: Optional[dict[str, Any]] = None


def configure_control(
    control: Any = None,
    experiment: Optional[dict[str, Any]] = None,
    configuration: Optional[dict[str, Any]] = None,
    **kwargs: Any,
) -> None:
    """
    Configure control - called once before experiment.
    Stores configuration for later use.
    """
    global _load_generator_config

    config = configuration or {}

    # Get load generator settings from configuration
    load_generator_url = config.get(
        "load_generator_url", "http://transaction-load-generator:5001"
    )
    load_generator_tps = float(config.get("load_generator_tps", "2.0"))
    auto_start = config.get("auto_start_load_generator", "true").lower() == "true"

    _load_generator_config = {
        "url": load_generator_url,
        "tps": load_generator_tps,
        "auto_start": auto_start,
    }

    logger.info(
        f"Load generator control configured: url={load_generator_url}, "
        f"tps={load_generator_tps}, auto_start={auto_start}"
    )


def before_experiment_control(
    context: Any,
    state: Any,
    experiment: dict[str, Any],
    **kwargs: Any,
) -> None:
    """
    Start load generator before experiment begins.
    Called after configure_control and before steady-state hypothesis.
    """
    global _load_generator_started, _load_generator_config

    if (
        not _load_generator_config
        or not _load_generator_config.get("auto_start", True)
    ):
        logger.info("Load generator auto-start is disabled, skipping")
        return

    try:
        url = _load_generator_config["url"]
        tps = _load_generator_config["tps"]

        logger.info(
            f"Starting background transaction load generator: {tps} TPS"
        )
        result = start_background_transaction_load(
            load_generator_url=url,
            transactions_per_second=tps,
        )

        _load_generator_started = True
        logger.info(f"Load generator started successfully: {result}")

        # Verify load generator is actually running
        from ..actions.load_generator.transaction_load_generator import (
            get_background_load_stats,
        )

        try:
            stats = get_background_load_stats(load_generator_url=url)
            logger.info(f"Load generator verification: {stats}")
        except Exception as verify_error:
            logger.warning(f"Could not verify load generator status: {verify_error}")

    except Exception as e:
        logger.warning(f"Failed to start load generator: {e}")
        # Don't fail the experiment if load generator fails to start
        _load_generator_started = False


def after_experiment_control(
    context: Any,
    state: Any,
    experiment: dict[str, Any],
    **kwargs: Any,
) -> None:
    """
    Stop load generator after experiment completes.
    """
    global _load_generator_started, _load_generator_config

    if not _load_generator_started:
        return

    try:
        url = (
            _load_generator_config["url"]
            if _load_generator_config
            else "http://transaction-load-generator:5001"
        )

        logger.info("Stopping background transaction load generator")
        result = stop_background_transaction_load(load_generator_url=url)

        logger.info(f"Load generator stopped: {result}")
        _load_generator_started = False

    except Exception as e:
        logger.warning(f"Failed to stop load generator: {e}")


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
    logger.info("Load generator control loaded")
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
    Ensures load generator is stopped.
    """
    logger.info("Load generator control unloaded")
    cleanup_control(control=None, experiment=experiment, **kwargs)


def cleanup_control(
    control: Any = None,
    experiment: Optional[dict[str, Any]] = None,
    **kwargs: Any,
) -> None:
    """
    Cleanup - ensure load generator is stopped.
    """
    global _load_generator_started, _load_generator_config

    if _load_generator_started:
        try:
            url = (
                _load_generator_config["url"]
                if _load_generator_config
                else "http://transaction-load-generator:5001"
            )
            stop_background_transaction_load(load_generator_url=url)
            _load_generator_started = False
        except Exception as e:
            logger.warning(f"Failed to stop load generator during cleanup: {e}")

