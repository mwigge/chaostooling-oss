"""
Network extension configuration.

All settings can be overridden via environment variables.
"""
import os
from typing import Optional


class NetworkConfig:
    """Configuration for network chaos actions and probes."""
    
    # Network Interface
    NETWORK_INTERFACE: str = os.getenv("CHAOS_NETWORK_INTERFACE", "eth0")
    
    # DNS Settings
    DNS_PORT: int = int(os.getenv("CHAOS_DNS_PORT", "53"))
    DNS_SERVER: Optional[str] = os.getenv("CHAOS_DNS_SERVER")  # Default system resolver
    DNS_TIMEOUT: int = int(os.getenv("CHAOS_DNS_TIMEOUT", "5"))
    
    # iptables Settings
    IPTABLES_CHAIN: str = os.getenv("CHAOS_IPTABLES_CHAIN", "OUTPUT")
    
    # Default Latency Settings
    DEFAULT_LATENCY_MS: int = int(os.getenv("CHAOS_DEFAULT_LATENCY_MS", "0"))
    DEFAULT_JITTER_MS: int = int(os.getenv("CHAOS_DEFAULT_JITTER_MS", "0"))
    DEFAULT_PACKET_LOSS: float = float(os.getenv("CHAOS_DEFAULT_PACKET_LOSS", "0.0"))
    DEFAULT_DURATION: int = int(os.getenv("CHAOS_DEFAULT_DURATION", "60"))
    
    # Randomized Chaos Defaults
    RANDOM_LATENCY_MIN: int = int(os.getenv("CHAOS_RANDOM_LATENCY_MIN", "50"))
    RANDOM_LATENCY_MAX: int = int(os.getenv("CHAOS_RANDOM_LATENCY_MAX", "1000"))
    RANDOM_JITTER_MIN: int = int(os.getenv("CHAOS_RANDOM_JITTER_MIN", "0"))
    RANDOM_JITTER_MAX: int = int(os.getenv("CHAOS_RANDOM_JITTER_MAX", "200"))
    RANDOM_LOSS_MIN: float = float(os.getenv("CHAOS_RANDOM_LOSS_MIN", "0.0"))
    RANDOM_LOSS_MAX: float = float(os.getenv("CHAOS_RANDOM_LOSS_MAX", "5.0"))
    
    # Probe Settings
    PING_COUNT: int = int(os.getenv("CHAOS_PING_COUNT", "5"))
    PING_TIMEOUT: int = int(os.getenv("CHAOS_PING_TIMEOUT", "5"))
    CONNECTIVITY_TIMEOUT: int = int(os.getenv("CHAOS_CONNECTIVITY_TIMEOUT", "5"))
    
    @classmethod
    def get_all(cls) -> dict:
        """Return all configuration values as a dictionary."""
        return {
            "NETWORK_INTERFACE": cls.NETWORK_INTERFACE,
            "DNS_PORT": cls.DNS_PORT,
            "DNS_SERVER": cls.DNS_SERVER,
            "DNS_TIMEOUT": cls.DNS_TIMEOUT,
            "IPTABLES_CHAIN": cls.IPTABLES_CHAIN,
            "DEFAULT_LATENCY_MS": cls.DEFAULT_LATENCY_MS,
            "DEFAULT_JITTER_MS": cls.DEFAULT_JITTER_MS,
            "DEFAULT_PACKET_LOSS": cls.DEFAULT_PACKET_LOSS,
            "DEFAULT_DURATION": cls.DEFAULT_DURATION,
            "RANDOM_LATENCY_MIN": cls.RANDOM_LATENCY_MIN,
            "RANDOM_LATENCY_MAX": cls.RANDOM_LATENCY_MAX,
            "RANDOM_JITTER_MIN": cls.RANDOM_JITTER_MIN,
            "RANDOM_JITTER_MAX": cls.RANDOM_JITTER_MAX,
            "RANDOM_LOSS_MIN": cls.RANDOM_LOSS_MIN,
            "RANDOM_LOSS_MAX": cls.RANDOM_LOSS_MAX,
            "PING_COUNT": cls.PING_COUNT,
            "PING_TIMEOUT": cls.PING_TIMEOUT,
            "CONNECTIVITY_TIMEOUT": cls.CONNECTIVITY_TIMEOUT,
        }


# Convenience instance
config = NetworkConfig()

