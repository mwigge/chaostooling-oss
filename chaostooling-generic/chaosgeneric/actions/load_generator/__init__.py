"""Background transaction load generator actions."""

from .gatling_api import (
    get_gatling_simulation_status,
    start_gatling_simulation,
    stop_gatling_simulation,
)
from .jmeter_api import (
    get_jmeter_test_status,
    start_jmeter_test,
    stop_jmeter_test,
)
from .transaction_load_generator import (
    get_background_load_stats,
    start_background_transaction_load,
    stop_background_transaction_load,
)

__all__ = [
    # Transaction load generator
    "start_background_transaction_load",
    "stop_background_transaction_load",
    "get_background_load_stats",
    # JMeter
    "start_jmeter_test",
    "stop_jmeter_test",
    "get_jmeter_test_status",
    # Gatling
    "start_gatling_simulation",
    "stop_gatling_simulation",
    "get_gatling_simulation_status",
]
