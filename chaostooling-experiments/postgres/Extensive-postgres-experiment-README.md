# Extensive Postgres Chaos Experiment

This experiment combines multiple PostgreSQL failure scenarios, Disaster Recovery (DR) tests, and infrastructure chaos into a single, comprehensive validation suite.

## Included Scenarios

1. **Cache Miss Storm**: Forces sequential scans to degrade cache hit ratio.
2. **Vacuum Starvation**: Generates dead tuples to simulate maintenance failure.
3. **Temp File Spill**: Forces complex sorts that spill to disk.
4. **Lock Storm**: Creates massive lock contention.
5. **Pool Exhaustion**: Exhausts database connection pool.
6. **Query Saturation**: Floods the database with queries.
7. **Slow Transactions**: Simulates application-layer transaction delays.
8. **Infrastructure CPU Stress**: Stresses the CPU of the host/container.
9. **Infrastructure Network Latency**: Injects network latency.
10. **DR Primary Failover**: Stops the primary database and verifies connectivity to the replica.
11. **Replication Lag Check**: Monitors and validates replication lag between primary and replica.

## Prerequisites

### Database Setup

Before running the experiments, initialize the test database:

```bash
# From the chaos-runner container or host with psql access
cd /experiments/postgres
./setup_postgres_test_db.sh
```

This creates the `mobile_purchases` table and seeds 10,000 test rows.

### Optional: Using Configuration Files

You can use the `env.example` file to set custom configurations:

```bash
# Run with custom configuration
chaos run postgres/Extensive-postgres-experiment.json --var-file=postgres/env.example

# Or set environment variables directly
export STRESS_DURATION=60
export NUM_THREADS=10
chaos run postgres/Extensive-postgres-experiment.json
```

The `env.example` file provides all available configuration options for the Postgres experiments.

## Load / Pressure Sizing ("T-Shirt Sizes")

You can adjust the intensity of the experiment using environment variables. Use the following "T-Shirt Sizes" as a guide:

| Variable | Description | Small (S) | Medium (M) | Large (L) | X-Large (XL) |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `STRESS_DURATION` | Duration of each chaos action (seconds) | 10 | 30 | 60 | 120 |
| `NUM_THREADS` | Number of concurrent threads/connections | 2 | 5 | 20 | 50 |
| `ROW_COUNT` | Number of rows for data generation/updates | 100 | 1000 | 10,000 | 100,000 |
| `CPU_STRESS_LOAD` | CPU load percentage | 20 | 50 | 80 | 100 |
| `NETWORK_LATENCY_MS` | Network latency in milliseconds | 50 | 200 | 500 | 1000 |

### Example Usage

**Run a "Medium" load experiment:**

```bash
export STRESS_DURATION=30
export NUM_THREADS=5
export ROW_COUNT=1000
export CPU_STRESS_LOAD=50
export NETWORK_LATENCY_MS=200

chaos run Extensive-postgres-experiment.json
```

**Run an "X-Large" stress test:**

```bash
export STRESS_DURATION=120
export NUM_THREADS=50
export ROW_COUNT=100000
export CPU_STRESS_LOAD=100
export NETWORK_LATENCY_MS=1000

chaos run Extensive-postgres-experiment.json
```

## Dashboard

Use the `Extensive Postgres Dashboard` in Grafana to monitor:

- **SRE Signals**: Cache Hit Ratio, Dead Tuples, WAL Files.
- **Performance**: Query Latency, Throughput.
- **Chaos Impact**: Correlation between chaos events and metric spikes.
