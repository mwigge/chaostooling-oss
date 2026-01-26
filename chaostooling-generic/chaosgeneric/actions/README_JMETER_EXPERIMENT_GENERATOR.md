# JMeter Test Plan to Chaos Experiment Generator

Automatically generate Chaos Toolkit experiments from JMeter test plans, combining load testing with chaos engineering scenarios.

## Overview

This feature extracts information from JMeter test plans (`.jmx` files) and automatically generates chaos experiments that:

1. **Use JMeter as the load generator** - Your existing JMeter test plan runs as background load
2. **Target discovered services** - Automatically identifies databases, messaging systems, and applications from endpoints
3. **Inject chaos scenarios** - Generates appropriate chaos scenarios based on service types
4. **Integrate observability** - Includes OTEL traces, metrics, and logs for full visibility
5. **Simulate real-world conditions** - Combines realistic load with failures for comprehensive resilience testing

## Features

- **Automatic endpoint discovery** - Extracts HTTP requests, URLs, and service patterns from JMeter test plans
- **Service type detection** - Identifies databases (PostgreSQL, MySQL, MongoDB, Redis, etc.), messaging systems (Kafka, RabbitMQ), and applications
- **Intelligent scenario generation** - Creates appropriate chaos scenarios based on discovered services
- **Load testing integration** - Uses `jmeter_gatling_control` to automatically start/stop JMeter during experiments
- **Observability ready** - Generated experiments include OTEL instrumentation for traces, metrics, and logs

## Usage

### Python API

```python
from chaosgeneric.actions import generate_chaos_experiment_from_jmeter

# Generate experiment from JMeter test plan
result = generate_chaos_experiment_from_jmeter(
    jmeter_test_plan_path="/path/to/test-plan.jmx",
    output_path="/path/to/generated-experiment.json",
    experiment_title="My Custom Chaos Experiment"
)

# Access parsed JMeter data
jmeter_data = result["jmeter_data"]
print(f"Discovered {len(jmeter_data['endpoints'])} endpoints")
print(f"Thread groups: {len(jmeter_data['thread_groups'])}")

# Access generated experiment
experiment = result["experiment"]
print(f"Generated experiment: {experiment['title']}")
```

### CLI Wrapper

```python
from chaosgeneric.actions import generate_experiment_from_jmeter_cli

# Generate experiment (auto-determines output path)
output_file = generate_experiment_from_jmeter_cli(
    jmeter_test_plan_path="/path/to/test-plan.jmx",
    output_dir="/path/to/output",  # Optional
    experiment_title="My Experiment"  # Optional
)

print(f"Generated: {output_file}")
```

### Direct Parser Usage

```python
from chaosgeneric.actions import JMeterTestPlanParser

# Parse JMeter test plan
parser = JMeterTestPlanParser("/path/to/test-plan.jmx")
jmeter_data = parser.parse()

# Access parsed data
print(f"Test Plan: {jmeter_data['test_plan']['name']}")
print(f"HTTP Requests: {len(jmeter_data['http_requests'])}")
print(f"Endpoints: {len(jmeter_data['endpoints'])}")
print(f"Load Config: {jmeter_data['load_config']}")

# Inspect endpoints
for endpoint in jmeter_data['endpoints']:
    print(f"  - {endpoint['url']} ({endpoint['service_type']})")
```

## Generated Experiment Structure

The generated experiment includes:

### Configuration

- **JMeter Load Generator** - Configured to use your test plan via `jmeter_gatling_control`
- **Chaos Parameters** - Stress duration, thread counts, etc.
- **Observability** - OTEL service name and configuration
- **Reporting** - Output directory and formats

### Controls

- `env-loader` - Environment variable loading
- `opentelemetry` - OTEL instrumentation for traces, metrics, logs
- `reporting` - Experiment report generation
- `jmeter_load_generator` - Automatic JMeter start/stop during experiment

### Steady-State Hypothesis

Probes generated based on discovered services:

- Database connectivity probes (PostgreSQL, MySQL, etc.)
- Messaging system probes (Kafka, RabbitMQ, etc.)
- HTTP endpoint availability probes

### Method (Chaos Scenarios)

1. **Phase 1: Baseline** - Establish baseline with JMeter load running
2. **Phase 2: Chaos Scenarios** - Inject failures during load:
   - Database: Connection pool exhaustion, query saturation
   - Messaging: Message floods, topic saturation, slow consumers
   - Applications: Network latency, CPU/memory stress
3. **Phase 3: Final Validation** - Verify system recovery

### Rollbacks

- Automatic report generation after experiment completion

## Service Type Detection

The parser automatically identifies service types from hostnames and URLs:

### Databases

- `database_postgres` - PostgreSQL
- `database_mysql` - MySQL/MariaDB
- `database_mongodb` - MongoDB
- `database_redis` - Redis
- `database_cassandra` - Cassandra
- `database_mssql` - Microsoft SQL Server

### Messaging

- `messaging_kafka` - Apache Kafka
- `messaging_rabbitmq` - RabbitMQ
- `messaging_activemq` - ActiveMQ

### Infrastructure

- `load_balancer` - HAProxy, Nginx, load balancers
- `application` - Generic application services

## Example Workflow

1. **Create/Use JMeter Test Plan**

   ```bash
   # Your existing JMeter test plan (.jmx file)
   /path/to/my-load-test.jmx
   ```

2. **Generate Chaos Experiment**
   ```python
   from chaosgeneric.actions import generate_chaos_experiment_from_jmeter
   
   result = generate_chaos_experiment_from_jmeter(
       jmeter_test_plan_path="/path/to/my-load-test.jmx",
       output_path="/path/to/my-chaos-experiment.json"
   )
   ```

3. **Review Generated Experiment**
   ```bash
   cat /path/to/my-chaos-experiment.json
   ```

4. **Run Chaos Experiment**
   ```bash
   chaos run /path/to/my-chaos-experiment.json
   ```

   The experiment will:
   - Start JMeter load generator automatically
   - Run baseline validation
   - Inject chaos scenarios during load
   - Stop JMeter automatically
   - Generate reports

## Integration with Existing Features

### JMeter/Gatling Control

The generated experiments use `jmeter_gatling_control` to manage JMeter lifecycle:
- Starts before experiment begins
- Runs throughout chaos scenarios
- Stops after experiment completes
- Handles cleanup on failures

### Observability (OTEL)

Generated experiments include:
- **Traces** - Full distributed tracing via Tempo
- **Metrics** - Experiment metrics via Prometheus
- **Logs** - Structured logging via Loki
- **Dashboards** - Automatic dashboard generation

### Reporting

Experiments include automatic report generation:
- Executive summaries
- Compliance reports
- Audit trails
- Product owner reports

## Customization

### Custom Experiment Title

```python
result = generate_chaos_experiment_from_jmeter(
    jmeter_test_plan_path="/path/to/test-plan.jmx",
    experiment_title="Production Load Test with Chaos"
)
```

### Manual Scenario Addition

After generation, you can edit the JSON to add custom scenarios:

```json
{
  "method": [
    {
      "name": "custom-chaos-scenario",
      "type": "action",
      "provider": {
        "type": "python",
        "module": "your.module",
        "func": "your_function"
      }
    }
  ]
}
```

## Limitations

- **Service Detection** - Relies on hostname patterns; may not detect all service types
- **Scenario Selection** - Generates common scenarios; may need customization for specific use cases
- **Complex Test Plans** - Very complex JMeter test plans with many nested elements may require manual review

## Troubleshooting

### Parser Errors

If parsing fails, check:
- Valid JMeter XML format (.jmx file)
- File is readable and not corrupted
- XML structure matches expected JMeter format

### Missing Service Detection

If services aren't detected:

- Check hostnames in JMeter test plan
- Manually edit generated experiment to add correct service types
- Use custom scenarios for specific services

### JMeter Control Issues

If JMeter doesn't start:

- Verify `JMETER_HOME` environment variable
- Check test plan path is correct
- Ensure JMeter is installed and accessible

## See Also

- [JMeter/Gatling Control Documentation](README_JMETER_GATLING.md)
- [CLAUDE.md](../../../../CLAUDE.md) - Project observability guidelines
- [Chaos Toolkit Documentation](https://chaostoolkit.org/)

