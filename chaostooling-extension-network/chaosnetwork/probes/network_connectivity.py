"""Network connectivity probes."""

import logging
import socket
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


def probe_network_connectivity(
    host: str,
    port: int,
    timeout: int = 5,
    protocol: str = "tcp",
) -> dict:
    """
    Probe network connectivity to a host:port.

    Args:
        host: Target hostname or IP address
        port: Target port number
        timeout: Connection timeout in seconds
        protocol: Protocol to use (tcp or udp)

    Returns:
        Dict with connectivity status and timing
    """
    ensure_initialized()
    tracer = get_tracer()
    logger = logging.getLogger("chaosnetwork.probes.network_connectivity")
    metrics = get_metrics_core()
    start = time.time()

    try:
        with tracer.start_as_current_span("probe.network.connectivity") as span:
            span.set_attribute("network.peer.address", host)
            span.set_attribute("network.peer.port", port)
            span.set_attribute("network.protocol", protocol.upper())
            span.set_attribute("network.operation", "connectivity_probe")

            socket_type = (
                socket.SOCK_STREAM if protocol.lower() == "tcp" else socket.SOCK_DGRAM
            )

            sock = socket.socket(socket.AF_INET, socket_type)
            sock.settimeout(timeout)

            try:
                if protocol.lower() == "tcp":
                    sock.connect((host, port))
                    connected = True
                else:
                    # UDP - send a small packet and see if we get ICMP unreachable
                    sock.sendto(b"\x00", (host, port))
                    connected = True  # UDP is connectionless, assume reachable

            except (OSError, socket.timeout, ConnectionRefusedError) as e:
                connected = False
                error_msg = str(e)
            else:
                error_msg = None
            finally:
                sock.close()

            connection_time_ms = (time.time() - start) * 1000

            tags = get_metric_tags(
                protocol=protocol.upper(), operation="connectivity_probe"
            )

            # Record metrics
            if connected:
                metrics.record_custom_metric(
                    "network.connection.time_ms",
                    connection_time_ms,
                    metric_type="histogram",
                    unit="ms",
                    tags=tags,
                    description="Network connection time",
                )

            if not connected:
                metrics.record_custom_metric(
                    "network.connection.errors",
                    1,
                    metric_type="counter",
                    tags=tags,
                    description="Network connection failures",
                )

            result_data = {
                "success": connected,
                "host": host,
                "port": port,
                "protocol": protocol.upper(),
                "connection_time_ms": connection_time_ms if connected else None,
                "error": error_msg,
            }

            span.set_attribute("network.connectivity.success", connected)
            span.set_attribute("network.connectivity.time_ms", connection_time_ms)

            if connected:
                span.set_status(StatusCode.OK)
                logger.info(
                    f"Network connectivity to {host}:{port} OK ({connection_time_ms:.2f}ms)"
                )
            else:
                span.set_status(StatusCode.ERROR, error_msg or "Connection failed")
                logger.warning(
                    f"Network connectivity to {host}:{port} failed: {error_msg}"
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
        span.set_status(StatusCode.ERROR, str(e))
        logger.error(f"Network connectivity probe failed: {e}")
        flush()
        raise


def probe_host_reachable(
    host: str,
    count: int = 3,
    timeout: int = 5,
    use_tcp_fallback: bool = True,
    tcp_port: int = 80,
) -> bool:
    """
    Simple probe to check if a host is reachable via ICMP ping or TCP fallback.

    This is a simpler version that returns just a boolean for use
    in steady-state hypothesis checks.

    Args:
        host: Target hostname or IP address
        count: Number of ping packets (or TCP connection attempts for fallback)
        timeout: Timeout in seconds
        use_tcp_fallback: If True, use TCP connection check if ping is unavailable
        tcp_port: Port to use for TCP reachability check (default: 80)

    Returns:
        True if host is reachable, False otherwise
    """
    ensure_initialized()
    tracer = get_tracer()
    logger = logging.getLogger("chaosnetwork.probes.network_connectivity")
    metrics = get_metrics_core()
    start = time.time()

    try:
        with tracer.start_as_current_span("probe.network.host_reachable") as span:
            span.set_attribute("network.peer.address", host)
            span.set_attribute("network.operation", "reachability_probe")

            # Try to use ping first, fallback to TCP if ping is not available
            ping_available = True
            try:
                # Check if ping is available
                subprocess.run(
                    ["ping", "-c", "1", "-W", "1", "127.0.0.1"],
                    capture_output=True,
                    text=True,
                    timeout=2,
                )
            except (FileNotFoundError, subprocess.TimeoutExpired):
                ping_available = False

            if ping_available:
                result = subprocess.run(
                    ["ping", "-c", str(count), "-W", str(timeout), host],
                    capture_output=True,
                    text=True,
                    timeout=timeout * count + 5,
                )
                reachable = result.returncode == 0
            elif use_tcp_fallback:
                # Fallback to TCP connection check
                logger.debug(
                    f"ping not available, using TCP connection check to {host}:{tcp_port}"
                )
                span.set_attribute("network.reachability.method", "tcp")

                import socket

                reachable = False
                for i in range(count):
                    try:
                        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                        sock.settimeout(timeout)
                        sock.connect((host, tcp_port))
                        sock.close()
                        reachable = True
                        break
                    except (socket.gaierror, socket.timeout, OSError):
                        continue
                    finally:
                        try:
                            sock.close()
                        except:
                            pass
            else:
                # ping not available and TCP fallback disabled
                logger.error("ping command not found and TCP fallback is disabled")
                reachable = False

            probe_time_ms = (time.time() - start) * 1000

            # Determine protocol for tags
            protocol = "TCP" if not ping_available and use_tcp_fallback else "ICMP"
            tags = get_metric_tags(protocol=protocol, operation="reachability_probe")

            if reachable:
                metrics.record_custom_metric(
                    "network.reachability.time_ms",
                    probe_time_ms,
                    metric_type="histogram",
                    unit="ms",
                    tags=tags,
                    description="Host reachability probe duration",
                )

            span.set_attribute("network.host.reachable", reachable)

            if reachable:
                span.set_status(StatusCode.OK)
                logger.info(f"Host {host} is reachable ({probe_time_ms:.2f}ms)")
            else:
                span.set_status(StatusCode.ERROR, "Host unreachable")
                logger.warning(f"Host {host} is not reachable")
                metrics.record_custom_metric(
                    "network.connection.errors",
                    1,
                    metric_type="counter",
                    tags=tags,
                    description="Network connection failures",
                )

            flush()
            return reachable

    except subprocess.TimeoutExpired:
        metrics.record_custom_metric(
            "network.errors",
            1,
            metric_type="counter",
            tags=get_metric_tags(error_type="TimeoutExpired"),
            description="Network probe errors",
        )
        span.set_status(StatusCode.ERROR, "Ping timeout")
        logger.error(f"Host reachability probe to {host} timed out")
        flush()
        return False
    except Exception as e:
        metrics.record_custom_metric(
            "network.errors",
            1,
            metric_type="counter",
            tags=get_metric_tags(error_type=type(e).__name__),
            description="Network probe errors",
        )
        span.set_status(StatusCode.ERROR, str(e))
        logger.error(f"Host reachability probe failed: {e}")
        flush()
        return False
