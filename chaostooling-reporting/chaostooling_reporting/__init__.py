"""
chaostooling-reporting: Chaos Engineering reporting extension for Chaos Toolkit
"""

__version__ = "0.1.0"
__author__ = "Morgan Wigge"

from chaostooling_reporting.control import (
    after_experiment_control,
    configure_control,
    load_control,
    unload_control,
)

__all__ = [
    "configure_control",
    "load_control",
    "unload_control",
    "after_experiment_control",
]
