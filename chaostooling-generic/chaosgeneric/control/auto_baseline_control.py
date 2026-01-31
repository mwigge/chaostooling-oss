"""
Auto-Baseline Control

Automatically checks if baseline metrics exist before running experiments.
If no baseline is found, runs baseline collection before continuing.

This control implements the "baseline-first" workflow:
1. Before experiment method: Check if baseline exists
2. If not: Run baseline collection
3. If yes: Continue with experiment

Typical usage in experiment JSON:

{
  "controls": [
    {
      "name": "auto-baseline",
      "provider": {
        "type": "python",
        "module": "chaosgeneric.control.auto_baseline_control"
      }
    }
  ]
}

This ensures every experiment has a baseline reference without manual setup.
"""

import logging
import os
import sys
import subprocess
import json
from datetime import datetime
from typing import Dict, Any

from chaoslib.exceptions import ChaosException

logger = logging.getLogger(__name__)


def on_experiment_start(context: Dict[str, Any] = None, **kwargs) -> None:
    """
    Before-experiment hook: Check if baseline exists, run if missing.

    Called at very start of experiment run, before steady-state hypothesis check.

    Args:
        context: Chaos Toolkit experiment context
    """
    if not context:
        logger.warning("No context provided to auto-baseline control")
        return

    logger.info("=" * 70)
    logger.info("AUTO-BASELINE CONTROL: Checking baseline data...")
    logger.info("=" * 70)

    try:
        # Extract configuration from experiment context
        config = context.get("configuration", {})
        baseline_file = config.get("baseline_file", {}).get("default")
        service_name = context.get("description", "unknown-service")

        # Try to get service name from experiment method or steady-state
        if "method" in context:
            for action in context.get("method", []):
                if "baseline" in action.get("name", "").lower():
                    service_name = (
                        action.get("provider", {})
                        .get("arguments", {})
                        .get("service_name", service_name)
                    )
                    baseline_file = (
                        action.get("provider", {})
                        .get("arguments", {})
                        .get("output_file", baseline_file)
                    )

        logger.info(f"Service: {service_name}")
        logger.info(f"Baseline file: {baseline_file}")

        # Check if baseline exists
        baseline_exists = _check_baseline_exists(service_name, baseline_file)

        if baseline_exists:
            logger.info("✓ Baseline data found - proceeding with experiment")
            return

        # Baseline missing - need to collect
        logger.warning(
            "✗ No baseline data found - collecting baseline before experiment..."
        )

        if not _run_baseline_collection(context):
            logger.error("Failed to collect baseline - cannot continue with experiment")
            raise ChaosException("Baseline collection failed - experiment aborted")

        logger.info("✓ Baseline collection complete - proceeding with experiment")

    except Exception as e:
        logger.error(f"Auto-baseline control error: {str(e)}")
        raise


def _check_baseline_exists(service_name: str, baseline_file: str = None) -> bool:
    """
    Check if baseline data exists (either in file or database).

    Args:
        service_name: Service name
        baseline_file: Optional baseline JSON file path

    Returns:
        True if baseline exists, False otherwise
    """
    # Check file first
    if baseline_file and os.path.exists(baseline_file):
        try:
            with open(baseline_file, "r") as f:
                data = json.load(f)
                if data and isinstance(data, dict) and data.get("metrics"):
                    logger.debug(f"✓ Found baseline file: {baseline_file}")
                    return True
        except Exception as e:
            logger.debug(f"Could not read baseline file: {str(e)}")

    # Check database
    try:
        from chaosgeneric.data.chaos_db import ChaosDb

        db_host = os.getenv("CHAOS_DB_HOST", "localhost")
        db_port = int(os.getenv("CHAOS_DB_PORT", "5434"))

        db = ChaosDb(host=db_host, port=db_port)

        with db._get_connection() as conn:
            with conn.cursor() as cur:
                # Check if any baseline metrics exist for this service
                cur.execute(
                    """
                    SELECT COUNT(*) FROM chaos_platform.baseline_metrics bm
                    JOIN chaos_platform.services s ON bm.service_id = s.service_id
                    WHERE s.service_name = %s AND bm.is_active = true
                """,
                    (service_name,),
                )

                count = cur.fetchone()[0]
                if count > 0:
                    logger.debug(
                        f"✓ Found {count} baseline metrics in database for {service_name}"
                    )
                    return True

    except Exception as e:
        logger.debug(f"Could not check database for baseline: {str(e)}")

    return False


def _run_baseline_collection(context: Dict[str, Any]) -> bool:
    """
    Run baseline collection experiment.

    Looks for baseline-collection-{service}.json in experiments directory.

    Args:
        context: Experiment context

    Returns:
        True if successful, False otherwise
    """
    try:
        # Try to find baseline collection experiment
        baseline_experiment = _find_baseline_experiment(context)

        if not baseline_experiment:
            logger.error("Could not find baseline collection experiment")
            return False

        logger.info(f"Running baseline collection: {baseline_experiment}")

        # Run baseline collection via chaos toolkit
        result = subprocess.run(
            ["chaos", "run", baseline_experiment, "--no-log"],
            capture_output=True,
            timeout=300,  # 5 minute timeout
        )

        if result.returncode != 0:
            logger.error(f"Baseline collection failed:\n{result.stderr.decode()}")
            return False

        logger.info(f"Baseline collection output:\n{result.stdout.decode()}")
        return True

    except subprocess.TimeoutExpired:
        logger.error("Baseline collection timed out (5 minutes)")
        return False
    except Exception as e:
        logger.error(f"Error running baseline collection: {str(e)}")
        return False


def _find_baseline_experiment(context: Dict[str, Any]) -> str:
    """
    Find baseline collection experiment file.

    Looks for:
    1. baseline-collection-{service}.json in same directory as current experiment
    2. baseline-collection.json as fallback

    Args:
        context: Experiment context

    Returns:
        Path to baseline experiment, or None if not found
    """
    try:
        # Get current experiment file from context
        current_file = context.get("source")
        if not current_file:
            # Try to determine from cwd
            current_file = os.getcwd()

        # Get directory and service name
        if os.path.isfile(current_file):
            exp_dir = os.path.dirname(current_file)
            exp_name = os.path.basename(current_file)
        else:
            exp_dir = current_file
            exp_name = "experiment"

        # Extract service name from experiment name
        # e.g., "postgres-pool-exhaustion.json" -> "postgres"
        service = exp_name.split("-")[0].replace(".json", "")

        # Try service-specific baseline first
        baseline_paths = [
            os.path.join(exp_dir, f"baseline-collection-{service}.json"),
            os.path.join(exp_dir, "baseline-collection.json"),
        ]

        for path in baseline_paths:
            if os.path.exists(path):
                logger.debug(f"Found baseline experiment: {path}")
                return path

        logger.warning(f"No baseline experiment found in {exp_dir}")
        return None

    except Exception as e:
        logger.error(f"Error finding baseline experiment: {str(e)}")
        return None
