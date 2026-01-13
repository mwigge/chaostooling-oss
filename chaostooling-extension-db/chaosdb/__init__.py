"""Chaos Toolkit Database Extension - Multi-Database Support."""

try:
    from ._version import version as __version__
except ImportError:
    # Fallback for when package is not installed
    __version__ = "0.0.0.dev0"

# Re-export common utilities
from chaosotel import ensure_initialized, flush, get_logger, get_tracer, initialize

__all__ = [
    "initialize",
    "ensure_initialized",
    "get_tracer",
    "get_logger",
    "flush",
]
