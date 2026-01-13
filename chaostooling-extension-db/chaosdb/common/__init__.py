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

__all__ = [
    "instrument_db_span",
    "instrument_messaging_span",
    "create_instrumented_span",
    "InstrumentedSpan",
    "get_system_name_from_module",
    "DB_SYSTEM_MAP",
    "MESSAGING_SYSTEM_MAP",
]
