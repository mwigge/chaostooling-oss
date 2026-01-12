import subprocess
import logging
from typing import Optional

logger = logging.getLogger("chaostoolkit")

import time
from chaosotel import ensure_initialized, get_tracer, get_logger, flush, get_metric_tags, get_metrics_core
from opentelemetry.trace import StatusCode

def simulate_network_conditions(latency: int = 0, jitter: int = 0, loss: float = 0.0, bandwidth: str = "", duration: int = 0) -> bool:
    """
    Simulate network conditions using `tc` (Traffic Control).
    This requires the container/host to have NET_ADMIN capability.
    
    :param latency: Latency in milliseconds
    :param jitter: Jitter in milliseconds
    :param loss: Packet loss percentage
    :param bandwidth: Bandwidth limit (e.g., "1mbit")
    :param duration: Duration in seconds to apply the conditions (0 means indefinite)
    """
    ensure_initialized()
    tracer = get_tracer()
    metrics = get_metrics_core()
    
    try:
        with tracer.start_as_current_span("chaos.network.simulate_conditions") as span:
            span.set_attribute("chaos.action", "simulate_network_conditions")
            span.set_attribute("chaos.network.latency_ms", latency)
            span.set_attribute("chaos.network.jitter_ms", jitter)
            span.set_attribute("chaos.network.loss_percent", loss)
            span.set_attribute("chaos.duration_seconds", duration)
            
            # Update metrics via chaosotel
            tags = get_metric_tags(target_type="network", operation="simulate_network_conditions")
            if latency > 0:
                metrics.record_custom_metric(
                    "network.latency_injection.ms",
                    latency,
                    metric_type="gauge",
                    unit="ms",
                    tags=tags,
                    description="Injected network latency in ms",
                )
            if loss > 0:
                metrics.record_custom_metric(
                    "network.packet_loss.percent",
                    loss,
                    metric_type="gauge",
                    unit="percent",
                    tags=tags,
                    description="Injected packet loss percentage",
                )

            # Reset existing rules
            try:
                subprocess.run(["tc", "qdisc", "del", "dev", "eth0", "root"], stderr=subprocess.DEVNULL, check=False)
            except Exception:
                pass

            if latency == 0 and loss == 0.0 and not bandwidth:
                logger.info("Resetting network conditions")
                return True

            cmd = ["tc", "qdisc", "add", "dev", "eth0", "root", "netem"]
            
            if latency > 0:
                cmd.extend(["delay", f"{latency}ms"])
                if jitter > 0:
                    cmd.append(f"{jitter}ms")
                    
            if loss > 0:
                cmd.extend(["loss", f"{loss}%"])
                
            if bandwidth:
                logger.warning("Bandwidth simulation is not fully implemented in this simple action. Ignoring bandwidth parameter.")

            logger.info(f"Applying network conditions: {' '.join(cmd)}")
            
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode != 0:
                logger.error(f"Failed to apply network conditions: {result.stderr}")
                span.set_status(StatusCode.ERROR, result.stderr)
                return False
                
            if duration > 0:
                logger.info(f"Sleeping for {duration} seconds...")
                time.sleep(duration)
                logger.info("Resetting network conditions after duration")
                subprocess.run(["tc", "qdisc", "del", "dev", "eth0", "root"], stderr=subprocess.DEVNULL, check=False)
                
            span.set_status(StatusCode.OK)
            flush()
            return True
            
    except Exception as e:
        logger.error(f"Error executing tc command: {e}")
        error_tags = get_metric_tags(target_type="network", error_type=type(e).__name__)
        metrics.record_custom_metric(
            "network.errors",
            1,
            metric_type="counter",
            tags=error_tags,
            description="Network chaos errors",
        )
        flush()
        return False

def simulate_dns_timeout(duration: int = 10) -> bool:
    """
    Simulate DNS timeout by blocking port 53.
    This requires the container/host to have NET_ADMIN capability.
    
    :param duration: Duration in seconds to block DNS
    """
    ensure_initialized()
    tracer = get_tracer()
    metrics = get_metrics_core()
    try:
        with tracer.start_as_current_span("chaos.network.simulate_dns_timeout") as span:
            span.set_attribute("chaos.action", "simulate_dns_timeout")
            span.set_attribute("chaos.duration_seconds", duration)
            
            logger.info(f"Blocking DNS (port 53) for {duration} seconds")
            
            metrics.record_custom_metric(
                "network.dns.partition.active",
                1,
                metric_type="gauge",
                tags=get_metric_tags(target_type="network"),
                description="DNS partition active flag",
            )
            
            # Block DNS traffic
            cmds = [
                ["iptables", "-A", "OUTPUT", "-p", "udp", "--dport", "53", "-j", "DROP"],
                ["iptables", "-A", "OUTPUT", "-p", "tcp", "--dport", "53", "-j", "DROP"]
            ]
            
            for cmd in cmds:
                subprocess.run(cmd, check=True, stderr=subprocess.DEVNULL)
                
            if duration > 0:
                logger.info(f"Sleeping for {duration} seconds...")
                time.sleep(duration)
                
                logger.info("Unblocking DNS")
                cleanup_cmds = [
                    ["iptables", "-D", "OUTPUT", "-p", "udp", "--dport", "53", "-j", "DROP"],
                    ["iptables", "-D", "OUTPUT", "-p", "tcp", "--dport", "53", "-j", "DROP"]
                ]
                for cmd in cleanup_cmds:
                    subprocess.run(cmd, check=False, stderr=subprocess.DEVNULL)
                    
                metrics.record_custom_metric(
                    "network.dns.partition.active",
                    0,
                    metric_type="gauge",
                    tags=get_metric_tags(target_type="network"),
                    description="DNS partition active flag",
                )
                    
            span.set_status(StatusCode.OK)
            flush()
            return True
            
    except Exception as e:
        logger.error(f"Failed to simulate DNS timeout: {e}")
        metrics.record_custom_metric(
            "network.errors",
            1,
            metric_type="counter",
            tags=get_metric_tags(target_type="network", error_type=type(e).__name__),
            description="Network chaos errors",
        )
        
        # Try to cleanup if something failed
        try:
            cleanup_cmds = [
                ["iptables", "-D", "OUTPUT", "-p", "udp", "--dport", "53", "-j", "DROP"],
                ["iptables", "-D", "OUTPUT", "-p", "tcp", "--dport", "53", "-j", "DROP"]
            ]
            for cmd in cleanup_cmds:
                subprocess.run(cmd, check=False, stderr=subprocess.DEVNULL)
            
            metrics.record_custom_metric(
                "network.dns.partition.active",
                0,
                metric_type="gauge",
                tags=get_metric_tags(target_type="network"),
                description="DNS partition active flag",
            )
        except:
            pass
            
        flush()
        return False
