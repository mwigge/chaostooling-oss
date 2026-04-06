# ChaosTooling Reporting

**Reporting, Analytics, and Compliance Extension**

Generate professional experiment reports, analyze results, compare against baselines, and track compliance metrics (SOX, GDPR, PCI-DSS, HIPAA). Fully integrated with chaos_platform database.

[![Python Version](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/downloads/)
[![Chaos Toolkit](https://img.shields.io/badge/chaos--toolkit-compatible-green.svg)](https://chaostoolkit.org/)
[![PDF Support](https://img.shields.io/badge/PDF-generation-blue.svg)](https://weasyprint.org/)

---

## Overview

ChaosTooling Reporting provides comprehensive post-experiment analysis and report generation. Automatically:

- **Generate Reports** - PDF, HTML, JSON formats
- **Baseline Comparison** - Compare experiment results against baseline metrics
- **Anomaly Detection** - Identify unexpected behavior
- **Trend Analysis** - Track performance changes over time
- **Compliance Reports** - SOX, GDPR, PCI-DSS, HIPAA audit trails
- **Metrics Analysis** - Statistical analysis with standard deviation, percentiles
- **Risk Scoring** - Calculate experiment impact and risk

### Key Features

✅ **Multi-Format Reports** - PDF (visual), HTML (interactive), JSON (programmatic)
✅ **Baseline Comparison** - Sigma-based anomaly detection
✅ **Compliance Tracking** - Built-in audit trails for regulations
✅ **Trend Analysis** - Track metrics over multiple experiments
✅ **Database Integration** - Direct access to chaos_platform results
✅ **Customizable Templates** - Jinja2-based report generation
✅ **Batch Processing** - Generate reports for multiple experiments
✅ **Statistics** - Mean, stdev, percentiles, min/max, anomalies

---

## Installation

### Prerequisites

- Python 3.10+
- Chaos Toolkit 1.42.1+
- PostgreSQL with chaos_platform database
- WeasyPrint for PDF generation

### Install Package

```bash
pip install chaostooling-reporting
```

### Install from Source

```bash
cd chaostooling-reporting
pip install -e .
```

---

## Quick Start

### 1. Generate Report from Experiment Run

```python
from chaostooling_reporting import generate_report
from chaostooling_reporting.generators import PDFReportGenerator

# Generate PDF report for latest experiment
report = generate_report(
    format="pdf",
    run_id="run_1847291234",
    include_baseline_comparison=True,
    include_compliance=True,
    compliance_frameworks=["SOX", "GDPR"]
)

print(f"Report generated: {report.filename}")
```

### 2. Generate via Chaos Toolkit Control

Add reporting control to experiment.json:

```json
{
  "controls": [
    {
      "name": "reporting",
      "provider": {
        "type": "python",
        "module": "chaostooling_reporting.control.reporting_control",
        "arguments": {
          "report_format": "pdf",
          "include_baseline_comparison": true,
          "include_compliance": true
        }
      }
    }
  ]
}
```

### 3. Run Experiment

```bash
export CHAOS_DB_HOST=localhost
export CHAOS_DB_PORT=5432
export CHAOS_DB_NAME=chaos_platform
export CHAOS_DB_USER=chaos_admin
export CHAOS_DB_PASSWORD=changeme

chaos run experiment.json
```

Report automatically generated and saved!

---

## Report Generation

### PDF Reports

Generate professional PDF reports with charts and statistics:

```python
from chaostooling_reporting import PDFReportGenerator

generator = PDFReportGenerator(
    run_id="run_1847291234",
    title="PostgreSQL Connection Pool Test",
    include_charts=True,
    include_baseline_comparison=True
)

pdf_file = generator.generate()
print(f"PDF saved to: {pdf_file}")
```

**PDF Report Contents:**
- Executive summary
- Experiment objectives and timeline
- Baseline metrics comparison (pre/during/post)
- Collected metrics with charts
- Anomalies detected
- Risk assessment
- Compliance audit trail (if enabled)
- Recommendations

### HTML Reports

Interactive HTML reports with sortable tables:

```python
from chaostooling_reporting import HTMLReportGenerator

generator = HTMLReportGenerator(
    run_id="run_1847291234",
    include_interactive_charts=True,
    theme="dark"
)

html_file = generator.generate()
print(f"HTML saved to: {html_file}")
```

### JSON Reports

Programmatic access to experiment results:

```python
from chaostooling_reporting import JSONReportGenerator

generator = JSONReportGenerator(run_id="run_1847291234")
report_data = generator.generate()

# Access structured data
print(f"Status: {report_data['status']}")
print(f"Duration: {report_data['duration_seconds']}")
print(f"Metrics: {report_data['metrics']}")
```

---

## Baseline Comparison

### Automatic Baseline Detection

```python
from chaostooling_reporting import analyze_against_baseline

analysis = analyze_against_baseline(
    run_id="run_1847291234",
    sigma_threshold=2.0  # 2-sigma = 95% normal variation
)

for metric_name, analysis in analysis.metrics.items():
    print(f"{metric_name}:")
    print(f"  Baseline mean: {analysis.baseline_mean}")
    print(f"  Baseline stdev: {analysis.baseline_stdev}")
    print(f"  Observed value: {analysis.observed_value}")
    print(f"  Sigma deviation: {analysis.sigma_deviation}")
    print(f"  Is anomaly: {analysis.is_anomaly}")
```

### Custom Thresholds

```python
analysis = analyze_against_baseline(
    run_id="run_1847291234",
    custom_thresholds={
        "postgresql_commits_total": {"min": 40, "max": 50},
        "db_query_latency_ms": {"max": 1000}
    }
)
```

---

## Compliance Reporting

### Generate Compliance Reports

```python
from chaostooling_reporting import generate_compliance_report

report = generate_compliance_report(
    run_id="run_1847291234",
    frameworks=["SOX", "GDPR", "PCI-DSS", "HIPAA"],
    period_start="2026-01-01",
    period_end="2026-01-31"
)

print(f"Compliance report: {report.filename}")
```

### Supported Frameworks

| Framework | Features |
|-----------|----------|
| **SOX** | Change audit trail, approval tracking, segregation of duties |
| **GDPR** | Data processing records, consent tracking, breach notifications |
| **PCI-DSS** | Vulnerability scanning, change control, access logs |
| **HIPAA** | Audit trails, access controls, encryption verification |

### Sample Compliance Output

```json
{
  "framework": "SOX",
  "period": "2026-01",
  "controls_tested": [
    {
      "name": "Change Control",
      "status": "PASS",
      "evidence": "Experiment tracked with experiment_id, approval recorded"
    },
    {
      "name": "Access Logs",
      "status": "PASS",
      "evidence": "All actions logged in audit_log table"
    }
  ],
  "compliance_score": 0.95,
  "recommendations": ["Enable encryption for results database"]
}
```

---

## Trend Analysis

### Track Metrics Over Time

```python
from chaostooling_reporting import analyze_trends

trends = analyze_trends(
    experiment_name="postgres-pool-exhaustion",
    metric_names=["postgresql_backends", "chaos_db_query_latency_ms"],
    days=7
)

for metric_name, trend in trends.items():
    print(f"{metric_name}:")
    print(f"  Latest: {trend.latest_value}")
    print(f"  Average: {trend.average_value}")
    print(f"  Trend: {trend.trend_direction}  ({trend.percent_change}%)")
```

### Generate Trend Report

```python
from chaostooling_reporting import TrendReportGenerator

generator = TrendReportGenerator(
    experiment_name="postgres-pool-exhaustion",
    lookback_days=30,
    output_format="pdf"
)

report = generator.generate()
print(f"Trend report: {report}")
```

---

## Anomaly Detection

### Automatic Anomaly Detection

```python
from chaostooling_reporting import detect_anomalies

anomalies = detect_anomalies(
    run_id="run_1847291234",
    sensitivity="medium"  # low, medium, high
)

for anomaly in anomalies:
    print(f"Anomaly: {anomaly.metric_name}")
    print(f"  Expected: {anomaly.expected_range}")
    print(f"  Actual: {anomaly.actual_value}")
    print(f"  Severity: {anomaly.severity}")
```

### Severity Levels

- **Low** - 1-2 sigma deviation
- **Medium** - 2-3 sigma deviation  
- **High** - >3 sigma deviation

---

## Configuration

### Environment Variables

```bash
# Database Connection
CHAOS_DB_HOST=localhost
CHAOS_DB_PORT=5432
CHAOS_DB_NAME=chaos_platform
CHAOS_DB_USER=chaos_admin
CHAOS_DB_PASSWORD=password

# Report Generation
REPORT_OUTPUT_DIR=./reports
REPORT_FORMATS=pdf,html,json
REPORT_INCLUDE_CHARTS=true
REPORT_INCLUDE_COMPLIANCE=true
REPORT_COMPLIANCE_FRAMEWORKS=SOX,GDPR,PCI-DSS

# PDF Generation
WEASYPRINT_DPI=300
WEASYPRINT_PAGE_SIZE=A4

# Email Delivery (optional)
REPORT_EMAIL_ENABLED=false
REPORT_EMAIL_TO=team@example.com
REPORT_EMAIL_SUBJECT=Chaos Experiment Report
```

### .env.example

```bash
# Database
export CHAOS_DB_HOST=localhost
export CHAOS_DB_PORT=5432
export CHAOS_DB_NAME=chaos_platform
export CHAOS_DB_USER=chaos_admin
export CHAOS_DB_PASSWORD=changeme

# Reporting
export REPORT_OUTPUT_DIR=./reports
export REPORT_FORMATS=pdf,html,json
export REPORT_INCLUDE_CHARTS=true
export REPORT_INCLUDE_COMPLIANCE=true
export REPORT_COMPLIANCE_FRAMEWORKS=SOX,GDPR

# PDF Quality
export WEASYPRINT_DPI=300
export WEASYPRINT_PAGE_SIZE=A4
```

---

## Examples

### Example 1: Generate PDF Report

```python
from chaostooling_reporting import PDFReportGenerator

generator = PDFReportGenerator(
    run_id="run_1847291234",
    title="PostgreSQL Connection Pool Exhaustion",
    include_baseline_comparison=True,
    include_charts=True,
    include_metrics_table=True
)

pdf_file = generator.generate()
print(f"Report generated: {pdf_file}")
```

### Example 2: Batch Report Generation

```python
from chaostooling_reporting import batch_generate_reports
import pandas as pd

# Get all runs from this week
runs = pd.read_sql("""
    SELECT run_id, experiment_id, created_at
    FROM experiment_runs
    WHERE created_at > NOW() - INTERVAL '7 days'
""", db_connection)

# Generate PDF report for each
for run in runs:
    generate_report(
        format="pdf",
        run_id=run['run_id'],
        output_file=f"reports/{run['run_id']}_report.pdf"
    )
    print(f"Generated report for {run['run_id']}")
```

### Example 3: Compliance Report

```python
from chaostooling_reporting import generate_compliance_report

# Generate month-end compliance report
report = generate_compliance_report(
    frameworks=["SOX", "GDPR", "PCI-DSS"],
    period_start="2026-01-01",
    period_end="2026-01-31",
    output_format="pdf",
    archive=True
)

print(f"Compliance report: {report.filename}")
```

### Example 4: Trend Analysis Report

```python
from chaostooling_reporting import TrendReportGenerator

# Weekly trend analysis
generator = TrendReportGenerator(
    experiment_names=["postgres-pool-exhaustion", "mysql-slow-query"],
    lookback_days=7,
    output_format="html",
    include_forecasts=True
)

report = generator.generate()
```

---

## API Reference

### PDFReportGenerator

```python
PDFReportGenerator(
    run_id: str,
    title: str = None,
    include_baseline_comparison: bool = True,
    include_charts: bool = True,
    include_metrics_table: bool = True,
    include_compliance: bool = False,
    compliance_frameworks: List[str] = None,
    output_dir: str = "./reports",
    dpi: int = 300,
    page_size: str = "A4"
)
```

### HTMLReportGenerator

```python
HTMLReportGenerator(
    run_id: str,
    include_interactive_charts: bool = True,
    include_baseline_comparison: bool = True,
    theme: str = "light",  # light, dark
    output_dir: str = "./reports"
)
```

### analyze_against_baseline()

```python
analyze_against_baseline(
    run_id: str,
    sigma_threshold: float = 2.0,
    custom_thresholds: dict = None,
    metric_names: List[str] = None
) -> BaselineAnalysis
```

---

## Troubleshooting

### "Database connection failed"

**Problem:** Cannot connect to chaos_platform database

**Solution:**
```bash
# Check environment variables
echo $CHAOS_DB_HOST $CHAOS_DB_PORT $CHAOS_DB_NAME

# Test connection
psql -h $CHAOS_DB_HOST -U $CHAOS_DB_USER -d $CHAOS_DB_NAME -c "SELECT 1"
```

### "No data found for run_id"

**Problem:** Experiment run not in database

**Solution:**
```bash
# Check available runs
psql -U chaos_admin -d chaos_platform -c \
  "SELECT run_id, experiment_id FROM experiment_runs LIMIT 10;"

# Verify database-storage control was enabled in experiment
grep "database-storage" experiment.json
```

### "PDF generation failed"

**Problem:** WeasyPrint cannot generate PDF

**Solution:**
```bash
# Reinstall WeasyPrint with all dependencies
pip install --upgrade weasyprint

# On Ubuntu/Debian, ensure system libraries are installed
sudo apt-get install libffi-dev libcairo2-dev libpango-1.0-0 libpango-cairo-1.0-0
```

### "Charts not appearing in PDF"

**Problem:** Matplotlib/chart generation failed

**Solution:**
```bash
# Enable debug logging
export REPORT_DEBUG=true
python -c "from chaostooling_reporting import generate_report; generate_report(...)"

# Check chart data exists in database
psql -U chaos_admin -d chaos_platform -c \
  "SELECT COUNT(*) FROM metric_snapshots WHERE run_id='your_run_id';"
```

---

## Advanced Usage

### Custom Report Templates

Create custom Jinja2 template:

```jinja2
# reports/custom_template.html
<!DOCTYPE html>
<html>
<head>
    <title>{{ experiment_title }}</title>
</head>
<body>
    <h1>{{ experiment_title }}</h1>
    <p>Duration: {{ duration_seconds }} seconds</p>
    
    <h2>Metrics</h2>
    <table>
    {% for metric in metrics %}
        <tr>
            <td>{{ metric.name }}</td>
            <td>{{ metric.value }}</td>
        </tr>
    {% endfor %}
    </table>
</body>
</html>
```

Use custom template:

```python
from chaostooling_reporting import HTMLReportGenerator

generator = HTMLReportGenerator(
    run_id="run_123",
    template_path="reports/custom_template.html"
)
```

### Email Delivery

```python
from chaostooling_reporting import generate_report

report = generate_report(
    format="pdf",
    run_id="run_123",
    email_to="team@example.com",
    email_subject="Experiment Results Available"
)
```

---

## See Also

- [Main README](../README.md) - Project overview
- [chaostooling-generic](../chaostooling-generic/README.md) - Database controls
- [chaostooling-otel](../chaostooling-otel/README.md) - Observability

---

**Last Updated:** January 30, 2026  
**Version:** 0.1.0  
**Status:** Production Ready
