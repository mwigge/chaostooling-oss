# ChaosTooling OSS

Open source Chaos Engineering toolkit ecosystem built on Chaos Toolkit.

## Overview

ChaosTooling provides a comprehensive set of extensions, observability tools, and demo environments for chaos engineering. This monorepo contains all components needed to run chaos experiments with full observability.

## Architecture

### Core Components

1. **chaostooling-otel** - OpenTelemetry observability for Chaos Toolkit (module: `chaosotel`)
2. **chaostooling-extension-db** - Database and messaging system extensions
3. **chaostooling-extension-compute** - Compute resource extensions
4. **chaostooling-extension-network** - Network extensions
5. **chaostooling-reporting** - Reporting and analytics extension
6. **chaostooling-demo** - Demo environment with full observability stack
7. **chaostooling-experiments** - Example experiments

## Quick Start

### Prerequisites
- Docker and Docker Compose
- Python 3.9+ (for local development)

### Installation

1. **Clone this repository:**
   ```bash
   git clone <chaostooling-oss-repo>
   cd chaostooling-oss
   ```

2. **Start the demo environment:**
   ```bash
   cd chaostooling-demo
   docker compose up -d
   ```

3. **Run an experiment:**
   ```bash
   docker compose exec chaos-runner chaos run /experiments/postgres/test-postgres-query-saturation.json
   ```

4. **View dashboards:**
   - Grafana: http://localhost:3000 (admin/admin)
   - Prometheus: http://localhost:9090
   - Tempo: http://localhost:3200

## Observability (chaostooling-otel)

ChaosTooling uses OpenTelemetry for unified observability across all experiments.

### Features
- 📊 Structured Logging → Loki via OpenTelemetry
- 📈 Prometheus Metrics → 60+ built-in metrics
- 🔍 Distributed Tracing → Tempo/Jaeger via OpenTelemetry
- ✅ Compliance Tracking → SOX, GDPR, PCI-DSS, HIPAA
- 🎯 Automatic Instrumentation → Zero-boilerplate decorators
- 🧮 Risk Calculation → Experiment complexity & risk scoring
- 🔄 MTTR Tracking → Mean Time To Recovery metrics

### Installation
```bash
pip install chaostooling-otel
```

### Usage
```python
from chaosotel import initialize, instrument_action

# Initialize at startup
initialize(target_type="database")

# Decorate your actions
@instrument_action(name="kill_connections", target_type="database", severity="high")
def my_chaos_action():
    """Your chaos logic here"""
    pass
```

### In Experiments
```json
{
  "controls": [
    {
      "name": "chaosotel",
      "provider": {
        "type": "python",
        "module": "chaosotel.control"
      }
    }
  ]
}
```

## Extensions

### chaostooling-extension-db
Database and messaging system extensions for:
- **Databases**: PostgreSQL, MySQL, MSSQL, MongoDB, Redis, Cassandra
- **Messaging**: Kafka, RabbitMQ, ActiveMQ

**Installation:**
```bash
pip install chaostooling-extension-db
```

**Usage:**
```json
{
  "probes": [
    {
      "type": "probe",
      "name": "check-postgres",
      "provider": {
        "type": "python",
        "module": "chaosdb.probes.postgres.postgres_connectivity",
        "func": "probe_postgres_connectivity"
      }
    }
  ]
}
```

**Available Probes:**

| System | Probes |
|--------|--------|
| PostgreSQL | `probe_postgres_connectivity`, `probe_query_saturation_status`, `probe_lock_storm_status`, `probe_slow_transactions_status`, `probe_pool_exhaustion_status`, `probe_replication_lag`, `probe_data_consistency`, `collect_postgres_system_metrics`, `probe_transaction_count`, `probe_transaction_integrity`, `probe_api_transaction_flow` |
| MySQL | `probe_mysql_connectivity`, `probe_query_saturation_status`, `probe_lock_storm_status`, `probe_slow_transactions_status`, `probe_pool_exhaustion_status` |
| MSSQL | `probe_mssql_connectivity`, `probe_query_saturation_status`, `probe_lock_storm_status`, `probe_slow_transactions_status`, `probe_pool_exhaustion_status` |
| MongoDB | `probe_mongodb_connectivity`, `probe_query_saturation_status`, `probe_slow_operations_status`, `probe_connection_exhaustion_status`, `probe_document_contention_status` |
| Redis | `probe_redis_connectivity`, `probe_command_saturation_status`, `probe_slow_operations_status`, `probe_connection_exhaustion_status`, `probe_key_contention_status` |
| Cassandra | `probe_cassandra_connectivity`, `probe_query_saturation_status`, `probe_slow_operations_status`, `probe_connection_exhaustion_status`, `probe_row_contention_status` |
| Kafka | `probe_kafka_connectivity`, `probe_topic_saturation_status`, `probe_message_flood_status`, `probe_slow_consumer_status`, `probe_connection_exhaustion_status` |
| RabbitMQ | `probe_rabbitmq_connectivity`, `probe_queue_saturation_status`, `probe_message_flood_status`, `probe_slow_consumer_status`, `probe_connection_exhaustion_status` |
| ActiveMQ | `probe_activemq_connectivity`, `probe_queue_saturation_status`, `probe_message_flood_status`, `probe_slow_consumer_status`, `probe_connection_exhaustion_status` |

### chaostooling-extension-compute
Compute resource extensions for CPU, memory, disk, and process management.

**Installation:**
```bash
pip install chaostooling-extension-compute
```

### chaostooling-extension-network
Network extensions for latency, packet loss, and connectivity testing.

**Installation:**
```bash
pip install chaostooling-extension-network
```

### chaostooling-reporting
Automated reporting extension with:
- Executive summaries
- Compliance reports
- Product owner reports
- Audit trails
- CSV/JSON exports

**Installation:**
```bash
pip install chaostooling-reporting
```

**Usage:**
```json
{
  "controls": [
    {
      "name": "reporting",
      "provider": {
        "type": "python",
        "module": "chaostooling_reporting.control"
      }
    }
  ]
}
```

## Demo Environment (chaostooling-demo)

The demo environment provides a complete observability stack:

### Services
- **Grafana**: Dashboards and visualization
- **Prometheus**: Metrics collection
- **Loki**: Log aggregation
- **Tempo**: Distributed tracing
- **OTEL Collector**: Unified signal collection
- **Application Stack**: HA-Proxy, app servers, databases, messaging systems

### Structure
- `docker-compose.yml` - Main orchestration
- `dashboards/` - Grafana dashboard definitions
- `scripts/` - Setup and utility scripts
- `otel-collector/` - OpenTelemetry collector configuration
- `prometheus.yml` - Prometheus configuration
- `promtail/` - Log collection configuration

### Running Experiments
```bash
cd chaostooling-demo
docker compose up -d
docker compose exec chaos-runner chaos run /experiments/postgres/Extensive-postgres-experiment.json
```

## Experiments (chaostooling-experiments)

Ready-to-use chaos experiments organized by system type:

- `postgres/` - PostgreSQL chaos scenarios
- `mysql/` - MySQL chaos scenarios
- `mongodb/` - MongoDB chaos scenarios
- `redis/` - Redis chaos scenarios
- `kafka/` - Kafka chaos scenarios
- `rabbitmq/` - RabbitMQ chaos scenarios
- `production-scale/` - Production-scale distributed transaction experiments

### Example Experiment
```json
{
  "version": "1.0.0",
  "title": "PostgreSQL Query Saturation Test",
  "steady-state-hypothesis": {
    "probes": [
      {
        "type": "probe",
        "name": "check-postgres",
        "provider": {
          "type": "python",
          "module": "chaosdb.probes.postgres.postgres_connectivity",
          "func": "probe_postgres_connectivity"
        }
      }
    ]
  },
  "method": [
    {
      "type": "action",
      "name": "saturate-queries",
      "provider": {
        "type": "python",
        "module": "chaosdb.actions.postgres.postgres_query_saturation",
        "func": "action_postgres_query_saturation"
      }
    }
  ]
}
```

## Development

### Local Development Setup
```bash
# Install all extensions in development mode
cd chaostooling-otel && pip install -e .
cd ../chaostooling-extension-db && pip install -e .
cd ../chaostooling-reporting && pip install -e .
```

### Running Tests
```bash
# In each extension directory
pytest
```

## License

Apache 2.0

## Author

Morgan Wigge (morgan@wigge.nu)

