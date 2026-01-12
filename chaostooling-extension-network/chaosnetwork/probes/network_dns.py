"""Network DNS resolution probes."""
import socket
import subprocess
import time
import logging
from typing import Optional, Dict, List
from chaosotel import ensure_initialized, get_tracer, flush, get_metric_tags, get_metrics_core
from opentelemetry.trace import StatusCode


def probe_dns_resolution(
    hostname: str,
    dns_server: Optional[str] = None,
    timeout: int = 5,
) -> Dict:
    """
    Probe DNS resolution for a hostname.
    
    Args:
        hostname: Hostname to resolve
        dns_server: Optional DNS server to use (default: system resolver)
        timeout: Timeout in seconds
        
    Returns:
        Dict with DNS resolution results
    """
    ensure_initialized()
    tracer = get_tracer()
    logger = logging.getLogger("chaosnetwork.probes.network_dns")
    metrics = get_metrics_core()
    start = time.time()
    
    try:
        with tracer.start_as_current_span("probe.network.dns_resolution") as span:
            span.set_attribute("network.operation", "dns_resolution")
            span.set_attribute("dns.hostname", hostname)
            if dns_server:
                span.set_attribute("dns.server", dns_server)
            
            resolved_ips: List[str] = []
            
            if dns_server:
                # Use nslookup/dig with specific DNS server
                try:
                    result = subprocess.run(
                        ["nslookup", hostname, dns_server],
                        capture_output=True,
                        text=True,
                        timeout=timeout
                    )
                    # Parse IPs from nslookup output
                    for line in result.stdout.split('\n'):
                        if 'Address:' in line and not line.strip().startswith('Server:'):
                            ip = line.split('Address:')[1].strip().split('#')[0].strip()
                            if ip and not ip.startswith('127.'):
                                resolved_ips.append(ip)
                except subprocess.TimeoutExpired:
                    pass
            else:
                # Use Python's built-in resolver
                socket.setdefaulttimeout(timeout)
                try:
                    # Get all addresses
                    addr_info = socket.getaddrinfo(hostname, None)
                    resolved_ips = list(set(addr[4][0] for addr in addr_info))
                except socket.gaierror:
                    pass
            
            resolution_time_ms = (time.time() - start) * 1000
            
            tags = get_metric_tags(
                protocol="DNS",
                operation="dns_resolution"
            )
            
            # Record metrics
            metrics.record_custom_metric(
                "network.dns.resolution.time_ms",
                resolution_time_ms,
                metric_type="histogram",
                unit="ms",
                tags=tags,
                description="DNS resolution time",
            )
            
            success = len(resolved_ips) > 0
            
            result_data = {
                "success": success,
                "hostname": hostname,
                "dns_server": dns_server,
                "resolved_ips": resolved_ips,
                "resolution_time_ms": resolution_time_ms,
                "ip_count": len(resolved_ips)
            }
            
            span.set_attribute("dns.resolution.success", success)
            span.set_attribute("dns.resolution.ip_count", len(resolved_ips))
            span.set_attribute("dns.resolution.time_ms", resolution_time_ms)
            
            if success:
                span.set_status(StatusCode.OK)
                logger.info(f"DNS resolution for {hostname}: {resolved_ips} ({resolution_time_ms:.2f}ms)")
            else:
                span.set_status(StatusCode.ERROR, "DNS resolution failed")
                logger.warning(f"DNS resolution for {hostname} failed")
                metrics.record_custom_metric(
                    "network.dns.failures",
                    1,
                    metric_type="counter",
                    tags=tags,
                    description="DNS resolution failures",
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
        logger.error("DNS resolution probe failed: %s", e)
        flush()
        raise

