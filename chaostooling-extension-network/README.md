# ChaosTooling Extension Network

**Network Chaos Engineering Extension for Chaos Toolkit**

Test network resilience by injecting latency, packet loss, bandwidth limits, and DNS failures. Fully instrumented with OpenTelemetry for complete observability.

[![Python Version](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/downloads/)
[![Chaos Toolkit](https://img.shields.io/badge/chaos--toolkit-compatible-green.svg)](https://chaostoolkit.org/)
[![OpenTelemetry](https://img.shields.io/badge/opentelemetry-instrumented-orange.svg)](https://opentelemetry.io/)

---

## Overview

ChaosTooling Extension Network enables realistic network failure testing to validate application resilience. Test how your systems handle:

- **Latency** - Network delays and slow connections
- **Jitter** - Variable delays and packet variance
- **Packet Loss** - Dropped or corrupted packets
- **Bandwidth Limits** - Rate limiting and saturation
- **DNS Failures** - DNS lookup timeouts and errors
- **Connection Drops** - Sudden connection termination
- **Reordering** - Out-of-order packet delivery

### Key Features

✅ **Latency Injection** - Precise per-interface delays
✅ **Packet Loss Simulation** - Random or targeted packet drops
✅ **Bandwidth Throttling** - Rate limiting via tc (traffic control)
✅ **DNS Chaos** - Query failure injection
✅ **Connection Management** - Drop/reset active connections
✅ **Full Observability** - Every network action traced via OpenTelemetry
✅ **Automatic Cleanup** - Revert all network changes after experiment

---

## Installation

### Prerequisites

- Python 3.10+
- Chaos Toolkit 1.42.1+
- Linux with tc (traffic control) installed
- Root/sudo access for network manipulation

### Install Package

```bash
pip install chaostooling-extension-network
```

### Install Dependencies

```bash
# Ubuntu/Debian
sudo apt-get install iproute2 net-tools iputils-ping

# RHEL/CentOS
sudo yum install iproute net-tools iputils
```

### Install from Source

```bash
cd chaostooling-extension-network
pip install -e .
```

---

## Quick Start

### 1. Latency Injection

```json
{
  "version": "1.0",
  "title": "Network Latency Test",
  "description": "Inject 500ms latency on eth0",
  
  "configuration": {
    "network_interface": {
      "type": "env",
      "key": "NETWORK_INTERFACE",
      "default": "eth0"
    }
  },
  
  "controls": [
    {
      "name": "experiment-orchestrator",
      "provider": {
        "type": "python",
        "module": "chaosgeneric.control.experiment_orchestrator_control"
      }
    }
  ],
  
  "steady-state-hypothesis": {
    "title": "Network is responsive",
    "probes": [
      {
        "type": "probe",
        "name": "network-latency-baseline",
        "provider": {
          "type": "python",
          "module": "chaosnetwork.probes",
          "func": "network_latency_is_normal",
          "arguments": {
            "target": "8.8.8.8",
            "max_latency_ms": 100
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
        "module": "chaosnetwork.actions",
        "func": "inject_latency",
        "arguments": {
          "interface": "${network_interface}",
          "latency_ms": 500,
          "jitter_ms": 50,
          "duration_seconds": 300
        }
      }
    }
  ]
}
```

### 2. Run Experiment

```bash
export NETWORK_INTERFACE=eth0
export OTEL_SERVICE_NAME=network-chaos-test

sudo chaos run network-latency-test.json
```

---

## Actions

### Latency & Jitter

**inject_latency**
- Add fixed delay to network packets
- Optional jitter for variance
- Tests timeout and retry behavior

```json
{
  "type": "action",
  "name": "add-delay",
  "provider": {
    "type": "python",
    "module": "chaosnetwork.actions",
    "func": "inject_latency",
    "arguments": {
      "interface": "eth0",
      "latency_ms": 500,
      "jitter_ms": 100,
      "target": "10.0.0.0/24",
      "duration_seconds": 300
    }
  }
}
```

**inject_jitter**
- Add random variance to delays
- Simulates unreliable networks
- Tests time-sensitive operations

```json
{
  "type": "action",
  "name": "add-jitter",
  "provider": {
    "type": "python",
    "module": "chaosnetwork.actions",
    "func": "inject_jitter",
    "arguments": {
      "interface": "eth0",
      "jitter_ms": 200,
      "duration_seconds": 300
    }
  }
}
```

### Packet Loss

**inject_packet_loss**
- Drop packets randomly
- Simulates unreliable links
- Tests retransmission logic

```json
{
  "type": "action",
  "name": "drop-packets",
  "provider": {
    "type": "python",
    "module": "chaosnetwork.actions",
    "func": "inject_packet_loss",
    "arguments": {
      "interface": "eth0",
      "loss_percent": 10,
      "target": "10.0.0.0/24",
      "duration_seconds": 300
    }
  }
}
```

**inject_packet_corruption**
- Corrupt packets (toggle bits)
- Tests checksum validation
- Simulates data corruption

```json
{
  "type": "action",
  "name": "corrupt-packets",
  "provider": {
    "type": "python",
    "module": "chaosnetwork.actions",
    "func": "inject_packet_corruption",
    "arguments": {
      "interface": "eth0",
      "corruption_percent": 5,
      "duration_seconds": 300
    }
  }
}
```

### Bandwidth Control

**limit_bandwidth**
- Rate limit traffic
- Simulates slow connections
- Tests backpressure handling

```json
{
  "type": "action",
  "name": "throttle-bandwidth",
  "provider": {
    "type": "python",
    "module": "chaosnetwork.actions",
    "func": "limit_bandwidth",
    "arguments": {
      "interface": "eth0",
      "bandwidth_mbps": 10,
      "target": "10.0.0.0/24",
      "duration_seconds": 300
    }
  }
}
```

**fill_bandwidth**
- Saturate available bandwidth
- Background traffic generation
- Tests throughput limits

```json
{
  "type": "action",
  "name": "saturate-bandwidth",
  "provider": {
    "type": "python",
    "module": "chaosnetwork.actions",
    "func": "fill_bandwidth",
    "arguments": {
      "interface": "eth0",
      "target": "1.1.1.1",
      "duration_seconds": 300
    }
  }
}
```

### DNS Chaos

**inject_dns_failure**
- Make DNS lookups fail
- Tests DNS error handling
- Validates fallback logic

```json
{
  "type": "action",
  "name": "dns-failure",
  "provider": {
    "type": "python",
    "module": "chaosnetwork.actions",
    "func": "inject_dns_failure",
    "arguments": {
      "target_domains": ["example.com", "api.example.com"],
      "duration_seconds": 300
    }
  }
}
```

**inject_dns_latency**
- Slow DNS resolution
- Tests DNS timeout handling
- Simulates overloaded DNS

```json
{
  "type": "action",
  "name": "dns-latency",
  "provider": {
    "type": "python",
    "module": "chaosnetwork.actions",
    "func": "inject_dns_latency",
    "arguments": {
      "latency_ms": 5000,
      "duration_seconds": 300
    }
  }
}
```

### Connection Management

**drop_connections**
- Forcefully close active connections
- Tests reconnection logic
- Simulates network resets

```json
{
  "type": "action",
  "name": "drop-conns",
  "provider": {
    "type": "python",
    "module": "chaosnetwork.actions",
    "func": "drop_connections",
    "arguments": {
      "interface": "eth0",
      "target": "10.0.0.0/24",
      "protocol": "tcp"
    }
  }
}
```

**reset_connections**
- Send RST packets
- Tests graceful connection handling
- Simulates network resets

```json
{
  "type": "action",
  "name": "reset-conns",
  "provider": {
    "type": "python",
    "module": "chaosnetwork.actions",
    "func": "reset_connections",
    "arguments": {
      "interface": "eth0",
      "target_port": 443
    }
  }
}
```

---

## Probes

### Network Health

**network_latency_is_normal**
```json
{
  "type": "probe",
  "name": "check-latency",
  "provider": {
    "type": "python",
    "module": "chaosnetwork.probes",
    "func": "network_latency_is_normal",
    "arguments": {
      "target": "8.8.8.8",
      "max_latency_ms": 100,
      "sample_count": 10
    }
  }
}
```

**dns_is_responsive**
```json
{
  "type": "probe",
  "name": "check-dns",
  "provider": {
    "type": "python",
    "module": "chaosnetwork.probes",
    "func": "dns_is_responsive",
    "arguments": {
      "nameserver": "8.8.8.8",
      "timeout_seconds": 5
    }
  }
}
```

**bandwidth_is_available**
```json
{
  "type": "probe",
  "name": "check-bandwidth",
  "provider": {
    "type": "python",
    "module": "chaosnetwork.probes",
    "func": "bandwidth_is_available",
    "arguments": {
      "interface": "eth0",
      "min_bandwidth_mbps": 100
    }
  }
}
```

### Metrics Collection

**collect_network_metrics**
```json
{
  "type": "probe",
  "name": "collect-metrics",
  "provider": {
    "type": "python",
    "module": "chaosnetwork.probes",
    "func": "collect_network_metrics",
    "arguments": {
      "interface": "eth0",
      "duration_seconds": 10
    }
  }
}
```

---

## Configuration

### Environment Variables

```bash
# Network Interface
NETWORK_INTERFACE=eth0
NETWORK_TARGET=10.0.0.0/24

# Chaos Parameters
NETWORK_LATENCY_MS=500
NETWORK_JITTER_MS=50
NETWORK_PACKET_LOSS_PERCENT=5
NETWORK_BANDWIDTH_MBPS=100
NETWORK_CHAOS_DURATION_SECONDS=300

# DNS
DNS_NAMESERVER=8.8.8.8
DNS_TIMEOUT_SECONDS=5

# Observability
OTEL_SERVICE_NAME=network-chaos-test
OTEL_EXPORTER_OTLP_ENDPOINT=http://otel-collector:4317
```

### .env.example

```bash
# Network Configuration
export NETWORK_INTERFACE=eth0
export NETWORK_TARGET=10.0.0.0/24

# Chaos Parameters
export NETWORK_LATENCY_MS=500
export NETWORK_JITTER_MS=50
export NETWORK_PACKET_LOSS_PERCENT=5
export NETWORK_BANDWIDTH_MBPS=100
export NETWORK_CHAOS_DURATION_SECONDS=300

# DNS Configuration
export DNS_NAMESERVER=8.8.8.8
export DNS_TIMEOUT_SECONDS=5

# Observability
export OTEL_SERVICE_NAME=network-chaos-test
export OTEL_EXPORTER_OTLP_ENDPOINT=http://otel-collector:4317
```

---

## Examples

### Example 1: High Latency Test

```json
{
  "version": "1.0",
  "title": "High Latency Resilience",
  "description": "Test with 1 second latency",
  
  "method": [
    {
      "type": "action",
      "name": "inject-1s-latency",
      "provider": {
        "type": "python",
        "module": "chaosnetwork.actions",
        "func": "inject_latency",
        "arguments": {
          "interface": "eth0",
          "latency_ms": 1000,
          "duration_seconds": 300
        }
      }
    }
  ]
}
```

### Example 2: Packet Loss Scenario

```json
{
  "method": [
    {
      "type": "action",
      "name": "packet-loss",
      "provider": {
        "type": "python",
        "module": "chaosnetwork.actions",
        "func": "inject_packet_loss",
        "arguments": {
          "interface": "eth0",
          "loss_percent": 25,
          "duration_seconds": 300
        }
      }
    }
  ]
}
```

### Example 3: Bandwidth Limit

```json
{
  "method": [
    {
      "type": "action",
      "name": "limit-bandwidth",
      "provider": {
        "type": "python",
        "module": "chaosnetwork.actions",
        "func": "limit_bandwidth",
        "arguments": {
          "interface": "eth0",
          "bandwidth_mbps": 5,
          "duration_seconds": 300
        }
      }
    }
  ]
}
```

---

## Troubleshooting

### "Permission denied" or "Operation not permitted"

**Problem:** Network manipulation requires root

**Solution:**
```bash
# Run with sudo
sudo chaos run network-chaos-test.json

# Or use Docker
docker run --privileged chaostoolkit chaos run network-chaos-test.json
```

### "interface not found"

**Problem:** Specified network interface doesn't exist

**Solution:**
```bash
# List available interfaces
ip link show

# Update experiment with correct interface
export NETWORK_INTERFACE=eth1
```

### "tc command not found"

**Problem:** Traffic control (tc) not installed

**Solution:**
```bash
# Install iproute2
sudo apt-get install iproute2

# Or on RHEL/CentOS
sudo yum install iproute
```

### "Chaos not applying"

**Problem:** Network changes not taking effect

**Solution:**
```bash
# Check tc rules
tc qdisc show dev eth0

# Verify interface is up
ip link show eth0

# Check iptables rules
sudo iptables -L -n -v
```

---

## Advanced Usage

### Custom Network Profiles

```python
from chaosnetwork.actions import inject_latency
from chaosnetwork.profiles import NetworkProfile

class HighLatencyWiFi(NetworkProfile):
    latency_ms = 150
    jitter_ms = 80
    loss_percent = 2

profile = HighLatencyWiFi()
inject_latency(interface="eth0", profile=profile)
```

### Selective Targeting

```python
# Only affect traffic to specific IP ranges
inject_latency(
    interface="eth0",
    target="10.0.0.0/24",  # Only to 10.0.0.0/24
    latency_ms=500
)

# Only specific protocol
inject_packet_loss(
    interface="eth0",
    protocol="tcp",  # Only TCP, not UDP
    loss_percent=10
)
```

---

## See Also

- [Main README](../README.md) - Project overview
- [chaostooling-otel](../chaostooling-otel/README.md) - Observability
- [chaostooling-extension-db](../chaostooling-extension-db/README.md) - Database chaos
- [chaostooling-extension-compute](../chaostooling-extension-compute/README.md) - Compute chaos

---

**Last Updated:** January 30, 2026  
**Version:** 0.1.0  
**Status:** Production Ready
