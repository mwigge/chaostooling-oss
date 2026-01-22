# chaostooling-generic

Generic chaos engineering controls and utilities for Chaos Toolkit.

This package provides general-purpose controls and actions that can be used across different types of chaos experiments, regardless of the target system (databases, networks, compute, etc.).

## Controls

### Environment Loader Control

Automatically loads environment variables from `.env` files before running experiments.

**Module:** `chaosgeneric.control.env_loader_control`

See [control/README_ENV_LOADER.md](chaosgeneric/control/README_ENV_LOADER.md) for detailed documentation.

### Load Generator Control

Automatically starts and stops background transaction load generators during experiments.

**Module:** `chaosgeneric.control.load_generator_control`

### JMeter/Gatling Load Generator Control

Automatically starts and stops JMeter or Gatling load generators during experiments. Supports both tools via their APIs or CLI interfaces.

**Module:** `chaosgeneric.control.jmeter_gatling_control`

See [control/README_JMETER_GATLING.md](chaosgeneric/control/README_JMETER_GATLING.md) for detailed documentation.

## Actions

### Load Generator Actions

Actions for controlling background transaction load generators.

**Module:** `chaosgeneric.actions.load_generator.transaction_load_generator`

Functions:
- `start_background_transaction_load()` - Start load generator
- `stop_background_transaction_load()` - Stop load generator
- `get_background_load_stats()` - Get current statistics

### JMeter Actions

Actions for controlling Apache JMeter load generator.

**Module:** `chaosgeneric.actions.load_generator.jmeter_api`

Functions:
- `start_jmeter_test()` - Start JMeter test plan
- `stop_jmeter_test()` - Stop running JMeter test
- `get_jmeter_test_status()` - Get test status and statistics

### Gatling Actions

Actions for controlling Gatling load generator.

**Module:** `chaosgeneric.actions.load_generator.gatling_api`

Functions:
- `start_gatling_simulation()` - Start Gatling simulation
- `stop_gatling_simulation()` - Stop running Gatling simulation
- `get_gatling_simulation_status()` - Get simulation status and statistics

### JMeter Experiment Generator

Automatically generate chaos experiments from JMeter test plans. Extracts endpoints, service patterns, and load configuration from `.jmx` files and generates complete Chaos Toolkit experiments that combine load testing with chaos scenarios.

**Module:** `chaosgeneric.actions.generate_experiment_from_jmeter`

Functions:
- `generate_chaos_experiment_from_jmeter()` - Generate chaos experiment from JMeter test plan
- `generate_experiment_from_jmeter_cli()` - CLI-friendly wrapper
- `JMeterTestPlanParser` - Parse JMeter test plans

See [actions/README_JMETER_EXPERIMENT_GENERATOR.md](chaosgeneric/actions/README_JMETER_EXPERIMENT_GENERATOR.md) for detailed documentation.

## Installation

```bash
pip install chaostooling-generic
```

## Usage

### Environment Loader Control

```json
{
  "controls": [
    {
      "name": "env-loader",
      "provider": {
        "type": "python",
        "module": "chaosgeneric.control.env_loader_control"
      }
    }
  ]
}
```

### Load Generator Control

```json
{
  "controls": [
    {
      "name": "load_generator",
      "provider": {
        "type": "python",
        "module": "chaosgeneric.control.load_generator_control"
      },
      "configuration": {
        "load_generator_url": "http://transaction-load-generator:5001",
        "load_generator_tps": 2.0,
        "auto_start_load_generator": "true"
      }
    }
  ]
}
```

### JMeter/Gatling Load Generator Control

#### JMeter Example

```json
{
  "controls": [
    {
      "name": "jmeter_gatling",
      "provider": {
        "type": "python",
        "module": "chaosgeneric.control.jmeter_gatling_control"
      },
      "configuration": {
        "tool": "jmeter",
        "jmeter_test_plan": "./load-tests/api-load-test.jmx",
        "jmeter_home": "/opt/apache-jmeter-5.6"
      }
    }
  ]
}
```

#### Gatling Example

```json
{
  "controls": [
    {
      "name": "jmeter_gatling",
      "provider": {
        "type": "python",
        "module": "chaosgeneric.control.jmeter_gatling_control"
      },
      "configuration": {
        "tool": "gatling",
        "gatling_simulation_class": "com.example.BasicSimulation",
        "gatling_home": "/opt/gatling"
      }
    }
  ]
}
```

### Generate Chaos Experiments from JMeter Test Plans

Automatically generate chaos experiments that combine your JMeter load tests with chaos scenarios:

```python
from chaosgeneric.actions import generate_chaos_experiment_from_jmeter

# Generate experiment from JMeter test plan
result = generate_chaos_experiment_from_jmeter(
    jmeter_test_plan_path="/path/to/test-plan.jmx",
    output_path="/path/to/generated-experiment.json",
    experiment_title="My Custom Chaos Experiment"
)

# The generated experiment will:
# - Use JMeter as the load generator
# - Include chaos scenarios targeting discovered services
# - Integrate observability (OTEL traces, metrics, logs)
```

See [actions/README_JMETER_EXPERIMENT_GENERATOR.md](chaosgeneric/actions/README_JMETER_EXPERIMENT_GENERATOR.md) for complete documentation and examples.

## Dependencies

- `requests>=2.31.0` - For HTTP requests to load generator service

## License

Apache-2.0

