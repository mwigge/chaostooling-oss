Project Overview

Project: chaostooling-oss
Version: 0.1.0
Language: Python 3.9+
Observability targets: Grafana Tempo (traces), Prometheus (metrics), Loki (logs)
Dashboard format: JSON dashboards for Grafana (Tempo/Prometheus/Loki wired), plus CSV/Markdown and JSON for chaos experiments
Table of contents

Goals and scope
Observability components and integration notes
Validation plan (phases and checkpoints)
Dashboard strategy (primary vs secondary)
Reusable templates (dashboard, prompts, and configurations)
Example prompts (patterns)
Workflow and validation steps
Outputs and artifact formats
Quick-start checklist
Change log and maintenance notes
Goals and scope

Primary objective: Validate end-to-end observability for Chaos Toolkit extensions:
Traces exported to Tempo via OTLP (HTTP or gRPC) and visible in Grafana
Metrics exposed to Prometheus (including custom metrics via MetricsCore)
Logs ingested by Loki and viewable in Grafana
Secondary objective: Alter existing dashboards and produce new ones as needed
Output deliverables: reusable dashboard templates (JSON), PromQL snippets, OTEL config snippets, and CSV/Markdown validation checklists
Observability components and integration notes

Tempo (traces)
Ensure OTEL instrumentation is enabled in instrumented services
OTLP exporter endpoints must be reachable (environment variables or config)
Grafana Tempo data source is configured; traces should render in the service map or traces panel
Prometheus (metrics)
Prometheus scrapes Chaos Toolkit endpoints and metrics exporters
MetricsCore must implement a valid record_custom_metric method (name and signature aligned with tests)
PromQL in dashboards must return data in the expected time windows
Loki (logs)
Logs are pushed to Loki with appropriate labels (service_name, instance, pod, etc.)
Loki data source in Grafana must be configured; logs panel filters should work
Dashboards (JSON)
Dashboards should reference Tempo (traces), Prometheus (metrics), and Loki (logs)
Skeletons or scaffolds should be easy to clone for new services/scenarios
Validation plan (phases and checkpoints)
Phase 1: Instrumentation and configuration checks

Check environment:
OTEL_EXPORTER_OTLP_ENDPOINT and OTEL_EXPORTER_OTLP_PROTOCOL
Grafana data sources for tempo, prometheus, and loki
Verify application startup with OTEL instrumentation enabled
Confirm MetricsCore has record_custom_metric method (no AttributeError on init)
Phase 2: End-to-end trace validation (Tempo)

Generate a representative Chaos Toolkit scenario action
Verify that a trace is produced and visible in Tempo (service map or traces)
Validate propagators (B3/ Jaeger) as needed
Confirm Tempo exporter configuration (OTLP/HTTP vs OTLP/GRPC)
Phase 3: Metrics validation (Prometheus)

Trigger a chaos scenario and verify key metrics increment
Validate essential PromQL queries in Prometheus or Grafana panels
Confirm custom metrics emitted by MetricsCore appear in Prometheus
Phase 4: Logs validation (Loki)

Emit a test log with known labels
Verify Loki ingestion and visibility in Grafana logs panel
Validate log filters and time range behavior
Phase 5: Dashboard sanity (secondary)

Ensure Tempo, Prometheus, Loki data sources are wired in Grafana
Validate a subset of panels render without errors
Add minimal, reusable JSON dashboards scaffolds for Compute/DB/Messaging if needed
Dashboard strategy (primary vs secondary)

Primary: dashboards that validate traces, metrics, and logs during tests
Tempo traces panels (service map / traces)
Prometheus metrics panels (key metrics, status gauges, duration, success rates)
Loki logs panels (log streams with filters)
Secondary: dashboards for broader coverage or new scenarios
Use a template to generate dashboards for new services/scenarios
JSON dashboards for Chaos Toolkit experiments
Metadata-driven dashboards that can be instantiated via automation
Reusable templates (dashboard, prompts, configurations)

Dashboard template (JSON)
A compact scaffold wiring Tempo, Prometheus, Loki
Contains placeholders for service groups: Compute, Database, Messaging
Panels include:
Service Map or Trace list (Tempo)
Key gauges/tills (Prometheus): Experiment Status, Duration, Success Rate
Logs panel (Loki) with a reasonable filter
CSV/Markdown validation checklist
Columns: Step, Category (Trace/Metric/Log), Prompts, Expected outcome, Validation commands, Expected result
Prompts template (Claude-style or similar)
Generate a minimal Tempo-trace validation snippet for a chaos scenario
Create Prometheus queries to validate “Experiment Duration” and “Success Rate” panels
Produce Loki log pipeline test prompts
Build a compact dashboard scaffold (JSON) for a subset of services
Config snippets
OTEL SDK/collector config (exporters, receivers)
Prometheus scrape targets (jobs/targets)
Tempo data source configuration in Grafana
Loki pipeline/promtail config notes
Chaos Toolkit experiment JSON scaffold
Create an experiment run that exercises the validation steps and yields dashboards/templates as outputs
Example prompts (patterns you can reuse)

Traces: "Generate a minimal Tempo OTLP/HTTP trace export snippet for Chaos Toolkit operations and ensure traces show up in Tempo service map."
Metrics: "Produce PromQL to validate the Experiment Duration and Experiment Status using chaos_experiment_duration_seconds and chaos_experiment_success_ratio metrics."
Logs: "Create a Loki log ingestion test that emits a standard Chaos Toolkit event and validates log lines appear with labels service_name, instance, and pod."
Dashboard scaffold: "Output a JSON Grafana dashboard scaffold with Tempo traces, Prometheus metrics, and Loki logs wired to a subset of services (Compute, DB, Messaging)."
Output formats and artifacts

Dashboard JSON templates
Reusable scaffold with placeholders for services and panels
Can be imported via Grafana API or UI
PromQL snippets
Example queries for common panels (Experiment Status, Duration, Success/Failure, etc.)
OTEL/Tempo config snippets
Environment variable blocks and/or YAML snippets for exporters and propagators
Loki/promtail config notes
Ingestion labels and scrape targets
CSV/Markdown validation checklists
Quick references for runbooks and automated validation steps
Chaos Toolkit experiment snippets
Minimal JSON to run a validation-focused experiment and produce dashboard outputs
Example structure for a compact, reusable dashboard template (JSON)

Tempo traces panel (Tempo data source, traces)
Prometheus panels
Experiment Status (last_over_time(chaos_experiment_success_ratio[1m]))
Experiment Duration (last_over_time(chaos_experiment_duration_seconds_sum[5m]))
Transactions, Failures, and Latency panels (example PromQL)
Loki logs panel
Query for chaos toolkit logs, filtered by service_name and relevant keywords
Compute, DB, and Messaging rows with representative panels
Global settings
Datasources: tempo, prometheus, loki
Time range presets (now-1h, now)
Example Prompts for automation

Generate a compact Tempo trace validation snippet for Chaos Toolkit operations, exporting traces to Tempo via OTLP/HTTP.
Produce a minimal dashboard JSON scaffold for a subset of services (Compute, DB, Messaging) wired to Tempo/Prometheus/Loki.
Create a CSV validation checklist with steps to verify Traces, Metrics, and Logs, including commands to validate data presence in Tempo Grafana, Prometheus UI, and Loki.
Create a Chaos Toolkit experiment JSON to verify dashboards: it should run a small scenario, emit traces and metrics, and produce a dashboard artifact.
Quick-start tips

Start with instrumentation: ensure OTEL is enabled, OTLP endpoint is reachable, and Tempo datasource is configured in Grafana.
Ensure MetricsCore has a valid record_custom_metric implementation to prevent initialization errors.
Verify Prometheus scrapes Chaos Toolkit endpoints and exports metrics as expected.
Validate Loki ingestion by pushing a test log entry and checking Grafana logs with a time window covering the ingestion moment.
Use the dashboard template scaffold to iterate quickly on new scenarios or services.
Change log and maintenance notes

Critical Rules
1. Code Organization
Many small files over few large files
High cohesion, low coupling
200-400 lines typical, 800 max per file
Organize by feature/domain, not by type
2. Code Style
No emojis in code, comments, or documentation
Immutability always - never mutate objects or arrays
No console.log in production code
Proper error handling with try/catch
Input validation with Zod or similar
3. Testing
TDD: Write tests first
80% minimum coverage
Unit tests for utilities
Integration tests for APIs
E2E tests for critical flows
4. Security
No hardcoded secrets
Environment variables for sensitive data
Validate all user inputs
Parameterized queries only
CSRF protection enabled

File Structure
chaostooling-oss/                           # home for the chaostooling, based on ChaosToolkit
├── chaostooling-demo                       # docker-compose demo 
├── chaostooling-experiments                # json based experiment files for chaos engineering
├── chaostooling-extension-app              # application focused probes and actions 
├── chaostooling-extension-compute          # cpu , memory, io focused probes and actions
├── chaostooling-extension-db               # database and event messaging focused probes and actions
├── chaostooling-extension-network          # network (ping, latency) focused probes and actions
├── chaostooling-generic                    # generic or common focused probes, actions and helpers
├── chaostooling-otel                       # observability , monitoring, logs, metrics, traces helpers based on open telemetry
├── chaostooling-reporting                  # reporting modules, data extraction modules


Error Handling
try {
  const result = await operation()
  return { success: true, data: result }
} catch (error) {
  console.error('Operation failed:', error)
  return { success: false, error: 'User-friendly message' }
}

Environment Variables
# Required
DATABASE_URL=
API_KEY=

# Optional
DEBUG=false

Development Context
Mode: Active development Focus: Implementation, coding, building features

Behavior
Write code first, explain after
Prefer working solutions over perfect solutions
Run tests after changes
Keep commits atomic
Priorities
Get it working
Get it right
Get it clean
Tools to favor
Edit, Write for code changes
Bash for running tests/builds
Grep, Glob for finding code

