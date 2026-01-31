"""
Network-Based Chaos Experiments

Latency injection, packet loss, bandwidth limiting, and DNS disruption.
Supports Linux (via tc, iptables) and Windows (via NetLimiter or built-in tools).

Installation:
- Linux: apt-get install iproute2 iptables-persistent
- Windows: Built-in (netsh, Hyper-V)
"""

import logging
import platform
import subprocess
import time
from typing import Any, Optional

logger = logging.getLogger("chaosnetwork")


class NetworkChaosError(Exception):
    """Base exception for network chaos errors."""

    pass


class LinuxNetworkChaos:
    """Linux-based network chaos using tc (traffic control) and iptables."""

    @staticmethod
    def _ensure_tc() -> None:
        """Ensure tc is installed."""
        try:
            subprocess.run(["tc", "qdisc", "show"], capture_output=True, check=True)
        except (FileNotFoundError, subprocess.CalledProcessError):
            raise NetworkChaosError(
                "tc not found. Install with: apt-get install iproute2"
            )

    @staticmethod
    def _get_interface(interface: Optional[str] = None) -> str:
        """Get network interface, default to eth0 or first available."""
        if interface:
            return interface

        # Try common interface names
        for iface in ["eth0", "en0", "wlan0", "ens0"]:
            try:
                subprocess.run(
                    ["ip", "link", "show", iface], capture_output=True, check=True
                )
                return iface
            except:
                continue

        raise NetworkChaosError("Could not detect network interface")

    @staticmethod
    def inject_latency(
        latency_ms: int = 100,
        jitter_ms: int = 10,
        duration_seconds: int = 60,
        interface: Optional[str] = None,
    ) -> dict[str, Any]:
        """
        Inject network latency using tc (qdisc).

        Args:
            latency_ms: Latency in milliseconds
            jitter_ms: Jitter variation in milliseconds
            duration_seconds: Duration of injection
            interface: Network interface (auto-detect if None)

        Returns:
            Dict with injection metrics
        """
        try:
            LinuxNetworkChaos._ensure_tc()
            interface = LinuxNetworkChaos._get_interface(interface)

            # Create qdisc with netem (network emulation)
            cmd = [
                "tc",
                "qdisc",
                "add",
                "dev",
                interface,
                "root",
                "netem",
                "delay",
                f"{latency_ms}ms",
                f"{jitter_ms}ms",
            ]

            logger.info(
                f"Injecting {latency_ms}ms latency (±{jitter_ms}ms) on {interface}"
            )
            subprocess.run(cmd, check=True, capture_output=True)

            # Wait for duration
            time.sleep(duration_seconds)

            # Remove qdisc
            subprocess.run(
                ["tc", "qdisc", "del", "dev", interface, "root"],
                check=True,
                capture_output=True,
            )

            logger.info(f"Latency injection completed on {interface}")

            return {
                "status": "completed",
                "interface": interface,
                "latency_ms": latency_ms,
                "jitter_ms": jitter_ms,
                "duration_seconds": duration_seconds,
            }
        except Exception as e:
            # Cleanup on error
            try:
                subprocess.run(
                    ["tc", "qdisc", "del", "dev", interface, "root"],
                    capture_output=True,
                )
            except:
                pass

            logger.error(f"Latency injection failed: {e}")
            raise NetworkChaosError(f"Latency injection failed: {e}")

    @staticmethod
    def inject_packet_loss(
        loss_percent: float = 5.0,
        duration_seconds: int = 60,
        interface: Optional[str] = None,
    ) -> dict[str, Any]:
        """
        Inject packet loss using tc.

        Args:
            loss_percent: Percentage of packets to drop (0-100)
            duration_seconds: Duration of injection
            interface: Network interface

        Returns:
            Dict with injection metrics
        """
        try:
            LinuxNetworkChaos._ensure_tc()
            interface = LinuxNetworkChaos._get_interface(interface)

            if loss_percent < 0 or loss_percent > 100:
                raise NetworkChaosError("Loss percent must be 0-100")

            # Create qdisc with packet loss
            cmd = [
                "tc",
                "qdisc",
                "add",
                "dev",
                interface,
                "root",
                "netem",
                "loss",
                f"{loss_percent}%",
            ]

            logger.info(f"Injecting {loss_percent}% packet loss on {interface}")
            subprocess.run(cmd, check=True, capture_output=True)

            # Wait for duration
            time.sleep(duration_seconds)

            # Remove qdisc
            subprocess.run(
                ["tc", "qdisc", "del", "dev", interface, "root"],
                check=True,
                capture_output=True,
            )

            logger.info(f"Packet loss injection completed on {interface}")

            return {
                "status": "completed",
                "interface": interface,
                "loss_percent": loss_percent,
                "duration_seconds": duration_seconds,
            }
        except Exception as e:
            # Cleanup on error
            try:
                subprocess.run(
                    ["tc", "qdisc", "del", "dev", interface, "root"],
                    capture_output=True,
                )
            except:
                pass

            logger.error(f"Packet loss injection failed: {e}")
            raise NetworkChaosError(f"Packet loss injection failed: {e}")

    @staticmethod
    def limit_bandwidth(
        rate_mbps: int = 10, duration_seconds: int = 60, interface: Optional[str] = None
    ) -> dict[str, Any]:
        """
        Limit bandwidth using tc.

        Args:
            rate_mbps: Bandwidth limit in Mbps
            duration_seconds: Duration of limitation
            interface: Network interface

        Returns:
            Dict with injection metrics
        """
        try:
            LinuxNetworkChaos._ensure_tc()
            interface = LinuxNetworkChaos._get_interface(interface)

            if rate_mbps <= 0:
                raise NetworkChaosError("Rate must be positive")

            rate_kbps = rate_mbps * 1000

            # Create qdisc with rate limiting
            cmd = [
                "tc",
                "qdisc",
                "add",
                "dev",
                interface,
                "root",
                "tbf",
                "rate",
                f"{rate_kbps}kbit",
                "burst",
                f"{rate_kbps}kbit",
                "latency",
                "400ms",
            ]

            logger.info(f"Limiting bandwidth to {rate_mbps}Mbps on {interface}")
            subprocess.run(cmd, check=True, capture_output=True)

            # Wait for duration
            time.sleep(duration_seconds)

            # Remove qdisc
            subprocess.run(
                ["tc", "qdisc", "del", "dev", interface, "root"],
                check=True,
                capture_output=True,
            )

            logger.info(f"Bandwidth limitation completed on {interface}")

            return {
                "status": "completed",
                "interface": interface,
                "rate_mbps": rate_mbps,
                "duration_seconds": duration_seconds,
            }
        except Exception as e:
            # Cleanup on error
            try:
                subprocess.run(
                    ["tc", "qdisc", "del", "dev", interface, "root"],
                    capture_output=True,
                )
            except:
                pass

            logger.error(f"Bandwidth limitation failed: {e}")
            raise NetworkChaosError(f"Bandwidth limitation failed: {e}")


class WindowsNetworkChaos:
    """Windows-based network chaos using netsh or built-in tools."""

    @staticmethod
    def inject_latency(
        latency_ms: int = 100,
        jitter_ms: int = 10,
        duration_seconds: int = 60,
        interface: Optional[str] = None,
    ) -> dict[str, Any]:
        """
        Inject latency on Windows using NetLimiter or netsh.
        (Requires admin privileges)
        """
        try:
            # PowerShell script using NetLimiter COM object if available
            ps_script = f"""
            try {{
                Add-Type -AssemblyName "NetLimiterAPI"
                $limiter = New-Object NetLimiter.APIv2.NetLimiter
                $limiter.SetSimulatedLatency({latency_ms})
                Start-Sleep -Seconds {duration_seconds}
                $limiter.SetSimulatedLatency(0)
            }} catch {{
                Write-Error "NetLimiter not installed or admin privileges required"
            }}
            """

            logger.info(f"Injecting {latency_ms}ms latency on Windows")

            process = subprocess.Popen(
                ["powershell", "-Command", ps_script],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )

            stdout, stderr = process.communicate(timeout=duration_seconds + 10)

            return {
                "status": "completed",
                "latency_ms": latency_ms,
                "jitter_ms": jitter_ms,
                "duration_seconds": duration_seconds,
                "exit_code": process.returncode,
            }
        except Exception as e:
            logger.error(f"Latency injection failed: {e}")
            raise NetworkChaosError(f"Latency injection failed: {e}")

    @staticmethod
    def inject_packet_loss(
        loss_percent: float = 5.0,
        duration_seconds: int = 60,
        interface: Optional[str] = None,
    ) -> dict[str, Any]:
        """
        Inject packet loss on Windows.
        (Requires admin privileges and NetLimiter or equivalent)
        """
        try:
            ps_script = f"""
            try {{
                Add-Type -AssemblyName "NetLimiterAPI"
                $limiter = New-Object NetLimiter.APIv2.NetLimiter
                $limiter.SetSimulatedPacketLoss({loss_percent})
                Start-Sleep -Seconds {duration_seconds}
                $limiter.SetSimulatedPacketLoss(0)
            }} catch {{
                Write-Error "NetLimiter not installed or admin privileges required"
            }}
            """

            logger.info(f"Injecting {loss_percent}% packet loss on Windows")

            process = subprocess.Popen(
                ["powershell", "-Command", ps_script],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )

            stdout, stderr = process.communicate(timeout=duration_seconds + 10)

            return {
                "status": "completed",
                "loss_percent": loss_percent,
                "duration_seconds": duration_seconds,
                "exit_code": process.returncode,
            }
        except Exception as e:
            logger.error(f"Packet loss injection failed: {e}")
            raise NetworkChaosError(f"Packet loss injection failed: {e}")

    @staticmethod
    def limit_bandwidth(
        rate_mbps: int = 10, duration_seconds: int = 60, interface: Optional[str] = None
    ) -> dict[str, Any]:
        """
        Limit bandwidth on Windows.
        (Requires admin privileges and NetLimiter)
        """
        try:
            ps_script = f"""
            try {{
                Add-Type -AssemblyName "NetLimiterAPI"
                $limiter = New-Object NetLimiter.APIv2.NetLimiter
                $limiter.SetSimulatedBandwidth({rate_mbps})
                Start-Sleep -Seconds {duration_seconds}
                $limiter.SetSimulatedBandwidth(0)
            }} catch {{
                Write-Error "NetLimiter not installed or admin privileges required"
            }}
            """

            logger.info(f"Limiting bandwidth to {rate_mbps}Mbps on Windows")

            process = subprocess.Popen(
                ["powershell", "-Command", ps_script],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )

            stdout, stderr = process.communicate(timeout=duration_seconds + 10)

            return {
                "status": "completed",
                "rate_mbps": rate_mbps,
                "duration_seconds": duration_seconds,
                "exit_code": process.returncode,
            }
        except Exception as e:
            logger.error(f"Bandwidth limitation failed: {e}")
            raise NetworkChaosError(f"Bandwidth limitation failed: {e}")


def get_network_chaos() -> LinuxNetworkChaos or WindowsNetworkChaos:
    """Get platform-appropriate network chaos implementation."""
    system = platform.system()
    if system == "Linux":
        return LinuxNetworkChaos()
    elif system == "Windows":
        return WindowsNetworkChaos()
    else:
        raise NetworkChaosError(f"Unsupported platform: {system}")


# ============================================================================
# Chaos Toolkit Actions (callable from experiments)
# ============================================================================


def inject_latency(
    latency_ms: int = 100,
    jitter_ms: int = 10,
    duration_seconds: int = 60,
    interface: Optional[str] = None,
) -> dict[str, Any]:
    """
    Inject network latency.

    Usage in experiment:
        {
            "type": "action",
            "name": "Inject Latency",
            "provider": {
                "type": "python",
                "module": "chaosnetwork.network_chaos_actions",
                "func": "inject_latency",
                "arguments": {
                    "latency_ms": 500,
                    "jitter_ms": 50,
                    "duration_seconds": 30
                }
            }
        }
    """
    logger.info(f"[NETWORK] Injecting {latency_ms}ms latency for {duration_seconds}s")
    chaos = get_network_chaos()
    result = chaos.inject_latency(latency_ms, jitter_ms, duration_seconds, interface)
    logger.info("[NETWORK] Latency injection completed")
    return result


def inject_packet_loss(
    loss_percent: float = 5.0,
    duration_seconds: int = 60,
    interface: Optional[str] = None,
) -> dict[str, Any]:
    """
    Inject packet loss.

    Usage in experiment:
        {
            "type": "action",
            "name": "Inject Packet Loss",
            "provider": {
                "type": "python",
                "module": "chaosnetwork.network_chaos_actions",
                "func": "inject_packet_loss",
                "arguments": {
                    "loss_percent": 10,
                    "duration_seconds": 30
                }
            }
        }
    """
    logger.info(
        f"[NETWORK] Injecting {loss_percent}% packet loss for {duration_seconds}s"
    )
    chaos = get_network_chaos()
    result = chaos.inject_packet_loss(loss_percent, duration_seconds, interface)
    logger.info("[NETWORK] Packet loss injection completed")
    return result


def limit_bandwidth(
    rate_mbps: int = 10, duration_seconds: int = 60, interface: Optional[str] = None
) -> dict[str, Any]:
    """
    Limit network bandwidth.

    Usage in experiment:
        {
            "type": "action",
            "name": "Limit Bandwidth",
            "provider": {
                "type": "python",
                "module": "chaosnetwork.network_chaos_actions",
                "func": "limit_bandwidth",
                "arguments": {
                    "rate_mbps": 5,
                    "duration_seconds": 30
                }
            }
        }
    """
    logger.info(
        f"[NETWORK] Limiting bandwidth to {rate_mbps}Mbps for {duration_seconds}s"
    )
    chaos = get_network_chaos()
    result = chaos.limit_bandwidth(rate_mbps, duration_seconds, interface)
    logger.info("[NETWORK] Bandwidth limitation completed")
    return result
