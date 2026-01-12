"""Chaos Toolkit Extension for Network Chaos Engineering.

This extension provides network-level chaos engineering capabilities including:
- Network latency injection (fixed and randomized)
- Jitter and packet loss simulation  
- Bandwidth throttling
- DNS timeout simulation
- Network partition testing
- Network latency and connectivity probes
"""

__version__ = "0.1.0"

from typing import Dict

__all__ = ["__version__", "discover"]


def discover(discover_system: bool = True) -> Dict:
    """
    Discover network chaos capabilities.
    
    Returns:
        Dict with actions and probes available
    """
    return {
        "chaostoolkit_extension_name": "chaostoolkit-extension-network",
        "chaostoolkit_extension_version": __version__,
        "actions": [
            {
                "type": "action",
                "name": "simulate_network_conditions",
                "mod": "chaosnetwork.actions.network_latency",
                "doc": "Simulate fixed network latency, jitter, and packet loss"
            },
            {
                "type": "action",
                "name": "simulate_random_network_conditions",
                "mod": "chaosnetwork.actions.network_latency",
                "doc": "Simulate randomized network conditions for chaos testing"
            },
            {
                "type": "action",
                "name": "simulate_dns_timeout",
                "mod": "chaosnetwork.actions.network_dns",
                "doc": "Simulate DNS resolution timeouts"
            },
            {
                "type": "action",
                "name": "create_network_partition",
                "mod": "chaosnetwork.actions.network_partition",
                "doc": "Create network partition between components"
            }
        ],
        "probes": [
            {
                "type": "probe",
                "name": "probe_network_latency",
                "mod": "chaosnetwork.probes.network_latency",
                "doc": "Measure network latency and packet loss to a target host"
            },
            {
                "type": "probe",
                "name": "probe_network_conditions",
                "mod": "chaosnetwork.probes.network_latency",
                "doc": "Check current traffic control (tc) settings"
            },
            {
                "type": "probe",
                "name": "probe_dns_resolution",
                "mod": "chaosnetwork.probes.network_dns",
                "doc": "Verify DNS resolution for a hostname"
            },
            {
                "type": "probe",
                "name": "probe_network_connectivity",
                "mod": "chaosnetwork.probes.network_connectivity",
                "doc": "Check TCP/UDP connectivity to a host:port"
            },
            {
                "type": "probe",
                "name": "probe_host_reachable",
                "mod": "chaosnetwork.probes.network_connectivity",
                "doc": "Simple ICMP ping check for host reachability"
            }
        ]
    }
