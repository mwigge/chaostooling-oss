"""
ChaoSOTEL Core Classes

Unified interfaces for:
- Metrics (MetricsCore) → Prometheus
- Logging (LogCore) → Loki
- Tracing (TraceCore) → Tempo/Jaeger
- Compliance (ComplianceCore) → SOX, GDPR, PCI-DSS, HIPAA
- Span Helpers (in trace_core) → Modular tracing instrumentation
"""

from .compliance_core import ComplianceCore, Regulation
from .log_core import LogCore
from .metrics_core import MetricsCore
from .trace_core import (DB_SYSTEM_MAP, MESSAGING_SYSTEM_MAP, InstrumentedSpan,
                         TraceCore, create_instrumented_span,
                         get_system_name_from_module, instrument_db_span,
                         instrument_messaging_span)

__all__ = [
    "MetricsCore",
    "LogCore",
    "TraceCore",
    "ComplianceCore",
    "Regulation",
    # Span helpers (from trace_core)
    "instrument_db_span",
    "instrument_messaging_span",
    "create_instrumented_span",
    "InstrumentedSpan",
    "get_system_name_from_module",
    "DB_SYSTEM_MAP",
    "MESSAGING_SYSTEM_MAP",
]
