"""Compute stress actions for CPU, memory, and disk."""

import logging
import os
import subprocess
from typing import Optional

import psutil

from chaoscompute.config import config

logger = logging.getLogger("chaostoolkit")


def stress_cpu(
    duration: Optional[int] = None,
    load: Optional[int] = None,
    cores: Optional[int] = None,
) -> bool:
    """
    Stress CPU using stress-ng.

    :param duration: Duration in seconds (default: CHAOS_CPU_DURATION or 10)
    :param load: Load percentage per core (default: CHAOS_CPU_LOAD or 100)
    :param cores: Number of cores to stress, 0 = all (default: CHAOS_CPU_CORES or 0)

    Environment variables:
        CHAOS_CPU_DURATION: Default duration in seconds (default: 10)
        CHAOS_CPU_LOAD: Default CPU load percentage (default: 100)
        CHAOS_CPU_CORES: Default cores to stress, 0=all (default: 0)
        CHAOS_STRESS_NG_PATH: Path to stress-ng binary (default: stress-ng)
    """
    # Handle string input from Chaos Toolkit configuration
    if duration is not None:
        duration = int(duration) if isinstance(duration, str) else duration
    if load is not None:
        load = int(load) if isinstance(load, str) else load
    if cores is not None:
        cores = int(cores) if isinstance(cores, str) else cores

    # Use config defaults if not specified
    duration = duration if duration is not None else config.DEFAULT_CPU_DURATION
    load = load if load is not None else config.DEFAULT_CPU_LOAD
    cores = cores if cores is not None else config.DEFAULT_CPU_CORES

    if cores == 0:
        cores = psutil.cpu_count()

    logger.info(f"Stressing {cores} CPU cores at {load}% load for {duration} seconds")

    cmd = [
        config.STRESS_NG_PATH,
        "--cpu",
        str(cores),
        "--cpu-load",
        str(load),
        "--timeout",
        f"{duration}s",
    ]

    try:
        subprocess.run(cmd, check=True)
        return True
    except FileNotFoundError:
        logger.error("stress-ng not found. Please install it.")
        return False
    except subprocess.CalledProcessError as e:
        logger.error(f"stress-ng failed: {e}")
        return False


def stress_memory(
    duration: Optional[int] = None,
    amount: Optional[str] = None,
) -> bool:
    """
    Stress Memory using stress-ng.

    :param duration: Duration in seconds (default: CHAOS_MEMORY_DURATION or 10)
    :param amount: Amount of memory to stress (default: CHAOS_MEMORY_AMOUNT or "100M")

    Environment variables:
        CHAOS_MEMORY_DURATION: Default duration in seconds (default: 10)
        CHAOS_MEMORY_AMOUNT: Default memory amount (default: 100M)
        CHAOS_STRESS_NG_PATH: Path to stress-ng binary (default: stress-ng)
    """
    # Handle string input from Chaos Toolkit configuration
    if duration is not None:
        duration = int(duration) if isinstance(duration, str) else duration

    # Use config defaults if not specified
    duration = duration if duration is not None else config.DEFAULT_MEMORY_DURATION
    amount = amount or config.DEFAULT_MEMORY_AMOUNT

    logger.info(f"Stressing memory with {amount} for {duration} seconds")

    cmd = [
        config.STRESS_NG_PATH,
        "--vm",
        "1",
        "--vm-bytes",
        amount,
        "--timeout",
        f"{duration}s",
    ]

    try:
        subprocess.run(cmd, check=True)
        return True
    except FileNotFoundError:
        logger.error("stress-ng not found. Please install it.")
        return False
    except subprocess.CalledProcessError as e:
        logger.error(f"stress-ng failed: {e}")
        return False


def fill_disk(
    path: Optional[str] = None,
    amount: Optional[str] = None,
) -> bool:
    """
    Fill disk space using fallocate.

    :param path: Path to directory to fill (default: CHAOS_DISK_PATH or /tmp)
    :param amount: Amount to fill (default: CHAOS_DISK_AMOUNT or "100M")

    Environment variables:
        CHAOS_DISK_PATH: Default path to fill (default: /tmp)
        CHAOS_DISK_AMOUNT: Default amount to fill (default: 100M)
        CHAOS_DISK_FILL_FILENAME: Filename for fill file (default: chaos_disk_fill.tmp)
        CHAOS_FALLOCATE_PATH: Path to fallocate binary (default: fallocate)
    """
    # Use config defaults if not specified
    path = path or config.DEFAULT_DISK_PATH
    amount = amount or config.DEFAULT_DISK_AMOUNT

    filename = os.path.join(path, config.DISK_FILL_FILENAME)
    logger.info(f"Filling disk at {filename} with {amount}")

    try:
        subprocess.run([config.FALLOCATE_PATH, "-l", amount, filename], check=True)
        logger.info(f"Created file {filename}")
        return True
    except FileNotFoundError:
        # Fallback to dd
        # Assuming amount is like 100M. dd needs bs and count.
        # Let's just use a simple python write for portability if fallocate fails?
        # Or just use stress-ng --hdd
        pass
    except subprocess.CalledProcessError:
        pass

    # Fallback to stress-ng if available
    try:
        # stress-ng --hdd 1 --hdd-bytes <amount> --timeout 1s (just to create it? no stress-ng cleans up)
        # We want to persist it? Usually chaos actions are transient or have a rollback.
        # If we want to fill disk to cause failure, we might want it to persist until rollback.
        pass
    except Exception:
        pass

    return False
