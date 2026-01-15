"""Compute chaos actions."""

from chaoscompute.actions.compute_stress import (fill_disk, stress_cpu,
                                                 stress_memory)

__all__ = [
    "stress_cpu",
    "stress_memory",
    "fill_disk",
]
