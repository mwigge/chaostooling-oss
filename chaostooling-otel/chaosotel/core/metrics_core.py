# chaosotel/core/metrics_core.py

"""MetricsCore - Unified Prometheus metrics recording interface."""

import logging
from typing import Any, Dict, Optional

from opentelemetry.sdk.metrics import MeterProvider

logger = logging.getLogger("chaosotel.metrics_core")


class MetricsCore:
    """Core metrics recording interface for Prometheus."""

    def __init__(self, meter_provider: MeterProvider, name: str = "chaosotel"):
        """Initialize MetricsCore."""
        self.meter_provider = meter_provider
        self.meter = meter_provider.get_meter(name)
        self._instruments: Dict[str, Any] = {}
        self._metric_count = 0
        logger.info(f"MetricsCore initialized with meter: {name}")

    def record_action_duration(
        self,
        name: str,
        duration_ms: float,
        status: str = "success",
        severity: Optional[str] = None,
        target_type: Optional[str] = None,
        tags: Optional[Dict[str, str]] = None,
    ) -> None:
        """Record action duration."""
        try:
            histogram = self._get_or_create_histogram(
                "operation.duration",
                unit="ms",
                description="Operation execution duration",
            )
            attributes = {
                "operation.name": str(name),
                "operation.status": str(status),
            }
            if severity:
                attributes["operation.severity"] = str(severity)
            if target_type:
                attributes["operation.target_type"] = str(target_type)
            if tags:
                attributes.update({f"tag.{k}": str(v) for k, v in tags.items()})
            histogram.record(float(duration_ms), attributes=attributes)
            self._metric_count += 1
        except Exception as e:
            logger.error(f"Error recording action duration: {e}")

    def record_action_count(
        self,
        name: str,
        status: str = "success",
        severity: Optional[str] = None,
        target_type: Optional[str] = None,
        count: int = 1,
    ) -> None:
        """Record action count."""
        try:
            counter = self._get_or_create_counter(
                f"chaos.operation.{status}",
                description=f"Count of {status} operations",
            )
            attributes = {"operation.name": str(name)}
            if severity:
                attributes["operation.severity"] = str(severity)
            if target_type:
                attributes["operation.target_type"] = str(target_type)
            counter.add(int(count), attributes=attributes)
            self._metric_count += 1
        except Exception as e:
            logger.error(f"Error recording action count: {e}")

    def record_probe_duration(
        self,
        name: str,
        duration_ms: float,
        status: str = "success",
        target_type: Optional[str] = None,
        tags: Optional[Dict[str, str]] = None,
    ) -> None:
        """Record probe duration."""
        try:
            histogram = self._get_or_create_histogram(
                "probe.duration",
                unit="ms",
                description="Probe execution duration",
            )
            attributes = {"probe.name": str(name), "probe.status": str(status)}
            if target_type:
                attributes["probe.target_type"] = str(target_type)
            if tags:
                attributes.update({f"tag.{k}": str(v) for k, v in tags.items()})
            histogram.record(float(duration_ms), attributes=attributes)
            self._metric_count += 1
        except Exception as e:
            logger.error(f"Error recording probe duration: {e}")

    def record_probe_count(
        self,
        name: str,
        status: str = "success",
        target_type: Optional[str] = None,
    ) -> None:
        """Record probe count."""
        try:
            counter = self._get_or_create_counter(
                "probe.executions", description="Probe execution count"
            )
            attributes = {"probe.name": str(name), "probe.status": str(status)}
            if target_type:
                attributes["probe.target_type"] = str(target_type)
            counter.add(1, attributes=attributes)
            self._metric_count += 1
        except Exception as e:
            logger.error(f"Error recording probe count: {e}")

    def record_recovery_time(
        self,
        name: str,
        duration_ms: float,
        success: bool = True,
        target_type: Optional[str] = None,
    ) -> None:
        """Record recovery time (MTTR)."""
        try:
            histogram = self._get_or_create_histogram(
                "recovery.duration",
                unit="ms",
                description="Recovery execution duration",
            )
            attributes = {
                "recovery.name": str(name),
                "recovery.success": str(success),
            }
            if target_type:
                attributes["recovery.target_type"] = str(target_type)
            histogram.record(float(duration_ms), attributes=attributes)
            self._metric_count += 1
        except Exception as e:
            logger.error(f"Error recording recovery time: {e}")

    def record_compliance_score(
        self,
        regulation: str,
        score: float,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Record compliance score."""
        try:
            gauge = self._get_or_create_gauge(
                "compliance.score", description="Compliance score"
            )
            attributes = {"compliance.regulation": str(regulation)}
            if details:
                attributes.update(
                    {f"compliance.{k}": str(v) for k, v in details.items()}
                )
            # Newer OTEL SDK gauges may not support .record; fall back to .set when available
            if hasattr(gauge, "record"):
                gauge.record(float(score), attributes=attributes)
            elif hasattr(gauge, "set"):
                gauge.set(float(score), attributes=attributes)
            else:
                logger.error(
                    "Gauge instrument for compliance.score has no record/set method"
                )
                return
            self._metric_count += 1
        except Exception as e:
            logger.error(f"Error recording compliance score: {e}")

    def record_compliance_violation(
        self, regulation: str, violation: str, severity: str = "medium"
    ) -> None:
        """Record compliance violation."""
        try:
            counter = self._get_or_create_counter(
                "compliance.violations", description="Compliance violations"
            )
            attributes = {
                "compliance.regulation": str(regulation),
                "compliance.violation": str(violation),
                "compliance.severity": str(severity),
            }
            counter.add(1, attributes=attributes)
            self._metric_count += 1
        except Exception as e:
            logger.error(f"Error recording compliance violation: {e}")

    def record_impact_scope(
        self,
        action_name: str,
        impact_type: str,
        count: int,
        percentage: Optional[float] = None,
    ) -> None:
        """Record impact scope."""
        try:
            counter = self._get_or_create_counter(
                "chaos.impact.total",
                description="Impact scope of chaos actions",
            )
            attributes = {
                "chaos.action": str(action_name),
                "chaos.impact_type": str(impact_type),
            }
            if percentage is not None:
                attributes["chaos.impact_percentage"] = str(percentage)
            counter.add(int(count), attributes=attributes)
            self._metric_count += 1
        except Exception as e:
            logger.error(f"Error recording impact scope: {e}")

    def record_custom_metric(
        self,
        name: str,
        value: float,
        metric_type: str = "gauge",
        unit: str = "1",
        tags: Optional[Dict[str, str]] = None,
        description: Optional[str] = None,
    ) -> None:
        """Record custom metric."""
        try:
            attributes = {}
            if tags:
                attributes = {f"tag.{k}": str(v) for k, v in tags.items()}

            if metric_type == "gauge":
                instrument = self._get_or_create_gauge(
                    name,
                    unit=unit,
                    description=description or f"Custom: {name}",
                )
                if hasattr(instrument, "record"):
                    instrument.record(float(value), attributes=attributes)
                elif hasattr(instrument, "set"):
                    instrument.set(float(value), attributes=attributes)
                else:
                    logger.error(
                        f"Gauge instrument for {name} has no record/set method"
                    )
                    return
            elif metric_type == "counter":
                instrument = self._get_or_create_counter(
                    name, description=description or f"Custom: {name}"
                )
                instrument.add(int(value), attributes=attributes)
            elif metric_type == "histogram":
                instrument = self._get_or_create_histogram(
                    name,
                    unit=unit,
                    description=description or f"Custom: {name}",
                )
                instrument.record(float(value), attributes=attributes)
            else:
                logger.error(f"Unknown metric type: {metric_type}")
                return

            self._metric_count += 1
        except Exception as e:
            logger.error(f"Error recording custom metric: {e}")

    def _get_or_create_histogram(
        self, name: str, unit: str = "1", description: str = ""
    ):
        """Get or create histogram."""
        cache_key = f"histogram_{name}"
        if cache_key not in self._instruments:
            self._instruments[cache_key] = self.meter.create_histogram(
                name=name, unit=unit, description=description
            )
        return self._instruments[cache_key]

    def _get_or_create_counter(
        self, name: str, unit: str = "1", description: str = ""
    ):
        """Get or create counter."""
        cache_key = f"counter_{name}"
        if cache_key not in self._instruments:
            self._instruments[cache_key] = self.meter.create_counter(
                name=name, unit=unit, description=description
            )
        return self._instruments[cache_key]

    def _get_or_create_gauge(
        self, name: str, unit: str = "1", description: str = ""
    ):
        """Get or create gauge."""
        cache_key = f"gauge_{name}"
        if cache_key not in self._instruments:
            self._instruments[cache_key] = self.meter.create_gauge(
                name=name, unit=unit, description=description
            )
        return self._instruments[cache_key]

    # ========================================================================
    # Database Metrics - Reusable across database extensions
    # ========================================================================

    def record_db_query_latency(
        self,
        duration_ms: float,
        db_system: str,
        db_name: Optional[str] = None,
        db_operation: Optional[str] = None,
        tags: Optional[Dict[str, str]] = None,
    ) -> None:
        """Record database query latency."""
        try:
            histogram = self._get_or_create_histogram(
                "db.query.latency",
                unit="ms",
                description="Database query latency",
            )
            attributes = {"db.system": str(db_system)}
            if db_name:
                attributes["db.name"] = str(db_name)
            if db_operation:
                attributes["db.operation"] = str(db_operation)
            if tags:
                attributes.update({f"tag.{k}": str(v) for k, v in tags.items()})
            histogram.record(float(duration_ms), attributes=attributes)
            self._metric_count += 1
        except Exception as e:
            logger.error(f"Error recording db query latency: {e}")

    def record_db_query_count(
        self,
        db_system: str,
        db_name: Optional[str] = None,
        db_operation: Optional[str] = None,
        count: int = 1,
        tags: Optional[Dict[str, str]] = None,
    ) -> None:
        """Record database query count."""
        try:
            counter = self._get_or_create_counter(
                "db.query.count", description="Database query count"
            )
            attributes = {"db.system": str(db_system)}
            if db_name:
                attributes["db.name"] = str(db_name)
            if db_operation:
                attributes["db.operation"] = str(db_operation)
            if tags:
                attributes.update({f"tag.{k}": str(v) for k, v in tags.items()})
            counter.add(int(count), attributes=attributes)
            self._metric_count += 1
        except Exception as e:
            logger.error(f"Error recording db query count: {e}")

    def record_db_error(
        self,
        db_system: str,
        error_type: str,
        db_name: Optional[str] = None,
        tags: Optional[Dict[str, str]] = None,
    ) -> None:
        """Record database error."""
        try:
            counter = self._get_or_create_counter(
                "db.error.count", description="Database error count"
            )
            attributes = {
                "db.system": str(db_system),
                "error.type": str(error_type),
            }
            if db_name:
                attributes["db.name"] = str(db_name)
            if tags:
                attributes.update({f"tag.{k}": str(v) for k, v in tags.items()})
            counter.add(1, attributes=attributes)
            self._metric_count += 1
        except Exception as e:
            logger.error(f"Error recording db error: {e}")

    def record_db_connection_failure(
        self,
        db_system: str,
        db_name: Optional[str] = None,
        tags: Optional[Dict[str, str]] = None,
    ) -> None:
        """Record database connection failure."""
        try:
            counter = self._get_or_create_counter(
                "db.connection.failure",
                description="Database connection failure count",
            )
            attributes = {"db.system": str(db_system)}
            if db_name:
                attributes["db.name"] = str(db_name)
            if tags:
                attributes.update({f"tag.{k}": str(v) for k, v in tags.items()})
            counter.add(1, attributes=attributes)
            self._metric_count += 1
        except Exception as e:
            logger.error(f"Error recording db connection failure: {e}")

    def record_db_gauge(
        self,
        metric_name: str,
        value: float,
        db_system: str,
        db_name: Optional[str] = None,
        unit: str = "1",
        tags: Optional[Dict[str, str]] = None,
        description: Optional[str] = None,
    ) -> None:
        """Record database gauge metric."""
        try:
            gauge = self._get_or_create_gauge(
                f"db.{metric_name}",
                unit=unit,
                description=description or f"Database {metric_name}",
            )
            attributes = {"db.system": str(db_system)}
            if db_name:
                attributes["db.name"] = str(db_name)
            if tags:
                attributes.update({f"tag.{k}": str(v) for k, v in tags.items()})
            if hasattr(gauge, "record"):
                gauge.record(float(value), attributes=attributes)
            elif hasattr(gauge, "set"):
                gauge.set(float(value), attributes=attributes)
            else:
                logger.error(
                    f"Gauge instrument for db.{metric_name} has no record/set method"
                )
                return
            self._metric_count += 1
        except Exception as e:
            logger.error(f"Error recording db gauge: {e}")

    def record_db_counter(
        self,
        metric_name: str,
        db_system: str,
        db_name: Optional[str] = None,
        count: int = 1,
        tags: Optional[Dict[str, str]] = None,
        description: Optional[str] = None,
    ) -> None:
        """Record database counter metric."""
        try:
            counter = self._get_or_create_counter(
                f"db.{metric_name}",
                description=description or f"Database {metric_name}",
            )
            attributes = {"db.system": str(db_system)}
            if db_name:
                attributes["db.name"] = str(db_name)
            if tags:
                attributes.update({f"tag.{k}": str(v) for k, v in tags.items()})
            counter.add(int(count), attributes=attributes)
            self._metric_count += 1
        except Exception as e:
            logger.error(f"Error recording db counter: {e}")

    def record_db_histogram(
        self,
        metric_name: str,
        value: float,
        db_system: str,
        db_name: Optional[str] = None,
        unit: str = "ms",
        tags: Optional[Dict[str, str]] = None,
        description: Optional[str] = None,
    ) -> None:
        """Record database histogram metric."""
        try:
            histogram = self._get_or_create_histogram(
                f"db.{metric_name}",
                unit=unit,
                description=description or f"Database {metric_name}",
            )
            attributes = {"db.system": str(db_system)}
            if db_name:
                attributes["db.name"] = str(db_name)
            if tags:
                attributes.update({f"tag.{k}": str(v) for k, v in tags.items()})
            histogram.record(float(value), attributes=attributes)
            self._metric_count += 1
        except Exception as e:
            logger.error(f"Error recording db histogram: {e}")

    # ========================================================================
    # Messaging Metrics - Reusable across messaging system extensions
    # ========================================================================

    def record_messaging_operation_latency(
        self,
        duration_ms: float,
        mq_system: str,
        mq_destination: Optional[str] = None,
        mq_operation: Optional[str] = None,
        tags: Optional[Dict[str, str]] = None,
    ) -> None:
        """Record messaging operation latency."""
        try:
            histogram = self._get_or_create_histogram(
                "messaging.operation.latency",
                unit="ms",
                description="Messaging operation latency",
            )
            attributes = {"messaging.system": str(mq_system)}
            if mq_destination:
                attributes["messaging.destination"] = str(mq_destination)
            if mq_operation:
                attributes["messaging.operation"] = str(mq_operation)
            if tags:
                attributes.update({f"tag.{k}": str(v) for k, v in tags.items()})
            histogram.record(float(duration_ms), attributes=attributes)
            self._metric_count += 1
        except Exception as e:
            logger.error(f"Error recording messaging operation latency: {e}")

    def record_messaging_operation_count(
        self,
        mq_system: str,
        mq_destination: Optional[str] = None,
        mq_operation: Optional[str] = None,
        count: int = 1,
        tags: Optional[Dict[str, str]] = None,
    ) -> None:
        """Record messaging operation count."""
        try:
            counter = self._get_or_create_counter(
                "messaging.operation.count",
                description="Messaging operation count",
            )
            attributes = {"messaging.system": str(mq_system)}
            if mq_destination:
                attributes["messaging.destination"] = str(mq_destination)
            if mq_operation:
                attributes["messaging.operation"] = str(mq_operation)
            if tags:
                attributes.update({f"tag.{k}": str(v) for k, v in tags.items()})
            counter.add(int(count), attributes=attributes)
            self._metric_count += 1
        except Exception as e:
            logger.error(f"Error recording messaging operation count: {e}")

    def record_messaging_error(
        self,
        mq_system: str,
        error_type: str,
        mq_destination: Optional[str] = None,
        mq_operation: Optional[str] = None,
        tags: Optional[Dict[str, str]] = None,
    ) -> None:
        """Record messaging error."""
        try:
            counter = self._get_or_create_counter(
                "messaging.error.count", description="Messaging error count"
            )
            attributes = {
                "messaging.system": str(mq_system),
                "error.type": str(error_type),
            }
            if mq_destination:
                attributes["messaging.destination"] = str(mq_destination)
            if mq_operation:
                attributes["messaging.operation"] = str(mq_operation)
            if tags:
                attributes.update({f"tag.{k}": str(v) for k, v in tags.items()})
            counter.add(1, attributes=attributes)
            self._metric_count += 1
        except Exception as e:
            logger.error(f"Error recording messaging error: {e}")

    def record_messaging_connection_failure(
        self,
        mq_system: str,
        mq_destination: Optional[str] = None,
        tags: Optional[Dict[str, str]] = None,
    ) -> None:
        """Record messaging connection failure."""
        try:
            counter = self._get_or_create_counter(
                "messaging.connection.failure",
                description="Messaging connection failure count",
            )
            attributes = {"messaging.system": str(mq_system)}
            if mq_destination:
                attributes["messaging.destination"] = str(mq_destination)
            if tags:
                attributes.update({f"tag.{k}": str(v) for k, v in tags.items()})
            counter.add(1, attributes=attributes)
            self._metric_count += 1
        except Exception as e:
            logger.error(f"Error recording messaging connection failure: {e}")

    def record_messaging_gauge(
        self,
        metric_name: str,
        value: float,
        mq_system: str,
        mq_destination: Optional[str] = None,
        unit: str = "1",
        tags: Optional[Dict[str, str]] = None,
        description: Optional[str] = None,
    ) -> None:
        """Record messaging gauge metric."""
        try:
            gauge = self._get_or_create_gauge(
                f"messaging.{metric_name}",
                unit=unit,
                description=description or f"Messaging {metric_name}",
            )
            attributes = {"messaging.system": str(mq_system)}
            if mq_destination:
                attributes["messaging.destination"] = str(mq_destination)
            if tags:
                attributes.update({f"tag.{k}": str(v) for k, v in tags.items()})
            if hasattr(gauge, "record"):
                gauge.record(float(value), attributes=attributes)
            elif hasattr(gauge, "set"):
                gauge.set(float(value), attributes=attributes)
            else:
                logger.error(
                    f"Gauge instrument for messaging.{metric_name} has no record/set method"
                )
                return
            self._metric_count += 1
        except Exception as e:
            logger.error(f"Error recording messaging gauge: {e}")

    def record_messaging_counter(
        self,
        metric_name: str,
        mq_system: str,
        mq_destination: Optional[str] = None,
        count: int = 1,
        tags: Optional[Dict[str, str]] = None,
        description: Optional[str] = None,
    ) -> None:
        """Record messaging counter metric."""
        try:
            counter = self._get_or_create_counter(
                f"messaging.{metric_name}",
                description=description or f"Messaging {metric_name}",
            )
            attributes = {"messaging.system": str(mq_system)}
            if mq_destination:
                attributes["messaging.destination"] = str(mq_destination)
            if tags:
                attributes.update({f"tag.{k}": str(v) for k, v in tags.items()})
            counter.add(int(count), attributes=attributes)
            self._metric_count += 1
        except Exception as e:
            logger.error(f"Error recording messaging counter: {e}")

    def record_messaging_histogram(
        self,
        metric_name: str,
        value: float,
        mq_system: str,
        mq_destination: Optional[str] = None,
        unit: str = "ms",
        tags: Optional[Dict[str, str]] = None,
        description: Optional[str] = None,
    ) -> None:
        """Record messaging histogram metric."""
        try:
            histogram = self._get_or_create_histogram(
                f"messaging.{metric_name}",
                unit=unit,
                description=description or f"Messaging {metric_name}",
            )
            attributes = {"messaging.system": str(mq_system)}
            if mq_destination:
                attributes["messaging.destination"] = str(mq_destination)
            if tags:
                attributes.update({f"tag.{k}": str(v) for k, v in tags.items()})
            histogram.record(float(value), attributes=attributes)
            self._metric_count += 1
        except Exception as e:
            logger.error(f"Error recording messaging histogram: {e}")

    def shutdown(self) -> None:
        """Shutdown metrics core."""
        try:
            if hasattr(self.meter_provider, "shutdown"):
                self.meter_provider.shutdown()
            logger.info("MetricsCore shutdown complete")
        except Exception as e:
            logger.error(f"Error during shutdown: {e}")
