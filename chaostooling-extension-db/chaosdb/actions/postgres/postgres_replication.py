"""PostgreSQL replication chaos actions."""

import logging
import os
import subprocess
import time
from typing import Optional

from chaosotel import ensure_initialized, flush, get_metrics_core, get_tracer
from opentelemetry.trace import StatusCode


def _find_container_by_name_pattern(service_name: str) -> Optional[str]:
    """
    Find container name by service name pattern.

    Since Docker Compose uses naming pattern: <project>_<service>_<instance>,
    we need to find the actual container name if the service name doesn't match exactly.

    Args:
        service_name: Service name (e.g., "app-server-1")

    Returns:
        Container name if found, None otherwise
    """
    import logging

    logger = logging.getLogger("chaos")

    try:
        # List all containers and find one matching the service name pattern
        result = subprocess.run(
            ["docker", "ps", "-a", "--format", "{{.Names}}"],
            capture_output=True,
            text=True,
            timeout=10,
        )

        if result.returncode != 0:
            logger.warning(f"Failed to list containers: {result.stderr}")
            return None

        if not result.stdout.strip():
            logger.warning(f"No containers found when searching for: {service_name}")
            return None

        # Look for containers that contain the service name
        # Docker Compose pattern: <project>_<service>_<instance>
        # Match containers containing the service name (case-insensitive)
        container_names = [
            name.strip() for name in result.stdout.strip().split("\n") if name.strip()
        ]

        # Try exact match first (in case container_name was already set)
        for container_name in container_names:
            if container_name == service_name:
                return container_name

        # Try pattern matching - look for containers containing the service name
        # Prefer containers where service name appears as a distinct segment
        for container_name in container_names:
            # Match if service name is in container name
            if service_name.lower() in container_name.lower():
                logger.info(
                    f"Found container '{container_name}' matching service name '{service_name}'"
                )
                return container_name

        logger.warning(f"No container found matching service name: {service_name}")
        logger.debug(f"Available containers: {container_names}")
        return None
    except Exception as e:
        logger.warning(f"Error finding container by pattern '{service_name}': {e}")
        return None


def _stop_container(container_name: str) -> str:
    """
    Stop a container by name, trying exact match first, then pattern matching.

    Args:
        container_name: Container name or service name to stop

    Returns:
        Actual container name that was stopped

    Raises:
        Exception if container cannot be found or stopped
    """
    # Try exact name first
    result = subprocess.run(
        ["docker", "stop", container_name], capture_output=True, text=True, timeout=30
    )

    if result.returncode == 0:
        return container_name

    # If exact name fails, try to find by pattern
    actual_container_name = _find_container_by_name_pattern(container_name)
    if actual_container_name:
        result = subprocess.run(
            ["docker", "stop", actual_container_name],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode == 0:
            return actual_container_name

    # If both fail, raise error with helpful message
    error_msg = result.stderr if result.stderr else "Container not found"
    raise Exception(f"Failed to stop container '{container_name}': {error_msg}")


def _start_container(container_name: str) -> str:
    """
    Start a container by name, trying exact match first, then pattern matching.

    Args:
        container_name: Container name or service name to start

    Returns:
        Actual container name that was started

    Raises:
        Exception if container cannot be found or started
    """
    # Try exact name first
    result = subprocess.run(
        ["docker", "start", container_name], capture_output=True, text=True, timeout=30
    )

    if result.returncode == 0:
        return container_name

    # If exact name fails, try to find by pattern
    actual_container_name = _find_container_by_name_pattern(container_name)
    if actual_container_name:
        result = subprocess.run(
            ["docker", "start", actual_container_name],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode == 0:
            return actual_container_name

    # If both fail, raise error with helpful message
    error_msg = result.stderr if result.stderr else "Container not found"
    raise Exception(f"Failed to start container '{container_name}': {error_msg}")


def stop_replica(
    replica_host: Optional[str] = None,
    replica_port: Optional[int] = None,
    container_name: Optional[str] = None,
) -> dict:
    """
    Stop a PostgreSQL replica by stopping the container or process.

    Args:
        replica_host: Replica hostname (if stopping via network)
        replica_port: Replica port
        container_name: Docker container name to stop (e.g., "postgres-replica")

    Returns:
        Dict with results
    """
    ensure_initialized()
    tracer = get_tracer()
    logger = logging.getLogger("chaosdb.postgres.replication")

    try:
        with tracer.start_as_current_span("chaos.postgres.stop_replica") as span:
            from chaosotel.core.trace_core import set_db_span_attributes
            set_db_span_attributes(
                span,
                db_system="postgresql",
                db_name=None,
                host=replica_host,
                port=replica_port,
                chaos_activity="postgresql_stop_replica",
                chaos_action="stop_replica",
                chaos_operation="stop_replica"
            )

            if container_name:
                span.set_attribute("chaos.container_name", container_name)
                logger.info(f"Stopping replica container: {container_name}")
                actual_container_name = _stop_container(container_name)
                logger.info(f"Replica container {actual_container_name} stopped")
            else:
                raise ValueError("container_name is required")

            result_dict = {
                "success": True,
                "container_name": container_name,
                "action": "stopped",
            }

            span.set_status(StatusCode.OK)
            logger.info(f"Replica stopped: {result_dict}")
            flush()
            return result_dict

    except Exception as e:
        db_system = os.getenv("DB_SYSTEM", "postgresql")
        metrics = get_metrics_core()
        metrics.record_db_error(db_system=db_system, error_type=type(e).__name__)
        logger.error("Failed to stop replica: %s", e)
        flush()
        raise


def start_replica(
    container_name: Optional[str] = None,
) -> dict:
    """
    Start a PostgreSQL replica by starting the container.

    Args:
        container_name: Docker container name to start (e.g., "postgres-replica")

    Returns:
        Dict with results
    """
    ensure_initialized()
    tracer = get_tracer()
    logger = logging.getLogger("chaosdb.postgres.replication")

    try:
        recovery_start_time = time.time()
        with tracer.start_as_current_span("chaos.postgres.start_replica") as span:
            from chaosotel.core.trace_core import set_db_span_attributes
            set_db_span_attributes(
                span,
                db_system="postgresql",
                db_name=None,
                host=None,  # replica_host not available in this function
                port=None,  # replica_port not available in this function
                chaos_activity="postgresql_start_replica",
                chaos_action="start_replica",
                chaos_operation="start_replica"
            )

            if container_name:
                span.set_attribute("chaos.container_name", container_name)
                logger.info(f"Starting replica container: {container_name}")
                actual_container_name = _start_container(container_name)

                # Wait for postgres to be ready
                logger.info("Waiting for replica to be ready...")
                time.sleep(5)

                logger.info(f"Replica container {actual_container_name} started")
            else:
                raise ValueError("container_name is required")

            # Calculate and record MTTR
            recovery_time_ms = (time.time() - recovery_start_time) * 1000
            metrics = get_metrics_core()
            metrics.record_mttr(
                service_name=container_name or "postgres-replica",
                recovery_time_ms=recovery_time_ms,
                recovery_type="replica_failover",
                success=True,
                tags={"container_name": container_name} if container_name else None,
            )

            result_dict = {
                "success": True,
                "container_name": container_name,
                "action": "started",
                "mttr_ms": recovery_time_ms,
            }

            span.set_status(StatusCode.OK)
            logger.info(f"Replica started: {result_dict}")
            flush()
            return result_dict

    except Exception as e:
        db_system = os.getenv("DB_SYSTEM", "postgresql")
        metrics = get_metrics_core()
        metrics.record_db_error(db_system=db_system, error_type=type(e).__name__)
        logger.error("Failed to start replica: %s", e)
        flush()
        raise


def stop_primary(
    primary_host: Optional[str] = None,
    primary_port: Optional[int] = None,
    container_name: Optional[str] = None,
) -> dict:
    """
    Stop a PostgreSQL primary by stopping the container or process.

    Args:
        primary_host: Primary hostname
        primary_port: Primary port
        container_name: Docker container name to stop (e.g., "postgres-primary")

    Returns:
        Dict with results
    """
    ensure_initialized()
    tracer = get_tracer()
    logger = logging.getLogger("chaosdb.postgres.replication")

    try:
        with tracer.start_as_current_span("chaos.postgres.stop_primary") as span:
            from chaosotel.core.trace_core import set_db_span_attributes
            set_db_span_attributes(
                span,
                db_system="postgresql",
                db_name=None,
                host=primary_host,
                port=primary_port,
                chaos_activity="postgresql_stop_primary",
                chaos_action="stop_primary",
                chaos_operation="stop_primary"
            )

            if container_name:
                span.set_attribute("chaos.container_name", container_name)
                logger.info(f"Stopping primary container: {container_name}")
                actual_container_name = _stop_container(container_name)
                logger.info(f"Primary container {actual_container_name} stopped")
            else:
                raise ValueError("container_name is required")

            result_dict = {
                "success": True,
                "container_name": container_name,
                "action": "stopped",
            }

            span.set_status(StatusCode.OK)
            logger.info(f"Primary stopped: {result_dict}")
            flush()
            return result_dict

    except Exception as e:
        db_system = os.getenv("DB_SYSTEM", "postgresql")
        metrics = get_metrics_core()
        metrics.record_db_error(db_system=db_system, error_type=type(e).__name__)
        logger.error("Failed to stop primary: %s", e)
        flush()
        raise
