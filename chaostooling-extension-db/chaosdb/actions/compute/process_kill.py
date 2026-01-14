"""Process kill chaos action for disaster recovery testing."""
import os
import signal
from typing import Dict

import psutil
from chaosotel import (ensure_initialized, flush, get_logger, get_metrics_core,
                       get_tracer)
from opentelemetry.trace import StatusCode


def kill_process_by_name(
    process_name: str,
    signal_type: str = "SIGTERM",
    timeout_seconds: int = 10
) -> Dict:
    """
    Kill a process by name for disaster recovery testing.
    
    Args:
        process_name: Name of the process to kill (e.g., "postgres", "mysqld")
        signal_type: Signal to send (SIGTERM, SIGKILL, etc.)
        timeout_seconds: Time to wait before force killing
        
    Returns:
        Dict with results including processes killed, PIDs, etc.
    """
    ensure_initialized()
    db_system = os.getenv("DB_SYSTEM", "postgresql")
    metrics = get_metrics_core()
    tracer = get_tracer()
    logger = get_logger()
    
    signal_map = {
        "SIGTERM": signal.SIGTERM,
        "SIGKILL": signal.SIGKILL,
        "SIGINT": signal.SIGINT,
        "SIGHUP": signal.SIGHUP
    }
    
    sig = signal_map.get(signal_type, signal.SIGTERM)
    killed_processes = []
    errors = []
    
    try:
        with tracer.start_as_current_span("chaos.compute.process_kill") as span:
            span.set_attribute("chaos.process_name", process_name)
            span.set_attribute("chaos.signal_type", signal_type)
            span.set_attribute("chaos.action", "process_kill")
            
            logger.info(f"Killing processes matching '{process_name}' with {signal_type}")
            
            # Find processes by name
            matching_processes = []
            for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
                try:
                    proc_info = proc.info
                    if process_name.lower() in proc_info['name'].lower():
                        matching_processes.append(proc)
                    elif proc_info['cmdline']:
                        cmdline_str = ' '.join(proc_info['cmdline']).lower()
                        if process_name.lower() in cmdline_str:
                            matching_processes.append(proc)
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
            
            if not matching_processes:
                logger.warning(f"No processes found matching '{process_name}'")
                result = {
                    "success": False,
                    "message": f"No processes found matching '{process_name}'",
                    "processes_killed": 0
                }
                span.set_status(StatusCode.ERROR, "No processes found")
                flush()
                return result
            
            # Kill processes
            for proc in matching_processes:
                try:
                    pid = proc.pid
                    proc_name = proc.name()
                    
                    logger.info(f"Killing process {pid} ({proc_name})")
                    
                    # Send signal
                    proc.send_signal(sig)
                    
                    # Wait for process to terminate
                    try:
                        proc.wait(timeout=timeout_seconds)
                    except psutil.TimeoutExpired:
                        # Force kill if still running
                        logger.warning(f"Process {pid} did not terminate, force killing")
                        proc.kill()
                        proc.wait(timeout=5)
                    
                    killed_processes.append({
                        "pid": pid,
                        "name": proc_name,
                        "signal": signal_type
                    })

                except psutil.NoSuchProcess:
                    logger.warning(f"Process {pid} already terminated")
                except psutil.AccessDenied:
                    error_msg = f"Access denied when killing process {pid}"
                    errors.append(error_msg)
                    logger.error(error_msg)
                    metrics.record_db_error(db_system=db_system, error_type="AccessDenied")
                except Exception as e:
                    error_msg = f"Error killing process {pid}: {e}"
                    errors.append(error_msg)
                    logger.error(error_msg)
                    metrics.record_db_error(db_system=db_system, error_type=type(e).__name__, process_name=process_name)
            
            result = {
                "success": len(killed_processes) > 0,
                "processes_killed": len(killed_processes),
                "killed_processes": killed_processes,
                "errors": errors
            }
            
            span.set_attribute("chaos.processes_killed", len(killed_processes))
            span.set_attribute("chaos.errors", len(errors))
            span.set_status(StatusCode.OK if len(killed_processes) > 0 else StatusCode.ERROR)
            
            logger.info(f"Process kill completed: {result}")
            flush()
            return result
            
    except Exception as e:
        metrics.record_db_error(db_system=db_system, error_type=type(e).__name__, process_name=process_name)
        logger.error(f"Process kill failed: {e}")
        flush()
        raise


def kill_process_by_pid(
    pid: int,
    signal_type: str = "SIGTERM",
    timeout_seconds: int = 10
) -> Dict:
    """
    Kill a process by PID for disaster recovery testing.
    
    Args:
        pid: Process ID to kill
        signal_type: Signal to send (SIGTERM, SIGKILL, etc.)
        timeout_seconds: Time to wait before force killing
        
    Returns:
        Dict with results
    """
    ensure_initialized()
    tracer = get_tracer()
    logger = get_logger()
    
    signal_map = {
        "SIGTERM": signal.SIGTERM,
        "SIGKILL": signal.SIGKILL,
        "SIGINT": signal.SIGINT,
        "SIGHUP": signal.SIGHUP
    }
    
    sig = signal_map.get(signal_type, signal.SIGTERM)
    
    try:
        with tracer.start_as_current_span("chaos.compute.process_kill_by_pid") as span:
            span.set_attribute("chaos.pid", pid)
            span.set_attribute("chaos.signal_type", signal_type)
            span.set_attribute("chaos.action", "process_kill")
            
            logger.info(f"Killing process {pid} with {signal_type}")
            
            proc = psutil.Process(pid)
            proc_name = proc.name()
            
            # Send signal
            proc.send_signal(sig)
            
            # Wait for process to terminate
            try:
                proc.wait(timeout=timeout_seconds)
            except psutil.TimeoutExpired:
                # Force kill if still running
                logger.warning(f"Process {pid} did not terminate, force killing")
                proc.kill()
                proc.wait(timeout=5)

            result = {
                "success": True,
                "pid": pid,
                "name": proc_name,
                "signal": signal_type
            }
            
            span.set_status(StatusCode.OK)
            logger.info(f"Process {pid} killed successfully")
            flush()
            return result
            
    except psutil.NoSuchProcess:
        error_msg = f"Process {pid} does not exist"
        logger.warning(error_msg)
        result = {
            "success": False,
            "message": error_msg
        }
        flush()
        return result
    except psutil.AccessDenied:
        error_msg = f"Access denied when killing process {pid}"
        logger.error(error_msg)
        metrics = get_metrics_core()
        db_system = os.getenv("DB_SYSTEM", "postgresql")
        metrics.record_db_error(db_system=db_system, error_type="AccessDenied")
        flush()
        raise
    except Exception as e:
        metrics = get_metrics_core()
        db_system = os.getenv("DB_SYSTEM", "postgresql")
        metrics.record_db_error(db_system=db_system, error_type=type(e).__name__, pid=str(pid))
        logger.error(f"Process kill failed: {e}")
        flush()
        raise

