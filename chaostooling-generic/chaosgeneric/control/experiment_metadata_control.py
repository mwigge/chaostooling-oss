"""
Experiment Metadata Control for Chaos Toolkit

Initializes experiment metadata that is used by all other controls.
MUST run first in the control chain to establish:
- chaos_experiment_id: Stable UUID based on service + title
- chaos_service_name: Target service extracted from tags
- chaos_experiment_key: Unique identifier for cross-system tracking

This ensures consistent experiment identification across:
- Database storage
- Baseline validation
- Analysis
- Metrics collection
- All downstream systems
"""

import os
import json
import logging
import hashlib
import uuid
from typing import Dict, Any, Optional

from chaoslib.control import Control

logger = logging.getLogger("chaosgeneric.control.experiment_metadata")

# List of known services for tag-based extraction
KNOWN_SERVICES = {
    # Databases
    "postgres", "postgresql", "mysql", "mssql", "mongodb", "cassandra", "redis",
    # Message brokers
    "rabbitmq", "kafka", "activemq",
    # Host/Infrastructure
    "host", "cpu", "memory", "disk", "io",
    # Network
    "network", "latency", "bandwidth"
}


def configure_control():
    """Configure the experiment metadata control."""
    logger.info("Configuring experiment metadata control")


def load_control(control: Control):
    """Load the experiment metadata control."""
    control.name = "experiment-metadata"
    control.description = "Initialize stable experiment metadata for all controls"
    
    # Register lifecycle hooks
    control.before_experiment_control = before_experiment_control
    
    logger.info("Experiment metadata control loaded")


def unload_control(control: Control):
    """Unload the experiment metadata control."""
    logger.info("Experiment metadata control unloaded")


def extract_service_name(experiment: Dict[str, Any]) -> str:
    """
    Extract service name from experiment definition.
    
    Tries multiple sources in order:
    1. From tags (first known service found)
    2. From baseline-metrics-summary.service
    3. From configuration.service_name
    4. Environment variable CHAOS_TARGET_SERVICE
    5. Parent directory of experiment file
    6. Default to 'unknown'
    
    Args:
        experiment: Experiment definition
        
    Returns:
        Service name (lowercase)
    """
    
    # Source 1: From tags (most reliable and explicit)
    tags = experiment.get("tags", [])
    if isinstance(tags, list):
        for tag in tags:
            if tag.lower() in KNOWN_SERVICES:
                return tag.lower()
    
    # Source 2: From baseline-metrics-summary
    baseline_summary = experiment.get("baseline-metrics-summary", {})
    if isinstance(baseline_summary, dict):
        service = baseline_summary.get("service")
        if service:
            return service.lower()
    
    # Source 3: From configuration
    config = experiment.get("configuration", {})
    if isinstance(config, dict):
        service_name = config.get("service_name")
        if service_name:
            return service_name.lower()
    
    # Source 4: Environment variable override
    env_service = os.getenv("CHAOS_TARGET_SERVICE")
    if env_service:
        return env_service.lower()
    
    # Source 5: Extract from experiment file path
    experiment_file = os.getenv("CHAOS_EXPERIMENT_FILE", "")
    if experiment_file and "/" in experiment_file:
        parts = experiment_file.split("/")
        if len(parts) >= 2:
            parent_dir = parts[-2].lower()
            if parent_dir in KNOWN_SERVICES:
                return parent_dir
    
    # Default
    logger.warning("Could not determine service name from experiment definition")
    return "unknown"


def generate_stable_experiment_id(service_name: str, experiment_title: str) -> int:
    """
    Generate deterministic experiment_id using UUID v5.
    
    Same service + title = same ID every time (deterministic).
    Different service/title = different ID.
    
    Args:
        service_name: Name of the service (postgres, mysql, etc.)
        experiment_title: Full experiment title
        
    Returns:
        Integer ID (0-2147483647 for 32-bit signed int compatibility)
    """
    
    # Create unique key: service:title
    # This ensures same experiment gets same ID across runs
    stable_key = f"{service_name}:{experiment_title}"
    
    # Generate UUID v5 (SHA-1 based, deterministic)
    # Using a fixed namespace so same key always generates same UUID
    namespace = uuid.NAMESPACE_DNS
    stable_uuid = uuid.uuid5(namespace, stable_key)
    
    # Convert UUID to integer
    # Use modulo to keep within 32-bit signed int range for database compatibility
    experiment_id = int(stable_uuid.int % 2147483647)
    
    logger.debug(f"Generated stable experiment_id: {experiment_id} from key: {stable_key}")
    
    return experiment_id


def before_experiment_control(context: Dict[str, Any], state: Any = None, 
                            experiment: Dict[str, Any] = None, **kwargs):
    """
    Initialize experiment metadata BEFORE any other controls run.
    
    This sets up shared context that all other controls depend on:
    - chaos_experiment_id: Stable UUID for this experiment
    - chaos_service_name: Target service name
    - chaos_experiment_key: Unique identifier string
    
    Args:
        context: Mutable context dict shared with other controls
        state: Current experiment state
        experiment: Experiment definition
        **kwargs: Additional arguments
    """
    
    logger.info("=" * 80)
    logger.info("EXPERIMENT METADATA CONTROL: before_experiment_control CALLED")
    logger.info("=" * 80)
    
    try:
        if not experiment:
            experiment = {}
        
        # Extract service name from experiment
        service_name = extract_service_name(experiment)
        
        # Get experiment title
        experiment_title = experiment.get("title", "Unknown Experiment")
        
        # Generate stable experiment_id
        experiment_id = generate_stable_experiment_id(service_name, experiment_title)
        
        # Create unique key for cross-system tracking
        # Format: service:title:uuid (compact identifier)
        experiment_key = f"{service_name}:{hashlib.md5(experiment_title.encode()).hexdigest()[:8]}"
        
        # Store in context for all downstream controls
        context["chaos_experiment_id"] = experiment_id
        context["chaos_service_name"] = service_name
        context["chaos_experiment_key"] = experiment_key
        context["chaos_experiment_title"] = experiment_title
        
        # Also export as environment variables for actions/probes that can't access context
        os.environ["CHAOS_EXPERIMENT_ID"] = str(experiment_id)
        os.environ["CHAOS_SERVICE_NAME"] = service_name
        os.environ["CHAOS_EXPERIMENT_KEY"] = experiment_key
        
        logger.info(
            f"✅ Experiment metadata initialized: "
            f"id={experiment_id}, service={service_name}, "
            f"key={experiment_key}, title={experiment_title}"
        )
        logger.info("=" * 80)
        
    except Exception as e:
        logger.error(f"❌ Failed to initialize experiment metadata: {e}")
        logger.info("=" * 80)
        # Don't fail experiment on metadata setup error
        # Set defaults so experiment can continue
        context["chaos_experiment_id"] = 0
        context["chaos_service_name"] = "unknown"
        context["chaos_experiment_key"] = "unknown:00000000"
        context["chaos_experiment_title"] = "Unknown Experiment"
