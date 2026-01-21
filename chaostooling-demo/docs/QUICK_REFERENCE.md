# Quick Reference Card

## 🎯 Your Questions Answered

### 1. How to make databases emit traces?

**Short Answer**: Deploy OpenTelemetry Collector sidecars

**Quick Setup** (5 minutes per database):
```yaml
# Add to docker-compose.yml
  postgres-otel-sidecar:
    image: otel/opentelemetry-collector-contrib:latest
    command: ["--config=/etc/otel-collector-config.yaml"]
    volumes:
      - ./otel-collectors/postgres-sidecar.yaml:/etc/otel-collector-config.yaml:ro
    environment:
      - POSTGRES_USER=postgres
      - POSTGRES_PASSWORD=postgres
```

**Full Guide**: [DATABASE_INSTRUMENTATION_GUIDE.md](DATABASE_INSTRUMENTATION_GUIDE.md)

### 2. Risk Level & Risk Score Panels

**Status**: ✅ **FIXED** in extensive postgres dashboard

**Changes Made**:
- Risk Level: Now shows 1-4 with labels (Low/Medium/High/Critical)
- Risk Score: Now shows 0-100 numeric (not percentage)
- Matches E2E dashboard exactly

**Verify**: http://localhost:3000/d/extensive-postgres

---

## 📊 Dashboard Panels Explained

| Panel | Metric | Display | Meaning |
|-------|--------|---------|---------|
| **Risk Level** | `chaos_experiment_risk_level_ratio` | 1=Low, 2=Medium, 3=High, 4=Critical | Categorical risk assessment |
| **Risk Score** | `chaos_experiment_risk_score_ratio` | 0-100 numeric | Calculated risk score |
| **Complexity** | `chaos_experiment_complexity_score_ratio` | 0-100 numeric | Experiment complexity |
| **Status** | `chaos_experiment_success_ratio` | 1=Success, 0=Failed | Overall experiment result |

---

## 🔍 Quick Diagnostics

### Check if traces have correct attributes
```bash
curl -s "http://localhost:3200/api/search?tags=db.system%3Dpostgresql" | jq '.traces[0]'
```
**Should see**: `traceID`, `rootServiceName`, etc.

### Check if peer.service is set
```bash
curl -s "http://localhost:9090/api/v1/query?query=traces_span_metrics_calls_total{peer_service=~'.*postgres.*'}"
```
**Should see**: Metrics with `peer_service="postgres-primary-site-a"`

### Check service graph connections
```bash
curl -s 'http://localhost:9090/api/v1/query?query=traces_service_graph_request_total{client="chaostoolkit"}' | jq -r '.data.result[].metric | {client, server}'
```
**Should see**: chaostoolkit → loki, prometheus, tempo

---

## 🚀 Common Tasks

### Apply template to dashboard
```bash
cd chaostooling-demo/dashboards/templates
python3 apply_template.py ../my_dashboard.json
```

### Run experiment
```bash
docker exec chaostooling-demo-chaos-runner-1 bash -c \
  "cd /experiments/postgres && chaos run test-postgres-lock-storm.json"
```

### Check experiment metrics
```bash
curl -s 'http://localhost:9090/api/v1/query?query=chaos_experiment_risk_level_ratio' | jq '.data.result[0].value[1]'
```

### View dashboard
```bash
open http://localhost:3000/d/extensive-postgres
```

---

## ⚠️ Known Limitations

### Databases Don't Appear in Service Graph

**Why**: Service graphs need BOTH client and server spans. Databases don't emit server spans.

**Solutions**:
1. ✅ Use "Database Interactions" table panel (works now)
2. 🔧 Deploy OTEL Collector sidecars (1-2 hours)
3. ⚙️ Instrument databases directly (1-2 weeks)

**Not a Bug**: This is how OpenTelemetry service graphs work by design.

---

## 📚 Documentation Index

| File | Purpose |
|------|---------|
| [DATABASE_INSTRUMENTATION_GUIDE.md](DATABASE_INSTRUMENTATION_GUIDE.md) | How to make DBs emit traces |
| [FINAL_SUMMARY.md](../FINAL_SUMMARY.md) | Complete summary of all work |
| [templates/README.md](dashboards/templates/README.md) | Template system docs |
| [templates/QUICKSTART.md](dashboards/templates/QUICKSTART.md) | Quick template guide |
| [SUMMARY_SERVICE_GRAPH_FIX.md](../SUMMARY_SERVICE_GRAPH_FIX.md) | Technical deep dive |

---

## ✅ Status Check

**What's Working**:
- ✅ Traces export with correct attributes
- ✅ Metrics export (risk, complexity, status)
- ✅ Dashboard panels display correctly
- ✅ Risk Level shows text labels (Low/Medium/High/Critical)
- ✅ Risk Score shows 0-100 numeric values
- ✅ Template system ready to use

**What's Expected Limitation**:
- ⚠️ Traditional service graph won't show databases (by design)

**Recommended Next Step**:
- 🎯 Deploy OTEL Collector sidecars for database visibility

---

## 🆘 Troubleshooting

### Dashboard shows "No Data"
```bash
# Check Prometheus has metrics
curl http://localhost:9090/api/v1/label/__name__/values | grep chaos_experiment

# Run an experiment to generate metrics
docker exec chaostooling-demo-chaos-runner-1 bash -c "chaos run /experiments/postgres/test-postgres-lock-storm.json"
```

### Risk panels show percentage instead of values
- File: `extensive_postgres_dashboard.json`
- Check: Lines 310-428
- Should be: `unit: "short"` (not `percentunit`)
- Should have: `mappings` array with value→text mappings

### Database not in traces
```bash
# Check if postgres_system_metrics.py was updated
grep -A 10 "set_db_span_attributes" chaostooling-extension-db/chaosdb/probes/postgres/postgres_system_metrics.py

# Should see: Lines 88-103 with set_db_span_attributes() call
```

---

## 📞 Quick Contacts

**Documentation**:
- Full guide: [FINAL_SUMMARY.md](../FINAL_SUMMARY.md)
- Database setup: [DATABASE_INSTRUMENTATION_GUIDE.md](DATABASE_INSTRUMENTATION_GUIDE.md)

**Key Files**:
- Dashboard: `chaostooling-demo/dashboards/extensive_postgres_dashboard.json`
- Template: `chaostooling-demo/dashboards/templates/experiment-overview-template.json`
- DB Probe: `chaostooling-extension-db/chaosdb/probes/postgres/postgres_system_metrics.py`

**Dashboards**:
- Extensive Postgres: http://localhost:3000/d/extensive-postgres
- E2E Comprehensive: http://localhost:3000/d/e2e-comprehensive-experiment
- Prometheus: http://localhost:9090
- Tempo: http://localhost:3200

---

*Quick Reference v1.0 - 2026-01-21*
