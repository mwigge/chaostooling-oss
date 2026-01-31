#!/usr/bin/env python3
"""
Phase 8 Task 8.3 - Phase 3: Metrics Validation for Prometheus

Metrics validation showing:
- Baseline discovery counter
- Baseline validation histogram
- Error tracking
- Custom metrics from MetricsCore
- PromQL queries for validation

Exports metrics in Prometheus text format and provides PromQL examples.

Usage:
    python metrics_validation.py
    python metrics_validation.py --output metrics.txt
    python metrics_validation.py --format prometheus
"""

import csv
import json
import time
from datetime import datetime

# ============================================================================
# PROMETHEUS METRICS DEFINITIONS
# ============================================================================

BASELINE_METRICS = {
    "baseline_discovery_total": {
        "type": "counter",
        "description": "Total number of baseline discovery operations",
        "labels": ["service", "status"],
        "unit": "operations",
        "examples": [
            ('baseline_discovery_total{service="postgres",status="success"}', 42),
            ('baseline_discovery_total{service="postgres",status="failure"}', 2),
            ('baseline_discovery_total{service="mysql",status="success"}', 15),
        ],
    },
    "baseline_validation_duration_seconds": {
        "type": "histogram",
        "description": "Duration of baseline validation operations",
        "labels": ["operation", "status"],
        "buckets": [0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0],
        "unit": "seconds",
        "examples": [
            (
                'baseline_validation_duration_seconds_bucket{operation="validate",le="0.05"}',
                38,
            ),
            (
                'baseline_validation_duration_seconds_bucket{operation="validate",le="0.1"}',
                48,
            ),
            ('baseline_validation_duration_seconds_sum{operation="validate"}', 2.34),
            ('baseline_validation_duration_seconds_count{operation="validate"}', 50),
        ],
    },
    "baseline_errors_total": {
        "type": "counter",
        "description": "Total baseline operation errors",
        "labels": ["operation", "error_type"],
        "unit": "errors",
        "examples": [
            ('baseline_errors_total{operation="discover",error_type="database"}', 2),
            (
                'baseline_errors_total{operation="validate",error_type="invalid_data"}',
                1,
            ),
        ],
    },
    "baseline_metrics_loaded": {
        "type": "gauge",
        "description": "Number of metrics currently loaded in memory",
        "labels": ["system"],
        "unit": "metrics",
        "examples": [
            ('baseline_metrics_loaded{system="postgres"}', 45),
            ('baseline_metrics_loaded{system="mysql"}', 28),
            ('baseline_metrics_loaded{system="redis"}', 12),
        ],
    },
    "baseline_quality_score": {
        "type": "gauge",
        "description": "Average quality score of loaded baselines",
        "labels": ["system"],
        "unit": "score (0-1)",
        "examples": [
            ('baseline_quality_score{system="postgres"}', 0.92),
            ('baseline_quality_score{system="mysql"}', 0.87),
        ],
    },
    "baseline_freshness_days": {
        "type": "gauge",
        "description": "Age of baseline metrics in days",
        "labels": ["system", "metric"],
        "unit": "days",
        "examples": [
            ('baseline_freshness_days{system="postgres",metric="pg_backends"}', 1.5),
            ('baseline_freshness_days{system="postgres",metric="pg_commits"}', 3.2),
        ],
    },
}


# ============================================================================
# PROMQL QUERIES
# ============================================================================

PROMQL_QUERIES = {
    "Discovery Rate": {
        "query": 'rate(baseline_discovery_total{status="success"}[5m])',
        "description": "Number of successful discoveries per second",
    },
    "Success Rate": {
        "query": 'baseline_discovery_total{status="success"} / (baseline_discovery_total{status="success"} + baseline_discovery_total{status="failure"})',
        "description": "Percentage of successful discoveries",
    },
    "Validation Duration (p95)": {
        "query": "histogram_quantile(0.95, baseline_validation_duration_seconds_bucket)",
        "description": "95th percentile validation duration",
    },
    "Error Rate": {
        "query": "rate(baseline_errors_total[5m])",
        "description": "Errors per second",
    },
    "Metrics Loaded": {
        "query": "baseline_metrics_loaded",
        "description": "Currently loaded metrics per system",
    },
    "Quality Score": {
        "query": "baseline_quality_score",
        "description": "Average quality of baselines",
    },
}


# ============================================================================
# METRIC GENERATOR
# ============================================================================


class MetricsGenerator:
    """Generate sample Prometheus metrics."""

    @staticmethod
    def generate_prometheus_format() -> str:
        """Generate metrics in Prometheus text format."""
        lines = []
        timestamp = int(time.time() * 1000)

        # Add HELP and TYPE for each metric
        for metric_name, metric_def in BASELINE_METRICS.items():
            lines.append(f"# HELP {metric_name} {metric_def['description']}")
            lines.append(f"# TYPE {metric_name} {metric_def['type']}")

            # Add example values
            for example_metric, value in metric_def.get("examples", []):
                lines.append(f"{example_metric} {value} {timestamp}")

            lines.append("")  # Blank line between metrics

        return "\n".join(lines)

    @staticmethod
    def generate_json_format() -> dict:
        """Generate metrics in JSON format."""
        metrics = []

        for metric_name, metric_def in BASELINE_METRICS.items():
            metric_obj = {
                "name": metric_name,
                "type": metric_def["type"],
                "description": metric_def["description"],
                "unit": metric_def.get("unit", ""),
                "labels": metric_def.get("labels", []),
                "values": [],
            }

            # Add example values
            for example_metric, value in metric_def.get("examples", []):
                metric_obj["values"].append(
                    {
                        "metric": example_metric,
                        "value": value,
                        "timestamp": datetime.utcnow().isoformat(),
                    }
                )

            metrics.append(metric_obj)

        return {
            "timestamp": datetime.utcnow().isoformat(),
            "metrics": metrics,
            "promql_queries": PROMQL_QUERIES,
        }


# ============================================================================
# CSV EXPORT
# ============================================================================


def generate_csv_definitions(output_file: str):
    """Generate CSV with metric definitions."""
    with open(output_file, "w", newline="") as f:
        writer = csv.writer(f)

        # Header
        writer.writerow(
            [
                "Metric Name",
                "Type",
                "Description",
                "Unit",
                "Labels",
                "Example Query",
                "Example Value",
            ]
        )

        # Rows
        for metric_name, metric_def in BASELINE_METRICS.items():
            first_example = metric_def.get("examples", [("", "")])[0]

            writer.writerow(
                [
                    metric_name,
                    metric_def["type"],
                    metric_def["description"],
                    metric_def.get("unit", ""),
                    ", ".join(metric_def.get("labels", [])),
                    first_example[0],
                    first_example[1],
                ]
            )


def generate_csv_promql(output_file: str):
    """Generate CSV with PromQL queries."""
    with open(output_file, "w", newline="") as f:
        writer = csv.writer(f)

        # Header
        writer.writerow(["Query Name", "PromQL", "Description", "Expected Output"])

        # Rows
        for query_name, query_def in PROMQL_QUERIES.items():
            writer.writerow(
                [
                    query_name,
                    query_def["query"],
                    query_def["description"],
                    "Numeric value or time series",
                ]
            )


# ============================================================================
# MARKDOWN DOCUMENTATION
# ============================================================================


def generate_markdown_docs(output_file: str):
    """Generate Markdown documentation of metrics and queries."""
    with open(output_file, "w") as f:
        f.write("""# Baseline Metrics Prometheus Validation

## Overview

Baseline metrics are exposed via Prometheus for monitoring and alerting.

## Metrics

""")

        for metric_name, metric_def in BASELINE_METRICS.items():
            f.write(f"### {metric_name}\n\n")
            f.write(f"**Type:** {metric_def['type']}\n\n")
            f.write(f"**Description:** {metric_def['description']}\n\n")
            f.write(f"**Unit:** {metric_def.get('unit', 'N/A')}\n\n")
            f.write(
                f"**Labels:** {', '.join(metric_def.get('labels', ['(none)']))}\n\n"
            )

            f.write("**Example Values:**\n\n")
            for example_metric, value in metric_def.get("examples", []):
                f.write(f"```\n{example_metric} {value}\n```\n\n")

        # PromQL Queries Section
        f.write("## PromQL Queries\n\n")

        for query_name, query_def in PROMQL_QUERIES.items():
            f.write(f"### {query_name}\n\n")
            f.write(f"**Description:** {query_def['description']}\n\n")
            f.write(f"**Query:**\n\n```promql\n{query_def['query']}\n```\n\n")

        # Verification Steps
        f.write("## Verification Steps\n\n")
        f.write("""
1. **Check Prometheus Endpoint**
   ```bash
   curl http://localhost:9090/api/v1/query?query=baseline_discovery_total
   ```

2. **Query a Metric**
   ```bash
   curl 'http://localhost:9090/api/v1/query?query=rate(baseline_discovery_total[5m])'
   ```

3. **View in Grafana**
   - Open http://localhost:3000
   - Add a panel with Prometheus data source
   - Use any of the PromQL queries above

4. **Check Metric Availability**
   ```bash
   curl http://localhost:9090/api/v1/label/__name__/values | grep baseline
   ```

## Custom Metrics (MetricsCore)

The `MetricsCore` class provides `record_custom_metric()` for application-specific metrics:

```python
from chaostooling_otel.metrics_core import MetricsCore

metrics = MetricsCore()
metrics.record_custom_metric(
    name='baseline_custom_operation',
    value=42,
    unit='operations',
    attributes={'system': 'postgres'}
)
```

## Troubleshooting

### No Metrics Appearing
- Verify Prometheus is running: `curl http://localhost:9090/-/healthy`
- Check application is exporting metrics: `curl http://localhost:8000/metrics`
- Verify scrape config includes baseline metrics job

### High Cardinality Issues
- Limit label combinations: avoid unbounded label values
- Use baseline_metrics_loaded gauge instead of per-metric labels when possible

### Query Performance
- Use aggregation operators: `sum()`, `avg()`, `rate()`
- Avoid high-resolution queries over long time ranges
- Use recording rules for complex queries
""")


# ============================================================================
# MAIN
# ============================================================================


def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Generate baseline metrics documentation"
    )
    parser.add_argument(
        "--format",
        choices=["prometheus", "json", "csv", "markdown", "all"],
        default="prometheus",
        help="Output format",
    )
    parser.add_argument(
        "--output",
        type=str,
        default="baseline_metrics",
        help="Output file prefix (without extension)",
    )

    args = parser.parse_args()

    print("Generating baseline metrics documentation...")

    if args.format in ["prometheus", "all"]:
        output_file = f"{args.output}_prometheus.txt"
        with open(output_file, "w") as f:
            f.write(MetricsGenerator.generate_prometheus_format())
        print(f"  ✓ Prometheus format: {output_file}")

    if args.format in ["json", "all"]:
        output_file = f"{args.output}_metrics.json"
        with open(output_file, "w") as f:
            json.dump(MetricsGenerator.generate_json_format(), f, indent=2)
        print(f"  ✓ JSON format: {output_file}")

    if args.format in ["csv", "all"]:
        defs_file = f"{args.output}_definitions.csv"
        queries_file = f"{args.output}_promql.csv"
        generate_csv_definitions(defs_file)
        generate_csv_promql(queries_file)
        print(f"  ✓ CSV definitions: {defs_file}")
        print(f"  ✓ CSV PromQL: {queries_file}")

    if args.format in ["markdown", "all"]:
        output_file = f"{args.output}_validation.md"
        generate_markdown_docs(output_file)
        print(f"  ✓ Markdown docs: {output_file}")

    print("\nMetrics documentation generated successfully!")

    if args.format in ["prometheus", "all"]:
        print("\nPrometheus metrics can be exposed via:")
        print("  - prometheus_client library")
        print("  - OTEL Prometheus exporter")
        print("  - Custom metrics endpoint")


if __name__ == "__main__":
    main()
