"""Network DNS chaos actions."""

import logging
import subprocess
import time
from typing import Optional

from chaosotel import (
    ensure_initialized,
    flush,
    get_metric_tags,
    get_metrics_core,
    get_tracer,
)
from opentelemetry.trace import StatusCode

from chaosnetwork.config import config

logger = logging.getLogger("chaostoolkit")


def simulate_dns_timeout(
    duration: int = 30,
    dns_port: Optional[int] = None,
    iptables_chain: Optional[str] = None,
) -> dict:
    """
    Simulate DNS timeouts by blocking DNS port.

    :param duration: Duration in seconds
    :param dns_port: DNS port to block (default: CHAOS_DNS_PORT or 53)
    :param iptables_chain: iptables chain to use (default: CHAOS_IPTABLES_CHAIN or OUTPUT)

    Environment variables:
        CHAOS_DNS_PORT: DNS port (default: 53)
        CHAOS_IPTABLES_CHAIN: iptables chain (default: OUTPUT)
    """
    # Handle string input from Chaos Toolkit configuration
    duration = int(duration) if isinstance(duration, str) else duration
    if dns_port is not None:
        dns_port = int(dns_port) if isinstance(dns_port, str) else dns_port

    # Use config defaults if not specified
    dns_port = dns_port or config.DNS_PORT
    iptables_chain = iptables_chain or config.IPTABLES_CHAIN

    ensure_initialized()
    tracer = get_tracer()
    logger = logging.getLogger("chaosnetwork.actions.network_dns")
    metrics = get_metrics_core()

    with tracer.start_as_current_span("network.dns_timeout") as span:
        span.set_attribute("network.dns_blocked", True)
        span.set_attribute("network.dns_port", dns_port)
        span.set_attribute("network.iptables_chain", iptables_chain)
        span.set_attribute("duration_seconds", duration)

        try:
            # Block DNS port
            subprocess.run(
                [
                    "iptables",
                    "-A",
                    iptables_chain,
                    "-p",
                    "udp",
                    "--dport",
                    str(dns_port),
                    "-j",
                    "DROP",
                ],
                check=True,
                capture_output=True,
            )

            subprocess.run(
                [
                    "iptables",
                    "-A",
                    iptables_chain,
                    "-p",
                    "tcp",
                    "--dport",
                    str(dns_port),
                    "-j",
                    "DROP",
                ],
                check=True,
                capture_output=True,
            )

            logger.info(f"DNS blocked on port {dns_port} for {duration}s")
            time.sleep(duration)

            # Unblock
            subprocess.run(
                [
                    "iptables",
                    "-D",
                    iptables_chain,
                    "-p",
                    "udp",
                    "--dport",
                    str(dns_port),
                    "-j",
                    "DROP",
                ],
                check=False,
                capture_output=True,
            )

            subprocess.run(
                [
                    "iptables",
                    "-D",
                    iptables_chain,
                    "-p",
                    "tcp",
                    "--dport",
                    str(dns_port),
                    "-j",
                    "DROP",
                ],
                check=False,
                capture_output=True,
            )

            logger.info("DNS unblocked")
            span.set_status(StatusCode.OK)

            # Record DNS chaos metrics
            tags = get_metric_tags(target_type="network", dns_port=dns_port)
            metrics.record_custom_metric(
                "network.dns.failures",
                1,
                metric_type="counter",
                tags=tags,
                description="DNS chaos failures injected",
            )
            logger.debug("Recorded network.dns.failures: 1 (simulated DNS block)")

            flush()

            return {"success": True, "duration": duration, "dns_port": dns_port}

        except Exception as e:
            tags = get_metric_tags(target_type="network", error_type=type(e).__name__)
            metrics.record_custom_metric(
                "network.errors",
                1,
                metric_type="counter",
                tags=tags,
                description="Network chaos errors",
            )
            logger.error(f"DNS timeout simulation failed: {e}")
            span.set_status(StatusCode.ERROR, str(e))
            flush()
            return {"success": False, "error": str(e)}
