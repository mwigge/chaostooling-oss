# Dashboarding & Reporting Implementation Plan

## Overview

This plan addresses the creation of a cohesive dashboarding and reporting system for the chaostooling-oss project, including a quality remediation of existing metrics issues.

**Priority Order:**
1. Unified Experiment Results Dashboard
2. Experiment Comparison Views
3. Per-Experiment Dashboard Generation
4. Enhanced Reporting Integration
5. Metrics Quality Fixes (prerequisite for all above)

---

## Phase 0: Metrics Quality Fixes (PREREQUISITE)

### Critical Issues Found

**Issue 1: Double "chaos_chaos_" Prefix in Dashboard Queries**

54 broken PromQL queries found across 5 dashboard files:
- `e2e_dashboard.json` (26 instances)
- `e2e_experiment_dashboard.json` (26 instances)
- `distributed_showcase_dashboard.json` (7 instances)
- `extensive_postgres_dashboard.json` (4 instances)
- `e2e_test_dashboard.json` (4 instances)

Examples of broken queries:
```promql
# BROKEN (current)
chaos_chaos_experiment_success_ratio
chaos_chaos_db_query_count_total
chaos_chaos_messaging_operation_count_total

# CORRECT (should be)
chaos_experiment_success_ratio
chaos_db_query_count_total
chaos_messaging_operation_count_total
```

**Issue 2: Inconsistent Metric Naming in MetricsCore**

In `metrics_core.py`, generic methods use non-standard prefixes:
- `record_db_gauge()` creates `db.{name}` instead of `chaos_db_{name}`
- `record_messaging_gauge()` creates `messaging.{name}` instead of `chaos_messaging_{name}`
- `record_compliance_score()` creates `compliance.score` instead of `chaos_compliance_score`

**Issue 3: Missing Experiment-Level Metrics**

Dashboard queries reference metrics that don't exist in MetricsCore:
- `chaos_experiment_success_ratio`
- `chaos_experiment_risk_level_ratio`
- `chaos_experiment_complexity_score_ratio`
- `chaos_experiment_duration_seconds_sum`
- `chaos_experiment_start_total`
- `chaos_experiment_failed_ratio`

These are recorded via `record_custom_metric()` but should have dedicated methods.

### Fix Tasks

| Task | File(s) | Effort |
|------|---------|--------|
| Fix all `chaos_chaos_` → `chaos_` in dashboards | 5 dashboard JSON files | Medium |
| Add `chaos_` prefix to generic db/messaging methods | metrics_core.py | Small |
| Add `chaos_` prefix to compliance metrics | metrics_core.py | Small |
| Add dedicated `record_experiment_*` methods | metrics_core.py | Medium |
| Create metrics naming validation test | tests/test_metrics_naming.py | Small |

---

## Phase 1: Unified Experiment Results Dashboard

### Goal
Create a central dashboard showing all experiment runs with status, outcomes, and drill-down capability.

### Dashboard: `experiment-results-overview.json`

#### Row 1: Summary Stats
| Panel | Type | Query |
|-------|------|-------|
| Total Experiments Run | Stat | `count(chaos_experiment_start_total)` |
| Success Rate | Gauge | `avg(chaos_experiment_success_ratio) * 100` |
| Avg Duration | Stat | `avg(chaos_experiment_duration_seconds)` |
| Active Experiments | Stat | `count(chaos_experiment_in_progress == 1)` |

#### Row 2: Experiment Timeline
| Panel | Type | Description |
|-------|------|-------------|
| Experiment History | Time series | Shows experiment starts/ends over time |
| Success/Failure Timeline | State timeline | Visual success/failure per experiment |

#### Row 3: Experiment List Table
| Panel | Type | Columns |
|-------|------|---------|
| All Experiments | Table | experiment_id, title, status, duration, risk_level, complexity, start_time, systems_affected |

Features:
- Clickable rows linking to per-experiment dashboard
- Filter by: status, system type, date range, risk level
- Sort by any column

#### Row 4: System Impact Overview
| Panel | Type | Description |
|-------|------|-------------|
| Systems Under Test | Pie chart | Distribution by db_system/mq_system |
| Error Distribution | Bar chart | Errors by system type |
| MTTR by System | Bar gauge | Recovery time comparison |

### Data Requirements

New metrics needed:
```python
# In MetricsCore - add these methods
def record_experiment_start(experiment_id, title, risk_level, complexity, systems):
    """Record experiment start with metadata."""

def record_experiment_end(experiment_id, status, duration_seconds):
    """Record experiment completion."""

def record_experiment_systems(experiment_id, systems: List[str]):
    """Record which systems an experiment affects."""
```

New labels needed on existing metrics:
- `experiment_id` - unique identifier per run
- `experiment_title` - human-readable name

---

## Phase 2: Experiment Comparison Views

### Goal
Enable comparison of multiple runs of the same experiment or different experiments targeting the same systems.

### Dashboard: `experiment-comparison.json`

#### Variables (Template Variables)
```
experiment_ids: multi-select of experiment IDs (from label values)
experiment_title: single-select to filter by experiment type
time_range: comparison time window
```

#### Row 1: Comparison Summary
| Panel | Type | Description |
|-------|------|-------------|
| Success Rate Trend | Time series | Success ratio over selected experiments |
| Duration Comparison | Bar chart | Duration per experiment_id |
| Risk Score Comparison | Stat grid | Risk levels side-by-side |

#### Row 2: Metric Deltas
| Panel | Type | Description |
|-------|------|-------------|
| Error Rate Delta | Stat | Change in error rate between runs |
| Recovery Time Delta | Stat | MTTR improvement/degradation |
| Throughput Impact | Time series | Operations/sec comparison |

#### Row 3: System-Level Comparison
| Panel | Type | Description |
|-------|------|-------------|
| DB Metrics Comparison | Multi-line | Query latency, errors, locks per experiment |
| Messaging Comparison | Multi-line | Message throughput, consumer lag per experiment |

#### Row 4: Detailed Breakdown
| Panel | Type | Description |
|-------|------|-------------|
| Action Success by Experiment | Stacked bar | Success/failure per action across experiments |
| Probe Results Table | Table | All probe results side-by-side |

### Implementation Approach

1. **Grafana Variables**
   - Use `label_values(chaos_experiment_start_total, experiment_id)` for dropdown
   - Multi-select enabled for comparison

2. **Query Patterns**
   ```promql
   # Compare success rates
   chaos_experiment_success_ratio{experiment_id=~"$experiment_ids"}

   # Compare durations
   chaos_experiment_duration_seconds{experiment_id=~"$experiment_ids"}
   ```

3. **Annotations**
   - Mark experiment start/end times as annotations
   - Highlight failures with red annotation markers

---

## Phase 3: Per-Experiment Dashboard Generation

### Goal
Auto-generate a dedicated dashboard for each experiment run showing its specific traces, metrics, and logs.

### Architecture

```
┌─────────────────────────────────────────────────────────┐
│                   Experiment Run                         │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────┐ │
│  │   OTEL      │  │  Reporting  │  │  Dashboard      │ │
│  │  Control    │──│  Control    │──│  Generator      │ │
│  └─────────────┘  └─────────────┘  └─────────────────┘ │
│                                            │            │
│                                    ┌───────▼────────┐  │
│                                    │  Grafana API   │  │
│                                    │  (provision)   │  │
│                                    └────────────────┘  │
└─────────────────────────────────────────────────────────┘
```

### Dashboard Template: `experiment-run-template.json`

This is a parameterized template that gets instantiated per experiment.

#### Header Row
| Panel | Type | Content |
|-------|------|---------|
| Experiment Info | Text | Title, ID, start time, status |
| Risk Level | Stat | From experiment metadata |
| Complexity | Stat | From experiment metadata |
| Duration | Stat | Total experiment duration |

#### Row 1: Traces (Tempo)
| Panel | Type | Query |
|-------|------|-------|
| Service Graph | Node graph | Tempo service map filtered by experiment time |
| Trace List | Traces | `{experiment_id="$id"}` |
| Trace Duration | Histogram | Span duration distribution |

#### Row 2: Experiment Progress
| Panel | Type | Description |
|-------|------|-------------|
| Activity Timeline | State timeline | Shows each action/probe execution |
| Steady State Status | Stat | Hypothesis before/after status |
| Rollback Status | Stat | Rollback execution status |

#### Row 3: System Metrics (Prometheus)
| Panel | Type | Query |
|-------|------|-------|
| Target System Health | Multi-stat | Key metrics for affected systems |
| Error Rate | Time series | `chaos_db_error_count_total{experiment_id="$id"}` |
| Latency | Time series | `chaos_db_query_latency_milliseconds{experiment_id="$id"}` |

#### Row 4: Logs (Loki)
| Panel | Type | Query |
|-------|------|-------|
| Experiment Logs | Logs | `{service_name="chaostoolkit"} |= "$experiment_id"` |
| Error Logs | Logs | `{level="error"} |= "$experiment_id"` |

### Dashboard Generator Module

New file: `chaostooling-reporting/chaostooling_reporting/dashboard_generator.py`

```python
class DashboardGenerator:
    """Generate Grafana dashboards for experiment runs."""

    def __init__(self, grafana_url: str, api_key: str, template_path: str):
        self.grafana_url = grafana_url
        self.api_key = api_key
        self.template = self._load_template(template_path)

    def generate_dashboard(
        self,
        experiment_id: str,
        experiment_title: str,
        start_time: datetime,
        end_time: datetime,
        systems: List[str],
        journal: Dict[str, Any],
    ) -> str:
        """Generate and provision a dashboard for this experiment run."""

    def _provision_to_grafana(self, dashboard_json: dict) -> str:
        """Upload dashboard to Grafana via API."""
```

### Integration Point

In `chaostooling-reporting/control.py`, add dashboard generation:

```python
def after_experiment_control(context, state, experiment, journal, **kwargs):
    # Existing report generation
    report_generator.generate_reports(experiment, journal, configuration)

    # NEW: Dashboard generation
    if config.get("generate_dashboard", True):
        dashboard_generator.generate_dashboard(
            experiment_id=journal["experiment"]["id"],
            experiment_title=experiment.get("title"),
            start_time=journal.get("start"),
            end_time=journal.get("end"),
            systems=extract_systems(experiment),
            journal=journal,
        )
```

---

## Phase 4: Enhanced Reporting Integration

### Goal
Tie the existing reporting module to dashboard generation, creating a unified experience where reports include dashboard links and dashboards link to reports.

### Enhancements to ReportGenerator

#### 1. Dashboard Link in Reports

Add dashboard URL to all report outputs:

```python
# In report_generator.py
def generate_reports(self, experiment, journal, configuration):
    # ... existing code ...

    # Add dashboard URL to report metadata
    dashboard_url = self._get_dashboard_url(experiment_id)
    report_data["dashboard_url"] = dashboard_url
```

#### 2. Report Link in Dashboards

Add a text panel to generated dashboards with report download links:

```json
{
  "type": "text",
  "title": "Reports",
  "options": {
    "content": "**Reports:**\n- [Executive Summary](${report_base_url}/executive_${experiment_id}.html)\n- [Compliance Report](${report_base_url}/compliance_${experiment_id}.html)\n- [JSON Data](${report_base_url}/${experiment_id}.json)",
    "mode": "markdown"
  }
}
```

#### 3. Unified Experiment Index

New file: `chaostooling-reporting/chaostooling_reporting/experiment_index.py`

```python
class ExperimentIndex:
    """Central index of all experiment runs with reports and dashboards."""

    def __init__(self, storage_path: str):
        self.storage_path = Path(storage_path)
        self.index_file = self.storage_path / "experiment_index.json"

    def register_experiment(
        self,
        experiment_id: str,
        title: str,
        status: str,
        start_time: datetime,
        end_time: datetime,
        report_paths: Dict[str, str],
        dashboard_uid: str,
        systems: List[str],
        risk_level: str,
        complexity_score: int,
    ):
        """Register a completed experiment in the index."""

    def get_experiments(
        self,
        status: Optional[str] = None,
        system: Optional[str] = None,
        date_range: Optional[Tuple[datetime, datetime]] = None,
    ) -> List[Dict]:
        """Query experiments with optional filters."""

    def get_experiment(self, experiment_id: str) -> Optional[Dict]:
        """Get single experiment details."""
```

#### 4. Index Dashboard Data Source

Create a JSON API endpoint or file that Grafana can use:

```python
# Generates experiment_index_grafana.json for Grafana JSON datasource
def export_for_grafana(self) -> str:
    """Export index in Grafana-compatible format."""
```

### Report Templates Enhancement

#### Executive Summary Additions
- Dashboard screenshot/link
- Comparison to previous runs (if available)
- Trend indicators (improving/degrading)

#### Compliance Report Additions
- Link to full trace in Tempo
- Link to relevant log queries in Loki
- Evidence links for audit trail

---

## Implementation Phases & Dependencies

```
Phase 0: Metrics Quality Fixes
    │
    ├──► Phase 1: Unified Experiment Results Dashboard
    │         │
    │         └──► Phase 2: Experiment Comparison Views
    │
    └──► Phase 3: Per-Experiment Dashboard Generation
              │
              └──► Phase 4: Enhanced Reporting Integration
```

### Detailed Task Breakdown

#### Phase 0 Tasks (Metrics Quality)
1. [ ] Fix `chaos_chaos_` prefix in all 5 dashboard files
2. [ ] Update `record_db_gauge/counter/histogram` to use `chaos_db_` prefix
3. [ ] Update `record_messaging_gauge/counter/histogram` to use `chaos_messaging_` prefix
4. [ ] Update compliance metrics to use `chaos_compliance_` prefix
5. [ ] Add dedicated `record_experiment_*` methods to MetricsCore
6. [ ] Add `experiment_id` label to all chaos metrics
7. [ ] Create metrics naming validation test
8. [ ] Validate all dashboard queries against actual metric names

#### Phase 1 Tasks (Unified Dashboard)
1. [ ] Create `experiment-results-overview.json` dashboard template
2. [ ] Implement experiment list table with filters
3. [ ] Add drill-down links to per-experiment view
4. [ ] Create system impact visualization panels
5. [ ] Test with multiple experiment runs

#### Phase 2 Tasks (Comparison Views)
1. [ ] Create `experiment-comparison.json` dashboard template
2. [ ] Implement Grafana template variables for experiment selection
3. [ ] Create comparison query patterns
4. [ ] Add delta/trend calculations
5. [ ] Test comparison across different experiment types

#### Phase 3 Tasks (Per-Experiment Dashboards)
1. [ ] Create `experiment-run-template.json` base template
2. [ ] Implement `DashboardGenerator` class
3. [ ] Add Grafana API integration for provisioning
4. [ ] Integrate with reporting control
5. [ ] Add dashboard cleanup/retention policy
6. [ ] Test end-to-end dashboard generation

#### Phase 4 Tasks (Reporting Integration)
1. [ ] Add dashboard URLs to report outputs
2. [ ] Add report links to generated dashboards
3. [ ] Implement `ExperimentIndex` class
4. [ ] Create Grafana JSON datasource export
5. [ ] Enhance report templates with links and trends
6. [ ] Create unified experiment browser UI concept

---

## File Changes Summary

### New Files
| File | Purpose |
|------|---------|
| `chaostooling-demo/dashboards/experiment-results-overview.json` | Unified results dashboard |
| `chaostooling-demo/dashboards/experiment-comparison.json` | Comparison dashboard |
| `chaostooling-demo/dashboards/templates/experiment-run-template.json` | Per-experiment template |
| `chaostooling-reporting/chaostooling_reporting/dashboard_generator.py` | Dashboard generation |
| `chaostooling-reporting/chaostooling_reporting/experiment_index.py` | Experiment indexing |
| `chaostooling-otel/tests/test_metrics_naming.py` | Metrics naming validation |

### Modified Files
| File | Changes |
|------|---------|
| `chaostooling-otel/chaosotel/core/metrics_core.py` | Fix naming, add experiment methods |
| `chaostooling-demo/dashboards/e2e_dashboard.json` | Fix chaos_chaos_ prefix |
| `chaostooling-demo/dashboards/e2e_experiment_dashboard.json` | Fix chaos_chaos_ prefix |
| `chaostooling-demo/dashboards/distributed_showcase_dashboard.json` | Fix chaos_chaos_ prefix |
| `chaostooling-demo/dashboards/extensive_postgres_dashboard.json` | Fix chaos_chaos_ prefix |
| `chaostooling-demo/dashboards/e2e_test_dashboard.json` | Fix chaos_chaos_ prefix |
| `chaostooling-reporting/chaostooling_reporting/control.py` | Add dashboard generation |
| `chaostooling-reporting/chaostooling_reporting/report_generator.py` | Add dashboard links |

---

## Success Criteria

### Phase 0
- [ ] All dashboard queries return data (no "No data" panels)
- [ ] All metrics use consistent `chaos_` prefix
- [ ] Metrics naming test passes

### Phase 1
- [ ] Can view all experiment runs in single dashboard
- [ ] Can filter by status, system, date
- [ ] Can drill down to individual experiment

### Phase 2
- [ ] Can select multiple experiments for comparison
- [ ] Delta values calculated correctly
- [ ] Trend visualization works

### Phase 3
- [ ] Dashboard auto-generated after each experiment
- [ ] Dashboard shows correct time window
- [ ] Traces, metrics, logs all linked to experiment

### Phase 4
- [ ] Reports contain dashboard links
- [ ] Dashboards contain report links
- [ ] Experiment index queryable
- [ ] Full audit trail from report ↔ dashboard ↔ traces/logs

---

## Open Questions

1. **Dashboard Retention**: How long should per-experiment dashboards be kept? Options:
   - Delete after N days
   - Keep last N per experiment type
   - Keep all (with archival)

2. **Grafana Authentication**: How should the dashboard generator authenticate?
   - Service account API key
   - Environment variable
   - Kubernetes secret

3. **Report Storage**: Where should reports be stored for dashboard linking?
   - Local filesystem (current)
   - Object storage (S3/GCS)
   - Grafana's own storage

4. **Real-time Updates**: Should the unified dashboard update in real-time during experiments?
   - Polling interval
   - WebSocket push
   - Manual refresh only

---

## Implementation Status

### Completed (2026-01-20)

#### Phase 0: Metrics Quality Fixes
- [x] Fixed 54 `chaos_chaos_` prefix issues in 5 dashboard files
- [x] Fixed metric naming in MetricsCore:
  - `record_db_gauge/counter/histogram` now uses `chaos_db_` prefix
  - `record_messaging_gauge/counter/histogram` now uses `chaos_messaging_` prefix
  - Compliance metrics now use `chaos_compliance_` prefix
- [x] Added dedicated experiment metrics methods:
  - `record_experiment_start()`
  - `record_experiment_end()`
  - `record_experiment_risk_level()`
  - `record_experiment_complexity()`
  - `record_experiment_activity()`
  - `record_experiment_systems()`

#### Phase 1: Unified Experiment Results Dashboard
- [x] Created `experiment-results-overview.json` with:
  - Summary stats (total, success rate, avg duration, active)
  - Experiment timeline visualization
  - Filterable experiment list table
  - System impact overview
  - Risk & complexity analysis
  - Logs panel integration

#### Phase 2: Experiment Comparison Dashboard
- [x] Created `experiment-comparison.json` with:
  - Multi-select experiment picker
  - Success rate trend comparison
  - Duration comparison
  - Risk/complexity comparison
  - Error rate and MTTR comparisons
  - System-level metric comparisons
  - Activity breakdown by experiment

#### Phase 3: Per-Experiment Dashboard Generation
- [x] Created `templates/experiment-run-template.json`
- [x] Implemented `DashboardGenerator` class with:
  - Template-based dashboard generation
  - Variable substitution
  - Grafana API provisioning
  - Local file saving
  - Journal data extraction

#### Phase 4: Reporting Integration
- [x] Integrated dashboard generation into `control.py`
- [x] Created `ExperimentIndex` class for centralized tracking
- [x] Added Grafana export functionality
- [x] Updated module exports in `__init__.py`

### Files Created/Modified

**New Files:**
- `chaostooling-demo/dashboards/experiment-results-overview.json`
- `chaostooling-demo/dashboards/experiment-comparison.json`
- `chaostooling-demo/dashboards/templates/experiment-run-template.json`
- `chaostooling-reporting/chaostooling_reporting/dashboard_generator.py`
- `chaostooling-reporting/chaostooling_reporting/experiment_index.py`

**Modified Files:**
- `chaostooling-otel/chaosotel/core/metrics_core.py` (fixed naming, added experiment metrics)
- `chaostooling-demo/dashboards/e2e_dashboard.json` (fixed chaos_chaos_ prefix)
- `chaostooling-demo/dashboards/e2e_experiment_dashboard.json` (fixed chaos_chaos_ prefix)
- `chaostooling-demo/dashboards/distributed_showcase_dashboard.json` (fixed chaos_chaos_ prefix)
- `chaostooling-demo/dashboards/extensive_postgres_dashboard.json` (fixed chaos_chaos_ prefix)
- `chaostooling-demo/dashboards/e2e_test_dashboard.json` (fixed chaos_chaos_ prefix)
- `chaostooling-reporting/chaostooling_reporting/control.py` (added dashboard generation)
- `chaostooling-reporting/chaostooling_reporting/__init__.py` (added exports)
