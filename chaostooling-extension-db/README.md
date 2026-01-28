# ChaosTooling Extension DB

**Database and Messaging Chaos Engineering Extension for Chaos Toolkit**

A comprehensive chaos engineering extension providing 60+ chaos actions and 60+ health probes for testing resilience of databases and messaging systems. Fully instrumented with OpenTelemetry for distributed tracing, metrics, and logging.

[![Python Version](https://img.shields.io/badge/python-3.9%2B-blue.svg)](https://www.python.org/downloads/)
[![Chaos Toolkit](https://img.shields.io/badge/chaos--toolkit-compatible-green.svg)](https://chaostoolkit.org/)
[![OpenTelemetry](https://img.shields.io/badge/opentelemetry-instrumented-orange.svg)](https://opentelemetry.io/)

---

## Table of Contents

- [Overview](#overview)
- [Architecture](#architecture)
- [Supported Systems](#supported-systems)
- [Chaos Actions](#chaos-actions)
- [Health Probes](#health-probes)
- [Observability](#observability)
- [Installation](#installation)
- [Quick Start](#quick-start)
- [Configuration](#configuration)
- [Examples](#examples)
- [Development](#development)

---

## Overview

ChaosTooling Extension DB enables platform teams to validate database and messaging system resilience through controlled chaos experiments. Test how your systems behave under:

- **Connection pool exhaustion** - Verify graceful degradation when connections are maxed out
- **Query saturation** - Test performance under high query load
- **Lock storms** - Validate deadlock detection and recovery
- **Slow transactions** - Test timeout and retry logic
- **Message floods** - Verify messaging system backpressure handling
- **Replication lag** - Test failover and consistency scenarios

### Key Features

✅ **9 Database & Messaging Systems** - PostgreSQL, MySQL, MSSQL, MongoDB, Redis, Cassandra, Kafka, RabbitMQ, ActiveMQ
✅ **60+ Chaos Actions** - Connection, query, transaction, lock, and messaging chaos scenarios
✅ **60+ Health Probes** - Real-time monitoring of database metrics and messaging queue status
✅ **Full Observability** - Every action/probe traced, metered, and logged via OpenTelemetry
✅ **Thread-Safe Parallelism** - Realistic load generation with multi-threaded execution
✅ **Graceful Cleanup** - Built-in rollback actions for safe chaos termination
✅ **Environment-Based Config** - Flexible configuration via environment variables or direct parameters

---

## Architecture

### High-Level Component Architecture

```
┌──────────────────────────────────────────────────────────────────────┐
│                    Chaos Toolkit Experiment                          │
│         (experiment.json with actions/probes/rollbacks)              │
└────────────────────────────┬─────────────────────────────────────────┘
                             │
                             ▼
┌──────────────────────────────────────────────────────────────────────┐
│                  chaostooling-extension-db                           │
│                                                                      │
│  ┌────────────────┐  ┌────────────────┐  ┌──────────────────┐      │
│  │    ACTIONS     │  │    PROBES      │  │     COMMON       │      │
│  │  (Inject Chaos)│  │  (Monitor)     │  │  (Shared Utils)  │      │
│  ├────────────────┤  ├────────────────┤  ├──────────────────┤      │
│  │ • postgres/    │  │ • postgres/    │  │ • connection.py  │      │
│  │ • mysql/       │  │ • mysql/       │  │ • validation.py  │      │
│  │ • mssql/       │  │ • mssql/       │  │ • constants.py   │      │
│  │ • mongodb/     │  │ • mongodb/     │  │                  │      │
│  │ • redis/       │  │ • redis/       │  │ Factories for:   │      │
│  │ • cassandra/   │  │ • cassandra/   │  │ - Connections    │      │
│  │ • kafka/       │  │ • kafka/       │  │ - Validation     │      │
│  │ • rabbitmq/    │  │ • rabbitmq/    │  │ - Defaults       │      │
│  │ • activemq/    │  │ • activemq/    │  │                  │      │
│  └────────┬───────┘  └────────┬───────┘  └────────┬─────────┘      │
│           │                   │                    │                │
│           └───────────────────┴────────────────────┘                │
│                               │                                     │
│                               │ Every action/probe calls:           │
│                               │ - ensure_initialized()              │
│                               │ - get_tracer()                      │
│                               │ - get_metrics_core()                │
│                               │ - flush()                           │
└───────────────────────────────┼─────────────────────────────────────┘
                                │
                                ▼
┌──────────────────────────────────────────────────────────────────────┐
│              chaostooling-otel (Observability Layer)                 │
│                                                                      │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐             │
│  │   TRACING    │  │   METRICS    │  │   LOGGING    │             │
│  │              │  │              │  │              │             │
│  │ • Spans for  │  │ • Query      │  │ • Structured │             │
│  │   all ops    │  │   latency    │  │   logs       │             │
│  │ • Nested     │  │ • Connection │  │ • Error      │             │
│  │   worker     │  │   pool usage │  │   tracking   │             │
│  │   spans      │  │ • Slow query │  │ • Context    │             │
│  │ • DB attrs   │  │   counts     │  │   propagation│             │
│  │ • Service    │  │ • Error      │  │              │             │
│  │   graph      │  │   rates      │  │              │             │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘             │
│         │                 │                  │                     │
│         └─────────────────┴──────────────────┘                     │
│                           │                                        │
│                  OTLP Exporter                                     │
└───────────────────────────┼────────────────────────────────────────┘
                            │
                            ▼
┌──────────────────────────────────────────────────────────────────────┐
│                  Observability Backend                               │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐             │
│  │   Tempo      │  │  Prometheus  │  │     Loki     │             │
│  │  (Traces)    │  │  (Metrics)   │  │    (Logs)    │             │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘             │
│         │                 │                  │                     │
│         └─────────────────┴──────────────────┘                     │
│                           │                                        │
│                    ┌──────▼───────┐                                │
│                    │   Grafana    │                                │
│                    │ (Dashboards) │                                │
│                    └──────────────┘                                │
└──────────────────────────────────────────────────────────────────────┘
```

### Action Execution Flow

```
┌─────────────────────────────────────────────────────────────────────┐
│  1. Chaos Toolkit invokes action function                          │
│     (e.g., postgres_pool_exhaustion)                                │
└────────────────┬────────────────────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────────────────────────┐
│  2. Validate parameters (chaosdb/common/validation.py)             │
│     - Port ranges, timeouts, connection counts                      │
│     - Host/database name sanitization                               │
│     - SQL injection prevention                                      │
└────────────────┬────────────────────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────────────────────────┐
│  3. Initialize OpenTelemetry (ensure_initialized)                   │
│     - Set up trace provider                                         │
│     - Configure metric exporters                                    │
│     - Initialize logging handlers                                   │
└────────────────┬────────────────────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────────────────────────┐
│  4. Create root tracing span                                        │
│     with tracer.start_as_current_span("chaos.postgres.*"):         │
│       - Set db.system, db.name, network.peer.address attributes    │
│       - Set chaos.activity, chaos.operation metadata               │
└────────────────┬────────────────────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────────────────────────┐
│  5. Launch worker threads (parallelism)                             │
│                                                                     │
│     Thread 1 ──┐                                                    │
│     Thread 2 ──┼─→  Execute chaos action                            │
│     Thread N ──┘     (connect, query, lock, etc.)                   │
│                                                                     │
│     Each thread:                                                    │
│     • Creates child span                                            │
│     • Records metrics (latency, errors)                             │
│     • Handles exceptions                                            │
│     • Monitors _stop_event for graceful shutdown                    │
└────────────────┬────────────────────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────────────────────────┐
│  6. Wait for completion or duration timeout                         │
│     - Monitor _active_threads list                                  │
│     - Check _stop_event for external interruption                   │
│     - Join threads with timeout                                     │
└────────────────┬────────────────────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────────────────────────┐
│  7. Aggregate results from all threads                              │
│     - Collect success/failure counts                                │
│     - Calculate min/max/avg latencies                               │
│     - Count errors and exceptions                                   │
└────────────────┬────────────────────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────────────────────────┐
│  8. Set span status and attributes                                  │
│     - span.set_status(StatusCode.OK or ERROR)                       │
│     - span.set_attribute("chaos.result.total_operations", count)    │
│     - span.set_attribute("chaos.result.errors", error_count)        │
└────────────────┬────────────────────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────────────────────────┐
│  9. Flush telemetry data                                            │
│     flush() - Ensures OTLP export before function return            │
└────────────────┬────────────────────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────────────────────────┐
│  10. Return structured result dictionary                            │
│      {                                                              │
│        "status": "completed",                                       │
│        "connections_created": 100,                                  │
│        "errors": 0,                                                 │
│        "avg_latency_ms": 45.2                                       │
│      }                                                              │
└─────────────────────────────────────────────────────────────────────┘
```

### Probe Execution Flow

```
┌─────────────────────────────────────────────────────────────────────┐
│  1. Chaos Toolkit invokes probe function                           │
│     (e.g., postgres_connection_pool_check)                          │
└────────────────┬────────────────────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────────────────────────┐
│  2. Validate parameters and resolve environment variables           │
└────────────────┬────────────────────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────────────────────────┐
│  3. Create tracing span for probe operation                         │
└────────────────┬────────────────────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────────────────────────┐
│  4. Execute database/messaging query                                │
│     - Query system tables (pg_stat_*, information_schema)           │
│     - Execute health check commands                                 │
│     - Measure execution time                                        │
└────────────────┬────────────────────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────────────────────────┐
│  5. Collect and calculate metrics                                   │
│     - Connection pool utilization (%)                               │
│     - Cache hit ratios                                              │
│     - Query latencies (p50, p95, p99)                               │
│     - Lock counts and durations                                     │
│     - Queue depths and consumer lag                                 │
└────────────────┬────────────────────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────────────────────────┐
│  6. Record metrics via get_metrics_core()                           │
│     - Record probe execution latency                                │
│     - Record system-specific metrics                                │
│     - Tag with db_system, db_name, operation                        │
└────────────────┬────────────────────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────────────────────────┐
│  7. Return structured dictionary                                    │
│     {                                                               │
│       "connection_pool_utilization": 45,                            │
│       "cache_hit_ratio": 98.5,                                      │
│       "active_connections": 23,                                     │
│       "slow_queries": 0                                             │
│     }                                                               │
│                                                                     │
│     Chaos Toolkit evaluates against tolerance:                      │
│     tolerance: {"type": "probe", "name": "check", "target": ...}   │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Supported Systems

### Database Systems (6)

| System | Default Port | Actions | Probes | Key Features |
|--------|--------------|---------|--------|--------------|
| **PostgreSQL** | 5432 | 11 | 17 | Most comprehensive support, replication testing, advanced metrics |
| **MySQL** | 3306 | 7 | 5 | InnoDB lock testing, transaction isolation |
| **Microsoft SQL Server** | 1433 | 7 | 5 | SNAPSHOT isolation, tempdb monitoring |
| **MongoDB** | 27017 | 5 | 5 | Document contention, replica set testing |
| **Redis** | 6379 | 5 | 5 | Key contention, command saturation |
| **Cassandra** | 9042 | 5 | 5 | Row contention, partition key testing |

### Messaging Systems (3)

| System | Default Port | Actions | Probes | Key Features |
|--------|--------------|---------|--------|--------------|
| **Kafka** | 9092 | 6 | 5 | Topic saturation, consumer lag, rebalancing |
| **RabbitMQ** | 5672 | 7 | 5 | Queue flooding, dead-letter queues, connection exhaustion |
| **ActiveMQ** | 61616 | 7 | 5 | Message flooding, slow consumers, DLQ testing |

**Total**: 9 systems, 60+ actions, 60+ probes

---

## Chaos Actions

### Connection Management

Test how systems handle connection pool limits:

- **pool_exhaustion** - Create many connections to exhaust pools (all systems)
- **connection_leak** - Intentionally leak connections to test cleanup

**Use Cases**:
- Validate connection pool monitoring and alerting
- Test application retry logic when pool is full
- Verify graceful degradation under connection pressure

### Query/Command Saturation

Flood databases with high query volumes:

- **query_saturation** - High-volume SELECT/INSERT/UPDATE queries (PostgreSQL, MySQL, MSSQL, MongoDB, Cassandra)
- **command_saturation** - Saturate Redis with GET/SET/HGET commands
- **topic_saturation** - Flood Kafka topics with messages

**Use Cases**:
- Validate query timeout configurations
- Test application circuit breakers
- Verify database autoscaling triggers

### Transaction and Lock Chaos

Create lock contention and transaction conflicts:

- **slow_transactions** - Long-running transactions (PostgreSQL, MySQL, MSSQL)
- **lock_storm** - Generate high lock contention (PostgreSQL, MySQL, MSSQL)
- **deadlock_injection** - Deliberately create deadlocks (PostgreSQL, MySQL, MSSQL)
- **document_contention** - MongoDB document-level conflicts
- **row_contention** - Cassandra row-level conflicts
- **key_contention** - Redis key-level conflicts

**Use Cases**:
- Test deadlock detection and recovery
- Validate transaction timeout handling
- Verify lock monitoring and alerting

### Messaging Chaos

Test messaging system resilience:

- **message_flood** - High-volume message production (RabbitMQ, Kafka, ActiveMQ)
- **slow_consumer** - Simulate slow message consumers (RabbitMQ, Kafka, ActiveMQ)
- **dlq_saturation** - Fill dead-letter queues (RabbitMQ, Kafka, ActiveMQ)
- **rebalancing_storm** - Trigger consumer group rebalances (Kafka)

**Use Cases**:
- Validate backpressure handling
- Test consumer lag monitoring
- Verify DLQ processing

### Operational Actions

Test maintenance and failover scenarios:

- **maintenance_operations** - PostgreSQL VACUUM, ANALYZE operations
- **replication_operations** - Test PostgreSQL primary/replica failover
- **load_generation** - Generic load testing for PostgreSQL

---

## Health Probes

### Connectivity Probes

Basic health checks for all 9 systems:

- **connectivity_check** - Verify database/messaging system is reachable
- Includes retry logic with exponential backoff
- Configurable timeout and retry counts

### Status Monitoring Probes

Real-time monitoring during chaos:

- **pool_exhaustion_status** - Monitor connection pool utilization
- **query_saturation_status** - Track query load and slow queries
- **slow_transaction_status** - Monitor long-running transactions
- **lock_status** - Detect lock contention
- **queue_status** - Monitor message queue depth and lag

### PostgreSQL Advanced Metrics (17 Probes)

Most comprehensive monitoring support:

| Probe | Metrics Collected |
|-------|-------------------|
| **cache_hit_ratio_check** | Buffer cache hit percentage, blocks hit/read |
| **connection_pool_check** | Active connections, pool utilization %, idle connections |
| **lock_check** | Lock count by mode, waiting locks, lock duration |
| **replication_lag_check** | Lag in bytes and seconds, standby status |
| **temp_file_check** | Temporary file count and size, temp_buffers usage |
| **dead_tuples_check** | Dead tuple count, dead tuple ratio, autovacuum status |
| **slow_query_check** | Slow query count, slowest queries, blocked queries |
| **transaction_check** | Transaction throughput, rollback ratio, long transactions |
| **vacuum_check** | Autovacuum runs, last vacuum time, wraparound safety |
| **wal_check** | WAL file count, WAL size, archive status |
| **active_sessions_check** | Active/idle/waiting sessions, session age |
| **error_check** | Error count by type, deadlocks, constraint violations |
| **system_metrics_check** | Comprehensive system overview (all above metrics) |
| **recovery_metrics_check** | Recovery progress, RTO measurement |
| **transaction_validation** | Data consistency checks after chaos |

### Messaging-Specific Probes

- **consumer_status** - Monitor consumer lag and throughput
- **queue_depth** - Track message accumulation
- **message_flood_status** - Detect high-volume scenarios
- **connection_exhaustion_status** - Monitor connection limits

---

## Observability

Every action and probe is fully instrumented with OpenTelemetry:

### Distributed Tracing

**Automatic span creation** for all operations:

```python
# Root span for chaos action
chaos.postgres.query_saturation
├─ attributes:
│  ├─ db.system: "postgresql"
│  ├─ db.name: "myapp_db"
│  ├─ network.peer.address: "postgres-primary"
│  ├─ network.peer.port: 5432
│  ├─ chaos.activity: "postgresql_query_saturation"
│  ├─ chaos.operation: "query_saturation"
│  └─ chaos.activity.type: "action"
│
├─ chaos.postgres.query_saturation.worker_1 (child span)
├─ chaos.postgres.query_saturation.worker_2 (child span)
└─ chaos.postgres.query_saturation.worker_N (child span)
```

**Service Graph Visibility**: Databases and messaging systems appear in Grafana Tempo service graphs via proper span attributes.

### Metrics Collection

**60+ metrics** automatically recorded:

**Database Metrics**:
- `db_query_latency` - Query execution time (histogram)
- `db_query_count` - Total queries executed (counter)
- `db_slow_query_count` - Slow queries detected (counter)
- `db_connection_pool_utilization` - Pool usage percentage (gauge)
- `db_lock_count` - Locks held (gauge)
- `db_deadlock_count` - Deadlocks detected (counter)
- `db_error_count` - Errors by type (counter)

**Messaging Metrics**:
- `messaging_operation_latency` - Message send/receive time (histogram)
- `messaging_queue_depth` - Messages in queue (gauge)
- `messaging_consumer_lag` - Consumer lag in messages (gauge)
- `messaging_slow_operation_count` - Slow operations (counter)

**Chaos Metrics**:
- `chaos_operation_duration` - Action execution time (histogram)
- `chaos_operation_success_total` - Successful operations (counter)
- `chaos_operation_error_total` - Failed operations (counter)

### Structured Logging

All logs use OpenTelemetry logging with context propagation:

```python
logger.info(
    "Started PostgreSQL query saturation",
    extra={
        "db.system": "postgresql",
        "db.name": "myapp_db",
        "chaos.threads": 10,
        "chaos.duration": 60
    }
)
```

Logs are automatically correlated with traces via trace_id and span_id.

### Telemetry Export

Telemetry is exported via **OTLP (OpenTelemetry Protocol)** to:
- **Tempo** - Distributed tracing backend
- **Prometheus** - Metrics storage (via OTLP → remote write)
- **Loki** - Log aggregation

Configure exporters via environment variables:
```bash
OTEL_EXPORTER_OTLP_ENDPOINT=http://otel-collector:4318
OTEL_SERVICE_NAME=chaos-experiment
OTEL_RESOURCE_ATTRIBUTES=deployment.environment=staging
```

---

## Installation

### Prerequisites

- Python 3.9 or higher
- Chaos Toolkit 1.0.0+
- Database/messaging system drivers (installed automatically)
- OpenTelemetry collector (for observability)

### Install from PyPI (when published)

```bash
pip install chaostooling-extension-db
```

### Install from source

```bash
# Clone repository
git clone https://github.com/your-org/chaostooling-oss.git
cd chaostooling-oss/chaostooling-extension-db

# Install with Poetry (recommended)
poetry install

# Or install with pip
pip install -e .
```

### Database Driver Dependencies

The following drivers are installed automatically:

- **PostgreSQL**: psycopg2-binary
- **MySQL**: mysql-connector-python
- **MSSQL**: pyodbc (requires ODBC driver installation)
- **MongoDB**: pymongo
- **Redis**: redis
- **Cassandra**: cassandra-driver
- **Kafka**: kafka-python
- **RabbitMQ**: pika
- **ActiveMQ**: stomp.py

### MSSQL Additional Setup

For Microsoft SQL Server support, install the ODBC driver:

**Linux (Ubuntu/Debian)**:
```bash
curl https://packages.microsoft.com/keys/microsoft.asc | sudo apt-key add -
curl https://packages.microsoft.com/config/ubuntu/$(lsb_release -rs)/prod.list | \
  sudo tee /etc/apt/sources.list.d/mssql-release.list
sudo apt-get update
sudo ACCEPT_EULA=Y apt-get install -y msodbcsql18
```

**macOS**:
```bash
brew tap microsoft/mssql-release https://github.com/Microsoft/homebrew-mssql-release
brew update
brew install msodbcsql18
```

---

## Quick Start

### 1. Basic PostgreSQL Connection Pool Exhaustion

Create an experiment file `postgres-pool-test.json`:

```json
{
  "version": "1.0.0",
  "title": "PostgreSQL Connection Pool Exhaustion Test",
  "description": "Test application behavior when database connection pool is exhausted",
  "configuration": {
    "postgres_host": {
      "type": "env",
      "key": "POSTGRES_HOST",
      "default": "localhost"
    },
    "postgres_database": {
      "type": "env",
      "key": "POSTGRES_DATABASE",
      "default": "myapp"
    }
  },
  "steady-state-hypothesis": {
    "title": "Application is healthy and connection pool is not saturated",
    "probes": [
      {
        "type": "probe",
        "name": "connection-pool-check",
        "tolerance": {
          "type": "range",
          "range": [0, 70],
          "target": "connection_pool_utilization"
        },
        "provider": {
          "type": "python",
          "module": "chaosdb.probes.postgres.postgres_connection_pool_check",
          "func": "postgres_connection_pool_check",
          "arguments": {
            "host": "${postgres_host}",
            "database": "${postgres_database}"
          }
        }
      }
    ]
  },
  "method": [
    {
      "type": "action",
      "name": "exhaust-connection-pool",
      "provider": {
        "type": "python",
        "module": "chaosdb.actions.postgres.postgres_pool_exhaustion",
        "func": "postgres_pool_exhaustion",
        "arguments": {
          "host": "${postgres_host}",
          "database": "${postgres_database}",
          "num_connections": 100,
          "duration": 60
        }
      },
      "pauses": {
        "after": 10
      }
    }
  ],
  "rollbacks": [
    {
      "type": "action",
      "name": "cleanup-connections",
      "provider": {
        "type": "python",
        "module": "chaosdb.actions.postgres.postgres_cleanup",
        "func": "postgres_cleanup",
        "arguments": {
          "host": "${postgres_host}",
          "database": "${postgres_database}",
          "terminate_idle": true
        }
      }
    }
  ]
}
```

Run the experiment:

```bash
chaos run postgres-pool-test.json
```

### 2. Kafka Consumer Lag Test with Observability

```json
{
  "version": "1.0.0",
  "title": "Kafka Consumer Lag Simulation",
  "description": "Test monitoring and alerting when consumers fall behind",
  "controls": [
    {
      "name": "opentelemetry",
      "provider": {
        "type": "python",
        "module": "chaosotel.control"
      }
    }
  ],
  "configuration": {
    "kafka_brokers": {
      "type": "env",
      "key": "KAFKA_BROKERS",
      "default": "localhost:9092"
    },
    "kafka_topic": {
      "type": "env",
      "key": "KAFKA_TOPIC",
      "default": "orders"
    }
  },
  "steady-state-hypothesis": {
    "title": "Consumer lag is within acceptable limits",
    "probes": [
      {
        "type": "probe",
        "name": "consumer-lag-check",
        "tolerance": {
          "type": "range",
          "range": [0, 1000],
          "target": "consumer_lag"
        },
        "provider": {
          "type": "python",
          "module": "chaosdb.probes.kafka.kafka_consumer_status",
          "func": "kafka_consumer_status",
          "arguments": {
            "bootstrap_servers": "${kafka_brokers}",
            "topic": "${kafka_topic}"
          }
        }
      }
    ]
  },
  "method": [
    {
      "type": "action",
      "name": "slow-consumer-simulation",
      "provider": {
        "type": "python",
        "module": "chaosdb.actions.kafka.kafka_slow_consumer",
        "func": "kafka_slow_consumer",
        "arguments": {
          "bootstrap_servers": "${kafka_brokers}",
          "topic": "${kafka_topic}",
          "delay_ms": 500,
          "duration": 120
        }
      }
    }
  ]
}
```

### 3. View Observability Data

**Start observability stack** (if using chaostooling-demo):

```bash
cd chaostooling-demo
docker compose up -d
```

**Access Grafana** (http://localhost:3000):
- Username: `admin`
- Password: `admin`

**View traces in Tempo**:
- Navigate to Explore → Tempo
- Search for trace: `chaos.postgres.query_saturation`
- Visualize span hierarchy and timings

**View metrics in Prometheus**:
- Navigate to Explore → Prometheus
- Query: `db_query_latency_bucket{db_system="postgresql"}`
- Visualize query latency distribution

**View logs in Loki**:
- Navigate to Explore → Loki
- Query: `{job="chaos-toolkit"} |= "query_saturation"`
- Correlate logs with traces via trace_id

---

## Configuration

### Environment Variables

All connection parameters support environment variable configuration:

**PostgreSQL**:
```bash
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DATABASE=myapp
POSTGRES_USER=postgres
POSTGRES_PASSWORD=secret
POSTGRES_SSLMODE=prefer
```

**MySQL**:
```bash
MYSQL_HOST=localhost
MYSQL_PORT=3306
MYSQL_DATABASE=myapp
MYSQL_USER=root
MYSQL_PASSWORD=secret
```

**MongoDB**:
```bash
MONGODB_HOST=localhost
MONGODB_PORT=27017
MONGODB_DATABASE=myapp
MONGODB_USERNAME=admin
MONGODB_PASSWORD=secret
```

**Redis**:
```bash
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_PASSWORD=secret
REDIS_DB=0
```

**Kafka**:
```bash
KAFKA_BROKERS=localhost:9092
KAFKA_SECURITY_PROTOCOL=PLAINTEXT
KAFKA_SASL_MECHANISM=PLAIN
KAFKA_SASL_USERNAME=user
KAFKA_SASL_PASSWORD=secret
```

**RabbitMQ**:
```bash
RABBITMQ_HOST=localhost
RABBITMQ_PORT=5672
RABBITMQ_VHOST=/
RABBITMQ_USERNAME=guest
RABBITMQ_PASSWORD=guest
```

### OpenTelemetry Configuration

Configure observability via environment variables:

```bash
# OTLP Exporter
OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4318
OTEL_EXPORTER_OTLP_PROTOCOL=http/protobuf
OTEL_EXPORTER_OTLP_TIMEOUT=10000

# Service naming
OTEL_SERVICE_NAME=chaos-experiment
OTEL_SERVICE_NAMESPACE=chaos-engineering

# Resource attributes
OTEL_RESOURCE_ATTRIBUTES=deployment.environment=staging,team=platform

# Sampling (optional)
OTEL_TRACES_SAMPLER=always_on
OTEL_METRICS_EXEMPLAR_FILTER=always_on
```

### Default Values

Defaults are defined in `chaosdb/common/constants.py`:

```python
# Connection timeouts
DEFAULT_CONNECT_TIMEOUT = 10  # seconds
DEFAULT_QUERY_TIMEOUT = 30    # seconds

# Stress testing defaults
DEFAULT_DURATION = 60         # seconds
DEFAULT_NUM_THREADS = 10      # parallel workers
DEFAULT_NUM_CONNECTIONS = 50  # concurrent connections

# Retry logic
DEFAULT_RETRY_ATTEMPTS = 5
DEFAULT_RETRY_DELAY = 2       # seconds
```

---

## Examples

### Example 1: PostgreSQL Lock Storm with Monitoring

Test deadlock detection and monitoring:

```json
{
  "title": "PostgreSQL Lock Storm Test",
  "steady-state-hypothesis": {
    "probes": [
      {
        "name": "low-lock-count",
        "tolerance": {
          "type": "range",
          "range": [0, 10],
          "target": "total_locks"
        },
        "provider": {
          "type": "python",
          "module": "chaosdb.probes.postgres.postgres_lock_check",
          "func": "postgres_lock_check",
          "arguments": {
            "host": "postgres-primary",
            "database": "production"
          }
        }
      }
    ]
  },
  "method": [
    {
      "name": "generate-lock-contention",
      "provider": {
        "type": "python",
        "module": "chaosdb.actions.postgres.postgres_lock_storm",
        "func": "postgres_lock_storm",
        "arguments": {
          "host": "postgres-primary",
          "database": "production",
          "num_threads": 20,
          "duration": 60,
          "table_name": "orders"
        }
      }
    },
    {
      "name": "check-locks-during-storm",
      "type": "probe",
      "provider": {
        "type": "python",
        "module": "chaosdb.probes.postgres.postgres_lock_check",
        "func": "postgres_lock_check",
        "arguments": {
          "host": "postgres-primary",
          "database": "production"
        }
      }
    }
  ]
}
```

### Example 2: Redis Key Contention Test

```json
{
  "title": "Redis Key Contention Test",
  "method": [
    {
      "name": "redis-key-contention",
      "provider": {
        "type": "python",
        "module": "chaosdb.actions.redis.redis_key_contention",
        "func": "redis_key_contention",
        "arguments": {
          "host": "redis-primary",
          "port": 6379,
          "key_pattern": "user:session:*",
          "num_threads": 50,
          "operations_per_thread": 10000,
          "duration": 120
        }
      }
    }
  ]
}
```

### Example 3: Multi-System Chaos (PostgreSQL + RabbitMQ)

Test cascading failures across systems:

```json
{
  "title": "Multi-System Chaos: Database + Messaging",
  "method": [
    {
      "name": "exhaust-postgres-pool",
      "provider": {
        "type": "python",
        "module": "chaosdb.actions.postgres.postgres_pool_exhaustion",
        "func": "postgres_pool_exhaustion",
        "arguments": {
          "host": "postgres-primary",
          "database": "production",
          "num_connections": 100,
          "duration": 60
        }
      }
    },
    {
      "name": "flood-rabbitmq-queue",
      "provider": {
        "type": "python",
        "module": "chaosdb.actions.rabbitmq.rabbitmq_message_flood",
        "func": "rabbitmq_message_flood",
        "arguments": {
          "host": "rabbitmq-primary",
          "queue": "orders",
          "num_messages": 100000,
          "message_size_bytes": 1024,
          "duration": 60
        }
      }
    }
  ]
}
```

---

## Development

### Setup Development Environment

```bash
# Clone repository
git clone https://github.com/your-org/chaostooling-oss.git
cd chaostooling-oss/chaostooling-extension-db

# Install with development dependencies
poetry install --with dev

# Activate virtual environment
poetry shell
```

### Code Quality Tools

```bash
# Format code with Black
poetry run black chaosdb/

# Lint code with Ruff
poetry run ruff check chaosdb/

# Type checking with mypy
poetry run mypy chaosdb/

# Run tests
poetry run pytest tests/ -v

# Run tests with coverage
poetry run pytest tests/ --cov=chaosdb --cov-report=html
```

### Project Structure

```
chaostooling-extension-db/
├── chaosdb/
│   ├── __init__.py              # Package initialization, re-exports chaosotel
│   ├── actions/                 # Chaos injection actions
│   │   ├── postgres/            # 11 PostgreSQL actions
│   │   ├── mysql/               # 7 MySQL actions
│   │   ├── mssql/               # 7 MSSQL actions
│   │   ├── mongodb/             # 5 MongoDB actions
│   │   ├── redis/               # 5 Redis actions
│   │   ├── cassandra/           # 5 Cassandra actions
│   │   ├── kafka/               # 6 Kafka actions
│   │   ├── rabbitmq/            # 7 RabbitMQ actions
│   │   ├── activemq/            # 7 ActiveMQ actions
│   │   └── compute/             # Process kill actions
│   ├── probes/                  # Health checks and monitoring
│   │   ├── postgres/            # 17 PostgreSQL probes
│   │   ├── mysql/               # 5 MySQL probes
│   │   ├── mssql/               # 5 MSSQL probes
│   │   ├── mongodb/             # 5 MongoDB probes
│   │   ├── redis/               # 5 Redis probes
│   │   ├── cassandra/           # 5 Cassandra probes
│   │   ├── kafka/               # 5 Kafka probes
│   │   ├── rabbitmq/            # 5 RabbitMQ probes
│   │   └── activemq/            # 5 ActiveMQ probes
│   └── common/                  # Shared utilities
│       ├── connection.py        # Database connection factories
│       ├── validation.py        # Input validation utilities
│       └── constants.py         # Default configurations
├── tests/                       # Test suite
├── pyproject.toml               # Project configuration
├── README.md                    # This file
└── REFACTORING_PLAN.md          # Future improvements plan
```

### Adding New Actions

To add a new chaos action, follow this template:

```python
# chaosdb/actions/postgres/new_action.py

import logging
from typing import Dict, Any
from opentelemetry.trace import Status, StatusCode
from chaosotel import (
    get_tracer,
    ensure_initialized,
    flush,
    get_metrics_core,
    get_metric_tags,
    set_db_span_attributes
)
from chaosdb.common.connection import create_postgres_connection
from chaosdb.common.validation import validate_host, validate_port

logger = logging.getLogger(__name__)
tracer = get_tracer()

def new_chaos_action(
    host: str = None,
    port: int = 5432,
    database: str = None,
    duration: int = 60,
    **kwargs
) -> Dict[str, Any]:
    """
    Brief description of what this action does.

    Args:
        host: PostgreSQL host (env: POSTGRES_HOST)
        port: PostgreSQL port (env: POSTGRES_PORT)
        database: Database name (env: POSTGRES_DATABASE)
        duration: Duration in seconds

    Returns:
        Dict with action results
    """
    # 1. Initialize observability
    ensure_initialized()

    # 2. Validate parameters
    host = validate_host(host)
    port = validate_port(port)

    # 3. Create root span
    with tracer.start_as_current_span("chaos.postgres.new_action") as span:
        set_db_span_attributes(
            span,
            db_system="postgresql",
            db_name=database,
            host=host,
            port=port,
            chaos_activity="postgresql_new_action",
            chaos_action="new_action"
        )

        try:
            # 4. Execute chaos logic
            conn = create_postgres_connection(host, port, database)
            cursor = conn.cursor()

            # ... your chaos implementation ...

            # 5. Record metrics
            metrics = get_metrics_core()
            tags = get_metric_tags(db_system="postgresql", db_name=database)
            metrics.record_chaos_operation_success(tags=tags)

            # 6. Set span status
            span.set_status(Status(StatusCode.OK))

            # 7. Return results
            return {
                "status": "completed",
                "host": host,
                "database": database
            }

        except Exception as e:
            logger.error(f"Action failed: {e}", exc_info=True)
            span.set_status(Status(StatusCode.ERROR, str(e)))
            metrics = get_metrics_core()
            metrics.record_chaos_operation_error(tags=get_metric_tags())
            raise

        finally:
            # 8. Flush telemetry
            flush()
```

### Running Tests

```bash
# Run all tests
poetry run pytest

# Run specific test file
poetry run pytest tests/test_postgres_actions.py

# Run with verbose output
poetry run pytest -v

# Run with coverage
poetry run pytest --cov=chaosdb --cov-report=html

# Open coverage report
open htmlcov/index.html  # macOS
xdg-open htmlcov/index.html  # Linux
```

---

## Contributing

We welcome contributions! Please see [CONTRIBUTING.md](../CONTRIBUTING.md) for guidelines.

### Code Style

- Follow [PEP 8](https://pep8.org/) style guide
- Use [Black](https://black.readthedocs.io/) for formatting (line length: 100)
- Use [Ruff](https://beta.ruff.rs/) for linting
- Add type hints for all function signatures
- Write docstrings for all public functions (Google style)

### Refactoring Priorities

See [REFACTORING_PLAN.md](REFACTORING_PLAN.md) for planned improvements.

---

## License

[MIT License](../LICENSE)

---

## Support

- **Issues**: [GitHub Issues](https://github.com/your-org/chaostooling-oss/issues)
- **Discussions**: [GitHub Discussions](https://github.com/your-org/chaostooling-oss/discussions)
- **Slack**: [Join our Slack](https://slack.chaostoolkit.org/)

---

## Related Projects

- **chaostooling-otel**: OpenTelemetry observability framework
- **chaostooling-reporting**: Automated experiment reporting and dashboards
- **chaostooling-generic**: Generic chaos engineering controls
- **chaostooling-extension-network**: Network chaos (latency, packet loss)
- **chaostooling-extension-compute**: Compute chaos (CPU, memory, disk)
- **chaostooling-demo**: Full demo environment with all extensions

---

## Acknowledgments

Built with:
- [Chaos Toolkit](https://chaostoolkit.org/) - Chaos engineering framework
- [OpenTelemetry](https://opentelemetry.io/) - Observability instrumentation
- [Python](https://www.python.org/) - Programming language
