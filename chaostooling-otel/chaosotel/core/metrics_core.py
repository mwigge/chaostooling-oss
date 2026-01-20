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
                "chaos_operation_duration_milliseconds",
                unit="ms",
                description="Operation execution duration",
            )
            attributes = {
                "operation_name": str(name),
                "operation_status": str(status),
            }
            if severity:
                attributes["operation_severity"] = str(severity)
            if target_type:
                attributes["operation_target_type"] = str(target_type)
            if tags:
                attributes.update({f"tag_{k}": str(v) for k, v in tags.items()})
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
                f"chaos_operation_{status}_total",
                description=f"Count of {status} operations",
            )
            attributes = {"operation_name": str(name)}
            if severity:
                attributes["operation_severity"] = str(severity)
            if target_type:
                attributes["operation_target_type"] = str(target_type)
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
                "chaos_probe_duration_milliseconds",
                unit="ms",
                description="Probe execution duration",
            )
            attributes = {"probe_name": str(name), "probe_status": str(status)}
            if target_type:
                attributes["probe_target_type"] = str(target_type)
            if tags:
                attributes.update({f"tag_{k}": str(v) for k, v in tags.items()})
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
                "chaos_probe_executions_total", description="Probe execution count"
            )
            attributes = {"probe_name": str(name), "probe_status": str(status)}
            if target_type:
                attributes["probe_target_type"] = str(target_type)
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
            # Use the new record_mttr method for consistency
            self.record_mttr(
                service_name=name,
                recovery_time_ms=duration_ms,
                recovery_type="recovery",
                success=success,
                tags={"target_type": target_type} if target_type else None,
            )
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
                "chaos_compliance_score", description="Compliance score"
            )
            attributes = {"regulation": str(regulation)}
            if details:
                attributes.update(
                    {f"compliance_{k}": str(v) for k, v in details.items()}
                )
            # Newer OTEL SDK gauges may not support .record; fall back to .set when available
            if hasattr(gauge, "record"):
                gauge.record(float(score), attributes=attributes)
            elif hasattr(gauge, "set"):
                gauge.set(float(score), attributes=attributes)
            else:
                logger.error(
                    "Gauge instrument for chaos_compliance_score has no record/set method"
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
                "chaos_compliance_violations_total", description="Compliance violations"
            )
            attributes = {
                "regulation": str(regulation),
                "violation": str(violation),
                "severity": str(severity),
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
                "chaos_impact_total",
                description="Impact scope of chaos actions",
            )
            attributes = {
                "action": str(action_name),
                "impact_type": str(impact_type),
            }
            if percentage is not None:
                attributes["impact_percentage"] = str(percentage)
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

    def _get_or_create_counter(self, name: str, unit: str = "1", description: str = ""):
        """Get or create counter."""
        cache_key = f"counter_{name}"
        if cache_key not in self._instruments:
            self._instruments[cache_key] = self.meter.create_counter(
                name=name, unit=unit, description=description
            )
        return self._instruments[cache_key]

    def _get_or_create_gauge(self, name: str, unit: str = "1", description: str = ""):
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
                "chaos_db_query_latency_milliseconds",
                unit="ms",
                description="Database query latency",
            )
            attributes = {"db_system": str(db_system)}
            if db_name:
                attributes["db_name"] = str(db_name)
            if db_operation:
                attributes["db_operation"] = str(db_operation)
            if tags:
                attributes.update({f"tag_{k}": str(v) for k, v in tags.items()})
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
                "chaos_db_query_count_total", description="Database query count"
            )
            attributes = {"db_system": str(db_system)}
            if db_name:
                attributes["db_name"] = str(db_name)
            if db_operation:
                attributes["db_operation"] = str(db_operation)
            if tags:
                attributes.update({f"tag_{k}": str(v) for k, v in tags.items()})
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
                "chaos_db_error_count_total", description="Database error count"
            )
            attributes = {
                "db_system": str(db_system),
                "error_type": str(error_type),
            }
            if db_name:
                attributes["db_name"] = str(db_name)
            if tags:
                attributes.update({f"tag_{k}": str(v) for k, v in tags.items()})
            counter.add(1, attributes=attributes)
            self._metric_count += 1
        except Exception as e:
            logger.error(f"Error recording db error: {e}")

    def record_db_deadlock(
        self,
        db_system: str,
        db_name: Optional[str] = None,
        tags: Optional[Dict[str, str]] = None,
    ) -> None:
        """Record database deadlock."""
        try:
            counter = self._get_or_create_counter(
                "chaos_db_deadlock_count_total", description="Database deadlock count"
            )
            attributes = {"db_system": str(db_system)}
            if db_name:
                attributes["db_name"] = str(db_name)
            if tags:
                attributes.update({f"tag_{k}": str(v) for k, v in tags.items()})
            counter.add(1, attributes=attributes)
            # Also record as error type "Deadlock"
            self.record_db_error(
                db_system=db_system,
                error_type="Deadlock",
                db_name=db_name,
                tags=tags,
            )
            self._metric_count += 1
        except Exception as e:
            logger.error(f"Error recording db deadlock: {e}")

    def record_db_lock(
        self,
        db_system: str,
        lock_type: str = "wait",
        db_name: Optional[str] = None,
        tags: Optional[Dict[str, str]] = None,
    ) -> None:
        """Record database lock event."""
        try:
            counter = self._get_or_create_counter(
                "chaos_db_lock_count_total", description="Database lock count"
            )
            attributes = {
                "db_system": str(db_system),
                "lock_type": str(lock_type),
            }
            if db_name:
                attributes["db_name"] = str(db_name)
            if tags:
                attributes.update({f"tag_{k}": str(v) for k, v in tags.items()})
            counter.add(1, attributes=attributes)
            self._metric_count += 1
        except Exception as e:
            logger.error(f"Error recording db lock: {e}")

    def record_db_slow_query_count(
        self,
        db_system: str,
        threshold_ms: float = 1000.0,
        db_name: Optional[str] = None,
        tags: Optional[Dict[str, str]] = None,
    ) -> None:
        """Record slow query count."""
        try:
            counter = self._get_or_create_counter(
                "chaos_db_slow_query_count_total",
                description="Database slow query count",
            )
            attributes = {
                "db_system": str(db_system),
                "threshold_ms": str(threshold_ms),
            }
            if db_name:
                attributes["db_name"] = str(db_name)
            if tags:
                attributes.update({f"tag_{k}": str(v) for k, v in tags.items()})
            counter.add(1, attributes=attributes)
            self._metric_count += 1
        except Exception as e:
            logger.error(f"Error recording slow query count: {e}")

    def record_db_connection_pool_utilization(
        self,
        db_system: str,
        utilization_percent: float,
        db_name: Optional[str] = None,
        tags: Optional[Dict[str, str]] = None,
    ) -> None:
        """Record connection pool utilization percentage."""
        try:
            gauge = self._get_or_create_gauge(
                "chaos_db_connection_pool_utilization",
                unit="percent",
                description="Database connection pool utilization",
            )
            attributes = {"db_system": str(db_system)}
            if db_name:
                attributes["db_name"] = str(db_name)
            if tags:
                attributes.update({f"tag_{k}": str(v) for k, v in tags.items()})
            if hasattr(gauge, "record"):
                gauge.record(float(utilization_percent), attributes=attributes)
            elif hasattr(gauge, "set"):
                gauge.set(float(utilization_percent), attributes=attributes)
            self._metric_count += 1
        except Exception as e:
            logger.error(f"Error recording connection pool utilization: {e}")

    def record_db_connection_failure(
        self,
        db_system: str,
        db_name: Optional[str] = None,
        tags: Optional[Dict[str, str]] = None,
    ) -> None:
        """Record database connection failure."""
        try:
            counter = self._get_or_create_counter(
                "chaos_db_connection_failure_total",
                description="Database connection failure count",
            )
            attributes = {"db_system": str(db_system)}
            if db_name:
                attributes["db_name"] = str(db_name)
            if tags:
                attributes.update({f"tag_{k}": str(v) for k, v in tags.items()})
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
                f"chaos_db_{metric_name}",
                unit=unit,
                description=description or f"Database {metric_name}",
            )
            attributes = {"db_system": str(db_system)}
            if db_name:
                attributes["db_name"] = str(db_name)
            if tags:
                attributes.update({f"tag_{k}": str(v) for k, v in tags.items()})
            if hasattr(gauge, "record"):
                gauge.record(float(value), attributes=attributes)
            elif hasattr(gauge, "set"):
                gauge.set(float(value), attributes=attributes)
            else:
                logger.error(
                    f"Gauge instrument for chaos_db_{metric_name} has no record/set method"
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
                f"chaos_db_{metric_name}",
                description=description or f"Database {metric_name}",
            )
            attributes = {"db_system": str(db_system)}
            if db_name:
                attributes["db_name"] = str(db_name)
            if tags:
                attributes.update({f"tag_{k}": str(v) for k, v in tags.items()})
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
                f"chaos_db_{metric_name}",
                unit=unit,
                description=description or f"Database {metric_name}",
            )
            attributes = {"db_system": str(db_system)}
            if db_name:
                attributes["db_name"] = str(db_name)
            if tags:
                attributes.update({f"tag_{k}": str(v) for k, v in tags.items()})
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
                "chaos_messaging_operation_latency_milliseconds",
                unit="ms",
                description="Messaging operation latency",
            )
            attributes = {"mq_system": str(mq_system)}
            if mq_destination:
                attributes["mq_destination"] = str(mq_destination)
            if mq_operation:
                attributes["mq_operation"] = str(mq_operation)
            if tags:
                attributes.update({f"tag_{k}": str(v) for k, v in tags.items()})
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
                "chaos_messaging_operation_count_total",
                description="Messaging operation count",
            )
            attributes = {"mq_system": str(mq_system)}
            if mq_destination:
                attributes["mq_destination"] = str(mq_destination)
            if mq_operation:
                attributes["mq_operation"] = str(mq_operation)
            if tags:
                attributes.update({f"tag_{k}": str(v) for k, v in tags.items()})
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
                "chaos_messaging_error_count_total", description="Messaging error count"
            )
            attributes = {
                "mq_system": str(mq_system),
                "error_type": str(error_type),
            }
            if mq_destination:
                attributes["mq_destination"] = str(mq_destination)
            if mq_operation:
                attributes["mq_operation"] = str(mq_operation)
            if tags:
                attributes.update({f"tag_{k}": str(v) for k, v in tags.items()})
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
                "chaos_messaging_connection_failure_total",
                description="Messaging connection failure count",
            )
            attributes = {"mq_system": str(mq_system)}
            if mq_destination:
                attributes["mq_destination"] = str(mq_destination)
            if tags:
                attributes.update({f"tag_{k}": str(v) for k, v in tags.items()})
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
                f"chaos_messaging_{metric_name}",
                unit=unit,
                description=description or f"Messaging {metric_name}",
            )
            attributes = {"mq_system": str(mq_system)}
            if mq_destination:
                attributes["mq_destination"] = str(mq_destination)
            if tags:
                attributes.update({f"tag_{k}": str(v) for k, v in tags.items()})
            if hasattr(gauge, "record"):
                gauge.record(float(value), attributes=attributes)
            elif hasattr(gauge, "set"):
                gauge.set(float(value), attributes=attributes)
            else:
                logger.error(
                    f"Gauge instrument for chaos_messaging_{metric_name} has no record/set method"
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
                f"chaos_messaging_{metric_name}",
                description=description or f"Messaging {metric_name}",
            )
            attributes = {"mq_system": str(mq_system)}
            if mq_destination:
                attributes["mq_destination"] = str(mq_destination)
            if tags:
                attributes.update({f"tag_{k}": str(v) for k, v in tags.items()})
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
                f"chaos_messaging_{metric_name}",
                unit=unit,
                description=description or f"Messaging {metric_name}",
            )
            attributes = {"mq_system": str(mq_system)}
            if mq_destination:
                attributes["mq_destination"] = str(mq_destination)
            if tags:
                attributes.update({f"tag_{k}": str(v) for k, v in tags.items()})
            histogram.record(float(value), attributes=attributes)
            self._metric_count += 1
        except Exception as e:
            logger.error(f"Error recording messaging histogram: {e}")

    # ========================================================================
    # Transaction Metrics
    # ========================================================================

    def record_transaction(
        self,
        db_operation: str,
        status: str = "successful",
        db_system: Optional[str] = None,
        tags: Optional[Dict[str, str]] = None,
    ) -> None:
        """Record transaction count."""
        try:
            counter = self._get_or_create_counter(
                f"chaos_transaction_{status}_total",
                description=f"Transaction {status} count",
            )
            attributes = {"tag_db_operation": str(db_operation)}
            if db_system:
                attributes["tag_db_system"] = str(db_system)
            if tags:
                attributes.update({f"tag_{k}": str(v) for k, v in tags.items()})
            counter.add(1, attributes=attributes)
            # Also record total
            total_counter = self._get_or_create_counter(
                "chaos_transaction_total",
                description="Total transaction count",
            )
            total_counter.add(1, attributes=attributes)
            self._metric_count += 1
        except Exception as e:
            logger.error(f"Error recording transaction: {e}")

    def record_transaction_reconnection_attempt(
        self,
        db_operation: str,
        db_system: Optional[str] = None,
        tags: Optional[Dict[str, str]] = None,
    ) -> None:
        """Record transaction reconnection attempt."""
        try:
            counter = self._get_or_create_counter(
                "chaos_transaction_reconnection_attempts_total",
                description="Transaction reconnection attempts",
            )
            attributes = {"tag_db_operation": str(db_operation)}
            if db_system:
                attributes["tag_db_system"] = str(db_system)
            if tags:
                attributes.update({f"tag_{k}": str(v) for k, v in tags.items()})
            counter.add(1, attributes=attributes)
            self._metric_count += 1
        except Exception as e:
            logger.error(f"Error recording transaction reconnection: {e}")

    def record_transaction_integrity(
        self,
        is_integrity_ok: bool,
        db_system: Optional[str] = None,
        tags: Optional[Dict[str, str]] = None,
    ) -> None:
        """Record transaction integrity check result."""
        try:
            gauge = self._get_or_create_gauge(
                "chaos_transaction_integrity_check",
                unit="1",
                description="Transaction integrity check (1=ok, 0=failed)",
            )
            attributes = {}
            if db_system:
                attributes["db_system"] = str(db_system)
            if tags:
                attributes.update({f"tag_{k}": str(v) for k, v in tags.items()})
            value = 1.0 if is_integrity_ok else 0.0
            if hasattr(gauge, "record"):
                gauge.record(float(value), attributes=attributes)
            elif hasattr(gauge, "set"):
                gauge.set(float(value), attributes=attributes)
            self._metric_count += 1
        except Exception as e:
            logger.error(f"Error recording transaction integrity: {e}")

    # ========================================================================
    # MTTR (Mean Time To Recovery) Metrics
    # ========================================================================

    def record_mttr(
        self,
        service_name: str,
        recovery_time_ms: float,
        recovery_type: str = "failover",
        success: bool = True,
        tags: Optional[Dict[str, str]] = None,
    ) -> None:
        """Record Mean Time To Recovery (MTTR) for a service."""
        try:
            # Convert milliseconds to seconds for consistency with metric name
            recovery_time_seconds = float(recovery_time_ms) / 1000.0

            histogram = self._get_or_create_histogram(
                "chaos_mttr_seconds",
                unit="s",
                description="Mean Time To Recovery in seconds",
            )
            attributes = {
                "service_name": str(service_name),
                "recovery_type": str(recovery_type),
                "recovery_success": str(success),
            }
            if tags:
                attributes.update({f"tag_{k}": str(v) for k, v in tags.items()})
            histogram.record(recovery_time_seconds, attributes=attributes)
            # Also record as gauge for current MTTR
            gauge = self._get_or_create_gauge(
                "chaos_mttr_current_seconds",
                unit="s",
                description="Current MTTR per service in seconds",
            )
            if hasattr(gauge, "record"):
                gauge.record(recovery_time_seconds, attributes=attributes)
            elif hasattr(gauge, "set"):
                gauge.set(recovery_time_seconds, attributes=attributes)
            self._metric_count += 1
        except Exception as e:
            logger.error(f"Error recording MTTR: {e}")

    # ========================================================================
    # Experiment Metrics - Track experiment lifecycle and status
    # ========================================================================

    def record_experiment_start(
        self,
        experiment_id: str,
        experiment_title: str,
        risk_level: Optional[str] = None,
        complexity_score: Optional[int] = None,
        systems: Optional[list] = None,
        tags: Optional[Dict[str, str]] = None,
    ) -> None:
        """Record experiment start with metadata."""
        try:
            counter = self._get_or_create_counter(
                "chaos_experiment_start_total",
                description="Total experiments started",
            )
            attributes = {
                "experiment_id": str(experiment_id),
                "experiment_title": str(experiment_title),
            }
            if risk_level:
                attributes["risk_level"] = str(risk_level)
            if complexity_score is not None:
                attributes["complexity_score"] = str(complexity_score)
            if systems:
                attributes["systems"] = ",".join(str(s) for s in systems)
            if tags:
                attributes.update({f"tag_{k}": str(v) for k, v in tags.items()})
            counter.add(1, attributes=attributes)

            # Record in-progress gauge
            gauge = self._get_or_create_gauge(
                "chaos_experiment_in_progress",
                description="Experiment currently in progress (1=running, 0=not running)",
            )
            if hasattr(gauge, "record"):
                gauge.record(1.0, attributes=attributes)
            elif hasattr(gauge, "set"):
                gauge.set(1.0, attributes=attributes)

            self._metric_count += 1
        except Exception as e:
            logger.error(f"Error recording experiment start: {e}")

    def record_experiment_end(
        self,
        experiment_id: str,
        experiment_title: str,
        status: str,
        duration_seconds: float,
        risk_level: Optional[str] = None,
        complexity_score: Optional[int] = None,
        systems: Optional[list] = None,
        tags: Optional[Dict[str, str]] = None,
    ) -> None:
        """Record experiment completion."""
        try:
            attributes = {
                "experiment_id": str(experiment_id),
                "experiment_title": str(experiment_title),
                "status": str(status),
            }
            if risk_level:
                attributes["risk_level"] = str(risk_level)
            if complexity_score is not None:
                attributes["complexity_score"] = str(complexity_score)
            if systems:
                attributes["systems"] = ",".join(str(s) for s in systems)
            if tags:
                attributes.update({f"tag_{k}": str(v) for k, v in tags.items()})

            # Record completion counter
            counter = self._get_or_create_counter(
                "chaos_experiment_end_total",
                description="Total experiments completed",
            )
            counter.add(1, attributes=attributes)

            # Record duration histogram
            histogram = self._get_or_create_histogram(
                "chaos_experiment_duration_seconds",
                unit="s",
                description="Experiment duration in seconds",
            )
            histogram.record(float(duration_seconds), attributes=attributes)

            # Record success ratio gauge (1.0 for success, 0.0 for failure)
            success_value = 1.0 if status in ("completed", "success") else 0.0
            gauge = self._get_or_create_gauge(
                "chaos_experiment_success_ratio",
                description="Experiment success ratio (1=success, 0=failure)",
            )
            if hasattr(gauge, "record"):
                gauge.record(success_value, attributes=attributes)
            elif hasattr(gauge, "set"):
                gauge.set(success_value, attributes=attributes)

            # Clear in-progress gauge
            in_progress_gauge = self._get_or_create_gauge(
                "chaos_experiment_in_progress",
                description="Experiment currently in progress (1=running, 0=not running)",
            )
            if hasattr(in_progress_gauge, "record"):
                in_progress_gauge.record(0.0, attributes=attributes)
            elif hasattr(in_progress_gauge, "set"):
                in_progress_gauge.set(0.0, attributes=attributes)

            # Record failed counter if applicable
            if status not in ("completed", "success"):
                failed_counter = self._get_or_create_counter(
                    "chaos_experiment_failed_total",
                    description="Total experiments failed",
                )
                failed_counter.add(1, attributes=attributes)

            self._metric_count += 1
        except Exception as e:
            logger.error(f"Error recording experiment end: {e}")

    def record_experiment_risk_level(
        self,
        experiment_id: str,
        experiment_title: str,
        risk_level: str,
        risk_score: Optional[float] = None,
        tags: Optional[Dict[str, str]] = None,
    ) -> None:
        """Record experiment risk level."""
        try:
            # Map risk levels to numeric values
            risk_level_map = {
                "low": 1.0,
                "medium": 2.0,
                "high": 3.0,
                "critical": 4.0,
            }
            risk_value = risk_level_map.get(risk_level.lower(), 0.0)

            attributes = {
                "experiment_id": str(experiment_id),
                "experiment_title": str(experiment_title),
                "risk_level": str(risk_level),
            }
            if tags:
                attributes.update({f"tag_{k}": str(v) for k, v in tags.items()})

            gauge = self._get_or_create_gauge(
                "chaos_experiment_risk_level_ratio",
                description="Experiment risk level (1=low, 2=medium, 3=high, 4=critical)",
            )
            if hasattr(gauge, "record"):
                gauge.record(risk_value, attributes=attributes)
            elif hasattr(gauge, "set"):
                gauge.set(risk_value, attributes=attributes)

            # Also record risk score if provided
            if risk_score is not None:
                score_gauge = self._get_or_create_gauge(
                    "chaos_experiment_risk_score_ratio",
                    description="Experiment risk score (0.0-1.0)",
                )
                if hasattr(score_gauge, "record"):
                    score_gauge.record(float(risk_score), attributes=attributes)
                elif hasattr(score_gauge, "set"):
                    score_gauge.set(float(risk_score), attributes=attributes)

            self._metric_count += 1
        except Exception as e:
            logger.error(f"Error recording experiment risk level: {e}")

    def record_experiment_complexity(
        self,
        experiment_id: str,
        experiment_title: str,
        complexity_score: int,
        complexity_level: Optional[str] = None,
        tags: Optional[Dict[str, str]] = None,
    ) -> None:
        """Record experiment complexity score."""
        try:
            attributes = {
                "experiment_id": str(experiment_id),
                "experiment_title": str(experiment_title),
            }
            if complexity_level:
                attributes["complexity_level"] = str(complexity_level)
            if tags:
                attributes.update({f"tag_{k}": str(v) for k, v in tags.items()})

            gauge = self._get_or_create_gauge(
                "chaos_experiment_complexity_score_ratio",
                description="Experiment complexity score",
            )
            if hasattr(gauge, "record"):
                gauge.record(float(complexity_score), attributes=attributes)
            elif hasattr(gauge, "set"):
                gauge.set(float(complexity_score), attributes=attributes)

            self._metric_count += 1
        except Exception as e:
            logger.error(f"Error recording experiment complexity: {e}")

    def record_experiment_activity(
        self,
        experiment_id: str,
        activity_type: str,
        activity_name: str,
        status: str,
        duration_ms: Optional[float] = None,
        tags: Optional[Dict[str, str]] = None,
    ) -> None:
        """Record individual experiment activity (action/probe/rollback)."""
        try:
            attributes = {
                "experiment_id": str(experiment_id),
                "activity_type": str(activity_type),
                "activity_name": str(activity_name),
                "status": str(status),
            }
            if tags:
                attributes.update({f"tag_{k}": str(v) for k, v in tags.items()})

            # Record activity count
            counter = self._get_or_create_counter(
                "chaos_experiment_activity_total",
                description="Total experiment activities executed",
            )
            counter.add(1, attributes=attributes)

            # Record duration if provided
            if duration_ms is not None:
                histogram = self._get_or_create_histogram(
                    "chaos_experiment_activity_duration_milliseconds",
                    unit="ms",
                    description="Experiment activity duration",
                )
                histogram.record(float(duration_ms), attributes=attributes)

            self._metric_count += 1
        except Exception as e:
            logger.error(f"Error recording experiment activity: {e}")

    def record_experiment_systems(
        self,
        experiment_id: str,
        experiment_title: str,
        systems: list,
        tags: Optional[Dict[str, str]] = None,
    ) -> None:
        """Record which systems an experiment affects."""
        try:
            for system in systems:
                attributes = {
                    "experiment_id": str(experiment_id),
                    "experiment_title": str(experiment_title),
                    "system": str(system),
                }
                if tags:
                    attributes.update({f"tag_{k}": str(v) for k, v in tags.items()})

                gauge = self._get_or_create_gauge(
                    "chaos_experiment_system_affected",
                    description="Systems affected by experiment (1=affected)",
                )
                if hasattr(gauge, "record"):
                    gauge.record(1.0, attributes=attributes)
                elif hasattr(gauge, "set"):
                    gauge.set(1.0, attributes=attributes)

            self._metric_count += 1
        except Exception as e:
            logger.error(f"Error recording experiment systems: {e}")

    def shutdown(self) -> None:
        """Shutdown metrics core."""
        try:
            if hasattr(self.meter_provider, "shutdown"):
                self.meter_provider.shutdown()
            logger.info("MetricsCore shutdown complete")
        except Exception as e:
            logger.error(f"Error during shutdown: {e}")
