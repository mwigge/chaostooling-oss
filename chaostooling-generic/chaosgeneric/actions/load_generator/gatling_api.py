"""
Chaos Toolkit actions for controlling Gatling load generator.

Supports:
- CLI mode execution
- Gatling Enterprise REST API
- Private locations / control plane
"""

import logging
import os
import subprocess
from pathlib import Path
from typing import Optional

import requests

logger = logging.getLogger("chaosgeneric.actions.load_generator.gatling")


def start_gatling_simulation(
    simulation_path: Optional[str] = None,
    simulation_class: Optional[str] = None,
    gatling_home: Optional[str] = None,
    gatling_api_url: Optional[str] = None,
    api_token: Optional[str] = None,
    team_id: Optional[str] = None,
    properties: Optional[dict[str, str]] = None,
    timeout: int = 30,
) -> dict:
    """
    Start a Gatling simulation.

    Supports multiple execution modes:
    1. CLI mode: Direct execution via gatling command
    2. Enterprise API mode: If gatling_api_url is provided (requires Gatling Enterprise)

    Args:
        simulation_path: Path to simulation Scala/Java file or compiled class
        simulation_class: Fully qualified class name of simulation (e.g., "com.example.BasicSimulation")
        gatling_home: Gatling installation directory (default: from GATLING_HOME env var)
        gatling_api_url: URL of Gatling Enterprise API (e.g., "https://cloud.gatling.io/api/public")
        api_token: API token for Gatling Enterprise
        team_id: Team ID for Gatling Enterprise
        properties: Dictionary of simulation properties/overrides
        timeout: Request timeout in seconds (default: 30)

    Returns:
        Dict with status, run ID, and simulation details
    """
    if gatling_api_url:
        # Use Enterprise API mode
        return _start_gatling_via_api(
            gatling_api_url=gatling_api_url,
            api_token=api_token,
            team_id=team_id,
            simulation_path=simulation_path,
            simulation_class=simulation_class,
            properties=properties,
            timeout=timeout,
        )
    else:
        # Use CLI mode
        return _start_gatling_via_cli(
            simulation_path=simulation_path,
            simulation_class=simulation_class,
            gatling_home=gatling_home,
            properties=properties,
        )


def _start_gatling_via_api(
    gatling_api_url: str,
    api_token: Optional[str],
    team_id: Optional[str],
    simulation_path: Optional[str],
    simulation_class: Optional[str],
    properties: Optional[dict[str, str]],
    timeout: int,
) -> dict:
    """Start Gatling simulation via Enterprise API."""
    if not api_token:
        api_token = os.getenv("GATLING_API_TOKEN")
        if not api_token:
            raise ValueError(
                "Gatling API token required. Provide api_token parameter or set GATLING_API_TOKEN environment variable."
            )

    try:
        headers = {
            "Authorization": f"Bearer {api_token}",
            "Content-Type": "application/json",
        }

        # Build payload for starting a simulation run
        payload = {}
        if team_id:
            payload["teamId"] = team_id
        if simulation_class:
            payload["simulationId"] = simulation_class
        if properties:
            payload["overrides"] = properties

        # If simulation_path is provided, it may need to be uploaded first
        # This depends on Gatling Enterprise API structure
        if simulation_path:
            payload["simulationPath"] = simulation_path

        # Start simulation run
        # Note: Actual endpoint may vary based on Gatling Enterprise version
        response = requests.post(
            f"{gatling_api_url}/runs",
            json=payload,
            headers=headers,
            timeout=timeout,
        )
        response.raise_for_status()
        result = response.json()

        logger.info(
            f"Started Gatling simulation via API: {result.get('runId', 'unknown')}",
            extra={"api_url": gatling_api_url, "run_id": result.get("runId")},
        )

        return result
    except requests.exceptions.RequestException as e:
        logger.error(
            f"Failed to start Gatling simulation via API: {e}",
            extra={"api_url": gatling_api_url},
        )
        raise


def _start_gatling_via_cli(
    simulation_path: Optional[str],
    simulation_class: Optional[str],
    gatling_home: Optional[str],
    properties: Optional[dict[str, str]],
) -> dict:
    """Start Gatling simulation via CLI."""
    gatling_home = gatling_home or os.getenv("GATLING_HOME")
    if not gatling_home:
        raise ValueError(
            "GATLING_HOME not set. Provide gatling_home parameter or set GATLING_HOME environment variable."
        )

    # Find Gatling executable
    gatling_bin = Path(gatling_home) / "bin" / "gatling.sh"
    if os.name == "nt":  # Windows
        gatling_bin = Path(gatling_home) / "bin" / "gatling.bat"

    if not gatling_bin.exists():
        raise FileNotFoundError(f"Gatling executable not found at {gatling_bin}")

    if not simulation_class:
        raise ValueError("simulation_class is required for CLI mode")

    # Build command
    # Gatling CLI typically requires simulation class name
    cmd = [str(gatling_bin), "-s", simulation_class]

    # Add properties if specified
    if properties:
        for key, value in properties.items():
            cmd.extend(["-D", f"{key}={value}"])

    try:
        logger.info(f"Starting Gatling simulation: {simulation_class}")
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=gatling_home,
        )

        return {
            "status": "started",
            "process_id": process.pid,
            "simulation_class": simulation_class,
            "simulation_path": simulation_path,
            "mode": "cli",
        }
    except Exception as e:
        logger.error(f"Failed to start Gatling simulation: {e}")
        raise


def stop_gatling_simulation(
    run_id: Optional[str] = None,
    process_id: Optional[int] = None,
    gatling_api_url: Optional[str] = None,
    api_token: Optional[str] = None,
    timeout: int = 10,
) -> dict:
    """
    Stop a running Gatling simulation.

    Args:
        run_id: Run ID from Enterprise API mode
        process_id: Process ID from CLI mode
        gatling_api_url: URL of Gatling Enterprise API (if used)
        api_token: API token for Gatling Enterprise
        timeout: Request timeout in seconds (default: 10)

    Returns:
        Dict with status and statistics
    """
    if gatling_api_url and run_id:
        return _stop_gatling_via_api(gatling_api_url, api_token, run_id, timeout)
    elif process_id:
        return _stop_gatling_via_cli(process_id)
    else:
        raise ValueError(
            "Either run_id (for API mode) or process_id (for CLI mode) must be provided"
        )


def _stop_gatling_via_api(
    gatling_api_url: str, api_token: Optional[str], run_id: str, timeout: int
) -> dict:
    """Stop Gatling simulation via Enterprise API."""
    if not api_token:
        api_token = os.getenv("GATLING_API_TOKEN")
        if not api_token:
            raise ValueError("Gatling API token required")

    try:
        headers = {"Authorization": f"Bearer {api_token}"}

        # Stop simulation run
        # Note: Actual endpoint may vary based on Gatling Enterprise version
        response = requests.post(
            f"{gatling_api_url}/runs/{run_id}/stop",
            headers=headers,
            timeout=timeout,
        )
        response.raise_for_status()
        result = response.json()

        logger.info(f"Stopped Gatling simulation via API: {run_id}")
        return result
    except requests.exceptions.RequestException as e:
        logger.error(f"Failed to stop Gatling simulation via API: {e}")
        raise


def _stop_gatling_via_cli(process_id: int) -> dict:
    """Stop Gatling simulation via CLI by terminating process."""
    try:
        import signal

        os.kill(process_id, signal.SIGTERM)
        logger.info(f"Stopped Gatling simulation process: {process_id}")
        return {"status": "stopped", "process_id": process_id}
    except ProcessLookupError:
        logger.warning(f"Process {process_id} not found (may have already terminated)")
        return {"status": "not_found", "process_id": process_id}
    except Exception as e:
        logger.error(f"Failed to stop Gatling simulation process: {e}")
        raise


def get_gatling_simulation_status(
    run_id: Optional[str] = None,
    process_id: Optional[int] = None,
    gatling_api_url: Optional[str] = None,
    api_token: Optional[str] = None,
    timeout: int = 10,
) -> dict:
    """
    Get status and statistics of a running or completed Gatling simulation.

    Args:
        run_id: Run ID from Enterprise API mode
        process_id: Process ID from CLI mode
        gatling_api_url: URL of Gatling Enterprise API (if used)
        api_token: API token for Gatling Enterprise
        timeout: Request timeout in seconds (default: 10)

    Returns:
        Dict with status, statistics, and metrics
    """
    if gatling_api_url and run_id:
        return _get_gatling_status_via_api(gatling_api_url, api_token, run_id, timeout)
    elif process_id:
        return _get_gatling_status_from_process(process_id)
    else:
        raise ValueError(
            "Either run_id (for API mode) or process_id (for CLI mode) must be provided"
        )


def _get_gatling_status_via_api(
    gatling_api_url: str, api_token: Optional[str], run_id: str, timeout: int
) -> dict:
    """Get Gatling simulation status via Enterprise API."""
    if not api_token:
        api_token = os.getenv("GATLING_API_TOKEN")
        if not api_token:
            raise ValueError("Gatling API token required")

    try:
        headers = {"Authorization": f"Bearer {api_token}"}

        # Get run status and metrics
        # Note: Actual endpoints may vary based on Gatling Enterprise version
        response = requests.get(
            f"{gatling_api_url}/runs/{run_id}",
            headers=headers,
            timeout=timeout,
        )
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        logger.error(f"Failed to get Gatling simulation status via API: {e}")
        raise


def _get_gatling_status_from_process(process_id: int) -> dict:
    """Get Gatling simulation status from running process."""
    try:
        os.kill(process_id, 0)  # Check if process exists
        return {
            "status": "running",
            "process_id": process_id,
        }
    except (OSError, ProcessLookupError):
        return {
            "status": "completed",
            "process_id": process_id,
        }
