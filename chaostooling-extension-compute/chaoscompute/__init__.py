from typing import List

__version__ = '0.1.0'

def discover(discover_system: bool = True) -> List[dict]:
    """
    Discover capabilities from this extension.
    """
    return [
        {
            "name": "chaoscompute",
            "version": __version__,
            "description": "Compute Resource Chaos Extension",
            "activities": [
                {
                    "name": "chaoscompute.actions.compute_stress.stress_cpu",
                    "type": "action",
                    "arguments": [
                        {"name": "duration", "type": "int", "default": 10},
                        {"name": "load", "type": "int", "default": 100},
                        {"name": "cores", "type": "int", "default": 0}
                    ]
                },
                {
                    "name": "chaoscompute.actions.compute_stress.stress_memory",
                    "type": "action",
                    "arguments": [
                        {"name": "duration", "type": "int", "default": 10},
                        {"name": "amount", "type": "string", "default": "100M"}
                    ]
                },
                {
                    "name": "chaoscompute.actions.compute_stress.fill_disk",
                    "type": "action",
                    "arguments": [
                        {"name": "path", "type": "string", "default": "/tmp"},
                        {"name": "amount", "type": "string", "default": "100M"}
                    ]
                },
                {
                    "name": "chaoscompute.probes.compute_system.get_cpu_usage",
                    "type": "probe",
                    "arguments": [
                        {"name": "interval", "type": "int", "default": 1}
                    ]
                },
                {
                    "name": "chaoscompute.probes.compute_system.get_memory_usage",
                    "type": "probe",
                    "arguments": []
                },
                {
                    "name": "chaoscompute.probes.compute_system.get_disk_usage",
                    "type": "probe",
                    "arguments": [
                        {"name": "path", "type": "string", "default": "/"}
                    ]
                },
                {
                    "name": "chaoscompute.probes.compute_system.process_exists",
                    "type": "probe",
                    "arguments": [
                        {"name": "process_name", "type": "string"}
                    ]
                },
                {
                    "name": "chaoscompute.probes.compute_system.get_uptime",
                    "type": "probe",
                    "arguments": []
                }
            ]
        }
    ]
