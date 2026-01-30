"""
Database Storage Control for Chaos Toolkit

Persists experiment execution data to PostgreSQL database.
Hooks into experiment lifecycle to:
1. Consume stable experiment_id from experiment-orchestrator control
2. Create experiment_run record at experiment start
3. Pass run_id to metrics collectors via context
4. Update experiment status and results at completion

REQUIRES: experiment-orchestrator control to run FIRST
"""

import os
import json
import logging
import requests
from datetime import datetime
from typing import Dict, Any, Optional

from chaoslib.control import Control
from chaoslib.exceptions import ChaosException

logger = logging.getLogger("chaosgeneric.control.database_storage")

# Import calculator for risk and complexity scoring
try:
    from chaosotel.calculator import (
        calculate_risk_level,
        calculate_complexity_score
    )
except ImportError:
    calculate_risk_level = None
    calculate_complexity_score = None
    logger.warning("ChaoSOTEL calculator not available - scores will use defaults")


def query_prometheus_metric(metric_name: str, prometheus_url: str = "http://prometheus:9090") -> Optional[float]:
    """
    Query Prometheus for a specific metric value.
    
    Args:
        metric_name: Name of the metric to query
        prometheus_url: Prometheus server URL
        
    Returns:
        Latest metric value or None if not found
    """
    try:
        response = requests.get(
            f"{prometheus_url}/api/v1/query",
            params={"query": metric_name},
            timeout=5
        )
        if response.status_code == 200:
            data = response.json()
            if data.get("status") == "success" and data.get("data", {}).get("result"):
                value = data["data"]["result"][0]["value"][1]
                return float(value)
    except Exception as e:
        logger.debug(f"Failed to query Prometheus for {metric_name}: {e}")
    return None


def configure_control():
    """Configure the database storage control."""
    logger.info("Configuring database storage control")


def load_control(control: Control):
    """Load the database storage control."""
    control.name = "database-storage"
    control.description = "Persist experiment execution to PostgreSQL"
    
    # Register lifecycle hooks
    control.before_experiment_control = before_experiment_control
    control.after_experiment_control = after_experiment_control
    control.after_experiment_step = after_experiment_step
    
    logger.info("Database storage control loaded")


def unload_control(control: Control):
    """Unload the database storage control."""
    logger.info("Database storage control unloaded")


def before_experiment_control(context: Dict[str, Any], state: Any = None, 
                            experiment: Dict[str, Any] = None, **kwargs):
    """
    Create experiment_run record using metadata from experiment-orchestrator control.
    
    REQUIRES: experiment-orchestrator control must run FIRST to set:
    - chaos_experiment_id (stable ID)
    - chaos_service_name
    - chaos_experiment_key
    - chaos_experiment_title
    
    Args:
        context: Mutable dictionary with metadata from orchestrator
        state: Current experiment state
        experiment: Experiment definition
        **kwargs: Additional arguments
    """
    try:
        from chaosgeneric.data.chaos_db import ChaosDb
        
        if not experiment:
            experiment = {}
        
        # Get metadata from experiment-orchestrator control (must run first!)
        experiment_id = context.get("chaos_experiment_id")
        service_name = context.get("chaos_service_name", "unknown")
        experiment_key = context.get("chaos_experiment_key")
        title = context.get("chaos_experiment_title") or experiment.get("title", "Unknown Experiment")
        
        # Validate that orchestrator ran first
        if not experiment_id:
            logger.warning("=" * 80)
            logger.warning("experiment-orchestrator control did NOT run first!")
            logger.warning("Add 'experiment-orchestrator' as the FIRST control in your experiment")
            logger.warning("Falling back to auto-generated experiment_id (not stable)")
            logger.warning("=" * 80)
        
        # Initialize database connection
        db_host = os.getenv("CHAOS_DB_HOST", "chaos-platform-db")
        db_port = int(os.getenv("CHAOS_DB_PORT", "5432"))
        db_name = os.getenv("CHAOS_DB_NAME", "chaos_platform")
        db_user = os.getenv("CHAOS_DB_USER", "chaos_admin")
        db_password = os.getenv("CHAOS_DB_PASSWORD", "chaos_admin_secure_password")
        
        db = ChaosDb(
            host=db_host,
            port=db_port,
            dbname=db_name,
            user=db_user,
            password=db_password
        )
        description = experiment.get("description", "")
        tags = experiment.get("tags", [])
        
        # Create experiment run record using stable experiment_id
        run_id = db.create_experiment_run(
            title=title,
            description=description,
            started_at=datetime.utcnow(),
            status="running",
            tags=json.dumps(tags) if tags else None,
            experiment_id=experiment_id,  # Pass stable ID from metadata control
            metadata=json.dumps({
                "orchestrator": "chaostoolkit",
                "control": "database-storage",
                "started_by": "chaos-control-plane",
                "service": service_name,
                "experiment_key": experiment_key
            })
        )
        
        # Store run_id in context for use by other controls/actions
        context["chaos_db"] = db
        context["chaos_run_id"] = run_id
        
        # Also export as environment variable for actions that can't access context
        os.environ["CHAOS_RUN_ID"] = str(run_id)
        
        logger.info(f"Created experiment run record: run_id={run_id}, title={title}")
        
    except ImportError:
        logger.warning("ChaosDb not available - database storage disabled")
    except Exception as e:
        logger.error(f"Failed to create experiment run record: {e}")
        raise ChaosException(f"Database storage initialization failed: {e}")


def after_experiment_step(context: Dict[str, Any], step: Dict[str, Any], 
                          result: Dict[str, Any], state: str):
    """
    Called after each experiment step (action/probe).
    Optionally store step results in database.
    """
    try:
        db = context.get("chaos_db")
        run_id = context.get("chaos_run_id")
        
        if not db or not run_id:
            return
        
        # Store step result metadata if needed
        step_name = step.get("name", "unknown")
        step_type = step.get("type", "unknown")
        
        # Log step completion for debugging
        logger.debug(f"Completed step: {step_name} ({step_type}) - state: {state}")
        
    except Exception as e:
        logger.warning(f"Failed to record step result: {e}")
        # Don't fail experiment on step logging errors


def after_experiment_control(context: Dict[str, Any], state: Any = None, 
                            journal: Dict[str, Any] = None, experiment: Dict[str, Any] = None, **kwargs):
    """
    Called after experiment execution completes or is interrupted.
    Updates experiment_run record with final status and end_time.
    
    Handles states:
    - succeeded: Experiment completed successfully
    - failed: Experiment completed but failed
    - interrupted: Experiment was manually aborted
    
    Note: The 'state' parameter may be passed as a dict (journal) in some cases
    """
    try:
        if not experiment:
            experiment = {}
        
        # Handle state parameter - it might be the journal dict or a string
        if isinstance(state, dict):
            # state is the journal object
            if not journal:
                journal = state
            state_str = journal.get("status", "completed")
        else:
            # state is a string
            state_str = state
            
        db = context.get("chaos_db")
        run_id = context.get("chaos_run_id")
        
        if not db or not run_id:
            return
        
        # Map chaos toolkit state to experiment status
        state_to_status = {
            "succeeded": "ended",
            "failed": "ended",
            "interrupted": "aborted",
            "aborted": "aborted",
            "completed": "ended",
            None: "ended"
        }
        
        status = state_to_status.get(state_str, "ended")
        
        # Extract summary from journal
        summary = journal.get("summary", {}) if journal else {}
        steady_state_passed = journal.get("steady_state_hypothesis", {}).get("passed", False) if journal else False
        
        # Count findings
        findings_count = len(journal.get("findings", [])) if journal else 0
        
        # Calculate success rate from journal
        # Success rate = (steps_succeeded / total_steps) * 100
        steps = journal.get("method", []) if journal else []
        total_steps = len(steps)
        steps_succeeded = sum(1 for step in steps if step.get("status") == "succeeded")
        success_rate = (steps_succeeded / total_steps * 100) if total_steps > 0 else 0
        
        # Extract experiment scores using calculator
        risk_score = None
        complexity_score = None
        test_quality = None
        risk_level = None
        
        # Use chaosotel calculator if available
        if calculate_risk_level and calculate_complexity_score:
            try:
                # Build experiment dict for calculators
                experiment_info = {
                    "severity": experiment.get("severity", "medium"),
                    "blast_radius": float(experiment.get("blast_radius", 0.5)),
                    "is_production": bool(experiment.get("is_production", False)),
                    "has_rollback": bool(experiment.get("has_rollback", True)),
                    "num_steps": len(experiment.get("method", [])),
                    "num_probes": len(experiment.get("steady-state-hypothesis", {}).get("probes", [])),
                    "num_rollbacks": len(experiment.get("rollbacks", [])),
                    "duration_seconds": journal.get("duration", 0) if journal else 0,
                    "target_types": [context.get("chaos_service_name", "unknown")],
                }
                
                # Calculate risk level (1-4 scale)
                risk_calc = calculate_risk_level(experiment_info)
                risk_level = risk_calc.get("level_name", "Medium").lower()  # low, medium, high, critical
                risk_score = int(risk_calc.get("score", 50) * 2.55)  # Scale 0-100 to 0-255
                
                logger.debug(f"Risk calculated: {risk_level} ({risk_score}/255)")
                
                # Calculate complexity (0-100 scale)
                complexity_calc = calculate_complexity_score(experiment_info)
                complexity_score = int(complexity_calc.get("score", 50) * 2.55)  # Scale 0-100 to 0-255
                
                logger.debug(f"Complexity calculated: {complexity_score}/255")
                
            except Exception as e:
                logger.warning(f"Error calculating scores: {e}")
        
        # Calculate test quality based on steady-state and success rate
        test_quality = None
        if journal:
            steady_state_quality = 0.5 if steady_state_passed else 0.2
            findings_quality = min(findings_count / 5, 1.0) * 0.5  # Scale by 0.5 weight
            success_quality = (success_rate / 100) * 0.5 if success_rate else 0.3
            
            # Test quality is weighted combination
            test_quality_0_100 = (steady_state_quality * 0.4 + findings_quality * 0.3 + success_quality * 0.3) * 100
            test_quality = int(test_quality_0_100 * 2.55)  # Scale 0-100 to 0-255
        
        # Prepare result summary
        result_summary = json.dumps({
            "status": status,
            "steady_state_passed": steady_state_passed,
            "findings_count": findings_count,
            "duration_seconds": summary.get("duration", 0),
            "started_at": journal.get("start_time") if journal else None,
            "ended_at": journal.get("end_time") if journal else None,
            "journal_id": journal.get("id") if journal else None,
            "risk_score": risk_score,
            "complexity_score": complexity_score,
            "test_quality": test_quality,
            "success_rate": success_rate
        })
        
        # Update experiment run with final status and scores
        metadata_dict = {
            "journal_id": journal.get("id") if journal else None,
            "steady_state_passed": steady_state_passed,
            "findings": findings_count,
            "state": state_str
        }
        
        db.update_experiment_run(
            run_id=run_id,
            status=status,
            ended_at=datetime.utcnow(),
            result_summary=result_summary,
            risk_score=risk_score,
            complexity_score=complexity_score,
            test_quality=test_quality,
            risk_level=risk_level,
            success_rate=success_rate,
            metadata=json.dumps(metadata_dict)  # Convert dict to JSON string
        )
        
        # Log after-experiment summary with same format as before-experiment
        logger.info("=" * 80)
        logger.info("EXPERIMENT COMPLETED - SUMMARY")
        logger.info("=" * 80)
        logger.info(f"Experiment Run ID: {run_id}")
        logger.info(f"Status: {status.upper()}")
        logger.info(f"Steady-State Hypothesis: {'PASSED' if steady_state_passed else 'FAILED'}")
        logger.info(f"Findings: {findings_count}")
        logger.info(f"Success Rate: {success_rate}%" if success_rate else "Success Rate: N/A")
        logger.info(f"Risk Score: {risk_score if risk_score is not None else 'N/A'}/255 (calculated by chaosotel.calculator)")
        logger.info(f"Complexity Score: {complexity_score if complexity_score is not None else 'N/A'}/255 (calculated by chaosotel.calculator)")
        logger.info(f"Test Quality: {test_quality if test_quality is not None else 'N/A'}/255 (based on steady-state, findings, success rate)")
        logger.info(f"Risk Level: {risk_level.upper() if risk_level else 'N/A'} (derived from risk score)")
        logger.info("=" * 80)
        
    except Exception as e:
        logger.error(f"Failed to update experiment run record: {e}")
        # Don't fail experiment on database update errors
