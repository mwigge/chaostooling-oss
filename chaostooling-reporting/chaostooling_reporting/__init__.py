"""
chaostooling-reporting: Chaos Engineering reporting extension for Chaos Toolkit

Includes report generation, dashboard generation, and experiment indexing.
"""

__version__ = "0.1.0"
__author__ = "Morgan Wigge"

from chaostooling_reporting.actions import generate_experiment_reports
from chaostooling_reporting.control import (
    after_experiment_control,
    configure_control,
    load_control,
    unload_control,
)
from chaostooling_reporting.dashboard_generator import (
    DashboardGenerator,
    extract_systems_from_experiment,
    extract_timestamps_from_journal,
)
from chaostooling_reporting.experiment_index import ExperimentIndex
from chaostooling_reporting.report_generator import ReportGenerator

__all__ = [
    # Control hooks
    "configure_control",
    "load_control",
    "unload_control",
    "after_experiment_control",
    # Actions
    "generate_experiment_reports",
    # Classes
    "ReportGenerator",
    "DashboardGenerator",
    "ExperimentIndex",
    # Utilities
    "extract_systems_from_experiment",
    "extract_timestamps_from_journal",
]
