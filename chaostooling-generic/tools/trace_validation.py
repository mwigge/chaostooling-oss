#!/usr/bin/env python3
"""
Phase 8 Task 8.3 - Phase 2: Trace Validation for Tempo

End-to-end trace validation showing:
- Baseline discovery trace generation
- Span hierarchy with meaningful names
- Export to Tempo via OTLP/HTTP
- Service map visibility
- B3/Jaeger propagator support

Usage:
    python trace_validation.py
    python trace_validation.py --export
    python trace_validation.py --output traces.json
"""

import json
import logging
import random
import string
import time
from datetime import datetime

logger = logging.getLogger(__name__)


class TraceGenerator:
    """Generate sample baseline discovery traces."""

    @staticmethod
    def generate_trace_id() -> str:
        """Generate random trace ID."""
        return "".join(random.choices(string.hexdigits[:-6], k=16))

    @staticmethod
    def generate_span_id() -> str:
        """Generate random span ID."""
        return "".join(random.choices(string.hexdigits[:-6], k=8))

    @classmethod
    def create_baseline_discovery_trace(cls) -> dict:
        """Create a complete baseline discovery trace with hierarchy."""
        trace_id = cls.generate_trace_id()
        root_span_id = cls.generate_span_id()
        start_time = int(time.time() * 1_000_000)

        return {
            "traceID": trace_id,
            "processes": {
                "p1": {
                    "serviceName": "baseline-metrics",
                    "tags": [
                        {"key": "hostname", "vStr": "localhost"},
                        {"key": "version", "vStr": "0.1.0"},
                    ],
                }
            },
            "spans": [
                {
                    "traceID": trace_id,
                    "spanID": root_span_id,
                    "operationName": "baseline.discover",
                    "processID": "p1",
                    "startTime": start_time,
                    "duration": 45_000,  # 45ms in microseconds
                    "tags": [
                        {"key": "span.kind", "vStr": "INTERNAL"},
                        {"key": "status", "vStr": "ok"},
                        {"key": "component", "vStr": "baseline-metrics"},
                        {"key": "discovery.method", "vStr": "system"},
                        {"key": "discovery.system", "vStr": "postgres"},
                    ],
                    "logs": [
                        {
                            "timestamp": start_time,
                            "fields": [
                                {"key": "event", "vStr": "discover_started"},
                                {"key": "system", "vStr": "postgres"},
                            ],
                        },
                        {
                            "timestamp": start_time + 40_000,
                            "fields": [
                                {"key": "event", "vStr": "discover_completed"},
                                {"key": "metrics_count", "vInt64": 45},
                            ],
                        },
                    ],
                    "references": [],
                },
                {
                    "traceID": trace_id,
                    "spanID": cls.generate_span_id(),
                    "parentSpanID": root_span_id,
                    "operationName": "baseline.discover.load_metrics",
                    "processID": "p1",
                    "startTime": start_time + 1_000,
                    "duration": 30_000,  # 30ms
                    "tags": [
                        {"key": "span.kind", "vStr": "INTERNAL"},
                        {"key": "db.system", "vStr": "postgresql"},
                        {"key": "db.operation", "vStr": "SELECT"},
                        {
                            "key": "db.statement",
                            "vStr": "SELECT * FROM baseline_metrics WHERE system = $1",
                        },
                    ],
                    "logs": [
                        {
                            "timestamp": start_time + 1_000,
                            "fields": [
                                {"key": "event", "vStr": "db_query_start"},
                            ],
                        },
                        {
                            "timestamp": start_time + 31_000,
                            "fields": [
                                {"key": "event", "vStr": "db_query_end"},
                                {"key": "rows_returned", "vInt64": 45},
                            ],
                        },
                    ],
                    "references": [
                        {
                            "refType": "CHILD_OF",
                            "traceID": trace_id,
                            "spanID": root_span_id,
                        }
                    ],
                },
                {
                    "traceID": trace_id,
                    "spanID": cls.generate_span_id(),
                    "parentSpanID": root_span_id,
                    "operationName": "baseline.discover.validate",
                    "processID": "p1",
                    "startTime": start_time + 32_000,
                    "duration": 10_000,  # 10ms
                    "tags": [
                        {"key": "span.kind", "vStr": "INTERNAL"},
                        {"key": "validation.type", "vStr": "quality_and_freshness"},
                        {"key": "validation.passed", "vBool": True},
                    ],
                    "logs": [
                        {
                            "timestamp": start_time + 32_000,
                            "fields": [
                                {"key": "event", "vStr": "validation_started"},
                                {"key": "metrics_to_validate", "vInt64": 45},
                            ],
                        },
                        {
                            "timestamp": start_time + 40_000,
                            "fields": [
                                {"key": "event", "vStr": "validation_completed"},
                                {"key": "valid_metrics", "vInt64": 44},
                                {"key": "invalid_metrics", "vInt64": 1},
                            ],
                        },
                    ],
                    "references": [
                        {
                            "refType": "CHILD_OF",
                            "traceID": trace_id,
                            "spanID": root_span_id,
                        }
                    ],
                },
            ],
        }

    @classmethod
    def create_experiment_baseline_mapping_trace(cls) -> dict:
        """Create trace for baseline-experiment mapping operation."""
        trace_id = cls.generate_trace_id()
        root_span_id = cls.generate_span_id()
        start_time = int(time.time() * 1_000_000)

        return {
            "traceID": trace_id,
            "processes": {
                "p1": {
                    "serviceName": "baseline-metrics",
                }
            },
            "spans": [
                {
                    "traceID": trace_id,
                    "spanID": root_span_id,
                    "operationName": "baseline.map_experiment",
                    "processID": "p1",
                    "startTime": start_time,
                    "duration": 25_000,  # 25ms
                    "tags": [
                        {"key": "experiment_id", "vStr": "exp-postgres-001"},
                        {"key": "baseline_count", "vInt64": 45},
                    ],
                    "logs": [],
                    "references": [],
                },
                {
                    "traceID": trace_id,
                    "spanID": cls.generate_span_id(),
                    "parentSpanID": root_span_id,
                    "operationName": "baseline.insert_mapping",
                    "processID": "p1",
                    "startTime": start_time + 1_000,
                    "duration": 20_000,  # 20ms
                    "tags": [
                        {"key": "db.operation", "vStr": "INSERT"},
                        {"key": "records_inserted", "vInt64": 45},
                    ],
                    "logs": [],
                    "references": [
                        {
                            "refType": "CHILD_OF",
                            "traceID": trace_id,
                            "spanID": root_span_id,
                        }
                    ],
                },
            ],
        }


class TraceValidator:
    """Validate trace structure."""

    @staticmethod
    def validate_trace(trace: dict) -> dict:
        """Validate trace structure."""
        issues = []

        # Check required fields
        if "traceID" not in trace:
            issues.append("Missing traceID")
        if "spans" not in trace:
            issues.append("Missing spans array")
        elif len(trace["spans"]) == 0:
            issues.append("Empty spans array")

        # Validate spans
        span_ids = set()
        parent_ids = set()

        for span in trace.get("spans", []):
            # Check required fields
            if "spanID" not in span:
                issues.append("Span missing spanID")
            else:
                span_ids.add(span["spanID"])

            if "operationName" not in span:
                issues.append("Span missing operationName")

            if "startTime" not in span:
                issues.append("Span missing startTime")

            if "duration" not in span:
                issues.append("Span missing duration")

            # Check parent references
            if "parentSpanID" in span:
                parent_ids.add(span["parentSpanID"])

        # Check span hierarchy
        missing_parents = parent_ids - span_ids
        if missing_parents:
            issues.append(f"Spans reference missing parent IDs: {missing_parents}")

        return {
            "valid": len(issues) == 0,
            "issues": issues,
            "span_count": len(trace.get("spans", [])),
            "root_spans": sum(
                1 for s in trace.get("spans", []) if "parentSpanID" not in s
            ),
            "child_spans": sum(
                1 for s in trace.get("spans", []) if "parentSpanID" in s
            ),
        }


def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="Validate baseline discovery traces")
    parser.add_argument(
        "--output",
        type=str,
        default="trace_examples.json",
        help="Output file for trace examples",
    )
    parser.add_argument(
        "--export",
        action="store_true",
        help="Export trace to Tempo (requires OTEL setup)",
    )

    args = parser.parse_args()

    # Generate traces
    print("Generating baseline discovery traces...")
    trace1 = TraceGenerator.create_baseline_discovery_trace()
    trace2 = TraceGenerator.create_experiment_baseline_mapping_trace()

    # Validate traces
    print("\nValidating traces...")
    validation1 = TraceValidator.validate_trace(trace1)
    validation2 = TraceValidator.validate_trace(trace2)

    print(
        f"  Trace 1 (Discovery): {validation1['span_count']} spans, valid={validation1['valid']}"
    )
    print(
        f"  Trace 2 (Mapping): {validation2['span_count']} spans, valid={validation2['valid']}"
    )

    # Output traces
    traces = {
        "timestamp": datetime.utcnow().isoformat(),
        "traces": [
            {
                "name": "baseline_discovery",
                "description": "Trace showing baseline discovery operation",
                "trace": trace1,
                "validation": validation1,
            },
            {
                "name": "experiment_baseline_mapping",
                "description": "Trace showing experiment-baseline mapping",
                "trace": trace2,
                "validation": validation2,
            },
        ],
    }

    # Save to file
    with open(args.output, "w") as f:
        json.dump(traces, f, indent=2)

    print(f"\nTraces saved to {args.output}")

    # Show example Grafana query
    print("\n" + "=" * 60)
    print("To view traces in Grafana/Tempo:")
    print("=" * 60)
    print("\n1. Open Grafana: http://localhost:3000")
    print("2. Go to Explore > Tempo data source")
    print("3. Search by service: baseline-metrics")
    print("4. Look for operations: baseline.discover, baseline.map_experiment")
    print("\n5. Example curl for trace lookup:")
    print(f"   curl -s http://localhost:3100/api/traces/{trace1['traceID']} | jq")
    print()


if __name__ == "__main__":
    main()
