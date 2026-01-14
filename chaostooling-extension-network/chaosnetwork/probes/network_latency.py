"""Network latency and conditions probes."""

import logging
import re
import subprocess
import time

from chaosotel import (
    ensure_initialized,
    flush,
    get_metric_tags,
    get_metrics_core,
    get_tracer,
)
from opentelemetry.trace import StatusCode


def probe_network_latency(
    target_host: str,
    count: int = 5,
    timeout: int = 5,
) -> dict:
    """
    Probe network latency to a target host using ping.

    Args:
        target_host: Target hostname or IP address to measure latency to
        count: Number of ping packets to send
        timeout: Timeout in seconds for each ping

    Returns:
        Dict with latency measurements (min, avg, max, packet_loss)
    """
    ensure_initialized()
    tracer = get_tracer()
    logger = logging.getLogger("chaosnetwork.probes.network_latency")
    metrics = get_metrics_core()
    start = time.time()

    try:
        with tracer.start_as_current_span("probe.network.latency") as span:
            span.set_attribute("network.peer.address", target_host)
            span.set_attribute("network.operation", "latency_probe")
            span.set_attribute("network.ping.count", count)

            # Run ping command
            result = subprocess.run(
                ["ping", "-c", str(count), "-W", str(timeout), target_host],
                capture_output=True,
                text=True,
                timeout=timeout * count + 5,
            )

            probe_time_ms = (time.time() - start) * 1000
            tags = get_metric_tags(
                network_interface="default", protocol="ICMP", operation="latency_probe"
            )

            # Parse ping output
            output = result.stdout

            # Extract packet loss
            loss_match = re.search(r"(\d+)% packet loss", output)
            packet_loss = float(loss_match.group(1)) if loss_match else 100.0

            # Extract latency stats (min/avg/max/mdev)
            stats_match = re.search(
                r"rtt min/avg/max/mdev = ([\d.]+)/([\d.]+)/([\d.]+)/([\d.]+)", output
            )

            if stats_match:
                min_latency = float(stats_match.group(1))
                avg_latency = float(stats_match.group(2))
                max_latency = float(stats_match.group(3))
                jitter = float(stats_match.group(4))
            else:
                min_latency = avg_latency = max_latency = jitter = 0.0

            # Record metrics
            metrics.record_custom_metric(
                "network.latency.ms",
                avg_latency,
                metric_type="histogram",
                unit="ms",
                tags=tags,
                description="Observed network latency (avg)",
            )

            if packet_loss > 0:
                metrics.record_custom_metric(
                    "network.packet_loss.count",
                    int(count * packet_loss / 100),
                    metric_type="counter",
                    tags=tags,
                    description="Lost packets during probe",
                )

            result_data = {
                "success": result.returncode == 0,
                "target_host": target_host,
                "packets_sent": count,
                "packet_loss_percent": packet_loss,
                "latency_min_ms": min_latency,
                "latency_avg_ms": avg_latency,
                "latency_max_ms": max_latency,
                "jitter_ms": jitter,
                "probe_time_ms": probe_time_ms,
            }

            span.set_attribute("network.latency.avg_ms", avg_latency)
            span.set_attribute("network.latency.min_ms", min_latency)
            span.set_attribute("network.latency.max_ms", max_latency)
            span.set_attribute("network.packet_loss.percent", packet_loss)
            span.set_status(StatusCode.OK)

            logger.info(
                f"Network latency probe to {target_host}: avg={avg_latency}ms, loss={packet_loss}%"
            )
            flush()
            return result_data

    except subprocess.TimeoutExpired:
        metrics.record_custom_metric(
            "network.errors",
            1,
            metric_type="counter",
            tags=get_metric_tags(error_type="TimeoutExpired"),
            description="Network probe errors",
        )
        logger.error("Network latency probe to %s timed out", target_host)
        flush()
        return {
            "success": False,
            "target_host": target_host,
            "error": "Ping timeout",
            "packet_loss_percent": 100.0,
        }
    except Exception as e:
        metrics.record_custom_metric(
            "network.errors",
            1,
            metric_type="counter",
            tags=get_metric_tags(error_type=type(e).__name__),
            description="Network probe errors",
        )
        logger.error("Network latency probe failed: %s", e)
        flush()
        raise


def probe_network_conditions() -> dict:
    """
    Probe current network conditions (tc qdisc rules).

    Returns:
        Dict with current traffic control settings
    """
    ensure_initialized()
    tracer = get_tracer()
    logger = logging.getLogger("chaosnetwork.probes.network_latency")
    metrics = get_metrics_core()

    try:
        with tracer.start_as_current_span("probe.network.conditions") as span:
            span.set_attribute("network.operation", "conditions_probe")

            # Get current tc qdisc rules
            result = subprocess.run(
                ["tc", "qdisc", "show", "dev", "eth0"], capture_output=True, text=True
            )

            output = result.stdout

            # Parse netem settings
            has_netem = "netem" in output

            latency_ms = 0
            jitter_ms = 0
            loss_percent = 0.0

            if has_netem:
                # Extract delay
                delay_match = re.search(r"delay ([\d.]+)ms", output)
                if delay_match:
                    latency_ms = float(delay_match.group(1))

                # Extract jitter
                jitter_match = re.search(r"delay [\d.]+ms\s+([\d.]+)ms", output)
                if jitter_match:
                    jitter_ms = float(jitter_match.group(1))

                # Extract loss
                loss_match = re.search(r"loss ([\d.]+)%", output)
                if loss_match:
                    loss_percent = float(loss_match.group(1))

            result_data = {
                "success": True,
                "interface": "eth0",
                "has_netem": has_netem,
                "latency_ms": latency_ms,
                "jitter_ms": jitter_ms,
                "loss_percent": loss_percent,
                "raw_output": output.strip(),
            }

            span.set_attribute("network.conditions.has_netem", has_netem)
            span.set_attribute("network.conditions.latency_ms", latency_ms)
            span.set_attribute("network.conditions.loss_percent", loss_percent)
            span.set_status(StatusCode.OK)

            logger.info(
                f"Network conditions: netem={has_netem}, latency={latency_ms}ms, loss={loss_percent}%"
            )
            flush()
            return result_data

    except Exception as e:
        metrics.record_custom_metric(
            "network.errors",
            1,
            metric_type="counter",
            tags=get_metric_tags(error_type=type(e).__name__),
            description="Network probe errors",
        )
        logger.error("Network conditions probe failed: %s", e)
        flush()
        raise
