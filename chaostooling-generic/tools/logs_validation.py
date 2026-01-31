#!/usr/bin/env python3
"""
Phase 8 Task 8.3 - Phase 4: Logs Validation for Loki

Logs validation showing:
- Structured log emission for baseline operations
- Log labels (service_name, instance, pod)
- Loki ingestion verification
- LogQL query examples

Usage:
    python logs_validation.py
    python logs_validation.py --output logs_examples.json
    python logs_validation.py --format logql
"""

import json
import csv
import logging
from datetime import datetime, timedelta
from typing import Dict, List
from dataclasses import dataclass, asdict
import sys


# ============================================================================
# STRUCTURED LOGGING
# ============================================================================


@dataclass
class StructuredLogEntry:
    """Structured log entry for Loki."""

    timestamp: str
    service_name: str
    instance: str
    level: str
    message: str
    operation: str
    system: str
    duration_ms: float = 0.0
    status: str = "success"
    error: str = None
    trace_id: str = None

    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        return asdict(self)

    def to_loki_label_string(self) -> str:
        """Generate Loki label string."""
        return (
            f'{{service_name="{self.service_name}", '
            f'instance="{self.instance}", '
            f'level="{self.level}"}}'
        )

    def to_logql_line(self) -> str:
        """Generate log line as it would appear in LogQL."""
        return (
            f"{self.timestamp} {self.level} {self.service_name} {self.operation} "
            f'message="{self.message}" duration_ms={self.duration_ms} status={self.status}'
        )


# ============================================================================
# LOG GENERATORS
# ============================================================================


class BaselineLogsGenerator:
    """Generate structured logs for baseline operations."""

    @staticmethod
    def generate_discovery_logs() -> List[StructuredLogEntry]:
        """Generate logs for baseline discovery operation."""
        base_time = datetime.utcnow()

        return [
            StructuredLogEntry(
                timestamp=base_time.isoformat(),
                service_name="baseline-metrics",
                instance="localhost",
                level="info",
                message="baseline discovery started",
                operation="discover",
                system="postgres",
                status="in_progress",
            ),
            StructuredLogEntry(
                timestamp=(base_time + timedelta(milliseconds=10)).isoformat(),
                service_name="baseline-metrics",
                instance="localhost",
                level="debug",
                message="querying database for postgres metrics",
                operation="discover",
                system="postgres",
                status="in_progress",
            ),
            StructuredLogEntry(
                timestamp=(base_time + timedelta(milliseconds=35)).isoformat(),
                service_name="baseline-metrics",
                instance="localhost",
                level="debug",
                message="validating 45 metrics",
                operation="discover",
                system="postgres",
                status="in_progress",
            ),
            StructuredLogEntry(
                timestamp=(base_time + timedelta(milliseconds=45)).isoformat(),
                service_name="baseline-metrics",
                instance="localhost",
                level="info",
                message="baseline discovery completed",
                operation="discover",
                system="postgres",
                duration_ms=45.0,
                status="success",
            ),
        ]

    @staticmethod
    def generate_validation_logs() -> List[StructuredLogEntry]:
        """Generate logs for baseline validation operation."""
        base_time = datetime.utcnow()

        return [
            StructuredLogEntry(
                timestamp=base_time.isoformat(),
                service_name="baseline-metrics",
                instance="localhost",
                level="info",
                message="baseline validation started",
                operation="validate",
                system="postgres",
                status="in_progress",
            ),
            StructuredLogEntry(
                timestamp=(base_time + timedelta(milliseconds=8)).isoformat(),
                service_name="baseline-metrics",
                instance="localhost",
                level="debug",
                message="checking baseline age",
                operation="validate",
                system="postgres",
                status="in_progress",
            ),
            StructuredLogEntry(
                timestamp=(base_time + timedelta(milliseconds=18)).isoformat(),
                service_name="baseline-metrics",
                instance="localhost",
                level="warn",
                message="1 metric exceeds max age threshold",
                operation="validate",
                system="postgres",
                status="in_progress",
            ),
            StructuredLogEntry(
                timestamp=(base_time + timedelta(milliseconds=25)).isoformat(),
                service_name="baseline-metrics",
                instance="localhost",
                level="info",
                message="baseline validation completed",
                operation="validate",
                system="postgres",
                duration_ms=25.0,
                status="success",
            ),
        ]

    @staticmethod
    def generate_error_logs() -> List[StructuredLogEntry]:
        """Generate logs for error scenarios."""
        base_time = datetime.utcnow()

        return [
            StructuredLogEntry(
                timestamp=base_time.isoformat(),
                service_name="baseline-metrics",
                instance="localhost",
                level="error",
                message="database connection failed",
                operation="discover",
                system="postgres",
                status="failure",
                error="Connection timeout: 5000ms",
            ),
        ]


# ============================================================================
# LOGQL QUERIES
# ============================================================================

LOGQL_QUERIES = {
    "All baseline metrics logs": {
        "query": '{service_name="baseline-metrics"}',
        "description": "All logs from baseline-metrics service",
    },
    "Discovery operations": {
        "query": '{service_name="baseline-metrics"} | operation="discover"',
        "description": "Only baseline discovery operation logs",
    },
    "Validation operations": {
        "query": '{service_name="baseline-metrics"} | operation="validate"',
        "description": "Only baseline validation operation logs",
    },
    "Error logs": {
        "query": '{service_name="baseline-metrics",level="error"}',
        "description": "Error logs from baseline service",
    },
    "By system": {
        "query": '{service_name="baseline-metrics"} | system="postgres"',
        "description": "Logs for postgres system",
    },
    "By operation and status": {
        "query": '{service_name="baseline-metrics"} | operation="discover" status="success"',
        "description": "Successful discovery operations",
    },
    "Duration analysis": {
        "query": '{service_name="baseline-metrics"} | json | duration_ms > 50',
        "description": "Operations taking >50ms",
    },
    "Requests per second": {
        "query": 'rate({service_name="baseline-metrics"}[5m])',
        "description": "Request rate over 5 minute window",
    },
}


# ============================================================================
# EXPORTERS
# ============================================================================


def export_logs_json(logs: List[StructuredLogEntry], output_file: str):
    """Export logs as JSON."""
    data = {
        "timestamp": datetime.utcnow().isoformat(),
        "logs": [log.to_dict() for log in logs],
        "logql_queries": LOGQL_QUERIES,
    }

    with open(output_file, "w") as f:
        json.dump(data, f, indent=2)


def export_logs_csv(logs: List[StructuredLogEntry], output_file: str):
    """Export logs as CSV."""
    with open(output_file, "w", newline="") as f:
        writer = csv.writer(f)

        # Header
        writer.writerow(
            [
                "timestamp",
                "service_name",
                "instance",
                "level",
                "message",
                "operation",
                "system",
                "duration_ms",
                "status",
                "error",
            ]
        )

        # Rows
        for log in logs:
            writer.writerow(
                [
                    log.timestamp,
                    log.service_name,
                    log.instance,
                    log.level,
                    log.message,
                    log.operation,
                    log.system,
                    log.duration_ms,
                    log.status,
                    log.error or "",
                ]
            )


def export_logql_queries(output_file: str):
    """Export LogQL queries as markdown and CSV."""
    # Markdown
    md_file = output_file.replace(".csv", ".md")
    with open(md_file, "w") as f:
        f.write("# LogQL Queries for Baseline Metrics Logs\n\n")

        for query_name, query_def in LOGQL_QUERIES.items():
            f.write(f"## {query_name}\n\n")
            f.write(f"**Description:** {query_def['description']}\n\n")
            f.write(f"**Query:**\n\n```logql\n{query_def['query']}\n```\n\n")

        f.write("## Viewing in Grafana\n\n")
        f.write("""1. Open Grafana (http://localhost:3000)
2. Navigate to Explore
3. Select Loki data source
4. Paste a LogQL query
5. View results in the Logs panel

## Common Patterns

### Parse JSON fields
```logql
{service_name="baseline-metrics"} | json
| operation="discover"
| duration_ms > 50
```

### Filter by level
```logql
{service_name="baseline-metrics",level="error"}
```

### Time range
```logql
{service_name="baseline-metrics"} 
| timestamp > "2026-01-31T12:00:00Z"
```

### Metrics from logs
```logql
bytes_rate(message) by (operation)
```
""")

    # CSV
    with open(output_file, "w", newline="") as f:
        writer = csv.writer(f)

        # Header
        writer.writerow(
            [
                "Query Name",
                "LogQL",
                "Description",
            ]
        )

        # Rows
        for query_name, query_def in LOGQL_QUERIES.items():
            writer.writerow(
                [
                    query_name,
                    query_def["query"],
                    query_def["description"],
                ]
            )


def generate_markdown_docs(output_file: str):
    """Generate comprehensive Markdown documentation."""
    with open(output_file, "w") as f:
        f.write("""# Baseline Metrics Logs Validation (Loki)

## Overview

Baseline metrics operations emit structured logs that are ingested by Loki for searchability and analysis.

## Log Structure

Each baseline operation emits structured logs with the following fields:

```json
{
  "timestamp": "2026-01-31T12:34:56Z",
  "service_name": "baseline-metrics",
  "instance": "localhost",
  "level": "info",
  "message": "baseline discovery completed",
  "operation": "discover",
  "system": "postgres",
  "duration_ms": 45.0,
  "status": "success",
  "trace_id": "abc123..."
}
```

### Required Fields

- **timestamp**: ISO 8601 format (UTC)
- **service_name**: Service emitting the log (e.g., "baseline-metrics")
- **instance**: Server instance identifier
- **level**: Log level (debug, info, warn, error)
- **message**: Human-readable log message
- **operation**: Operation being performed (discover, validate, map, suggest)
- **system**: Target system (postgres, mysql, redis, etc.)

### Optional Fields

- **duration_ms**: Operation duration in milliseconds
- **status**: Operation status (success, failure, in_progress)
- **error**: Error message if applicable
- **trace_id**: Distributed trace ID for correlation

## Loki Labels

Logs are labeled for efficient querying:

```
{service_name="baseline-metrics", instance="localhost", level="info"}
```

These labels enable filtering by service, instance, and log level.

## Log Examples

### Successful Discovery
```
2026-01-31T12:34:56Z baseline discovery started
2026-01-31T12:34:56.010Z querying database for postgres metrics
2026-01-31T12:34:56.035Z validating 45 metrics
2026-01-31T12:34:56.045Z baseline discovery completed duration_ms=45 status=success
```

### Validation with Issues
```
2026-01-31T12:35:00Z baseline validation started
2026-01-31T12:35:00.008Z checking baseline age
2026-01-31T12:35:00.018Z 1 metric exceeds max age threshold
2026-01-31T12:35:00.025Z baseline validation completed duration_ms=25 status=success
```

### Error Scenario
```
2026-01-31T12:36:00Z baseline discover started
2026-01-31T12:36:05Z database connection failed error="Connection timeout: 5000ms" status=failure
```

## LogQL Query Examples

### Basic Queries

**All baseline metrics logs:**
```logql
{service_name="baseline-metrics"}
```

**Discovery operations only:**
```logql
{service_name="baseline-metrics"} | operation="discover"
```

**Error logs:**
```logql
{service_name="baseline-metrics",level="error"}
```

### Advanced Queries

**Parse JSON and filter:**
```logql
{service_name="baseline-metrics"} | json | operation="discover" | status="success"
```

**Find slow operations (>50ms):**
```logql
{service_name="baseline-metrics"} | json | duration_ms > 50
```

**Operations by system:**
```logql
{service_name="baseline-metrics"} | json | system="postgres"
```

**Operations rate per service:**
```logql
rate({service_name="baseline-metrics"}[5m])
```

## Verification Steps

### 1. Check Loki is Running
```bash
curl http://localhost:3100/ready
```

### 2. Query for Baseline Logs
```bash
curl -G "http://localhost:3100/api/prom/query" \
  --data-urlencode 'query={service_name="baseline-metrics"}' \
  --data-urlencode 'limit=100'
```

### 3. View in Grafana
1. Open Grafana (http://localhost:3000)
2. Navigate to Explore
3. Select Loki data source
4. Use LogQL queries from this document

## Integration with OpenTelemetry

Logs are correlated with traces via `trace_id`:

```python
logger.info(
    "baseline discovery started",
    extra={
        "service_name": "baseline-metrics",
        "operation": "discover",
        "system": "postgres",
        "trace_id": span.get_span_context().trace_id,
    }
)
```

This enables switching between logs and traces in Grafana.

## Performance Considerations

### Label Strategy
- Keep labels low-cardinality (service_name, instance, level)
- Avoid using operation or system as labels if they have many values
- Use JSON parsing for high-cardinality fields

### Query Performance
- Use specific label filters when possible
- Avoid regex patterns on large text fields
- Aggregate logs with metrics queries

### Retention
- Logs are retained per Loki configuration (default: 30 days)
- Older logs are automatically deleted
- Critical logs can be archived separately
""")


# ============================================================================
# MAIN
# ============================================================================


def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="Generate baseline logs documentation")
    parser.add_argument(
        "--format",
        choices=["json", "csv", "markdown", "logql", "all"],
        default="json",
        help="Output format",
    )
    parser.add_argument(
        "--output",
        type=str,
        default="logs_examples",
        help="Output file prefix (without extension)",
    )

    args = parser.parse_args()

    print("Generating baseline logs documentation...")

    # Generate logs
    all_logs = (
        BaselineLogsGenerator.generate_discovery_logs()
        + BaselineLogsGenerator.generate_validation_logs()
        + BaselineLogsGenerator.generate_error_logs()
    )

    if args.format in ["json", "all"]:
        output_file = f"{args.output}.json"
        export_logs_json(all_logs, output_file)
        print(f"  ✓ JSON logs: {output_file}")

    if args.format in ["csv", "all"]:
        output_file = f"{args.output}.csv"
        export_logs_csv(all_logs, output_file)
        print(f"  ✓ CSV logs: {output_file}")

    if args.format in ["logql", "all"]:
        output_file = f"{args.output}_logql.csv"
        export_logql_queries(output_file)
        print(f"  ✓ LogQL queries: {output_file.replace('.csv', '.md')}")
        print(f"  ✓ LogQL CSV: {output_file}")

    if args.format in ["markdown", "all"]:
        output_file = f"{args.output}_validation.md"
        generate_markdown_docs(output_file)
        print(f"  ✓ Markdown docs: {output_file}")

    print("\nLogs documentation generated successfully!")
    print(f"\nGenerated {len(all_logs)} sample log entries")


if __name__ == "__main__":
    main()
