# Subset Chaos Experiments

This directory contains focused chaos engineering experiments, separated by database and messaging systems. Each experiment includes baseline setup, load generation, and system-specific chaos scenarios with proper test transactions and probes.

## Database System Experiments

### PostgreSQL (`postgresql-chaos-experiment.json`)
- **Scenarios**: 7 scenarios
  - Cache Miss Storm
  - Vacuum Starvation
  - Temp File Spill
  - Lock Storm
  - Pool Exhaustion
  - Query Saturation
  - Slow Transactions
- **Load Transactions**: Continuous transaction load targeting PostgreSQL via Payment Service → RabbitMQ → PostgreSQL flow
- **Duration**: ~5 minutes with continuous load

### MySQL (`mysql-chaos-experiment.json`)
- **Scenarios**: 2 scenarios
  - Slow Transactions
  - Query Saturation
- **Load Transactions**: Continuous transaction load targeting MySQL via Order Service → Kafka → MySQL flow
- **Duration**: ~5 minutes with continuous load

### MSSQL (`mssql-chaos-experiment.json`)
- **Scenarios**: 1 scenario
  - Slow Transactions
- **Load Transactions**: Continuous transaction load targeting MSSQL via event-driven updates
- **Duration**: ~5 minutes with continuous load

### MongoDB (`mongodb-chaos-experiment.json`)
- **Scenarios**: 2 scenarios
  - Document Contention
  - Query Saturation
- **Load Transactions**: Continuous transaction load targeting MongoDB via Inventory Service → MongoDB → Redis flow
- **Duration**: ~5 minutes with continuous load

### Redis (`redis-chaos-experiment.json`)
- **Scenarios**: 2 scenarios
  - Key Contention
  - Command Saturation
- **Load Transactions**: Continuous transaction load targeting Redis via Inventory Service → MongoDB → Redis flow
- **Duration**: ~5 minutes with continuous load

### Cassandra (`cassandra-chaos-experiment.json`)
- **Scenarios**: 1 scenario
  - Row Contention
- **Load Transactions**: Continuous transaction load targeting Cassandra via RabbitMQ Consumer → Cassandra flow
- **Duration**: ~5 minutes with continuous load

## Infrastructure/Compute Experiments

### Compute (`compute-chaos-experiment.json`)
- **Scenarios**: 3 scenarios
  - CPU Stress (40-90% of existing CPU)
  - Memory Stress (40-90% of existing memory)
  - Combined CPU + Memory Stress
- **Features**:
  - **Vault Integration**: Connects to remote hosts using Vault credentials for secure SSH access
  - **Probe-First Approach**: Probes current CPU/memory usage before applying stress
  - **Dynamic Stress**: Calculates stress-ng parameters based on 40-90% of existing resources
  - **Remote Host Support**: Executes stress-ng on remote hosts via SSH
- **Load Transactions**: Continuous transaction load during stress scenarios to validate system behavior
- **Duration**: ~5 minutes with continuous load

**Note**: This experiment requires implementation of remote host functions in `chaoscompute` extension:
- `chaoscompute.probes.compute_remote` module with Vault credential support
- `chaoscompute.actions.compute_remote_stress` module for remote stress-ng execution

## Messaging System Experiments

### Kafka (`kafka-chaos-experiment.json`)
- **Scenarios**: 3 scenarios
  - Message Flood
  - Topic Saturation
  - Slow Consumer
- **Load Transactions**: Continuous transaction load targeting Kafka via Order Service → Kafka → MySQL flow
- **Duration**: ~5 minutes with continuous load

### RabbitMQ (`rabbitmq-chaos-experiment.json`)
- **Scenarios**: 2 scenarios
  - Message Flood
  - Queue Saturation
- **Load Transactions**: Continuous transaction load targeting RabbitMQ via Payment Service → RabbitMQ → PostgreSQL flow
- **Duration**: ~5 minutes with continuous load

### ActiveMQ (`activemq-chaos-experiment.json`)
- **Scenarios**: 1 scenario
  - Message Flood
- **Load Transactions**: Continuous transaction load targeting ActiveMQ via Kafka Consumer → ActiveMQ → MSSQL flow
- **Duration**: ~5 minutes with continuous load

## Common Features

All subset experiments include:

1. **Baseline Setup**: Establishes baseline transaction flow before chaos scenarios
2. **Load Generator Control**: Automatically starts/stops background transaction load generator
3. **OpenTelemetry Integration**: All activities are traced and instrumented via `chaosotel`
4. **Test Transactions**: Each chaos scenario includes test transactions that exercise the target system
5. **Probes**: Validation probes after each chaos scenario to verify system state
6. **Final Validation**: Post-experiment connectivity and health checks
7. **Reporting**: Automatic report generation (HTML, JSON) with executive, compliance, audit, and product owner views

## Running Subset Experiments

Each experiment can be run independently:

```bash
# Example: Run PostgreSQL chaos experiment
chaos run chaostooling-experiments/e2e-test/postgresql-chaos-experiment.json

# Example: Run Kafka chaos experiment
chaos run chaostooling-experiments/e2e-test/kafka-chaos-experiment.json
```

## Load Generator Configuration

The load generator runs continuously throughout each experiment, generating transactions that flow through the target system:

- **Default TPS**: 2.0 transactions per second
- **Auto-start**: Enabled by default (configurable via `AUTO_START_LOAD_GENERATOR`)
- **URL**: `http://transaction-load-generator:5001` (configurable via `TRANSACTION_LOAD_GENERATOR_URL`)

The load generator ensures that chaos scenarios are tested under realistic production-like load conditions.

## Observability

All experiments are fully instrumented with OpenTelemetry:

- **Traces**: Distributed tracing across all activities
- **Metrics**: System and application metrics collection
- **Logs**: Structured logging with correlation IDs
- **Service Name**: Configurable per experiment (e.g., `postgresql-chaos-experiment`, `kafka-chaos-experiment`)

All observability data is exported to the configured OpenTelemetry collector endpoint.

