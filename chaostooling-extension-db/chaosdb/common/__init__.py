"""Common utilities for chaosdb extension."""

# Re-export span helpers from chaosotel for convenience
# This allows: from chaosdb.common import instrument_db_span
# Instead of: from chaosotel.core.trace_core import instrument_db_span
try:
    from chaosotel.core.trace_core import (
        DB_SYSTEM_MAP,
        MESSAGING_SYSTEM_MAP,
        InstrumentedSpan,
        create_instrumented_span,
        get_system_name_from_module,
        instrument_db_span,
        instrument_messaging_span,
    )
except ImportError:
    # Fallback if chaosotel not available
    instrument_db_span = None
    instrument_messaging_span = None
    create_instrumented_span = None
    InstrumentedSpan = None
    get_system_name_from_module = None
    DB_SYSTEM_MAP = {}
    MESSAGING_SYSTEM_MAP = {}

# Re-export constants
# Re-export connection utilities
from .connection import (
    create_mysql_connection,
    create_postgres_connection,
    get_mysql_connection_params,
    get_postgres_connection_params,
)
from .constants import (
    ConnectionDefaults,
    DatabaseDefaults,
    MessagingDefaults,
    StressDefaults,
)

__all__ = [
    "instrument_db_span",
    "instrument_messaging_span",
    "create_instrumented_span",
    "InstrumentedSpan",
    "get_system_name_from_module",
    "DB_SYSTEM_MAP",
    "MESSAGING_SYSTEM_MAP",
    "DatabaseDefaults",
    "MessagingDefaults",
    "ConnectionDefaults",
    "StressDefaults",
    "validate_port",
    "validate_host",
    "validate_database_name",
    "validate_timeout",
    "validate_positive_int",
    "create_postgres_connection",
    "get_postgres_connection_params",
    "create_mysql_connection",
    "get_mysql_connection_params",
]
