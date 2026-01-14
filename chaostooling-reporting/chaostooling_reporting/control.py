"""
Chaos Toolkit control hooks for automated report generation.
"""

import json
import logging
import os
from pathlib import Path
from typing import Any, Dict

from chaostooling_reporting.report_generator import ReportGenerator

logger = logging.getLogger("chaostooling_reporting")

__all__ = ["configure_control", "load_control", "unload_control"]


def configure_control(
    experiment: Dict[str, Any],
    configuration: Dict[str, Any],
    **kwargs: Any,
) -> Dict[str, Any]:
    """
    Configure the reporting control.

    This is called when the control is loaded.
    """
    logger.info("Configuring chaostooling-reporting control")

    # Get configuration from experiment or environment
    reporting_config = configuration.get("reporting", {})
    if not reporting_config:
        reporting_config = {
            "enabled": os.getenv("CHAOS_REPORTING_ENABLED", "true").lower() == "true",
            "output_dir": os.getenv(
                "CHAOS_REPORTING_OUTPUT_DIR", "/var/log/chaostoolkit/reports"
            ),
            "formats": os.getenv("CHAOS_REPORTING_FORMATS", "html,json").split(","),
            "templates": {
                "executive": os.getenv("CHAOS_REPORTING_EXECUTIVE", "true").lower()
                == "true",
                "compliance": os.getenv("CHAOS_REPORTING_COMPLIANCE", "true").lower()
                == "true",
                "audit": os.getenv("CHAOS_REPORTING_AUDIT", "true").lower() == "true",
                "product_owner": os.getenv(
                    "CHAOS_REPORTING_PRODUCT_OWNER", "true"
                ).lower()
                == "true",
            },
        }

    # Initialize report generator
    output_dir = Path(
        reporting_config.get("output_dir", "/var/log/chaostoolkit/reports")
    )
    output_dir.mkdir(parents=True, exist_ok=True)

    return {
        "reporting_config": reporting_config,
        "output_dir": str(output_dir),
        "report_generator": None,  # Will be initialized in load_control
    }


def load_control(
    experiment: Dict[str, Any],
    configuration: Dict[str, Any],
    **kwargs: Any,
) -> Dict[str, Any]:
    """
    Load the reporting control.

    This is called before the experiment runs.
    """
    # Get control state from context
    # Note: In Chaos Toolkit, control state is managed internally
    # We'll store config in the control return value

    reporting_config = configuration.get("reporting", {})
    if not reporting_config:
        reporting_config = {
            "enabled": os.getenv("CHAOS_REPORTING_ENABLED", "true").lower() == "true",
            "output_dir": os.getenv(
                "CHAOS_REPORTING_OUTPUT_DIR", "/var/log/chaostoolkit/reports"
            ),
            "formats": os.getenv("CHAOS_REPORTING_FORMATS", "html,json").split(","),
            "templates": {
                "executive": os.getenv("CHAOS_REPORTING_EXECUTIVE", "true").lower()
                == "true",
                "compliance": os.getenv("CHAOS_REPORTING_COMPLIANCE", "true").lower()
                == "true",
                "audit": os.getenv("CHAOS_REPORTING_AUDIT", "true").lower() == "true",
                "product_owner": os.getenv(
                    "CHAOS_REPORTING_PRODUCT_OWNER", "true"
                ).lower()
                == "true",
            },
        }

    if not reporting_config.get("enabled", True):
        logger.info("Reporting is disabled, skipping control setup")
        return {}

    logger.info("Loading chaostooling-reporting control")

    # Initialize report generator
    output_dir = reporting_config.get("output_dir", "/var/log/chaostoolkit/reports")
    report_generator = ReportGenerator(
        output_dir=output_dir,
        formats=reporting_config.get("formats", ["html", "json"]),
        templates=reporting_config.get("templates", {}),
    )

    logger.info(f"Report generator initialized, output directory: {output_dir}")

    # Return control state (will be stored by Chaos Toolkit)
    return {
        "reporting_config": reporting_config,
        "output_dir": output_dir,
        "report_generator": report_generator,
        "experiment": experiment,
    }


def unload_control(
    experiment: Dict[str, Any],
    configuration: Dict[str, Any],
    **kwargs: Any,
) -> None:
    """
    Unload the reporting control.

    This is called after the experiment completes.
    Reports are generated in after_experiment_control hook.
    """
    logger.info("Unloading chaostooling-reporting control")
    # Reports will be generated in after_experiment_control hook


def after_experiment_control(
    context: Any,
    state: Any,
    experiment: Dict[str, Any],
    **kwargs: Any,
) -> None:
    """
    Generate reports after experiment completes.

    This hook receives the journal with all experiment results.
    """
    # Try to get journal from multiple sources
    journal = None

    # 1. Try kwargs (if Chaos Toolkit passes it directly)
    journal = kwargs.get("journal")

    # 2. Try context (if stored there)
    if not journal and hasattr(context, "journal"):
        journal = context.journal
    elif not journal and isinstance(context, dict):
        journal = context.get("journal")

    # 3. Try reading from journal.json file (Chaos Toolkit creates this)
    if not journal:
        journal_path = None

        # First, check environment variable (set by docker-compose.yml)
        env_journal_path = os.getenv("CHAOSTOOLKIT_JOURNAL_PATH")
        if env_journal_path and Path(env_journal_path).exists():
            journal_path = Path(env_journal_path)
        else:
            # Try common locations - Chaos Toolkit writes journal.json in the current working directory
            # In Docker, chaos-runner-entrypoint.sh changes to /var/log/chaostoolkit
            possible_paths = []

            # Priority 1: Environment variables
            if env_journal_path:
                possible_paths.append(Path(env_journal_path))

            chaos_experiment_dir = os.getenv("CHAOS_EXPERIMENT_DIR")
            if chaos_experiment_dir:
                possible_paths.append(Path(chaos_experiment_dir) / "journal.json")

            # Priority 2: Log directory (where chaos-runner-entrypoint.sh sets working directory)
            possible_paths.extend(
                [
                    Path(
                        "/var/log/chaostoolkit/journal.json"
                    ),  # Log directory (primary location in Docker)
                    Path.cwd() / "journal.json",  # Current working directory
                    Path("journal.json"),  # Relative to current directory
                ]
            )

            # Priority 3: Parent directories (for detached runs)
            current = Path.cwd()
            for _ in range(5):  # Check up to 5 levels up
                possible_paths.append(current / "journal.json")
                if current == current.parent:  # Reached root
                    break
                current = current.parent

            # Priority 4: Experiment mount points
            possible_paths.extend(
                [
                    Path("/experiments") / "journal.json",
                    Path("/experiments") / "production-scale" / "journal.json",
                ]
            )

            # Try each path
            for path in possible_paths:
                try:
                    if path.exists() and path.is_file():
                        journal_path = path
                        break
                except (PermissionError, OSError):
                    continue

        if journal_path and journal_path.exists():
            try:
                with open(journal_path, "r") as f:
                    journal = json.load(f)
                logger.info(f"Loaded journal from {journal_path}")
            except Exception as e:
                logger.warning(f"Failed to read journal.json from {journal_path}: {e}")

    if not journal:
        logger.warning("No journal available, skipping report generation")
        return

    # Get control state - try multiple ways to access it
    reporting_control = None

    # Try from state.controls (if state is a dict or has controls attribute)
    if hasattr(state, "controls"):
        controls = state.controls
        if isinstance(controls, dict):
            reporting_control = controls.get("reporting")
    elif isinstance(state, dict):
        controls = state.get("controls", {})
        reporting_control = controls.get("reporting")

    # If not found, try to get from context or recreate from config
    if not reporting_control:
        # Try to recreate report generator from configuration
        configuration = kwargs.get("configuration", {})
        reporting_config = configuration.get("reporting", {})
        if not reporting_config:
            reporting_config = {
                "enabled": os.getenv("CHAOS_REPORTING_ENABLED", "true").lower()
                == "true",
                "output_dir": os.getenv(
                    "CHAOS_REPORTING_OUTPUT_DIR", "/var/log/chaostoolkit/reports"
                ),
                "formats": os.getenv("CHAOS_REPORTING_FORMATS", "html,json").split(","),
                "templates": {
                    "executive": os.getenv("CHAOS_REPORTING_EXECUTIVE", "true").lower()
                    == "true",
                    "compliance": os.getenv(
                        "CHAOS_REPORTING_COMPLIANCE", "true"
                    ).lower()
                    == "true",
                    "audit": os.getenv("CHAOS_REPORTING_AUDIT", "true").lower()
                    == "true",
                    "product_owner": os.getenv(
                        "CHAOS_REPORTING_PRODUCT_OWNER", "true"
                    ).lower()
                    == "true",
                },
            }

        if reporting_config.get("enabled", True):
            output_dir = reporting_config.get(
                "output_dir", "/var/log/chaostoolkit/reports"
            )
            report_generator = ReportGenerator(
                output_dir=output_dir,
                formats=reporting_config.get("formats", ["html", "json"]),
                templates=reporting_config.get("templates", {}),
            )
            reporting_control = {
                "reporting_config": reporting_config,
                "report_generator": report_generator,
            }

    if not reporting_control:
        logger.warning("Reporting control not found, skipping report generation")
        return

    reporting_config = reporting_control.get("reporting_config", {})
    if not reporting_config.get("enabled", True):
        return

    report_generator = reporting_control.get("report_generator")
    if not report_generator:
        logger.warning("Report generator not initialized, skipping report generation")
        return

    logger.info("Generating reports from experiment journal")

    try:
        # Generate all requested report types
        configuration = kwargs.get("configuration", {})
        reports = report_generator.generate_reports(experiment, journal, configuration)

        logger.info(f"Successfully generated {len(reports)} reports")
        for report_type, report_path in reports.items():
            logger.info(f"  - {report_type}: {report_path}")

    except Exception as e:
        logger.error(f"Error generating reports: {e}", exc_info=True)
