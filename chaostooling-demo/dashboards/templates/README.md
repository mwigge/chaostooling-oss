# Dashboard Templates

This directory contains reusable dashboard templates for chaos experiments. These templates provide standardized panels that should appear in all chaos experiment dashboards.

## Available Templates

### 1. `experiment-overview-template.json`

**Purpose**: Provides a consistent header section for all chaos experiment dashboards, including service graph visibility and key experiment metrics.

**Contains**:
- **Service Graph Panel** (Tempo): Shows distributed tracing service graph with all connected services
- **Experiment Overview & Status Row**: Header section for experiment metrics
- **Experiment Status Gauge**: Success (green) / Failed (red) indicator
- **Risk Level Gauge**: 1-4 scale (Low/Medium/High/Critical)
- **Risk Score Gauge**: 0-100 scale with color thresholds
- **Complexity Score Gauge**: 0-100 scale indicating experiment complexity
- **Experiment Duration Stat**: Total experiment runtime in seconds
- **Experiment Logs Panel** (Loki): Recent experiment log entries

**Panel IDs Used**: 999-106 (reserved for template)

**Grid Layout**:
```
Row 0: Service Graph (full width, 18h)
Row 1: Experiment Overview & Status (row header, 1h)
Row 2: Status | Risk Level | Risk Score | Complexity | Duration | Logs (6h each)
```

## Usage

### Option 1: Python Script (Recommended)

Use the provided Python script to merge templates with your dashboard:

```python
import json

def add_experiment_overview(dashboard_file):
    """Add experiment overview template to existing dashboard."""

    # Load template
    with open('templates/experiment-overview-template.json', 'r') as f:
        template = json.load(f)

    # Load your dashboard
    with open(dashboard_file, 'r') as f:
        dashboard = json.load(f)

    # Insert template panels at the beginning
    template_panels = template['panels']
    existing_panels = dashboard.get('panels', [])

    # Adjust Y positions of existing panels to make room
    y_offset = 25  # Service graph (18h) + Overview row (1h) + Status panels (6h)
    for panel in existing_panels:
        if 'gridPos' in panel:
            panel['gridPos']['y'] += y_offset

    # Combine panels
    dashboard['panels'] = template_panels + existing_panels

    # Save updated dashboard
    with open(dashboard_file, 'w') as f:
        json.dump(dashboard, f, indent=2)

    print(f"✅ Added experiment overview to {dashboard_file}")

# Usage
add_experiment_overview('my-chaos-dashboard.json')
```

### Option 2: Manual Copy-Paste

1. Open `experiment-overview-template.json`
2. Copy the entire `panels` array
3. Open your target dashboard JSON
4. **Adjust Y positions**: Add 25 to the `y` value in `gridPos` for all existing panels
5. Insert the template panels at the beginning of your dashboard's `panels` array
6. Save the dashboard

### Option 3: Grafana UI Import

1. Create a new dashboard in Grafana
2. Import the template as panels
3. Add your custom panels below (starting at y=25)
4. Export the combined dashboard

## Panel Details

### Service Graph (ID: 999)
- **Type**: nodeGraph
- **Data Source**: Tempo
- **Query**: serviceMap (automatic)
- **Position**: Top of dashboard (y=0)
- **Purpose**: Visualize distributed tracing service graph showing all services involved in the experiment

**What you'll see**:
- `chaostoolkit-demo` (main service running experiments)
- Database nodes (e.g., `postgres-primary-site-a`, `mysql`, `redis`)
- Application services (e.g., `app-server-1-site-a`)
- Messaging systems (e.g., `kafka`, `rabbitmq`, `activemq`)
- Connection lines showing service interactions

### Experiment Status (ID: 101)
- **Type**: gauge
- **Metric**: `chaos_experiment_success_ratio`
- **Range**: 0-1 (0 = Failed, 1 = Success)
- **Colors**: Red (failed) / Green (success)

### Risk Level (ID: 102)
- **Type**: gauge
- **Metric**: `chaos_experiment_risk_level_ratio`
- **Range**: 1-4
- **Mapping**:
  - 1 = Low (green)
  - 2 = Medium (yellow)
  - 3 = High (orange)
  - 4 = Critical (red)
- **Calculated from**: Severity, blast radius, production flag, rollback availability

### Risk Score (ID: 103)
- **Type**: gauge
- **Metric**: `chaos_experiment_risk_score_ratio`
- **Range**: 0-100
- **Thresholds**:
  - 0-20: Green (low risk)
  - 20-40: Yellow (moderate risk)
  - 40-60: Orange (high risk)
  - 60+: Red (critical risk)

### Complexity Score (ID: 104)
- **Type**: gauge
- **Metric**: `chaos_experiment_complexity_score_ratio`
- **Range**: 0-100
- **Thresholds**:
  - 0-30: Green (simple)
  - 30-60: Yellow (moderate)
  - 60-80: Orange (complex)
  - 80+: Red (very complex)
- **Factors**: Number of steps, probes, rollbacks, duration, target types

### Experiment Duration (ID: 105)
- **Type**: stat
- **Metric**: `chaos_experiment_duration_seconds_sum`
- **Unit**: seconds
- **Display**: Shows total experiment runtime

### Experiment Logs (ID: 106)
- **Type**: logs
- **Data Source**: Loki
- **Query**: `{service_name=~".+"} |= "experiment"`
- **Display**: Recent log entries related to experiment execution

## Metrics Reference

All metrics are exported by `chaosotel` (chaostooling-otel) during experiment execution:

| Metric | Type | Description |
|--------|------|-------------|
| `chaos_experiment_success_ratio` | Gauge | Experiment success (1.0) or failure (0.0) |
| `chaos_experiment_risk_level_ratio` | Gauge | Risk level (1-4): Low, Medium, High, Critical |
| `chaos_experiment_risk_score_ratio` | Gauge | Risk score (0-100) based on multiple factors |
| `chaos_experiment_complexity_score_ratio` | Gauge | Complexity score (0-100) |
| `chaos_experiment_duration_seconds` | Histogram | Experiment duration distribution |
| `chaos_experiment_start_total` | Counter | Total experiments started |
| `chaos_experiment_end_total` | Counter | Total experiments completed |

## Customization

### Changing Panel Order

To move experiment overview panels to a different position:

1. Adjust the `gridPos.y` values for template panels
2. Ensure no overlap with other panels
3. Update the row header position accordingly

### Adding Custom Panels

Add your custom panels after the template panels (starting at y=25):

```json
{
  "panels": [
    ...template panels (y=0 to y=24)...,
    {
      "id": 200,
      "title": "My Custom Panel",
      "gridPos": {
        "h": 8,
        "w": 12,
        "x": 0,
        "y": 25  // Start below template
      },
      ...
    }
  ]
}
```

### Adjusting Service Graph Height

To change service graph height:

1. Modify `gridPos.h` in panel ID 999
2. Update y_offset calculations in documentation/scripts
3. Adjust subsequent panel positions

## Best Practices

1. **Always include template**: Every chaos experiment dashboard should start with this template
2. **Preserve panel IDs**: Use IDs 999-106 for template panels, start custom panels at 200+
3. **Consistent positioning**: Keep template at the top for visual consistency
4. **Grid alignment**: Use 24-column grid width, align panels to grid
5. **Y-offset**: Leave 25 units of vertical space for template panels

## Example Dashboards

See these dashboards for reference implementations:

- `e2e-comprehensive-experiment-dashboard.json` (full template usage)
- `extensive_postgres_dashboard.json` (with risk/complexity panels)
- `distributed_showcase_dashboard.json` (service graph emphasis)

## Troubleshooting

### Service Graph is Empty

**Symptoms**: Service graph panel shows no nodes or connections

**Causes**:
1. No traces in Tempo (experiment hasn't run yet)
2. Traces not exported (check OTEL configuration)
3. Database/services missing `peer.service` attributes

**Fix**:
- Verify traces exist: `curl http://localhost:3200/api/search`
- Check OTEL endpoint: `OTEL_EXPORTER_OTLP_ENDPOINT`
- Ensure probes use `set_db_span_attributes()` helper

### Metrics Show "No Data"

**Symptoms**: Gauges show N/A or no values

**Causes**:
1. Experiment hasn't run yet
2. Metrics not exported to Prometheus
3. Wrong metric names in queries

**Fix**:
- Check Prometheus: `curl http://localhost:9090/api/v1/label/__name__/values`
- Verify metric names match template
- Ensure `chaosotel.control` is configured in experiment

### Logs Panel is Empty

**Symptoms**: Logs panel shows no log entries

**Causes**:
1. Logs not sent to Loki
2. Wrong label selector
3. Time range issue

**Fix**:
- Check Loki: `curl http://localhost:3100/loki/api/v1/query?query={service_name=~".+"}`
- Adjust query label selectors
- Extend time range (now-1h to now)

## Template Versioning

- **Version**: 1.0.0
- **Last Updated**: 2026-01-21
- **Compatible Grafana**: 10.x, 11.x, 12.x
- **Required Data Sources**: Tempo, Prometheus, Loki

## Future Enhancements

Planned additions to the template:

- [ ] Experiment timeline panel (Gantt chart of activities)
- [ ] Blast radius visualization
- [ ] Compliance status indicators (SOX, GDPR, PCI-DSS)
- [ ] MTTR/MTTD metrics
- [ ] Service dependency graph (separate from service graph)
- [ ] Scenario success/failure breakdown
