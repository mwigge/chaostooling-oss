# ChaosTooling Extension App

**Application-Level Chaos Engineering Extension for Chaos Toolkit**

Application-level chaos testing to validate how your applications handle failures, degradation, and unexpected conditions. Fully instrumented with OpenTelemetry for complete observability.

[![Python Version](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/downloads/)
[![Chaos Toolkit](https://img.shields.io/badge/chaos--toolkit-compatible-green.svg)](https://chaostoolkit.org/)
[![OpenTelemetry](https://img.shields.io/badge/opentelemetry-instrumented-orange.svg)](https://opentelemetry.io/)

---

## Overview

ChaosTooling Extension App enables teams to test application resilience through controlled chaos at the application layer. Validate how your services behave when:

- **Requests fail or timeout** - Test circuit breakers and fallback logic
- **Responses are delayed** - Verify timeout and retry handling
- **Errors are injected** - Test error handling and recovery
- **Sessions are killed** - Test connection management and reconnection
- **Features are disabled** - Test graceful degradation
- **Configuration changes** - Test dynamic configuration handling

### Key Features

✅ **Request Injection** - Slow responses, errors, timeouts
✅ **Session Management** - Disrupt active sessions and connections
✅ **Feature Flags** - Toggle features during experiments
✅ **Configuration Chaos** - Dynamic configuration changes
✅ **Response Manipulation** - Modify response bodies and headers
✅ **Full Observability** - Every action traced and metered via OpenTelemetry
✅ **Multi-Protocol Support** - HTTP/REST, gRPC, databases

---

## Installation

### Prerequisites

- Python 3.10+
- Chaos Toolkit 1.42.1+
- chaostooling-otel (for observability)

### Install Package

```bash
pip install chaostooling-extension-app
```

### Install from Source

```bash
cd chaostooling-extension-app
pip install -e .
```

---

## Quick Start

### 1. Basic Configuration

Create an experiment JSON with app chaos actions:

```json
{
  "version": "1.0",
  "title": "Application Resilience Test",
  "description": "Test HTTP timeout handling",
  
  "configuration": {
    "api_url": {
      "type": "env",
      "key": "APP_API_URL",
      "default": "http://localhost:5000"
    }
  },
  
  "controls": [
    {
      "name": "experiment-orchestrator",
      "provider": {
        "type": "python",
        "module": "chaosgeneric.control.experiment_orchestrator_control"
      }
    },
    {
      "name": "env-loader",
      "provider": {
        "type": "python",
        "module": "chaosgeneric.control.env_loader_control"
      }
    }
  ],
  
  "steady-state-hypothesis": {
    "title": "Service is responding normally",
    "probes": [
      {
        "type": "probe",
        "name": "api-health",
        "provider": {
          "type": "python",
          "module": "chaosapp.probes",
          "func": "api_is_healthy",
          "arguments": {
            "url": "${api_url}/health",
            "timeout": 5
          }
        }
      }
    ]
  },
  
  "method": [
    {
      "type": "action",
      "name": "inject-latency",
      "provider": {
        "type": "python",
        "module": "chaosapp.actions",
        "func": "inject_response_latency",
        "arguments": {
          "url": "${api_url}",
          "latency_ms": 5000,
          "duration_seconds": 30,
          "percentage": 100
        }
      }
    }
  ]
}
```

### 2. Environment Setup

```bash
export APP_API_URL=http://localhost:5000
export OTEL_SERVICE_NAME=my-app-chaos
export OTEL_EXPORTER_OTLP_ENDPOINT=http://otel-collector:4317
```

### 3. Run Experiment

```bash
chaos run app-chaos-experiment.json
```

---

## Actions

### Request Injection

**inject_request_errors**
- Inject HTTP errors (500, 503, 429) into requests
- Supports percentage-based injection
- Tests error handling and retry logic

```json
{
  "type": "action",
  "name": "inject-errors",
  "provider": {
    "type": "python",
    "module": "chaosapp.actions",
    "func": "inject_request_errors",
    "arguments": {
      "url": "http://api.example.com",
      "error_codes": [500, 503],
      "percentage": 25,
      "duration_seconds": 60
    }
  }
}
```

**inject_response_latency**
- Add delays to API responses
- Simulates network latency or slow processing
- Tests timeout handling

```json
{
  "type": "action",
  "name": "inject-latency",
  "provider": {
    "type": "python",
    "module": "chaosapp.actions",
    "func": "inject_response_latency",
    "arguments": {
      "url": "http://api.example.com",
      "latency_ms": 3000,
      "duration_seconds": 60,
      "percentage": 50
    }
  }
}
```

**inject_response_corruption**
- Return malformed or partial responses
- Tests client-side error handling
- Validates input validation

```json
{
  "type": "action",
  "name": "corrupt-responses",
  "provider": {
    "type": "python",
    "module": "chaosapp.actions",
    "func": "inject_response_corruption",
    "arguments": {
      "url": "http://api.example.com",
      "corruption_type": "partial",
      "duration_seconds": 30
    }
  }
}
```

### Session Management

**kill_active_sessions**
- Terminate active client sessions
- Force reconnection and resynchronization
- Tests connection pooling and recovery

```json
{
  "type": "action",
  "name": "kill-sessions",
  "provider": {
    "type": "python",
    "module": "chaosapp.actions",
    "func": "kill_active_sessions",
    "arguments": {
      "service_name": "my-service",
      "session_type": "http"
    }
  }
}
```

**disconnect_clients**
- Forcefully close client connections
- Tests graceful connection handling
- Simulates network disconnections

```json
{
  "type": "action",
  "name": "disconnect-clients",
  "provider": {
    "type": "python",
    "module": "chaosapp.actions",
    "func": "disconnect_clients",
    "arguments": {
      "service_name": "my-service",
      "protocol": "http"
    }
  }
}
```

### Feature Flags & Configuration

**disable_feature**
- Disable features during experiments
- Tests graceful degradation
- Validates fallback behavior

```json
{
  "type": "action",
  "name": "disable-caching",
  "provider": {
    "type": "python",
    "module": "chaosapp.actions",
    "func": "disable_feature",
    "arguments": {
      "service_name": "my-service",
      "feature_name": "response_caching",
      "duration_seconds": 60
    }
  }
}
```

**modify_configuration**
- Dynamically change application configuration
- Tests config reload mechanisms
- Simulates deployment scenarios

```json
{
  "type": "action",
  "name": "increase-timeout",
  "provider": {
    "type": "python",
    "module": "chaosapp.actions",
    "func": "modify_configuration",
    "arguments": {
      "service_name": "my-service",
      "config_key": "request_timeout_ms",
      "new_value": 1000,
      "duration_seconds": 60
    }
  }
}
```

---

## Probes

### Health Checks

**api_is_healthy**
```json
{
  "type": "probe",
  "name": "check-health",
  "provider": {
    "type": "python",
    "module": "chaosapp.probes",
    "func": "api_is_healthy",
    "arguments": {
      "url": "http://api.example.com/health",
      "timeout": 5,
      "expected_status": 200
    }
  }
}
```

**service_is_responsive**
```json
{
  "type": "probe",
  "name": "check-responsiveness",
  "provider": {
    "type": "python",
    "module": "chaosapp.probes",
    "func": "service_is_responsive",
    "arguments": {
      "service_name": "my-service",
      "max_latency_ms": 1000,
      "sample_size": 10
    }
  }
}
```

### Metrics Collection

**collect_request_metrics**
```json
{
  "type": "probe",
  "name": "collect-metrics",
  "provider": {
    "type": "python",
    "module": "chaosapp.probes",
    "func": "collect_request_metrics",
    "arguments": {
      "url": "http://api.example.com",
      "metric_names": ["request_latency", "error_rate"],
      "duration_seconds": 10
    }
  }
}
```

---

## Configuration

### Environment Variables

```bash
# Chaos Parameters
APP_CHAOS_INTENSITY=0.5           # Percentage of requests affected (0-1)
APP_CHAOS_DURATION_SECONDS=60     # How long to inject chaos
APP_REQUEST_TIMEOUT_MS=5000        # Request timeout in milliseconds
APP_RETRY_ATTEMPTS=3               # Max retries for failed requests

# API Configuration
APP_API_URL=http://localhost:5000  # Target API endpoint
APP_API_TIMEOUT=10                 # API timeout in seconds
APP_API_POOL_SIZE=10               # Connection pool size

# Observability
OTEL_SERVICE_NAME=app-chaos-test
OTEL_EXPORTER_OTLP_ENDPOINT=http://otel-collector:4317
```

### .env.example

```bash
# Application API
export APP_API_URL=http://localhost:5000
export APP_API_TIMEOUT=10
export APP_API_POOL_SIZE=10

# Chaos Parameters
export APP_CHAOS_INTENSITY=0.5
export APP_CHAOS_DURATION_SECONDS=60
export APP_REQUEST_TIMEOUT_MS=5000
export APP_RETRY_ATTEMPTS=3

# Observability
export OTEL_SERVICE_NAME=app-chaos-test
export OTEL_EXPORTER_OTLP_ENDPOINT=http://otel-collector:4317
export OTEL_EXPORTER_OTLP_PROTOCOL=http/protobuf
```

---

## Examples

### Example 1: HTTP Timeout Handling

**File:** `app-http-timeout-test.json`

Tests how the application handles slow HTTP responses:

```json
{
  "version": "1.0",
  "title": "HTTP Timeout Resilience",
  "description": "Test application timeout handling with 5 second delays",
  
  "configuration": {
    "api_url": {
      "type": "env",
      "key": "APP_API_URL",
      "default": "http://localhost:5000"
    }
  },
  
  "controls": [
    {
      "name": "experiment-orchestrator",
      "provider": {"type": "python", "module": "chaosgeneric.control.experiment_orchestrator_control"}
    },
    {
      "name": "env-loader",
      "provider": {"type": "python", "module": "chaosgeneric.control.env_loader_control"}
    }
  ],
  
  "steady-state-hypothesis": {
    "title": "API is responsive",
    "probes": [
      {
        "type": "probe",
        "name": "health-check",
        "provider": {
          "type": "python",
          "module": "chaosapp.probes",
          "func": "api_is_healthy",
          "arguments": {"url": "${api_url}/health"}
        }
      }
    ]
  },
  
  "method": [
    {
      "type": "action",
      "name": "add-latency",
      "provider": {
        "type": "python",
        "module": "chaosapp.actions",
        "func": "inject_response_latency",
        "arguments": {
          "url": "${api_url}",
          "latency_ms": 5000,
          "percentage": 100,
          "duration_seconds": 60
        }
      }
    }
  ],
  
  "rollbacks": [
    {
      "type": "action",
      "name": "restore-normal-latency",
      "provider": {
        "type": "python",
        "module": "chaosapp.actions",
        "func": "stop_latency_injection",
        "arguments": {"url": "${api_url}"}
      }
    }
  ]
}
```

**Run it:**
```bash
chaos run app-http-timeout-test.json
```

### Example 2: Error Injection

Test error handling:

```json
{
  "method": [
    {
      "type": "action",
      "name": "inject-500-errors",
      "provider": {
        "type": "python",
        "module": "chaosapp.actions",
        "func": "inject_request_errors",
        "arguments": {
          "url": "${api_url}",
          "error_codes": [500],
          "percentage": 10,
          "duration_seconds": 60
        }
      }
    }
  ]
}
```

### Example 3: Session Disruption

Test session recovery:

```json
{
  "method": [
    {
      "type": "action",
      "name": "kill-sessions",
      "provider": {
        "type": "python",
        "module": "chaosapp.actions",
        "func": "kill_active_sessions",
        "arguments": {
          "service_name": "my-service",
          "session_type": "http",
          "percentage": 20
        }
      }
    }
  ]
}
```

---

## Troubleshooting

### "Connection refused"

**Problem:** Cannot connect to target API

**Solution:**
```bash
# Verify API is running
curl http://localhost:5000/health

# Check environment variable
echo $APP_API_URL

# Test connectivity
curl -I ${APP_API_URL}/health
```

### "No metrics collected"

**Problem:** Metrics not being recorded during experiment

**Solution:**
1. Verify OpenTelemetry is initialized
2. Check `OTEL_EXPORTER_OTLP_ENDPOINT` is reachable
3. Verify `OTEL_SERVICE_NAME` is set
4. Check logs: `docker compose logs otel-collector`

### "Chaos action failed"

**Problem:** Action execution error

**Solution:**
```bash
# Enable debug logging
export OTEL_LOG_LEVEL=DEBUG
chaos run experiment.json

# Check Chaos Toolkit logs
tail -f chaostoolkit.log
```

---

## Advanced Usage

### Custom Error Handlers

```python
from chaosapp.actions import inject_request_errors
from chaosapp.handlers import ErrorHandler

class CustomErrorHandler(ErrorHandler):
    def handle_error(self, error_code: int, context: dict):
        # Custom logic for specific errors
        pass

# Use in action
inject_request_errors(
    url="http://api.example.com",
    error_codes=[500],
    handler=CustomErrorHandler()
)
```

### Integration with Load Testing

```json
{
  "controls": [
    {
      "name": "load-generator",
      "provider": {
        "type": "python",
        "module": "chaosgeneric.control.load_generator_control",
        "arguments": {
          "load_type": "http",
          "target_url": "${api_url}",
          "threads": 10,
          "requests_per_second": 100
        }
      }
    }
  ]
}
```

### CI/CD Integration

```yaml
name: App Chaos Tests
on: [push]
jobs:
  chaos:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - name: Start application
        run: docker run -d -p 5000:5000 myapp:latest
      - name: Run chaos experiment
        run: |
          pip install chaostoolkit chaostooling-extension-app
          chaos run app-http-timeout-test.json
      - name: Check results
        if: always()
        run: |
          cat journal.json | jq '.status'
```

---

## See Also

- [Main README](../README.md) - Project overview
- [chaostooling-otel](../chaostooling-otel/README.md) - Observability
- [chaostooling-extension-db](../chaostooling-extension-db/README.md) - Database chaos
- [chaostooling-extension-network](../chaostooling-extension-network/README.md) - Network chaos

---

**Last Updated:** January 30, 2026  
**Version:** 0.1.0  
**Status:** Production Ready
