# Quick Start: Dashboard Templates

## What This Is

A **reusable template** for chaos experiment dashboards that includes:

1. ✅ **Service Graph** - See all connected services (databases, messaging, apps)
2. ✅ **Experiment Status** - Success/Failure indicator
3. ✅ **Risk Level** - 1-4 scale (Low/Medium/High/Critical)
4. ✅ **Risk Score** - 0-100 numerical risk score
5. ✅ **Complexity Score** - 0-100 experiment complexity
6. ✅ **Duration** - Total experiment runtime
7. ✅ **Logs** - Recent experiment log entries

## Why Use This Template?

- **Consistency**: All dashboards have the same header section
- **Visibility**: Service graph shows database/messaging nodes automatically
- **Monitoring**: Risk and complexity metrics in every dashboard
- **Time-saving**: No need to recreate these panels manually

## Quick Usage

### Apply to Existing Dashboard

```bash
cd chaostooling-demo/dashboards/templates
python3 apply_template.py ../extensive_postgres_dashboard.json
```

That's it! Your dashboard now has the standard experiment overview section.

### Preview Before Applying

```bash
python3 apply_template.py ../my_dashboard.json --dry-run
```

### Save to New File

```bash
python3 apply_template.py ../my_dashboard.json --output ../my_dashboard_v2.json
```

### Batch Apply to Multiple Dashboards

```bash
for f in ../postgres*.json; do
    python3 apply_template.py "$f"
done
```

## What Happens?

**Before**:
```
┌─────────────────────────────┐
│ Your Custom Panel 1         │
├─────────────────────────────┤
│ Your Custom Panel 2         │
└─────────────────────────────┘
```

**After**:
```
┌─────────────────────────────┐
│ SERVICE GRAPH (Tempo)       │  ← Template
├─────────────────────────────┤
│ EXPERIMENT OVERVIEW ROW     │  ← Template
├─────┬─────┬─────┬─────┬─────┤
│Status│Risk │Score│Cmplx│Logs │  ← Template
├─────────────────────────────┤
│ Your Custom Panel 1         │  ← Your panels (shifted down)
├─────────────────────────────┤
│ Your Custom Panel 2         │
└─────────────────────────────┘
```

## Visual Example

Here's what the template section looks like in Grafana:

```
╔═══════════════════════════════════════════════════════════════════╗
║                        SERVICE GRAPH                              ║
║  ┌──────────┐        ┌──────────────────┐      ┌──────────┐     ║
║  │chaostool-│───────▶│postgres-primary- │─────▶│  redis   │     ║
║  │kit-demo  │        │    site-a        │      │          │     ║
║  └──────────┘        └──────────────────┘      └──────────┘     ║
║                              │                                    ║
║                              ▼                                    ║
║                      ┌──────────────┐                            ║
║                      │ app-server-1 │                            ║
║                      └──────────────┘                            ║
╠═══════════════════════════════════════════════════════════════════╣
║                   EXPERIMENT OVERVIEW & STATUS                    ║
╠═════════════╦═════════════╦══════════════╦═══════════╦═══════════╣
║  SUCCESS    ║    LOW      ║      15      ║    42     ║  [Logs]   ║
║  ✅ 1.0     ║  Risk Level ║  Risk Score  ║ Complexity║  Stream   ║
╚═════════════╩═════════════╩══════════════╩═══════════╩═══════════╝
```

## Metrics Overview

| Panel | Metric | What It Shows |
|-------|--------|---------------|
| Status | `chaos_experiment_success_ratio` | 1 = Success (green), 0 = Failed (red) |
| Risk Level | `chaos_experiment_risk_level_ratio` | 1=Low, 2=Medium, 3=High, 4=Critical |
| Risk Score | `chaos_experiment_risk_score_ratio` | 0-100 numerical risk assessment |
| Complexity | `chaos_experiment_complexity_score_ratio` | 0-100 experiment complexity |
| Duration | `chaos_experiment_duration_seconds_sum` | Total runtime in seconds |

## Files Created

```
chaostooling-demo/dashboards/templates/
├── experiment-overview-template.json  # The template panels
├── apply_template.py                   # Application script
├── README.md                           # Full documentation
└── QUICKSTART.md                       # This file
```

## Troubleshooting

### "Service graph is empty"

**Problem**: No nodes showing in service graph

**Solution**:
1. Run an experiment first to generate traces
2. Check that database probes use `set_db_span_attributes()` helper
3. Verify Tempo is receiving traces: `curl http://localhost:3200/api/search`

### "No data in metrics panels"

**Problem**: Gauges show N/A or no values

**Solution**:
1. Run an experiment to generate metrics
2. Check Prometheus has metrics: `curl http://localhost:9090/api/v1/label/__name__/values | grep chaos_experiment`
3. Verify `chaosotel.control` is configured in experiment

### "Template panels overlap with my panels"

**Problem**: Panels are on top of each other

**Solution**: The script automatically adjusts panel positions. If you see overlap:
1. Check dashboard JSON for duplicate panel IDs
2. Run `apply_template.py` again (it will re-apply cleanly)
3. Manually adjust `gridPos.y` values if needed

## Next Steps

1. ✅ Apply template to your dashboards
2. 📊 Run experiments to populate panels
3. 🔍 Check service graph to see database/service connections
4. 📈 Monitor risk levels and complexity scores
5. 🎨 Customize remaining dashboard panels as needed

## Support

- Full docs: `README.md`
- Template file: `experiment-overview-template.json`
- Script: `apply_template.py --help`

## Example: Complete Workflow

```bash
# 1. Navigate to templates directory
cd chaostooling-demo/dashboards/templates

# 2. Preview what will change
python3 apply_template.py ../postgres_dashboard.json --dry-run

# 3. Apply template
python3 apply_template.py ../postgres_dashboard.json

# 4. Import to Grafana (via UI or API)
curl -X POST http://localhost:3000/api/dashboards/db \
  -H "Content-Type: application/json" \
  -d @../postgres_dashboard.json

# 5. Run chaos experiment
cd ../../../chaostooling-experiments/postgres
chaos run Extensive-postgres-experiment.json

# 6. View dashboard
open http://localhost:3000/d/chaos-postgresql
```

🎉 You're done! Your dashboard now has standardized experiment monitoring.
