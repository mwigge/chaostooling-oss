"""
Compute-Based Chaos Experiments

CPU, memory, disk I/O, and filesystem stress actions.
Supports Linux (via stress-ng, sysbench) and Windows (via built-in tools).

Installation:
- Linux: apt-get install stress-ng sysbench
- Windows: Built-in (PowerShell, taskmgr)
"""

import logging
import os
import platform
import subprocess
from typing import Any

logger = logging.getLogger("chaoscompute")


class ComputeStressError(Exception):
    """Base exception for compute stress errors."""

    pass


class LinuxComputeStress:
    """Linux-based compute stress operations using stress-ng."""

    @staticmethod
    def _ensure_stress_ng() -> None:
        """Ensure stress-ng is installed."""
        try:
            subprocess.run(["stress-ng", "--version"], capture_output=True, check=True)
        except (FileNotFoundError, subprocess.CalledProcessError):
            raise ComputeStressError(
                "stress-ng not found. Install with: apt-get install stress-ng"
            )

    @staticmethod
    def cpu_stress(
        workers: int = 1, duration_seconds: int = 60, cpu_percent: int = 100
    ) -> dict[str, Any]:
        """
        Stress CPU cores.

        Args:
            workers: Number of CPU workers (default: all cores)
            duration_seconds: Duration of stress
            cpu_percent: CPU percentage to target (useful for throttling)

        Returns:
            Dict with stress metrics
        """
        try:
            LinuxComputeStress._ensure_stress_ng()

            if workers == 0:
                workers = os.cpu_count() or 1

            cmd = [
                "stress-ng",
                "--cpu",
                str(workers),
                "--cpu-ops",
                "0",  # Run indefinitely
                "--timeout",
                f"{duration_seconds}s",
                "--metrics",
                "--quiet",
            ]

            logger.info(
                f"Starting CPU stress: {workers} workers, {duration_seconds}s duration"
            )

            process = subprocess.Popen(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE
            )

            stdout, stderr = process.communicate(timeout=duration_seconds + 10)

            return {
                "status": "completed",
                "workers": workers,
                "duration_seconds": duration_seconds,
                "exit_code": process.returncode,
                "stdout": stdout.decode() if stdout else "",
                "stderr": stderr.decode() if stderr else "",
            }
        except Exception as e:
            logger.error(f"CPU stress failed: {e}")
            raise ComputeStressError(f"CPU stress failed: {e}")

    @staticmethod
    def memory_stress(
        workers: int = 1, memory_percent: int = 80, duration_seconds: int = 60
    ) -> dict[str, Any]:
        """
        Stress memory (RAM).

        Args:
            workers: Number of memory workers
            memory_percent: Percentage of available memory to allocate
            duration_seconds: Duration of stress

        Returns:
            Dict with stress metrics
        """
        try:
            LinuxComputeStress._ensure_stress_ng()

            # Calculate memory amount
            import psutil

            total_memory_mb = int(psutil.virtual_memory().total / (1024 * 1024))
            memory_to_stress_mb = int(total_memory_mb * memory_percent / 100)

            cmd = [
                "stress-ng",
                "--vm",
                str(workers),
                "--vm-bytes",
                f"{memory_to_stress_mb}M",
                "--vm-ops",
                "0",  # Run indefinitely
                "--timeout",
                f"{duration_seconds}s",
                "--metrics",
                "--quiet",
            ]

            logger.info(
                f"Starting memory stress: {memory_to_stress_mb}MB, {duration_seconds}s duration"
            )

            process = subprocess.Popen(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE
            )

            stdout, stderr = process.communicate(timeout=duration_seconds + 10)

            return {
                "status": "completed",
                "memory_mb": memory_to_stress_mb,
                "memory_percent": memory_percent,
                "duration_seconds": duration_seconds,
                "exit_code": process.returncode,
                "stdout": stdout.decode() if stdout else "",
                "stderr": stderr.decode() if stderr else "",
            }
        except Exception as e:
            logger.error(f"Memory stress failed: {e}")
            raise ComputeStressError(f"Memory stress failed: {e}")

    @staticmethod
    def disk_io_stress(
        workers: int = 1, duration_seconds: int = 60, directory: str = "/tmp"
    ) -> dict[str, Any]:
        """
        Stress disk I/O.

        Args:
            workers: Number of I/O workers
            duration_seconds: Duration of stress
            directory: Directory to use for I/O operations

        Returns:
            Dict with stress metrics
        """
        try:
            LinuxComputeStress._ensure_stress_ng()

            # Verify directory exists and is writable
            if not os.path.isdir(directory):
                raise ComputeStressError(f"Directory not found: {directory}")

            if not os.access(directory, os.W_OK):
                raise ComputeStressError(f"Directory not writable: {directory}")

            cmd = [
                "stress-ng",
                "--iomix",
                str(workers),
                "--iomix-bytes",
                "64M",
                "--timeout",
                f"{duration_seconds}s",
                "--temp-path",
                directory,
                "--metrics",
                "--quiet",
            ]

            logger.info(
                f"Starting disk I/O stress: {workers} workers, {duration_seconds}s duration in {directory}"
            )

            process = subprocess.Popen(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE
            )

            stdout, stderr = process.communicate(timeout=duration_seconds + 10)

            return {
                "status": "completed",
                "workers": workers,
                "duration_seconds": duration_seconds,
                "directory": directory,
                "exit_code": process.returncode,
                "stdout": stdout.decode() if stdout else "",
                "stderr": stderr.decode() if stderr else "",
            }
        except Exception as e:
            logger.error(f"Disk I/O stress failed: {e}")
            raise ComputeStressError(f"Disk I/O stress failed: {e}")

    @staticmethod
    def filesystem_stress(
        workers: int = 1,
        duration_seconds: int = 60,
        directory: str = "/tmp",
        file_size_mb: int = 10,
    ) -> dict[str, Any]:
        """
        Stress filesystem (create/delete/rename files).

        Args:
            workers: Number of filesystem workers
            duration_seconds: Duration of stress
            directory: Directory for test files
            file_size_mb: Size of files to create

        Returns:
            Dict with stress metrics
        """
        try:
            LinuxComputeStress._ensure_stress_ng()

            # Verify directory
            if not os.path.isdir(directory):
                raise ComputeStressError(f"Directory not found: {directory}")

            if not os.access(directory, os.W_OK):
                raise ComputeStressError(f"Directory not writable: {directory}")

            cmd = [
                "stress-ng",
                "--hdd",
                str(workers),
                "--hdd-bytes",
                f"{file_size_mb}M",
                "--timeout",
                f"{duration_seconds}s",
                "--temp-path",
                directory,
                "--metrics",
                "--quiet",
            ]

            logger.info(
                f"Starting filesystem stress: {workers} workers, {duration_seconds}s duration"
            )

            process = subprocess.Popen(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE
            )

            stdout, stderr = process.communicate(timeout=duration_seconds + 10)

            return {
                "status": "completed",
                "workers": workers,
                "duration_seconds": duration_seconds,
                "file_size_mb": file_size_mb,
                "exit_code": process.returncode,
                "stdout": stdout.decode() if stdout else "",
                "stderr": stderr.decode() if stderr else "",
            }
        except Exception as e:
            logger.error(f"Filesystem stress failed: {e}")
            raise ComputeStressError(f"Filesystem stress failed: {e}")


class WindowsComputeStress:
    """Windows-based compute stress operations."""

    @staticmethod
    def cpu_stress(
        workers: int = 1, duration_seconds: int = 60, cpu_percent: int = 100
    ) -> dict[str, Any]:
        """
        Stress CPU cores on Windows.
        Uses PowerShell to create CPU-intensive tasks.
        """
        try:
            if workers == 0:
                workers = os.cpu_count() or 1

            # PowerShell script for CPU stress
            ps_script = f"""
            $duration = {duration_seconds}
            $endTime = (Get-Date).AddSeconds($duration)

            $jobs = @()
            for ($i = 0; $i -lt {workers}; $i++) {{
                $jobs += Start-Job -ScriptBlock {{
                    while ((Get-Date) -lt $using:endTime) {{
                        $null = [math]::Sqrt([math]::Random())
                    }}
                }}
            }}

            foreach ($job in $jobs) {{
                Wait-Job -Job $job
                Receive-Job -Job $job
            }}
            """

            logger.info(
                f"Starting CPU stress: {workers} workers, {duration_seconds}s duration"
            )

            process = subprocess.Popen(
                ["powershell", "-Command", ps_script],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )

            stdout, stderr = process.communicate(timeout=duration_seconds + 10)

            return {
                "status": "completed",
                "workers": workers,
                "duration_seconds": duration_seconds,
                "exit_code": process.returncode,
            }
        except Exception as e:
            logger.error(f"CPU stress failed: {e}")
            raise ComputeStressError(f"CPU stress failed: {e}")

    @staticmethod
    def memory_stress(
        workers: int = 1, memory_percent: int = 80, duration_seconds: int = 60
    ) -> dict[str, Any]:
        """
        Stress memory on Windows.
        Uses .NET to allocate memory.
        """
        try:
            import psutil

            total_memory_mb = int(psutil.virtual_memory().total / (1024 * 1024))
            memory_to_stress_mb = int(total_memory_mb * memory_percent / 100)

            ps_script = f"""
            $duration = {duration_seconds}
            $endTime = (Get-Date).AddSeconds($duration)

            try {{
                [byte[]]$buffer = New-Object byte[] {memory_to_stress_mb * 1024 * 1024}

                while ((Get-Date) -lt $endTime) {{
                    for ($i = 0; $i -lt $buffer.Length; $i += 4096) {{
                        $buffer[$i] = 1
                    }}
                }}
            }} finally {{
                $buffer = $null
                [GC]::Collect()
            }}
            """

            logger.info(
                f"Starting memory stress: {memory_to_stress_mb}MB, {duration_seconds}s duration"
            )

            process = subprocess.Popen(
                ["powershell", "-Command", ps_script],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )

            stdout, stderr = process.communicate(timeout=duration_seconds + 10)

            return {
                "status": "completed",
                "memory_mb": memory_to_stress_mb,
                "memory_percent": memory_percent,
                "duration_seconds": duration_seconds,
                "exit_code": process.returncode,
            }
        except Exception as e:
            logger.error(f"Memory stress failed: {e}")
            raise ComputeStressError(f"Memory stress failed: {e}")

    @staticmethod
    def disk_io_stress(
        workers: int = 1, duration_seconds: int = 60, directory: str = None
    ) -> dict[str, Any]:
        """
        Stress disk I/O on Windows.
        """
        try:
            if directory is None:
                directory = os.path.expanduser("~\\AppData\\Local\\Temp")

            ps_script = f"""
            $directory = "{directory}"
            $duration = {duration_seconds}
            $endTime = (Get-Date).AddSeconds($duration)
            $testFile = Join-Path $directory "chaos_io_test.bin"

            try {{
                $buffer = New-Object byte[] (1MB)

                while ((Get-Date) -lt $endTime) {{
                    [System.IO.File]::WriteAllBytes($testFile, $buffer)
                    [System.IO.File]::ReadAllBytes($testFile) | Out-Null
                }}
            }} finally {{
                Remove-Item -Path $testFile -ErrorAction SilentlyContinue
            }}
            """

            logger.info(
                f"Starting disk I/O stress: {duration_seconds}s duration in {directory}"
            )

            process = subprocess.Popen(
                ["powershell", "-Command", ps_script],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )

            stdout, stderr = process.communicate(timeout=duration_seconds + 10)

            return {
                "status": "completed",
                "duration_seconds": duration_seconds,
                "directory": directory,
                "exit_code": process.returncode,
            }
        except Exception as e:
            logger.error(f"Disk I/O stress failed: {e}")
            raise ComputeStressError(f"Disk I/O stress failed: {e}")


# Factory function to get appropriate stress class
def get_compute_stress() -> LinuxComputeStress or WindowsComputeStress:
    """Get platform-appropriate compute stress implementation."""
    system = platform.system()
    if system == "Linux":
        return LinuxComputeStress()
    elif system == "Windows":
        return WindowsComputeStress()
    else:
        raise ComputeStressError(f"Unsupported platform: {system}")


# ============================================================================
# Chaos Toolkit Actions (callable from experiments)
# ============================================================================


def stress_cpu(
    duration_seconds: int = 60, workers: int = 0, cpu_percent: int = 100
) -> dict[str, Any]:
    """
    Stress CPU cores.

    Usage in experiment:
        {
            "type": "action",
            "name": "Stress CPU",
            "provider": {
                "type": "python",
                "module": "chaoscompute.compute_stress_actions",
                "func": "stress_cpu",
                "arguments": {
                    "duration_seconds": 30,
                    "workers": 4,
                    "cpu_percent": 100
                }
            }
        }
    """
    logger.info(
        f"[COMPUTE] Stressing CPU: {workers or 'all'} workers for {duration_seconds}s"
    )
    stress = get_compute_stress()
    result = stress.cpu_stress(workers, duration_seconds, cpu_percent)
    logger.info(f"[COMPUTE] CPU stress completed: {result.get('exit_code', 'unknown')}")
    return result


def stress_memory(
    duration_seconds: int = 60, workers: int = 1, memory_percent: int = 80
) -> dict[str, Any]:
    """
    Stress memory.

    Usage in experiment:
        {
            "type": "action",
            "name": "Stress Memory",
            "provider": {
                "type": "python",
                "module": "chaoscompute.compute_stress_actions",
                "func": "stress_memory",
                "arguments": {
                    "duration_seconds": 30,
                    "memory_percent": 75
                }
            }
        }
    """
    logger.info(
        f"[COMPUTE] Stressing memory: {memory_percent}% for {duration_seconds}s"
    )
    stress = get_compute_stress()
    result = stress.memory_stress(workers, memory_percent, duration_seconds)
    logger.info(
        f"[COMPUTE] Memory stress completed: {result.get('exit_code', 'unknown')}"
    )
    return result


def stress_disk_io(
    duration_seconds: int = 60, workers: int = 1, directory: str = "/tmp"
) -> dict[str, Any]:
    """
    Stress disk I/O.

    Usage in experiment:
        {
            "type": "action",
            "name": "Stress Disk I/O",
            "provider": {
                "type": "python",
                "module": "chaoscompute.compute_stress_actions",
                "func": "stress_disk_io",
                "arguments": {
                    "duration_seconds": 30,
                    "workers": 2,
                    "directory": "/data"
                }
            }
        }
    """
    logger.info(f"[COMPUTE] Stressing disk I/O: {duration_seconds}s in {directory}")
    stress = get_compute_stress()
    result = stress.disk_io_stress(workers, duration_seconds, directory)
    logger.info(
        f"[COMPUTE] Disk I/O stress completed: {result.get('exit_code', 'unknown')}"
    )
    return result


def stress_filesystem(
    duration_seconds: int = 60,
    workers: int = 1,
    directory: str = "/tmp",
    file_size_mb: int = 10,
) -> dict[str, Any]:
    """
    Stress filesystem.

    Usage in experiment:
        {
            "type": "action",
            "name": "Stress Filesystem",
            "provider": {
                "type": "python",
                "module": "chaoscompute.compute_stress_actions",
                "func": "stress_filesystem",
                "arguments": {
                    "duration_seconds": 30,
                    "file_size_mb": 20
                }
            }
        }
    """
    logger.info(
        f"[COMPUTE] Stressing filesystem: {duration_seconds}s, {file_size_mb}MB files"
    )
    stress = get_compute_stress()
    result = stress.stress_filesystem(
        workers, duration_seconds, directory, file_size_mb
    )
    logger.info(
        f"[COMPUTE] Filesystem stress completed: {result.get('exit_code', 'unknown')}"
    )
    return result
