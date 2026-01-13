"""Network latency injection actions - both fixed and randomized."""

import logging
import random
import subprocess
import time
from typing import Optional

from chaosnetwork.config import config
from chaosotel import (
    ensure_initialized,
    flush,
    get_metric_tags,
    get_metrics_core,
    get_tracer,
)
from opentelemetry.trace import StatusCode

logger = logging.getLogger("chaostoolkit")


def simulate_network_conditions(
    latency: int = 0,
    jitter: int = 0,
    loss: float = 0.0,
    bandwidth: str = "",
    duration: int = 0,
    interface: Optional[str] = None,
) -> dict:
    """
    Simulate network conditions using `tc` (Traffic Control).

    :param latency: Latency in milliseconds
    :param jitter: Jitter in milliseconds
    :param loss: Packet loss percentage
    :param bandwidth: Bandwidth limit (e.g., "1mbit")
    :param duration: Duration in seconds (0 means indefinite)
    :param interface: Network interface (default: CHAOS_NETWORK_INTERFACE or eth0)

    Environment variables:
        CHAOS_NETWORK_INTERFACE: Network interface to apply rules to (default: eth0)
    """
    # Handle string input from Chaos Toolkit configuration
    latency = int(latency) if isinstance(latency, str) else latency
    jitter = int(jitter) if isinstance(jitter, str) else jitter
    loss = float(loss) if isinstance(loss, str) else loss
    duration = int(duration) if isinstance(duration, str) else duration

    # Use config default if not specified
    interface = interface or config.NETWORK_INTERFACE

    ensure_initialized()
    tracer = get_tracer()
    logger = logging.getLogger("chaosnetwork.actions.network_latency")
    metrics = get_metrics_core()

    try:
        span = tracer.start_span("network.simulate_conditions")
        span.set_attribute("network.interface", interface)
        span.set_attribute("network.latency_ms", latency)
        span.set_attribute("network.jitter_ms", jitter)
        span.set_attribute("network.loss_percent", loss)
        span.set_attribute("duration_seconds", duration)

        # Reset existing rules
        try:
            subprocess.run(
                ["tc", "qdisc", "del", "dev", interface, "root"],
                stderr=subprocess.DEVNULL,
                check=False,
            )
        except Exception:
            pass

        if latency == 0 and loss == 0.0 and not bandwidth:
            logger.info("Resetting network conditions")
            span.set_status(StatusCode.OK)
            span.end()
            flush()
            return {"success": True, "reset": True}

        cmd = ["tc", "qdisc", "add", "dev", interface, "root", "netem"]

        if latency > 0:
            cmd.extend(["delay", f"{latency}ms"])
            if jitter > 0:
                cmd.append(f"{jitter}ms")

        if loss > 0:
            cmd.extend(["loss", f"{loss}%"])

        logger.info(f"Applying network conditions: {' '.join(cmd)}")

        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            logger.error(f"Failed to apply network conditions: {result.stderr}")
            span.set_status(StatusCode.ERROR, result.stderr)
            span.end()
            flush()
            return {"success": False, "error": result.stderr}

        # Record network chaos metrics
        tags = get_metric_tags(target_type="network", network_interface=interface)

        if latency > 0:
            metrics.record_custom_metric(
                "network.latency_injection.ms",
                latency,
                metric_type="gauge",
                unit="ms",
                tags=tags,
                description="Injected network latency in ms",
            )
            logger.debug(f"Recorded network.latency_injection.ms: {latency}ms")

        if loss > 0:
            metrics.record_custom_metric(
                "network.packet_loss.percent",
                loss,
                metric_type="gauge",
                unit="percent",
                tags=tags,
                description="Injected packet loss percentage",
            )
            logger.debug(f"Recorded network.packet_loss.percent: {loss}%")

        span.set_status(StatusCode.OK)
        span.end()  # End span BEFORE the sleep
        flush()

        # Sleep and cleanup OUTSIDE the span to avoid context issues
        if duration > 0:
            logger.info(f"Sleeping for {duration} seconds...")
            time.sleep(duration)
            logger.info("Resetting network conditions after duration")
            subprocess.run(
                ["tc", "qdisc", "del", "dev", interface, "root"],
                stderr=subprocess.DEVNULL,
                check=False,
            )

        return {
            "success": True,
            "latency_ms": latency,
            "jitter_ms": jitter,
            "loss_percent": loss,
            "duration": duration,
        }

    except Exception as e:
        tags = get_metric_tags(target_type="network", error_type=type(e).__name__)
        metrics.record_custom_metric(
            "network.errors",
            1,
            metric_type="counter",
            tags=tags,
            description="Network chaos errors",
        )
        logger.error(f"Error executing tc command: {e}")
        flush()
        return {"success": False, "error": str(e)}


def simulate_random_network_conditions(
    latency_min: int = 50,
    latency_max: int = 1000,
    jitter_min: int = 0,
    jitter_max: int = 200,
    loss_min: float = 0.0,
    loss_max: float = 5.0,
    duration: int = 60,
) -> dict:
    """
    Simulate RANDOM network conditions for chaos testing.
    Values are randomized within specified ranges.

    :param latency_min: Minimum latency in milliseconds
    :param latency_max: Maximum latency in milliseconds
    :param jitter_min: Minimum jitter in milliseconds
    :param jitter_max: Maximum jitter in milliseconds
    :param loss_min: Minimum packet loss percentage
    :param loss_max: Maximum packet loss percentage
    :param duration: Duration in seconds
    """
    ensure_initialized()
    tracer = get_tracer()
    logger = logging.getLogger("chaosnetwork.actions.network_latency")

    # Randomize parameters
    latency = random.randint(latency_min, latency_max)
    jitter = random.randint(jitter_min, jitter_max)
    loss = random.uniform(loss_min, loss_max)

    logger.info(
        f"RANDOM NETWORK CHAOS: {latency}ms latency, {jitter}ms jitter, {loss:.2f}% loss for {duration}s"
    )

    with tracer.start_as_current_span("network.random_chaos") as span:
        span.set_attribute("chaos.randomized", True)
        span.set_attribute("network.latency_ms", latency)
        span.set_attribute("network.jitter_ms", jitter)
        span.set_attribute("network.loss_percent", loss)

        # Use the fixed function with randomized values
        result = simulate_network_conditions(
            latency=latency, jitter=jitter, loss=loss, duration=duration
        )

        result["randomized"] = True
        result["ranges"] = {
            "latency": f"{latency_min}-{latency_max}ms",
            "jitter": f"{jitter_min}-{jitter_max}ms",
            "loss": f"{loss_min:.1f}-{loss_max:.1f}%",
        }

        return result
