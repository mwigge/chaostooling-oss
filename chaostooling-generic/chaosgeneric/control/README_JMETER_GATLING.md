# JMeter/Gatling Load Generator Control

This control automatically starts and stops JMeter or Gatling load generators during chaos experiments. It supports both tools via their APIs or CLI interfaces.

## Features

- **JMeter Support**: CLI mode, remote/distributed testing, and custom API wrappers
- **Gatling Support**: CLI mode and Gatling Enterprise REST API
- **Automatic Lifecycle Management**: Starts before experiment, stops after
- **Unified Interface**: Same control works for both tools

## Configuration

### Basic Configuration

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
        "auto_start_load_generator": "true"
      }
    }
  ]
}
```

### JMeter Configuration

#### CLI Mode (Recommended for Open Source)

```json
{
  "configuration": {
    "tool": "jmeter",
    "auto_start_load_generator": "true",
    "jmeter_test_plan": "/path/to/test-plan.jmx",
    "jmeter_home": "/opt/apache-jmeter-5.6",
    "jmeter_results_file": "/tmp/jmeter-results.jtl",
    "jmeter_properties": {
      "users": "100",
      "rampup": "60"
    }
  }
}
```

#### Remote/Distributed Mode

```json
{
  "configuration": {
    "tool": "jmeter",
    "jmeter_test_plan": "/path/to/test-plan.jmx",
    "jmeter_home": "/opt/apache-jmeter-5.6",
    "jmeter_remote_hosts": "jmeter-server1:1099,jmeter-server2:1099"
  }
}
```

#### API Mode (Requires Custom JMeter API Wrapper)

```json
{
  "configuration": {
    "tool": "jmeter",
    "jmeter_api_url": "http://jmeter-api:8080",
    "jmeter_test_plan": "test-plan-id"
  }
}
```

### Gatling Configuration

#### CLI Mode (Open Source)

```json
{
  "configuration": {
    "tool": "gatling",
    "auto_start_load_generator": "true",
    "gatling_simulation_class": "com.example.BasicSimulation",
    "gatling_home": "/opt/gatling",
    "gatling_properties": {
      "users": "100",
      "rampDuration": "60"
    }
  }
}
```

#### Enterprise API Mode

```json
{
  "configuration": {
    "tool": "gatling",
    "gatling_api_url": "https://cloud.gatling.io/api/public",
    "gatling_api_token": "your-api-token",
    "gatling_team_id": "your-team-id",
    "gatling_simulation_class": "com.example.BasicSimulation"
  }
}
```

## Environment Variables

### JMeter

- `JMETER_HOME`: JMeter installation directory (if not provided in configuration)

### Gatling

- `GATLING_HOME`: Gatling installation directory (if not provided in configuration)
- `GATLING_API_TOKEN`: API token for Gatling Enterprise (if not provided in configuration)

## Usage Examples

### Example 1: JMeter CLI Mode

```json
{
  "title": "Database chaos with JMeter load",
  "description": "Inject database failures while running JMeter load test",
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
  ],
  "steady-state-hypothesis": {
    "title": "Services are healthy",
    "probes": [
      {
        "type": "probe",
        "name": "api-health",
        "tolerance": 200,
        "provider": {
          "type": "http",
          "url": "http://api:8080/health"
        }
      }
    ]
  },
  "method": [
    {
      "type": "action",
      "name": "inject-database-latency",
      "provider": {
        "type": "python",
        "module": "chaosdb.actions",
        "func": "inject_latency",
        "arguments": {
          "database": "postgresql",
          "latency_ms": 500
        }
      }
    }
  ]
}
```

### Example 2: Gatling Enterprise API Mode

```json
{
  "title": "Network chaos with Gatling load",
  "controls": [
    {
      "name": "jmeter_gatling",
      "provider": {
        "type": "python",
        "module": "chaosgeneric.control.jmeter_gatling_control"
      },
      "configuration": {
        "tool": "gatling",
        "gatling_api_url": "https://cloud.gatling.io/api/public",
        "gatling_api_token": "${GATLING_API_TOKEN}",
        "gatling_team_id": "team-123",
        "gatling_simulation_class": "com.example.ApiLoadSimulation"
      }
    }
  ],
  "method": [
    {
      "type": "action",
      "name": "inject-network-packet-loss",
      "provider": {
        "type": "python",
        "module": "chaosnetwork.actions",
        "func": "inject_packet_loss",
        "arguments": {
          "percentage": 10
        }
      }
    }
  ]
}
```

## Manual Control via Actions

You can also control JMeter and Gatling manually using the action functions:

### JMeter Actions

```python
from chaosgeneric.actions.load_generator.jmeter_api import (
    start_jmeter_test,
    stop_jmeter_test,
    get_jmeter_test_status,
)

# Start test
result = start_jmeter_test(
    test_plan_path="./test-plan.jmx",
    jmeter_home="/opt/apache-jmeter-5.6"
)

# Get status
status = get_jmeter_test_status(
    process_id=result["process_id"],
    results_file=result["results_file"]
)

# Stop test
stop_jmeter_test(process_id=result["process_id"])
```

### Gatling Actions

```python
from chaosgeneric.actions.load_generator.gatling_api import (
    start_gatling_simulation,
    stop_gatling_simulation,
    get_gatling_simulation_status,
)

# Start simulation
result = start_gatling_simulation(
    simulation_class="com.example.BasicSimulation",
    gatling_home="/opt/gatling"
)

# Get status
status = get_gatling_simulation_status(
    process_id=result["process_id"]
)

# Stop simulation
stop_gatling_simulation(process_id=result["process_id"])
```

## Notes

- **JMeter**: For distributed testing, ensure JMeter servers are running on remote hosts before starting the test
- **Gatling Enterprise**: Requires a valid API token and team ID. The API endpoints may vary by version
- **Process Management**: In CLI mode, the control manages processes. Ensure proper cleanup on experiment failure
- **Results**: JMeter results are saved to `.jtl` files. Gatling Enterprise provides results via API

## Troubleshooting

### JMeter Issues

- **"JMETER_HOME not set"**: Set the `JMETER_HOME` environment variable or provide `jmeter_home` in configuration
- **"Test plan not found"**: Ensure the test plan path is correct and accessible
- **Remote hosts unreachable**: Verify JMeter servers are running and accessible on specified ports

### Gatling Issues

- **"GATLING_HOME not set"**: Set the `GATLING_HOME` environment variable or provide `gatling_home` in configuration
- **"simulation_class is required"**: Provide the fully qualified class name of your simulation
- **API authentication failed**: Verify your Gatling Enterprise API token and team ID are correct


