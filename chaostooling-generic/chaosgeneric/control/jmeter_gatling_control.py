"""
Chaos Toolkit control module for JMeter and Gatling load generators.

Automatically starts load generator (JMeter or Gatling) before experiment and stops it after.
Supports both tools via their APIs or CLI interfaces.
"""

import logging
from typing import Any, Optional

from ..actions.load_generator.gatling_api import (
    get_gatling_simulation_status,
    start_gatling_simulation,
    stop_gatling_simulation,
)
from ..actions.load_generator.jmeter_api import (
    get_jmeter_test_status,
    start_jmeter_test,
    stop_jmeter_test,
)

logger = logging.getLogger("chaosgeneric.control.jmeter_gatling")

# Global state
_load_generator_started = False
_load_generator_config: Optional[dict[str, Any]] = None
_load_generator_run_info: Optional[dict[str, Any]] = None


def configure_control(
    control: Any = None,
    experiment: Optional[dict[str, Any]] = None,
    configuration: Optional[dict[str, Any]] = None,
    **kwargs: Any,
) -> None:
    """
    Configure control - called once before experiment.
    Stores configuration for later use.

    Configuration options:
    - tool: "jmeter" or "gatling" (required)
    - auto_start: "true" or "false" (default: "true")

    For JMeter:
    - jmeter_test_plan: Path to .jmx test plan file
    - jmeter_home: JMeter installation directory
    - jmeter_api_url: URL of custom JMeter API wrapper (optional)
    - jmeter_remote_hosts: Comma-separated list of remote hosts
    - jmeter_properties: Dict of JMeter properties

    For Gatling:
    - gatling_simulation_class: Fully qualified simulation class name
    - gatling_simulation_path: Path to simulation file (optional)
    - gatling_home: Gatling installation directory
    - gatling_api_url: URL of Gatling Enterprise API (optional)
    - gatling_api_token: API token for Gatling Enterprise
    - gatling_team_id: Team ID for Gatling Enterprise
    - gatling_properties: Dict of simulation properties
    """
    global _load_generator_config

    config = configuration or {}

    tool = config.get("tool", "").lower()
    if tool not in ["jmeter", "gatling"]:
        raise ValueError(f"Invalid tool '{tool}'. Must be 'jmeter' or 'gatling'.")

    auto_start = config.get("auto_start_load_generator", "true").lower() == "true"

    _load_generator_config = {
        "tool": tool,
        "auto_start": auto_start,
    }

    # Tool-specific configuration
    if tool == "jmeter":
        _load_generator_config.update(
            {
                "test_plan": config.get("jmeter_test_plan"),
                "jmeter_home": config.get("jmeter_home"),
                "jmeter_api_url": config.get("jmeter_api_url"),
                "remote_hosts": config.get("jmeter_remote_hosts", "").split(",")
                if config.get("jmeter_remote_hosts")
                else None,
                "properties": config.get("jmeter_properties", {}),
                "results_file": config.get("jmeter_results_file"),
            }
        )
    elif tool == "gatling":
        _load_generator_config.update(
            {
                "simulation_class": config.get("gatling_simulation_class"),
                "simulation_path": config.get("gatling_simulation_path"),
                "gatling_home": config.get("gatling_home"),
                "gatling_api_url": config.get("gatling_api_url"),
                "api_token": config.get("gatling_api_token"),
                "team_id": config.get("gatling_team_id"),
                "properties": config.get("gatling_properties", {}),
            }
        )

    logger.info(
        f"JMeter/Gatling control configured: tool={tool}, auto_start={auto_start}"
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
    global _load_generator_started, _load_generator_config, _load_generator_run_info

    if not _load_generator_config or not _load_generator_config.get("auto_start", True):
        logger.info("Load generator auto-start is disabled, skipping")
        return

    tool = _load_generator_config.get("tool")
    if not tool:
        logger.warning("Load generator tool not configured, skipping")
        return

    try:
        if tool == "jmeter":
            logger.info("Starting JMeter load generator")
            result = start_jmeter_test(
                test_plan_path=_load_generator_config.get("test_plan"),
                jmeter_home=_load_generator_config.get("jmeter_home"),
                remote_hosts=_load_generator_config.get("remote_hosts"),
                properties=_load_generator_config.get("properties"),
                results_file=_load_generator_config.get("results_file"),
                jmeter_api_url=_load_generator_config.get("jmeter_api_url"),
            )
            _load_generator_run_info = {
                "test_id": result.get("test_id"),
                "process_id": result.get("process_id"),
                "results_file": result.get("results_file"),
                "mode": result.get("mode", "cli"),
            }

        elif tool == "gatling":
            logger.info("Starting Gatling load generator")
            result = start_gatling_simulation(
                simulation_path=_load_generator_config.get("simulation_path"),
                simulation_class=_load_generator_config.get("simulation_class"),
                gatling_home=_load_generator_config.get("gatling_home"),
                gatling_api_url=_load_generator_config.get("gatling_api_url"),
                api_token=_load_generator_config.get("api_token"),
                team_id=_load_generator_config.get("team_id"),
                properties=_load_generator_config.get("properties"),
            )
            _load_generator_run_info = {
                "run_id": result.get("runId") or result.get("run_id"),
                "process_id": result.get("process_id"),
                "mode": result.get("mode", "cli"),
            }

        _load_generator_started = True
        logger.info(f"Load generator started successfully: {result}")

        # Verify load generator is actually running
        try:
            status = _get_load_generator_status()
            logger.info(f"Load generator verification: {status}")
        except Exception as verify_error:
            logger.warning(f"Could not verify load generator status: {verify_error}")

    except Exception as e:
        logger.warning(f"Failed to start load generator: {e}")
        # Don't fail the experiment if load generator fails to start
        _load_generator_started = False
        _load_generator_run_info = None


def after_experiment_control(
    context: Any,
    state: Any,
    experiment: dict[str, Any],
    **kwargs: Any,
) -> None:
    """
    Stop load generator after experiment completes.
    """
    global _load_generator_started, _load_generator_config, _load_generator_run_info

    if not _load_generator_started or not _load_generator_run_info:
        return

    tool = _load_generator_config.get("tool") if _load_generator_config else None
    if not tool:
        return

    try:
        if tool == "jmeter":
            logger.info("Stopping JMeter load generator")
            result = stop_jmeter_test(
                test_id=_load_generator_run_info.get("test_id"),
                process_id=_load_generator_run_info.get("process_id"),
                jmeter_api_url=_load_generator_config.get("jmeter_api_url")
                if _load_generator_config
                else None,
            )
        elif tool == "gatling":
            logger.info("Stopping Gatling load generator")
            result = stop_gatling_simulation(
                run_id=_load_generator_run_info.get("run_id"),
                process_id=_load_generator_run_info.get("process_id"),
                gatling_api_url=_load_generator_config.get("gatling_api_url")
                if _load_generator_config
                else None,
                api_token=_load_generator_config.get("api_token")
                if _load_generator_config
                else None,
            )

        logger.info(f"Load generator stopped: {result}")
        _load_generator_started = False
        _load_generator_run_info = None

    except Exception as e:
        logger.warning(f"Failed to stop load generator: {e}")


def _get_load_generator_status() -> dict:
    """Get current load generator status."""
    global _load_generator_config, _load_generator_run_info

    if not _load_generator_config or not _load_generator_run_info:
        return {"status": "not_started"}

    tool = _load_generator_config.get("tool")
    if tool == "jmeter":
        return get_jmeter_test_status(
            test_id=_load_generator_run_info.get("test_id"),
            process_id=_load_generator_run_info.get("process_id"),
            jmeter_api_url=_load_generator_config.get("jmeter_api_url"),
            results_file=_load_generator_run_info.get("results_file"),
        )
    elif tool == "gatling":
        return get_gatling_simulation_status(
            run_id=_load_generator_run_info.get("run_id"),
            process_id=_load_generator_run_info.get("process_id"),
            gatling_api_url=_load_generator_config.get("gatling_api_url"),
            api_token=_load_generator_config.get("api_token"),
        )
    else:
        return {"status": "unknown"}


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
    logger.info("JMeter/Gatling load generator control loaded")
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
    logger.info("JMeter/Gatling load generator control unloaded")
    cleanup_control(control=None, experiment=experiment, **kwargs)


def cleanup_control(
    control: Any = None,
    experiment: Optional[dict[str, Any]] = None,
    **kwargs: Any,
) -> None:
    """
    Cleanup - ensure load generator is stopped.
    """
    global _load_generator_started, _load_generator_config, _load_generator_run_info

    if _load_generator_started and _load_generator_run_info:
        tool = _load_generator_config.get("tool") if _load_generator_config else None
        try:
            if tool == "jmeter":
                stop_jmeter_test(
                    test_id=_load_generator_run_info.get("test_id"),
                    process_id=_load_generator_run_info.get("process_id"),
                    jmeter_api_url=_load_generator_config.get("jmeter_api_url")
                    if _load_generator_config
                    else None,
                )
            elif tool == "gatling":
                stop_gatling_simulation(
                    run_id=_load_generator_run_info.get("run_id"),
                    process_id=_load_generator_run_info.get("process_id"),
                    gatling_api_url=_load_generator_config.get("gatling_api_url")
                    if _load_generator_config
                    else None,
                    api_token=_load_generator_config.get("api_token")
                    if _load_generator_config
                    else None,
                )
            _load_generator_started = False
            _load_generator_run_info = None
        except Exception as e:
            logger.warning(f"Failed to stop load generator during cleanup: {e}")
