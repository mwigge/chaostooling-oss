"""
Compute extension configuration.

All settings can be overridden via environment variables.
"""

import os


class ComputeConfig:
    """Configuration for compute chaos actions and probes."""

    # CPU Stress Defaults
    DEFAULT_CPU_DURATION: int = int(os.getenv("CHAOS_CPU_DURATION", "10"))
    DEFAULT_CPU_LOAD: int = int(os.getenv("CHAOS_CPU_LOAD", "100"))
    DEFAULT_CPU_CORES: int = int(os.getenv("CHAOS_CPU_CORES", "0"))  # 0 = all cores

    # Memory Stress Defaults
    DEFAULT_MEMORY_DURATION: int = int(os.getenv("CHAOS_MEMORY_DURATION", "10"))
    DEFAULT_MEMORY_AMOUNT: str = os.getenv("CHAOS_MEMORY_AMOUNT", "100M")

    # Disk Fill Defaults
    DEFAULT_DISK_PATH: str = os.getenv("CHAOS_DISK_PATH", "/tmp")
    DEFAULT_DISK_AMOUNT: str = os.getenv("CHAOS_DISK_AMOUNT", "100M")
    DISK_FILL_FILENAME: str = os.getenv(
        "CHAOS_DISK_FILL_FILENAME", "chaos_disk_fill.tmp"
    )

    # Probe Settings
    CPU_PROBE_INTERVAL: int = int(os.getenv("CHAOS_CPU_PROBE_INTERVAL", "1"))
    DEFAULT_DISK_PROBE_PATH: str = os.getenv("CHAOS_DISK_PROBE_PATH", "/")

    # Tool Paths (in case they're not in PATH)
    STRESS_NG_PATH: str = os.getenv("CHAOS_STRESS_NG_PATH", "stress-ng")
    FALLOCATE_PATH: str = os.getenv("CHAOS_FALLOCATE_PATH", "fallocate")

    @classmethod
    def get_all(cls) -> dict:
        """Return all configuration values as a dictionary."""
        return {
            "DEFAULT_CPU_DURATION": cls.DEFAULT_CPU_DURATION,
            "DEFAULT_CPU_LOAD": cls.DEFAULT_CPU_LOAD,
            "DEFAULT_CPU_CORES": cls.DEFAULT_CPU_CORES,
            "DEFAULT_MEMORY_DURATION": cls.DEFAULT_MEMORY_DURATION,
            "DEFAULT_MEMORY_AMOUNT": cls.DEFAULT_MEMORY_AMOUNT,
            "DEFAULT_DISK_PATH": cls.DEFAULT_DISK_PATH,
            "DEFAULT_DISK_AMOUNT": cls.DEFAULT_DISK_AMOUNT,
            "DISK_FILL_FILENAME": cls.DISK_FILL_FILENAME,
            "CPU_PROBE_INTERVAL": cls.CPU_PROBE_INTERVAL,
            "DEFAULT_DISK_PROBE_PATH": cls.DEFAULT_DISK_PROBE_PATH,
            "STRESS_NG_PATH": cls.STRESS_NG_PATH,
            "FALLOCATE_PATH": cls.FALLOCATE_PATH,
        }


# Convenience instance
config = ComputeConfig()
