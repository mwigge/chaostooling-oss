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
            # Try common locations
            possible_paths = [
                Path("journal.json"),
                Path.cwd() / "journal.json",
                Path("/var/log/chaostoolkit/journal.json"),
                Path(os.getenv("CHAOS_EXPERIMENT_DIR", ".")) / "journal.json",
            ]
            
            for path in possible_paths:
                if path.exists():
                    journal_path = str(path)
                    break
        
        if not journal_path or not Path(journal_path).exists():
            error_msg = f"Journal file not found. Tried: {[str(p) for p in possible_paths]}"
            logger.error(error_msg)
            return {
                "success": False,
                "error": error_msg,
                "reports": {}
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
