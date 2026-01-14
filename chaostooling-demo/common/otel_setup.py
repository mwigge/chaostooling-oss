"""
Common OpenTelemetry setup for all services
"""

import os
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider, SpanProcessor
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.resources import Resource
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter


class ServiceNameSpanProcessor(SpanProcessor):
    """Span processor to set service names for database and messaging spans"""

    def on_end(self, span):
        # Check for database system attribute
        if hasattr(span, "attributes") and span.attributes:
            db_system = span.attributes.get("db.system")
            if db_system:
                # Update resource to use database system as service name
                new_resource = Resource.create(
                    {
                        "service.name": str(db_system),
                        "service.version": "1.0.0",
                    }
                )
                span._resource = new_resource

        # Check for messaging system attribute
        if hasattr(span, "attributes") and span.attributes:
            messaging_system = span.attributes.get("messaging.system")
            if messaging_system:
                # Update resource to use messaging system as service name
                new_resource = Resource.create(
                    {
                        "service.name": str(messaging_system),
                        "service.version": "1.0.0",
                    }
                )
                span._resource = new_resource

    def shutdown(self):
        pass

    def force_flush(self, timeout_millis=30000):
        pass


def setup_otel(service_name: str):
    """Setup OpenTelemetry with proper service name and span processor"""
    resource = Resource.create(
        {
            "service.name": service_name,
            "service.version": "1.0.0",
        }
    )
    tracer_provider = TracerProvider(resource=resource)
    otlp_exporter = OTLPSpanExporter(
        endpoint=os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://otel-collector:4317"),
        insecure=True,
    )
    # Add span processor to set service names for DB/messaging spans
    tracer_provider.add_span_processor(ServiceNameSpanProcessor())
    tracer_provider.add_span_processor(BatchSpanProcessor(otlp_exporter))
    trace.set_tracer_provider(tracer_provider)
    return tracer_provider
