"""Compute/host chaos actions."""
from .process_kill import kill_process_by_name, kill_process_by_pid

__all__ = ["kill_process_by_name", "kill_process_by_pid"]

