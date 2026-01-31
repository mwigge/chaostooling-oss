# ChaosTooling Extension Compute

**CPU, Memory, and System Resource Chaos Extension for Chaos Toolkit**

Test how applications handle resource constraints, CPU spikes, memory exhaustion, and I/O limits. Fully instrumented with OpenTelemetry for complete observability.

[![Python Version](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/downloads/)
[![Chaos Toolkit](https://img.shields.io/badge/chaos--toolkit-compatible-green.svg)](https://chaostoolkit.org/)
[![OpenTelemetry](https://img.shields.io/badge/opentelemetry-instrumented-orange.svg)](https://opentelemetry.io/)

---

## Overview

ChaosTooling Extension Compute enables resource-level chaos testing to validate application behavior under degraded conditions. Test how your systems handle:

- **CPU Spikes** - High CPU load from background processes
- **Memory Exhaustion** - Out of memory conditions
- **Disk I/O Saturation** - Slow disk operations
- **Process Limits** - Max process creation limits
- **File Descriptor Limits** - Open file limits
- **Context Switching** - High context switch overhead

### Key Features

✅ **CPU Load Injection** - Spike CPU usage on specific cores
✅ **Memory Stress Testing** - Exhaust available memory
✅ **Disk I/O Chaos** - Saturate disk operations
✅ **Process Limits** - Hit ulimit boundaries
✅ **Real-Time Monitoring** - Track resource usage via Prometheus
✅ **Full Observability** - Every resource action traced via OpenTelemetry
✅ **Graceful Cleanup** - Automatic resource release after experiments

---

## Installation

### Prerequisites

- Python 3.10+
- Chaos Toolkit 1.42.1+
- psutil for system monitoring
- Linux/macOS (tested on kernel 5.10+)

### Install Package

```bash
pip install chaostooling-extension-compute
```

### Install from Source

```bash
cd chaostooling-extension-compute
pip install -e .
```

---

## Quick Start

### 1. CPU Spike Test

```json
{
  "version": "1.0",
  "title": "CPU Spike Resilience",
  "description": "Test application under CPU load",
  
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
    "title": "System CPU is normal",
    "probes": [
      {
        "type": "probe",
        "name": "cpu-baseline",
        "provider": {
          "type": "python",
          "module": "chaoscompute.probes",
          "func": "cpu_usage_is_normal",
          "arguments": {
            "max_cpu_percent": 30
          }
        }
      }
    ]
  },
  
  "method": [
    {
      "type": "action",
      "name": "spike-cpu",
      "provider": {
        "type": "python",
        "module": "chaoscompute.actions",
        "func": "spike_cpu",
        "arguments": {
          "cpu_cores": 2,
          "load_percent": 80,
          "duration_seconds": 60
        }
      }
    }
  ]
}
```

### 2. Run Experiment

```bash
export OTEL_SERVICE_NAME=compute-chaos-test
export OTEL_EXPORTER_OTLP_ENDPOINT=http://otel-collector:4317

chaos run cpu-spike-test.json
```

---

## Actions

### CPU Operations

**spike_cpu**
- Inject CPU load on specified cores
- Tests performance under high CPU
- Validates scaling logic

```json
{
  "type": "action",
  "name": "cpu-load",
  "provider": {
    "type": "python",
    "module": "chaoscompute.actions",
    "func": "spike_cpu",
    "arguments": {
      "cpu_cores": 4,
      "load_percent": 90,
      "duration_seconds": 300
    }
  }
}
```

**context_switch_load**
- Create high context switching overhead
- Simulates many competing processes
- Tests scheduler efficiency

```json
{
  "type": "action",
  "name": "context-switching",
  "provider": {
    "type": "python",
    "module": "chaoscompute.actions",
    "func": "context_switch_load",
    "arguments": {
      "num_processes": 100,
      "duration_seconds": 60
    }
  }
}
```

### Memory Operations

**exhaust_memory**
- Allocate increasing amounts of memory
- Test OOM killer behavior
- Validate memory cleanup

```json
{
  "type": "action",
  "name": "memory-stress",
  "provider": {
    "type": "python",
    "module": "chaoscompute.actions",
    "func": "exhaust_memory",
    "arguments": {
      "memory_amount": "500M",
      "allocation_rate_mb_per_sec": 100,
      "duration_seconds": 60
    }
  }
}
```

**fragment_memory**
- Create memory fragmentation
- Tests GC efficiency
- Simulates heap fragmentation

```json
{
  "type": "action",
  "name": "memory-fragmentation",
  "provider": {
    "type": "python",
    "module": "chaoscompute.actions",
    "func": "fragment_memory",
    "arguments": {
      "fragment_size_kb": 4,
      "num_fragments": 10000,
      "duration_seconds": 60
    }
  }
}
```

### Disk I/O Operations

**saturate_disk_io**
- Generate heavy disk I/O load
- Tests storage performance
- Validates disk limits

```json
{
  "type": "action",
  "name": "disk-io-load",
  "provider": {
    "type": "python",
    "module": "chaoscompute.actions",
    "func": "saturate_disk_io",
    "arguments": {
      "disk_path": "/",
      "io_threads": 8,
      "io_size_kb": 4096,
      "duration_seconds": 60
    }
  }
}
```

**fill_disk**
- Fill disk to capacity
- Tests disk full scenarios
- Validates error handling

```json
{
  "type": "action",
  "name": "fill-disk",
  "provider": {
    "type": "python",
    "module": "chaoscompute.actions",
    "func": "fill_disk",
    "arguments": {
      "disk_path": "/tmp",
      "fill_percent": 90,
      "file_size_mb": 100
    }
  }
}
```

### Process Limits

**hit_process_limit**
- Create many processes until limit reached
- Tests `ulimit -u` behavior
- Validates process pool sizing

```json
{
  "type": "action",
  "name": "process-limit",
  "provider": {
    "type": "python",
    "module": "chaoscompute.actions",
    "func": "hit_process_limit",
    "arguments": {
      "process_count": 500
    }
  }
}
```

**exhaust_file_descriptors**
- Open files until limit reached
- Tests `ulimit -n` behavior
- Validates connection pooling

```json
{
  "type": "action",
  "name": "fd-exhaustion",
  "provider": {
    "type": "python",
    "module": "chaoscompute.actions",
    "func": "exhaust_file_descriptors",
    "arguments": {
      "fd_count": 8000
    }
  }
}
```

---

## Probes

### Resource Monitoring

**cpu_usage_is_normal**
```json
{
  "type": "probe",
  "name": "check-cpu",
  "provider": {
    "type": "python",
    "module": "chaoscompute.probes",
    "func": "cpu_usage_is_normal",
    "arguments": {
      "max_cpu_percent": 50,
      "sample_count": 5
    }
  }
}
```

**memory_usage_is_normal**
```json
{
  "type": "probe",
  "name": "check-memory",
  "provider": {
    "type": "python",
    "module": "chaoscompute.probes",
    "func": "memory_usage_is_normal",
    "arguments": {
      "max_memory_percent": 80,
      "sample_count": 5
    }
  }
}
```

**disk_io_is_normal**
```json
{
  "type": "probe",
  "name": "check-disk-io",
  "provider": {
    "type": "python",
    "module": "chaoscompute.probes",
    "func": "disk_io_is_normal",
    "arguments": {
      "max_io_percent": 70,
      "disk_path": "/"
    }
  }
}
```

### Metrics Collection

**get_cpu_metrics**
```json
{
  "type": "probe",
  "name": "collect-cpu-metrics",
  "provider": {
    "type": "python",
    "module": "chaoscompute.probes",
    "func": "get_cpu_metrics",
    "arguments": {
      "sample_duration_seconds": 10
    }
  }
}
```

---

## Configuration

### Environment Variables

```bash
# Resource Limits
COMPUTE_CPU_CORES=4
COMPUTE_MEMORY_GB=16
COMPUTE_DISK_GB=100

# Chaos Parameters
COMPUTE_CPU_LOAD_PERCENT=80
COMPUTE_MEMORY_STRESS_MB=2000
COMPUTE_DISK_IO_THREADS=8
COMPUTE_CHAOS_DURATION_SECONDS=60

# Observability
OTEL_SERVICE_NAME=compute-chaos-test
OTEL_EXPORTER_OTLP_ENDPOINT=http://otel-collector:4317
```

### .env.example

```bash
# System Resources
export COMPUTE_CPU_CORES=4
export COMPUTE_MEMORY_GB=16
export COMPUTE_DISK_GB=100

# Chaos Intensity
export COMPUTE_CPU_LOAD_PERCENT=80
export COMPUTE_MEMORY_STRESS_MB=2000
export COMPUTE_DISK_IO_THREADS=8
export COMPUTE_CHAOS_DURATION_SECONDS=60

# Observability
export OTEL_SERVICE_NAME=compute-chaos-test
export OTEL_EXPORTER_OTLP_ENDPOINT=http://otel-collector:4317
```

---

## Examples

### Example 1: CPU Spike Under Load

```json
{
  "version": "1.0",
  "title": "CPU Spike Handling",
  "description": "Test app behavior when CPU spikes to 90%",
  
  "method": [
    {
      "type": "action",
      "name": "spike-cpu-to-90",
      "provider": {
        "type": "python",
        "module": "chaoscompute.actions",
        "func": "spike_cpu",
        "arguments": {
          "cpu_cores": 4,
          "load_percent": 90,
          "duration_seconds": 300
        }
      }
    }
  ]
}
```

### Example 2: Memory Exhaustion

```json
{
  "method": [
    {
      "type": "action",
      "name": "exhaust-memory",
      "provider": {
        "type": "python",
        "module": "chaoscompute.actions",
        "func": "exhaust_memory",
        "arguments": {
          "memory_amount": "8GB",
          "allocation_rate_mb_per_sec": 500,
          "duration_seconds": 120
        }
      }
    }
  ]
}
```

### Example 3: Disk I/O Saturation

```json
{
  "method": [
    {
      "type": "action",
      "name": "saturate-disk-io",
      "provider": {
        "type": "python",
        "module": "chaoscompute.actions",
        "func": "saturate_disk_io",
        "arguments": {
          "disk_path": "/",
          "io_threads": 16,
          "io_size_kb": 8192,
          "duration_seconds": 180
        }
      }
    }
  ]
}
```

---

## Troubleshooting

### "Permission denied"

**Problem:** Cannot inject resources (requires root)

**Solution:**
```bash
# Run with sudo
sudo chaos run cpu-spike-test.json

# Or use Docker
docker run --privileged -v $(pwd):/workspace chaostoolkit chaos run /workspace/cpu-spike-test.json
```

### "No metrics collected"

**Problem:** Prometheus metrics not appearing

**Solution:**
1. Verify Prometheus scrape config includes compute metrics
2. Check OTEL_EXPORTER_OTLP_ENDPOINT is reachable
3. View logs: `docker compose logs prometheus`

### "OOM killer terminated process"

**Problem:** Application crashed during memory stress

**Solution:**
- This is expected behavior; verify crash is handled gracefully
- Reduce `memory_amount` or increase `duration_seconds`
- Check application logs for OOM handling

---

## Advanced Usage

### Custom CPU Load Generators

```python
from chaoscompute.actions import spike_cpu
from chaoscompute.generators import CPULoadGenerator

class CustomCPULoad(CPULoadGenerator):
    def generate_load(self):
        # Custom workload logic
        pass

spike_cpu(cpu_cores=4, load_percent=80, generator=CustomCPULoad())
```

### Resource Monitoring

```python
from chaoscompute.probes import get_cpu_metrics, get_memory_metrics

# Collect detailed metrics
cpu_metrics = get_cpu_metrics(sample_duration_seconds=30)
mem_metrics = get_memory_metrics(sample_duration_seconds=30)

print(f"CPU: {cpu_metrics}")
print(f"Memory: {mem_metrics}")
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
