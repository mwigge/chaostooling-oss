"""
Experiment Orchestrator Control

Lightweight control that runs FIRST for ALL experiments (database, host, network, messaging).
Generates stable experiment metadata that other controls can consume.

NO DEPENDENCIES on database, OpenTelemetry, or other systems.

Responsibilities:
1. Extract service name from experiment definition
2. Generate stable experiment_id (UUID v5 based on service:title)
3. Create experiment key for cross-system tracking
4. Store metadata in context for downstream controls
5. Export as environment variables for actions

This control should be the FIRST control in every experiment's control chain.
"""

import hashlib
import logging
import os
import uuid
from typing import Any

logger = logging.getLogger("chaostoolkit")

# Supported service types across all experiments
KNOWN_SERVICES = {
    # Databases
    "postgres",
    "postgresql",
    "mysql",
    "mssql",
    "sqlserver",
    "mongodb",
    "mongo",
    "cassandra",
    "redis",
    "dynamodb",
    "elasticsearch",
    "couchdb",
    "neo4j",
    # Messaging & Streaming
    "rabbitmq",
    "kafka",
    "activemq",
    "sqs",
    "sns",
    "kinesis",
    "pubsub",
    # Host-based
    "host",
    "cpu",
    "memory",
    "disk",
    "io",
    "filesystem",
    # Network-based
    "network",
    "latency",
    "bandwidth",
    "packet",
    "dns",
    "tcp",
    "udp",
    # Container/Orchestration
    "docker",
    "kubernetes",
    "k8s",
    "ecs",
    "fargate",
    # Cloud Services
    "aws",
    "azure",
    "gcp",
    "ec2",
    "lambda",
    "s3",
}


def extract_service_name(experiment: dict[str, Any]) -> str:
    """
    Extract service name from experiment definition.

    Tries multiple strategies in order:
    1. Check experiment tags for known service names
    2. Check configuration for service hints
    3. Check title for service keywords
    4. Default to 'unknown'

    Args:
        experiment: Full experiment definition

    Returns:
        Service name (lowercase), e.g., 'postgres', 'kafka', 'host', 'network'
    """
    # Strategy 1: Check tags
    tags = experiment.get("tags", [])
    if isinstance(tags, list):
        for tag in tags:
            tag_lower = str(tag).lower()
            if tag_lower in KNOWN_SERVICES:
                logger.debug(f"Extracted service from tags: {tag_lower}")
                return tag_lower

    # Strategy 2: Check title for keywords
    title = experiment.get("title", "").lower()
    for service in KNOWN_SERVICES:
        if service in title:
            logger.debug(f"Extracted service from title: {service}")
            return service

    # Strategy 3: Check configuration keys
    config = experiment.get("configuration", {})
    for key in config.keys():
        key_lower = key.lower()
        for service in KNOWN_SERVICES:
            if service in key_lower:
                logger.debug(f"Extracted service from config key '{key}': {service}")
                return service

    # Default
    logger.warning("Could not extract service name - using 'unknown'")
    return "unknown"


def generate_stable_experiment_id(service_name: str, experiment_title: str) -> int:
    """
    Generate deterministic experiment_id using UUID v5.

    Same service + title always produces the same experiment_id.
    This enables:
    - Proper run_number incrementing across runs
    - Cross-system experiment tracking
    - Experiment history and trending

    Args:
        service_name: Service type (postgres, kafka, host, network, etc.)
        experiment_title: Human-readable experiment title

    Returns:
        Integer experiment_id in range [0, 2147483647] (PostgreSQL INT max)
    """
    # Create stable key from service and title
    stable_key = f"{service_name}:{experiment_title}"

    # Generate UUID v5 (deterministic based on namespace + key)
    namespace = uuid.NAMESPACE_DNS
    stable_uuid = uuid.uuid5(namespace, stable_key)

    # Convert to integer within PostgreSQL INT range
    experiment_id = int(stable_uuid.int % 2147483647)

    logger.debug(
        f"Generated stable experiment_id: {experiment_id} from key: {stable_key}"
    )
    return experiment_id


def configure_control(configuration: dict[str, Any] = None):
    """Initialize the experiment orchestrator control."""
    logger.info("=" * 80)
    logger.info("Experiment Orchestrator Control initialized")
    logger.info("This control runs FIRST to generate stable experiment metadata")
    logger.info("=" * 80)


def before_experiment_control(
    context: dict[str, Any],
    state: Any = None,
    experiment: dict[str, Any] = None,
    **kwargs,
):
    """
    Generate stable experiment metadata BEFORE any other control runs.

    This is the entry point for ALL experiments - database, host, network, messaging.
    No dependencies on external systems.

    Args:
        context: Mutable dictionary for sharing state between controls
        state: Current experiment state
        experiment: Experiment definition (title, tags, description, method)
        **kwargs: Additional arguments
    """
    logger.info("=" * 80)
    logger.info("EXPERIMENT ORCHESTRATOR: Generating stable experiment metadata")
    logger.info("=" * 80)

    try:
        if not experiment:
            experiment = {}

        # Extract service name (postgres, kafka, host, network, etc.)
        service_name = extract_service_name(experiment)

        # Get experiment title
        title = experiment.get("title", "Unknown Experiment")

        # Generate stable experiment_id (deterministic: same service+title = same ID)
        experiment_id = generate_stable_experiment_id(service_name, title)

        # Create experiment key for cross-system tracking
        title_hash = hashlib.md5(title.encode()).hexdigest()[:8]
        experiment_key = f"{service_name}:{title_hash}"

        # Store in context for ALL downstream controls to use
        context["chaos_experiment_id"] = experiment_id
        context["chaos_service_name"] = service_name
        context["chaos_experiment_key"] = experiment_key
        context["chaos_experiment_title"] = title

        # Export as environment variables for actions that can't access context
        os.environ["CHAOS_EXPERIMENT_ID"] = str(experiment_id)
        os.environ["CHAOS_SERVICE_NAME"] = service_name
        os.environ["CHAOS_EXPERIMENT_KEY"] = experiment_key
        os.environ["CHAOS_EXPERIMENT_TITLE"] = title

        logger.info(f"Experiment ID: {experiment_id} (stable)")
        logger.info(f"Service: {service_name}")
        logger.info(f"Title: {title}")
        logger.info(f"Key: {experiment_key}")
        logger.info("Metadata stored in context and environment variables")
        logger.info("=" * 80)

    except Exception as e:
        logger.error(f"Failed to generate experiment metadata: {e}")
        logger.error("Continuing with defaults - downstream controls may be affected")

        # Set fallback values
        context["chaos_experiment_id"] = None
        context["chaos_service_name"] = "unknown"
        context["chaos_experiment_key"] = "unknown:00000000"
        context["chaos_experiment_title"] = experiment.get(
            "title", "Unknown Experiment"
        )


def after_experiment_control(
    context: dict[str, Any] = None,
    state: Any = None,
    experiment: dict[str, Any] = None,
    **kwargs: Any,
) -> None:
    """
    Print experiment summary AFTER experiment completes.
    Shows key metrics and results for visibility.

    Args:
        context: Experiment context with metadata
        state: Experiment state (journal)
        experiment: Experiment definition
        **kwargs: Additional arguments
    """
    logger.info("=" * 80)
    logger.info("EXPERIMENT ORCHESTRATOR: Experiment Summary")
    logger.info("=" * 80)

    try:
        # Extract state string from journal
        if isinstance(state, dict):
            state_str = state.get("status", "unknown")
            steady_state_hypothesis = state.get("steady_states", {}).get("after", {})
            deviated = (
                not steady_state_hypothesis.get("steady_state_met", False)
                if steady_state_hypothesis
                else None
            )
        else:
            state_str = str(state) if state else "unknown"
            deviated = None

        # Get metadata from context
        experiment_id = context.get("chaos_experiment_id") if context else None
        run_id = context.get("chaos_run_id") if context else None
        service_name = (
            context.get("chaos_service_name", "unknown") if context else "unknown"
        )
        title = (
            context.get("chaos_experiment_title", "Unknown") if context else "Unknown"
        )

        # Display summary
        logger.info(f"Experiment ID: {experiment_id}")
        logger.info(f"Run ID: {run_id}")
        logger.info(f"Service: {service_name}")
        logger.info(f"Title: {title}")
        logger.info(f"Final Status: {state_str}")

        if deviated is not None:
            logger.info(
                f"Steady State: {'FAILED - Deviation Detected' if deviated else 'PASSED'}"
            )

        # Show where results are stored
        logger.info("")
        logger.info("Results stored in chaos_platform database:")
        logger.info(
            f"  - View summary: SELECT * FROM chaos_platform.experiment_runs_summary WHERE run_id = {run_id};"
        )
        logger.info(
            f"  - View audit: SELECT * FROM chaos_platform.experiment_audit_trail WHERE run_id = {run_id};"
        )

        logger.info("=" * 80)

    except Exception as e:
        logger.error(f"Failed to print experiment summary: {e}")
        logger.error("Experiment completed but summary unavailable")
