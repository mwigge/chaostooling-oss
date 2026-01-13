"""
Reporting actions for Chaos Toolkit experiments.

Provides actions that can be added to experiment rollback sections or as final steps
to generate reports after all rollbacks are complete.
"""

import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, Optional

from chaostooling_reporting.report_generator import ReportGenerator

logger = logging.getLogger("chaostooling_reporting.actions")

__all__ = ["generate_experiment_reports"]


def generate_experiment_reports(
    output_dir: Optional[str] = None,
    formats: Optional[str] = None,
    executive: bool = True,
    compliance: bool = True,
    audit: bool = True,
    product_owner: bool = True,
    journal_path: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Generate experiment reports from journal.
    
    This action should be added to the experiment's rollback section or as a final
    step after all rollbacks are complete. It reads the journal.json file and
    generates all requested report types.
    
    Args:
        output_dir: Directory to save reports (defaults to CHAOS_REPORTING_OUTPUT_DIR or ./reporting-output)
        formats: Comma-separated list of formats: html,json,csv,pdf (defaults to "html,json")
        executive: Generate executive summary report (default: True)
        compliance: Generate compliance report (default: True)
        audit: Generate audit trail report (default: True)
        product_owner: Generate product owner report (default: True)
        journal_path: Path to journal.json file (defaults to ./journal.json)
    
    Returns:
        Dictionary with report paths and status
    
    Example in experiment JSON:
        {
          "rollbacks": [
            {
              "type": "action",
              "name": "generate-reports",
              "provider": {
                "type": "python",
                "module": "chaostooling_reporting.actions",
                "func": "generate_experiment_reports",
                "arguments": {
                  "output_dir": "${CHAOS_REPORTING_OUTPUT_DIR}",
                  "formats": "html,json"
                }
              }
            }
          ]
        }
    """
    try:
        # Get configuration from environment variables or arguments
        if not output_dir:
            output_dir = os.getenv(
                "CHAOS_REPORTING_OUTPUT_DIR",
                os.getenv("REPORTING_OUTPUT_DIR", "./reporting-output")
            )
        
        if not formats:
            formats = os.getenv("CHAOS_REPORTING_FORMATS", "html,json")
        
        formats_list = [f.strip() for f in formats.split(",")]
        
        templates = {
            "executive": executive if isinstance(executive, bool) else os.getenv("CHAOS_REPORTING_EXECUTIVE", "true").lower() == "true",
            "compliance": compliance if isinstance(compliance, bool) else os.getenv("CHAOS_REPORTING_COMPLIANCE", "true").lower() == "true",
            "audit": audit if isinstance(audit, bool) else os.getenv("CHAOS_REPORTING_AUDIT", "true").lower() == "true",
            "product_owner": product_owner if isinstance(product_owner, bool) else os.getenv("CHAOS_REPORTING_PRODUCT_OWNER", "true").lower() == "true",
        }
        
        # Find journal.json file
        if not journal_path:
            # First, check environment variable (set by docker-compose.yml)
            env_journal_path = os.getenv("CHAOSTOOLKIT_JOURNAL_PATH")
            if env_journal_path and Path(env_journal_path).exists():
                journal_path = env_journal_path
                logger.info(f"Found journal from CHAOSTOOLKIT_JOURNAL_PATH: {journal_path}")
            else:
                # Try common locations - Chaos Toolkit writes journal.json in the experiment directory
                possible_paths = []
                
                # Priority 1: Environment variables
                if env_journal_path:
                    possible_paths.append(Path(env_journal_path))
                
                chaos_experiment_dir = os.getenv("CHAOS_EXPERIMENT_DIR")
                if chaos_experiment_dir:
                    possible_paths.append(Path(chaos_experiment_dir) / "journal.json")
                
                # Priority 2: Log directory (where chaos-runner-entrypoint.sh sets working directory)
                possible_paths.extend([
                    Path("/var/log/chaostoolkit/journal.json"),  # Log directory (primary location in Docker)
                    Path("/var/log/chaostoolkit") / "journal.json",  # Explicit log directory
                ])
                
                # Priority 3: Current working directory and parent directories
                current = Path.cwd()
                for _ in range(5):  # Check up to 5 levels up (for detached runs)
                    possible_paths.append(current / "journal.json")
                    if current == current.parent:  # Reached root
                        break
                    current = current.parent
                
                # Priority 4: Experiment mount points
                possible_paths.extend([
                    Path("/experiments") / "journal.json",  # Docker container experiments mount
                    Path("/experiments") / "production-scale" / "journal.json",  # Production scale experiments
                ])
                
                # Priority 5: Search in experiment subdirectories
                for base_path in [Path("/experiments"), Path.cwd(), Path(os.getenv("HOME", "/"))]:
                    if base_path.exists() and base_path.is_dir():
                        # Check for production-scale subdirectory
                        prod_scale = base_path / "production-scale" / "journal.json"
                        if prod_scale.exists():
                            possible_paths.append(prod_scale)
                        # Check for any subdirectories (limit depth to avoid performance issues)
                        try:
                            for subdir in base_path.iterdir():
                                if subdir.is_dir() and not subdir.name.startswith('.'):
                                    journal_file = subdir / "journal.json"
                                    if journal_file.exists():
                                        possible_paths.append(journal_file)
                        except (PermissionError, OSError) as e:
                            logger.debug(f"Could not search in {base_path}: {e}")
                
                # Priority 6: Home directory fallback
                home_dir = Path(os.getenv("HOME", "/"))
                if home_dir.exists():
                    possible_paths.append(home_dir / "journal.json")
                
                # Remove duplicates while preserving order
                seen = set()
                unique_paths = []
                for path in possible_paths:
                    path_str = str(path)
                    if path_str not in seen:
                        seen.add(path_str)
                        unique_paths.append(path)
                
                # Try each path
                for path in unique_paths:
                    try:
                        if path.exists() and path.is_file():
                            journal_path = str(path)
                            logger.info(f"Found journal at: {journal_path}")
                            break
                    except (PermissionError, OSError) as e:
                        logger.debug(f"Could not check {path}: {e}")
                        continue
        
        if not journal_path or not Path(journal_path).exists():
            # Log detailed debugging information
            logger.error("Journal file not found. Searched in multiple locations:")
            logger.error(f"  - CHAOSTOOLKIT_JOURNAL_PATH: {os.getenv('CHAOSTOOLKIT_JOURNAL_PATH', 'not set')}")
            logger.error(f"  - CHAOS_EXPERIMENT_DIR: {os.getenv('CHAOS_EXPERIMENT_DIR', 'not set')}")
            logger.error(f"  - Current working directory: {Path.cwd()}")
            logger.error("  - Primary log directory: /var/log/chaostoolkit/journal.json")
            logger.error("  - Experiments mount: /experiments/journal.json")
            
            # Try to list what's actually in the log directory
            log_dir = Path("/var/log/chaostoolkit")
            if log_dir.exists():
                try:
                    files = list(log_dir.iterdir())
                    logger.error(f"  - Files in /var/log/chaostoolkit: {[f.name for f in files[:10]]}")
                except Exception as e:
                    logger.error(f"  - Could not list /var/log/chaostoolkit: {e}")
            
            # Try to list what's in current directory
            try:
                current_files = list(Path.cwd().iterdir())
                logger.error(f"  - Files in current directory: {[f.name for f in current_files[:10]]}")
            except Exception as e:
                logger.error(f"  - Could not list current directory: {e}")
            
            error_msg = "Journal file not found. Please ensure the experiment has completed and journal.json exists."
            return {
                "success": False,
                "error": error_msg,
                "reports": {},
                "debug_info": {
                    "chaostoolkit_journal_path": os.getenv("CHAOSTOOLKIT_JOURNAL_PATH"),
                    "chaos_experiment_dir": os.getenv("CHAOS_EXPERIMENT_DIR"),
                    "current_working_directory": str(Path.cwd()),
                    "log_directory_exists": log_dir.exists() if log_dir.exists() else False,
                }
            }
        
        logger.info(f"Loading journal from {journal_path}")
        with open(journal_path, "r") as f:
            journal = json.load(f)
        
        # Extract experiment from journal
        experiment = journal.get("experiment", {})
        configuration = journal.get("configuration", {})
        
        # Initialize report generator
        logger.info(f"Initializing report generator: output_dir={output_dir}, formats={formats_list}")
        report_generator = ReportGenerator(
            output_dir=output_dir,
            formats=formats_list,
            templates=templates,
        )
        
        # Generate reports
        logger.info("Generating experiment reports...")
        reports = report_generator.generate_reports(
            experiment=experiment,
            journal=journal,
            configuration=configuration,
        )
        
        logger.info(f"Successfully generated {len(reports)} reports:")
        for report_type, report_path in reports.items():
            logger.info(f"  - {report_type}: {report_path}")
        
        return {
            "success": True,
            "output_dir": output_dir,
            "journal_path": journal_path,
            "reports": reports,
            "reports_generated": len(reports),
        }
    
    except Exception as e:
        error_msg = f"Error generating reports: {str(e)}"
        logger.error(error_msg, exc_info=True)
        return {
            "success": False,
            "error": error_msg,
            "reports": {}
        }
