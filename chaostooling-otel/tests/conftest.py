# tests/conftest.py

"""
Pytest configuration and shared fixtures for ChaoSOTEL tests.
"""

import pytest
from unittest.mock import MagicMock, patch

from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk._logs import LoggerProvider
from opentelemetry.sdk.metrics.export import InMemoryMetricReader
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter


@pytest.fixture(autouse=True)
def reset_chaosotel():
    """Reset ChaoSOTEL global state before each test."""
    import chaosotel.otel as otel_module
    
    otel_module._initialized = False
    otel_module._meter_provider = None
    otel_module._tracer_provider = None
    otel_module._logger_provider = None
    otel_module._metrics_core = None
    otel_module._log_core = None
    otel_module._trace_core = None
    otel_module._compliance_core = None
    
    yield
    
    # Cleanup after test
    otel_module._initialized = False


@pytest.fixture
def in_memory_metric_reader():
    """Create in-memory metric reader for testing."""
    return InMemoryMetricReader()


@pytest.fixture
def in_memory_span_exporter():
    """Create in-memory span exporter for testing."""
    return InMemorySpanExporter()


@pytest.fixture
def meter_provider(in_memory_metric_reader):
    """Create test MeterProvider."""
    return MeterProvider(metric_readers=[in_memory_metric_reader])


@pytest.fixture
def tracer_provider(in_memory_span_exporter):
    """Create test TracerProvider."""
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(in_memory_span_exporter))
    return provider


@pytest.fixture
def logger_provider():
    """Create test LoggerProvider."""
    return LoggerProvider()


@pytest.fixture
def mock_otel_setup(meter_provider, tracer_provider, logger_provider):
    """Mock OTEL setup for testing."""
    import chaosotel.otel as otel_module
    
    with patch("chaosotel.metrics.setup_metrics", return_value=meter_provider), \
         patch("chaosotel.traces.setup_traces", return_value=tracer_provider), \
         patch("chaosotel.logs.setup_logs", return_value=logger_provider):
        
        # Also set global state directly to avoid warnings
        otel_module._meter_provider = meter_provider
        otel_module._tracer_provider = tracer_provider
        otel_module._logger_provider = logger_provider
        
        yield
        
        # Cleanup
        otel_module._meter_provider = None
        otel_module._tracer_provider = None
        otel_module._logger_provider = None


@pytest.fixture
def initialized_chaosotel(mock_otel_setup):
    """Initialize ChaoSOTEL for testing."""
    from chaosotel import initialize
    
    try:
        initialize(target_type="database", regulations=["SOX"])
        yield
    finally:
        from chaosotel import shutdown
        try:
            shutdown()
        except:
            pass