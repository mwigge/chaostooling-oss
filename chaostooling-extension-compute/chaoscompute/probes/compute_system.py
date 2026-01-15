"""Compute system probes for CPU, memory, disk, and process monitoring."""

import logging
import time
from typing import Any

import psutil
from chaosotel import (ensure_initialized, flush, get_metric_tags,
                       get_metrics_core)

# Metrics are emitted via chaosotel MetricsCore for Prometheus/OTEL.
logger = logging.getLogger("chaostoolkit")


def get_cpu_usage(interval: int = 1) -> float:
    """
    Get the current CPU usage percentage.

    Records metric: chaos_compute_cpu_usage_percent
    """
    ensure_initialized()
    metrics = get_metrics_core()
    usage = psutil.cpu_percent(interval=interval)
    logger.info(f"Current CPU usage: {usage}%")

    tags = get_metric_tags(target_type="compute")
    metrics.record_custom_metric(
        "compute.cpu.usage.percent",
        usage,
        metric_type="gauge",
        unit="percent",
        tags=tags,
        description="Current CPU usage",
    )

    flush()
    return usage


def get_memory_usage() -> dict[str, Any]:
    """
    Get current memory usage details.

    Records metric: chaos_compute_memory_usage_percent
    """
    ensure_initialized()
    metrics = get_metrics_core()
    mem = psutil.virtual_memory()
    usage = {
        "total": mem.total,
        "available": mem.available,
        "percent": mem.percent,
        "used": mem.used,
        "free": mem.free,
    }
    logger.info(f"Current Memory usage: {usage['percent']}%")

    tags = get_metric_tags(target_type="compute")
    metrics.record_custom_metric(
        "compute.memory.usage.percent",
        usage["percent"],
        metric_type="gauge",
        unit="percent",
        tags=tags,
        description="Current memory usage",
    )

    flush()
    return usage


def get_disk_usage(path: str = "/") -> dict[str, Any]:
    """
    Get disk usage for the specified path.
    """
    ensure_initialized()
    disk = psutil.disk_usage(path)
    usage = {
        "total": disk.total,
        "used": disk.used,
        "free": disk.free,
        "percent": disk.percent,
    }
    logger.info(f"Disk usage at {path}: {usage['percent']}%")
    return usage


def process_exists(process_name: str) -> bool:
    """
    Check if a process with the given name is running.
    """
    for proc in psutil.process_iter(["name"]):
        try:
            if process_name.lower() in proc.info["name"].lower():
                logger.info(f"Process '{process_name}' found.")
                return True
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            pass
    logger.info(f"Process '{process_name}' not found.")
    return False


def get_uptime() -> float:
    """
    Get system uptime in seconds.

    Records metric: chaos_compute_uptime_seconds
    """
    ensure_initialized()
    metrics = get_metrics_core()
    boot_time = psutil.boot_time()
    uptime = time.time() - boot_time
    logger.info(f"System uptime: {uptime} seconds")

    tags = get_metric_tags(target_type="compute")
    metrics.record_custom_metric(
        "compute.uptime.seconds",
        uptime,
        metric_type="gauge",
        unit="s",
        tags=tags,
        description="System uptime in seconds",
    )

    flush()
    return uptime


def get_container_stats(
    container_name: str, logical_name: str | None = None
) -> dict[str, float]:
    """
    Get CPU and memory usage for a specific container.

    Records metrics:
    - container.cpu.usage_percent
    - container.memory.usage_percent
    """
    import subprocess

    ensure_initialized()
    metrics = get_metrics_core()

    try:
        # Use docker stats to get current usage
        # --no-stream ensures we get a single snapshot
        # format: {{.CPUPerc}},{{.MemPerc}}
        cmd = [
            "docker",
            "stats",
            container_name,
            "--no-stream",
            "--format",
            "{{.CPUPerc}},{{.MemPerc}}",
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)

        output = result.stdout.strip()
        if not output:
            logger.warning(f"No stats found for container {container_name}")
            return {}

        # Parse output "0.00%,0.00%"
        parts = output.split(",")
        if len(parts) != 2:
            logger.warning(f"Unexpected stats format for {container_name}: {output}")
            return {}

        cpu_str = parts[0].replace("%", "")
        mem_str = parts[1].replace("%", "")

        cpu_percent = float(cpu_str)
        mem_percent = float(mem_str)

        # Prefer logical_name (e.g. "app-server-1") for labeling; fall back to full container name
        label_name = logical_name or container_name

        # Use both semantic and custom tag keys so Prometheus sees a clear container label
        # container.name -> Prometheus 'container_name' via OTEL translation
        tags = get_metric_tags(
            target_type="kubernetes",
            **{
                "container.name": label_name,
                "container_name": label_name,
            },
        )

        metrics.record_custom_metric(
            "container.cpu.usage.percent",
            cpu_percent,
            metric_type="gauge",
            unit="percent",
            tags=tags,
            description="Container CPU usage",
        )

        metrics.record_custom_metric(
            "container.memory.usage.percent",
            mem_percent,
            metric_type="gauge",
            unit="percent",
            tags=tags,
            description="Container memory usage",
        )

        # Record container status as running (1)
        metrics.record_custom_metric(
            "container.status",
            1.0,
            metric_type="gauge",
            tags=tags,
            description="Container running status (1=running,0=down)",
        )

        logger.debug(
            f"Recorded stats for {container_name}: CPU={cpu_percent}%, Mem={mem_percent}%"
        )
        flush()

        return {"cpu_percent": cpu_percent, "memory_percent": mem_percent}

    except subprocess.CalledProcessError as e:
        logger.error(f"Failed to get stats for container {container_name}: {e}")
        return {}
    except Exception as e:
        logger.error(f"Error parsing stats for container {container_name}: {e}")
        return {}


def collect_container_metrics(containers: list = None) -> dict[str, Any]:
    """
    Collect metrics for a list of containers.
    If no list provided, tries to discover containers from common names.
    """
    import subprocess

    target_names = containers
    if target_names is None:
        target_names = [
            "postgres-primary",
            "postgres-replica",
            "app-server-1",
            "app-server-2",
            "payment-service",
            "haproxy",
        ]

    # Get all running container names to resolve prefixes/suffixes
    try:
        cmd = ["docker", "ps", "--format", "{{.Names}}"]
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        running_containers = result.stdout.strip().split("\n")
        logger.info(f"Found running containers: {running_containers}")
    except Exception as e:
        logger.error(f"Failed to list containers: {e}")
        running_containers = []

    ensure_initialized()
    metrics = get_metrics_core()
    results = {}
    for target in target_names:
        # Find matching container
        actual_name = target
        found = False

        # Exact match first
        if target in running_containers:
            actual_name = target
            found = True
        else:
            # Partial match
            for rc in running_containers:
                if target in rc:
                    actual_name = rc
                    found = True
                    break

        if found:
            logger.info(f"Matched target '{target}' to container '{actual_name}'")
            # Use target as logical_name so labels are stable (e.g., "app-server-1")
            stats = get_container_stats(actual_name, logical_name=target)
            if stats:
                results[target] = stats  # Key by target name for consistency
        else:
            logger.warning(
                f"Container matching '{target}' not found in {running_containers}"
            )
            # Record container status as stopped (0) for missing containers
            tags = get_metric_tags(
                target_type="kubernetes",
                **{
                    "container.name": target,
                    "container_name": target,
                },
            )
            metrics.record_custom_metric(
                "container.status",
                0.0,
                metric_type="gauge",
                tags=tags,
                description="Container running status (1=running,0=down)",
            )
            flush()

    # Return True for tolerance check (metrics are already recorded to OTEL)
    # The actual metrics dict is available in the logs
    return len(results) > 0
