from typing import List

from chaosotel import ensure_initialized, flush, get_logger, get_tracer, initialize

__version__ = "0.1.0"
__all__ = [
    "initialize",
    "ensure_initialized",
    "get_tracer",
    "get_logger",
    "flush",
]


def discover(discover_system: bool = True) -> List[dict]:
    """
    Discover capabilities from this extension.
    """
    return [
        {
            "name": "chaosmobile",
            "version": __version__,
            "description": "Mobile Edge Chaos Extension",
            "activities": [
                {
                    "name": "chaosmobile.actions.network.simulate_network_conditions",
                    "type": "action",
                    "arguments": [
                        {"name": "latency", "type": "int", "default": 0},
                        {"name": "jitter", "type": "int", "default": 0},
                        {"name": "loss", "type": "float", "default": 0.0},
                        {"name": "bandwidth", "type": "string", "default": ""},
                    ],
                },
                {
                    "name": "chaosmobile.actions.client.simulate_purchase",
                    "type": "action",
                    "arguments": [
                        {"name": "user_id", "type": "int"},
                        {"name": "amount", "type": "float"},
                        {"name": "item_id", "type": "string"},
                    ],
                },
                {
                    "name": "chaosmobile.actions.client.simulate_purchase_via_api",
                    "type": "action",
                    "arguments": [
                        {"name": "user_id", "type": "int"},
                        {"name": "amount", "type": "float"},
                        {"name": "item_id", "type": "string"},
                        {
                            "name": "url",
                            "type": "string",
                            "default": "http://haproxy:80/purchase",
                        },
                    ],
                },
                {
                    "name": "chaosmobile.probes.validation.validate_data_consistency",
                    "type": "probe",
                    "arguments": [
                        {"name": "expected_count", "type": "int"},
                        {"name": "item_id", "type": "string"},
                    ],
                },
            ],
        }
    ]
