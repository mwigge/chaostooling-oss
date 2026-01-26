"""
Chaos Toolkit actions for controlling Apache JMeter load generator.

Supports:
- CLI mode execution
- Remote/distributed testing via jmeter-server
- Programmatic test plan execution
"""

import logging
import os
import subprocess
import tempfile
from pathlib import Path
from typing import Optional

import requests

logger = logging.getLogger("chaosgeneric.actions.load_generator.jmeter")


def start_jmeter_test(
    test_plan_path: Optional[str] = None,
    jmeter_home: Optional[str] = None,
    remote_hosts: Optional[list[str]] = None,
    properties: Optional[dict[str, str]] = None,
    results_file: Optional[str] = None,
    jmeter_api_url: Optional[str] = None,
    timeout: int = 30,
) -> dict:
    """
    Start a JMeter test plan.

    Supports multiple execution modes:
    1. CLI mode: Direct execution via jmeter command
    2. Remote mode: Distributed execution via jmeter-server nodes
    3. API mode: If jmeter_api_url is provided (requires custom JMeter API wrapper)

    Args:
        test_plan_path: Path to .jmx test plan file
        jmeter_home: JMeter installation directory (default: from JMETER_HOME env var)
        remote_hosts: List of remote JMeter server hosts (e.g., ["host1:1099", "host2:1099"])
        properties: Dictionary of JMeter properties to set
        results_file: Path to save results (.jtl file)
        jmeter_api_url: URL of custom JMeter API wrapper (if available)
        timeout: Request timeout in seconds (default: 30)

    Returns:
        Dict with status, process info, and test run details
    """
    if jmeter_api_url:
        # Use API mode if available
        return _start_jmeter_via_api(
            jmeter_api_url=jmeter_api_url,
            test_plan_path=test_plan_path,
            remote_hosts=remote_hosts,
            properties=properties,
            timeout=timeout,
        )
    else:
        # Use CLI mode
        return _start_jmeter_via_cli(
            test_plan_path=test_plan_path,
            jmeter_home=jmeter_home,
            remote_hosts=remote_hosts,
            properties=properties,
            results_file=results_file,
        )


def _start_jmeter_via_api(
    jmeter_api_url: str,
    test_plan_path: Optional[str],
    remote_hosts: Optional[list[str]],
    properties: Optional[dict[str, str]],
    timeout: int,
) -> dict:
    """Start JMeter test via custom API wrapper."""
    try:
        payload = {}
        if test_plan_path:
            # If API supports file upload, handle it
            # Otherwise, assume test plan is already on server
            payload["test_plan"] = test_plan_path
        if remote_hosts:
            payload["remote_hosts"] = remote_hosts
        if properties:
            payload["properties"] = properties

        response = requests.post(
            f"{jmeter_api_url}/test/start", json=payload, timeout=timeout
        )
        response.raise_for_status()
        result = response.json()

        logger.info(
            f"Started JMeter test via API: {result.get('test_id', 'unknown')}",
            extra={"api_url": jmeter_api_url, "test_id": result.get("test_id")},
        )

        return result
    except requests.exceptions.RequestException as e:
        logger.error(
            f"Failed to start JMeter test via API: {e}",
            extra={"api_url": jmeter_api_url},
        )
        raise


def _start_jmeter_via_cli(
    test_plan_path: Optional[str],
    jmeter_home: Optional[str],
    remote_hosts: Optional[list[str]],
    properties: Optional[dict[str, str]],
    results_file: Optional[str],
) -> dict:
    """Start JMeter test via CLI."""
    jmeter_home = jmeter_home or os.getenv("JMETER_HOME")
    if not jmeter_home:
        raise ValueError(
            "JMETER_HOME not set. Provide jmeter_home parameter or set JMETER_HOME environment variable."
        )

    jmeter_bin = Path(jmeter_home) / "bin" / "jmeter"
    if os.name == "nt":  # Windows
        jmeter_bin = Path(jmeter_home) / "bin" / "jmeter.bat"

    if not jmeter_bin.exists():
        raise FileNotFoundError(f"JMeter executable not found at {jmeter_bin}")

    if not test_plan_path:
        raise ValueError("test_plan_path is required for CLI mode")

    if not Path(test_plan_path).exists():
        raise FileNotFoundError(f"Test plan not found: {test_plan_path}")

    # Prepare results file
    if not results_file:
        results_file = tempfile.mktemp(suffix=".jtl")

    # Build command
    cmd = [
        str(jmeter_bin),
        "-n",  # Non-GUI mode
        "-t",
        test_plan_path,  # Test plan
        "-l",
        results_file,  # Results file
    ]

    # Add remote hosts if specified
    if remote_hosts:
        cmd.extend(["-R", ",".join(remote_hosts)])

    # Add properties
    if properties:
        for key, value in properties.items():
            cmd.extend(["-J", f"{key}={value}"])

    try:
        logger.info(f"Starting JMeter test: {test_plan_path}")
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=jmeter_home,
        )

        return {
            "status": "started",
            "process_id": process.pid,
            "test_plan": test_plan_path,
            "results_file": results_file,
            "remote_hosts": remote_hosts or [],
            "mode": "cli",
        }
    except Exception as e:
        logger.error(f"Failed to start JMeter test: {e}")
        raise


def stop_jmeter_test(
    test_id: Optional[str] = None,
    process_id: Optional[int] = None,
    jmeter_api_url: Optional[str] = None,
    timeout: int = 10,
) -> dict:
    """
    Stop a running JMeter test.

    Args:
        test_id: Test ID from API mode
        process_id: Process ID from CLI mode
        jmeter_api_url: URL of JMeter API wrapper (if used)
        timeout: Request timeout in seconds (default: 10)

    Returns:
        Dict with status and statistics
    """
    if jmeter_api_url and test_id:
        return _stop_jmeter_via_api(jmeter_api_url, test_id, timeout)
    elif process_id:
        return _stop_jmeter_via_cli(process_id)
    else:
        raise ValueError(
            "Either test_id (for API mode) or process_id (for CLI mode) must be provided"
        )


def _stop_jmeter_via_api(jmeter_api_url: str, test_id: str, timeout: int) -> dict:
    """Stop JMeter test via API."""
    try:
        response = requests.post(
            f"{jmeter_api_url}/test/{test_id}/stop", timeout=timeout
        )
        response.raise_for_status()
        result = response.json()

        logger.info(f"Stopped JMeter test via API: {test_id}")
        return result
    except requests.exceptions.RequestException as e:
        logger.error(f"Failed to stop JMeter test via API: {e}")
        raise


def _stop_jmeter_via_cli(process_id: int) -> dict:
    """Stop JMeter test via CLI by terminating process."""
    try:
        import signal

        os.kill(process_id, signal.SIGTERM)
        logger.info(f"Stopped JMeter test process: {process_id}")
        return {"status": "stopped", "process_id": process_id}
    except ProcessLookupError:
        logger.warning(f"Process {process_id} not found (may have already terminated)")
        return {"status": "not_found", "process_id": process_id}
    except Exception as e:
        logger.error(f"Failed to stop JMeter test process: {e}")
        raise


def get_jmeter_test_status(
    test_id: Optional[str] = None,
    process_id: Optional[int] = None,
    jmeter_api_url: Optional[str] = None,
    results_file: Optional[str] = None,
    timeout: int = 10,
) -> dict:
    """
    Get status and statistics of a running or completed JMeter test.

    Args:
        test_id: Test ID from API mode
        process_id: Process ID from CLI mode
        jmeter_api_url: URL of JMeter API wrapper (if used)
        results_file: Path to .jtl results file (for CLI mode)
        timeout: Request timeout in seconds (default: 10)

    Returns:
        Dict with status, statistics, and metrics
    """
    if jmeter_api_url and test_id:
        return _get_jmeter_status_via_api(jmeter_api_url, test_id, timeout)
    elif results_file:
        return _get_jmeter_status_from_results(results_file, process_id)
    else:
        raise ValueError(
            "Either test_id (for API mode) or results_file (for CLI mode) must be provided"
        )


def _get_jmeter_status_via_api(jmeter_api_url: str, test_id: str, timeout: int) -> dict:
    """Get JMeter test status via API."""
    try:
        response = requests.get(
            f"{jmeter_api_url}/test/{test_id}/status", timeout=timeout
        )
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        logger.error(f"Failed to get JMeter test status via API: {e}")
        raise


def _get_jmeter_status_from_results(
    results_file: str, process_id: Optional[int]
) -> dict:
    """Parse JMeter results file to get status."""
    import csv

    if not Path(results_file).exists():
        # Test may still be running
        is_running = False
        if process_id:
            try:
                os.kill(process_id, 0)  # Check if process exists
                is_running = True
            except (OSError, ProcessLookupError):
                is_running = False

        return {
            "status": "running" if is_running else "unknown",
            "results_file": results_file,
            "process_id": process_id,
        }

    # Parse .jtl file (CSV format)
    try:
        with open(results_file, "r") as f:
            reader = csv.DictReader(f)
            rows = list(reader)

        if not rows:
            return {
                "status": "completed",
                "total_samples": 0,
                "results_file": results_file,
            }

        # Calculate statistics
        total_samples = len(rows)
        success_count = sum(
            1 for row in rows if row.get("success", "").lower() == "true"
        )
        error_count = total_samples - success_count

        # Extract response times (if available)
        response_times = []
        for row in rows:
            elapsed = row.get("elapsed", "")
            if elapsed and elapsed.isdigit():
                response_times.append(int(elapsed))

        avg_response_time = (
            sum(response_times) / len(response_times) if response_times else 0
        )

        return {
            "status": "completed",
            "total_samples": total_samples,
            "success_count": success_count,
            "error_count": error_count,
            "success_rate": (success_count / total_samples * 100)
            if total_samples > 0
            else 0,
            "avg_response_time_ms": avg_response_time,
            "results_file": results_file,
        }
    except Exception as e:
        logger.warning(f"Failed to parse JMeter results file: {e}")
        return {
            "status": "completed",
            "results_file": results_file,
            "parse_error": str(e),
        }
