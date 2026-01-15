# Comprehensive E2E Distributed Transaction Chaos Experiment

## Overview

The **Comprehensive E2E Distributed Transaction Chaos Experiment** is the ultimate end-to-end chaos engineering test that combines all scenarios from both the production-scale and extensive-postgres experiments. This experiment tests distributed transactions across **17 hops** with **5 minutes of continuous transaction load** while executing **29 comprehensive chaos scenarios** across all systems.

## Key Features

- **29 Chaos Scenarios**: Comprehensive testing across all systems
- **5 Minutes Continuous Load**: Background transaction generator runs at 2 TPS (600 transactions total)
- **17-Hop Transaction Flow**: Full distributed transaction validation
- **All Systems Tested**: PostgreSQL, MySQL, MongoDB, Redis, Kafka, RabbitMQ, ActiveMQ, MSSQL, Cassandra
- **Disaster Recovery**: Primary failover, DR site failover, replication lag testing
- **Infrastructure Chaos**: CPU stress, memory stress, network latency
- **Real-Time Observability**: Full OpenTelemetry tracing and metrics

## Transaction Flow (17 Hops)

The experiment validates a complex distributed transaction flow:

1. **HA-Proxy** → Receives purchase request
2. **App Server** → Processes request
3. **Payment Service** → Processes payment
4. **PostgreSQL (Primary)** → Stores payment record
5. **RabbitMQ** → Publishes payment event
6. **Kafka** → Publishes purchase event
7. **Order Service** → Creates order
8. **MySQL** → Stores order record
9. **Kafka** → Publishes order event
10. **Inventory Service** → Checks inventory
11. **MongoDB** → Queries inventory
12. **Redis** → Caches inventory data
13. **PostgreSQL** → Updates inventory
14. **Kafka** → Publishes inventory update
15. **Notification Service** → Sends notification
16. **PostgreSQL** → Stores notification
17. **PostgreSQL (Replica)** → Replicates all data

## Chaos Scenarios (29 Total)

### Phase 1: Baseline
- **Baseline Transaction Flow**: Establish baseline with 50 transactions
- **Baseline Validation**: Verify all systems are healthy

### Phase 2: PostgreSQL Chaos (During 5-Minute Transaction Load)

1. **Cache Miss Storm** (`SCENARIO-1`)
   - Forces sequential scans to cause cache misses
   - Duration: 5 minutes (300 seconds)
   - Tests: Transaction performance under cache pressure

2. **Vacuum Starvation** (`SCENARIO-2`)
   - Generates dead tuples to starve vacuum process
   - Row count: 1000 (configurable)
   - Tests: Database maintenance under load

3. **Temp File Spill** (`SCENARIO-3`)
   - Complex sort queries that spill to disk
   - Duration: 5 minutes
   - Tests: Disk I/O under memory pressure

4. **Lock Storm** (`SCENARIO-4`)
   - Creates contention with multiple locking threads
   - Threads: 10 (configurable)
   - Duration: 5 minutes
   - Tests: Transaction deadlock handling

5. **Pool Exhaustion** (`SCENARIO-5`)
   - Exhausts connection pool (100 connections)
   - Duration: 5 minutes
   - Tests: Connection pool resilience

6. **Query Saturation** (`SCENARIO-6`)
   - Saturates database with 20 threads × 1000 queries
   - Duration: 5 minutes
   - Tests: Database performance under extreme load

7. **Slow Transactions** (`SCENARIO-7`)
   - Injects 2-3 second delays in transactions
   - Threads: 10
   - Duration: 5 minutes
   - Tests: Application timeout handling

### Phase 3: Network Chaos

8. **Network Latency Across Sites** (`SCENARIO-8`)
   - Simulates 500ms network latency
   - Duration: 5 minutes
   - Tests: Distributed transaction handling under network delay

### Phase 4: Multi-Database Chaos

9. **MySQL Slow Transactions** (`SCENARIO-9`)
   - Injects 3 second delays in MySQL transactions
   - Duration: 5 minutes
   - Tests: MySQL performance under stress

10. **MySQL Query Saturation** (`SCENARIO-10`)
    - Saturates MySQL with 20 threads
    - Duration: 5 minutes
    - Tests: MySQL connection handling

11. **MSSQL Slow Transactions** (`SCENARIO-11`)
    - Injects delays in MSSQL transactions
    - Duration: 5 minutes
    - Tests: MSSQL performance

12. **MongoDB Document Contention** (`SCENARIO-12`)
    - Creates document-level contention
    - Threads: 10
    - Duration: 5 minutes
    - Tests: MongoDB write conflict handling

13. **MongoDB Query Saturation** (`SCENARIO-13`)
    - Saturates MongoDB with queries
    - Threads: 20
    - Duration: 5 minutes
    - Tests: MongoDB performance

14. **Redis Key Contention** (`SCENARIO-14`)
    - Creates key-level contention
    - Threads: 10
    - Duration: 5 minutes
    - Tests: Redis performance under contention

15. **Redis Command Saturation** (`SCENARIO-15`)
    - Saturates Redis with commands
    - Threads: 20
    - Duration: 5 minutes
    - Tests: Redis throughput limits

16. **Cassandra Row Contention** (`SCENARIO-16`)
    - Creates row-level contention
    - Threads: 10
    - Duration: 5 minutes
    - Tests: Cassandra consistency under contention

### Phase 5: Messaging Chaos

17. **Kafka Message Flood** (`SCENARIO-17`)
    - 10 producers × 1000 messages
    - Duration: 5 minutes
    - Tests: Kafka throughput and consumer lag

18. **Kafka Topic Saturation** (`SCENARIO-18`)
    - 20 producers continuously publishing
    - Duration: 5 minutes
    - Tests: Kafka topic partition handling

19. **Kafka Slow Consumer** (`SCENARIO-19`)
    - Consumers with 5 second delays
    - Duration: 5 minutes
    - Tests: Consumer lag and backpressure

20. **RabbitMQ Message Flood** (`SCENARIO-20`)
    - 10 producers × 1000 messages
    - Duration: 5 minutes
    - Tests: RabbitMQ queue depth

21. **RabbitMQ Queue Saturation** (`SCENARIO-21`)
    - 20 producers continuously publishing
    - Duration: 5 minutes
    - Tests: RabbitMQ memory limits

22. **ActiveMQ Message Flood** (`SCENARIO-22`)
    - 10 producers × 1000 messages
    - Duration: 5 minutes
    - Tests: ActiveMQ performance

### Phase 6: Infrastructure Chaos

23. **CPU Stress** (`SCENARIO-23`)
    - 80% CPU load on 2 cores
    - Duration: 5 minutes
    - Tests: System performance under CPU pressure

24. **Memory Stress** (`SCENARIO-24`)
    - 2GB memory allocation
    - Duration: 5 minutes
    - Tests: System performance under memory pressure

### Phase 7: Application & Load Balancer Failover

25. **Application Server Failure** (`SCENARIO-25`)
    - Stops app-server-1-site-a
    - Tests: HAProxy failover to app-server-2-site-a
    - Rollback: Restarts app-server-1-site-a

### Phase 8: Disaster Recovery

26. **Database Primary Failover** (`SCENARIO-26`)
    - Stops PostgreSQL primary
    - Tests: Replica promotion and connectivity
    - Rollback: Restarts primary

27. **Replication Lag Check** (`SCENARIO-27`)
    - Validates replication lag < 10 seconds
    - Tests: Replication health

28. **DR Site Failover** (`SCENARIO-28`)
    - Stops Site A HAProxy
    - Tests: Failover to Site B (DR)
    - Rollback: Restarts Site A HAProxy

### Phase 9: Final Validation

29. **Final Transaction Integrity Check** (`SCENARIO-29`)
    - Validates all transactions completed successfully
    - Checks data consistency across all systems
    - Verifies primary-replica consistency

## Configuration

All parameters are environment variable driven for scalability:

### Infrastructure Configuration

```bash
# Primary Site (Site A)
export SITE_A_HAPROXY_URL="http://haproxy-site-a:80"
export SITE_A_APP_SERVER_1_URL="http://app-server-1-site-a:5000"
export SITE_A_APP_SERVER_2_URL="http://app-server-2-site-a:5000"
export SITE_A_PAYMENT_SERVICE_URL="http://payment-service-site-a:5000"
export SITE_A_ORDER_SERVICE_URL="http://order-service-site-a:5000"
export SITE_A_INVENTORY_SERVICE_URL="http://inventory-service-site-a:5000"

# DR Site (Site B)
export SITE_B_HAPROXY_URL="http://haproxy-site-b:80"
export SITE_B_APP_SERVER_URL="http://app-server-site-b:5000"
```

### Database Configuration

```bash
# PostgreSQL
export POSTGRES_PRIMARY_HOST="postgres-primary-site-a"
export POSTGRES_REPLICA_HOST="postgres-replica-site-a"
export POSTGRES_DR_HOST="postgres-primary-site-b"
export POSTGRES_PORT="5432"
export POSTGRES_DB="testdb"
export POSTGRES_USER="postgres"
export POSTGRES_PASSWORD="postgres"

# MySQL
export MYSQL_HOST="mysql"
export MYSQL_PORT="3306"
export MYSQL_DB="testdb"
export MYSQL_USER="root"
export MYSQL_PASSWORD="mysql"

# MongoDB
export MONGODB_URI="mongodb://mongodb:27017"
export MONGODB_DB="test"

# Redis
export REDIS_HOST="redis"
export REDIS_PORT="6379"

# MSSQL
export MSSQL_HOST="mssql"
export MSSQL_PORT="1433"
export MSSQL_DB="master"
export MSSQL_USER="sa"
export MSSQL_SA_PASSWORD="Password123!"

# Cassandra
export CASSANDRA_HOST="cassandra"
export CASSANDRA_PORT="9042"
export CASSANDRA_KEYSPACE="system"
```

### Messaging Configuration

```bash
# Kafka
export KAFKA_BOOTSTRAP_SERVERS="kafka:9092"
export KAFKA_TOPIC="test"

# RabbitMQ
export RABBITMQ_HOST="rabbitmq"
export RABBITMQ_PORT="5672"
export RABBITMQ_USER="chaos"
export RABBITMQ_PASSWORD="password"

# ActiveMQ
export ACTIVEMQ_HOST="activemq"
export ACTIVEMQ_PORT="61616"
export ACTIVEMQ_WEB_PORT="8161"
```

### Chaos Parameters

```bash
# Stress Duration (5 minutes = 300 seconds)
export STRESS_DURATION="300"
export CHAOS_DURATION_MINUTES="5"

# Thread Configuration
export NUM_THREADS="10"  # Adjust for S/M/L/XL sizing
export ROW_COUNT="1000"

# Network Chaos
export CHAOS_NETWORK_LATENCY_MS="500"
export CHAOS_NETWORK_DURATION_S="300"

# CPU Stress
export CHAOS_CPU_LOAD="80"
export CHAOS_CPU_DURATION_S="300"

# Database Slow Transactions
export CHAOS_DB_SLOW_TXN_DELAY_MS="3000"
export CHAOS_DB_SLOW_TXN_DURATION_S="300"
```

### Test Parameters

```bash
# Baseline
export TEST_BASELINE_TRANSACTIONS="50"

# Distributed Transaction Tests
export TEST_DISTRIBUTED_TXN_COUNT="30"

# DR Failover Tests
export TEST_DR_FAILOVER_COUNT="20"
```

### Background Transaction Load (5 Minutes)

```bash
# Load Generator Configuration
export TRANSACTION_LOAD_GENERATOR_URL="http://transaction-load-generator:5001"
export TRANSACTION_LOAD_GENERATOR_TPS="2.0"  # 2 transactions/second = 600 over 5 minutes
export TRANSACTION_LOAD_GENERATOR_DURATION_MINUTES="5"
export AUTO_START_LOAD_GENERATOR="true"
```

### Observability

```bash
export OTEL_SERVICE_NAME="e2e-comprehensive-chaos-experiment"
```

### Reporting

```bash
export CHAOS_REPORTING_OUTPUT_DIR="/var/log/chaostoolkit/reports"
export CHAOS_REPORTING_FORMATS="html,json"
```

## Scaling Examples

### Small (S) - Development/Testing
```bash
export STRESS_DURATION="60"      # 1 minute
export NUM_THREADS="5"
export TRANSACTION_LOAD_GENERATOR_TPS="1.0"
export CHAOS_DURATION_MINUTES="1"
```

### Medium (M) - Staging
```bash
export STRESS_DURATION="180"    # 3 minutes
export NUM_THREADS="10"
export TRANSACTION_LOAD_GENERATOR_TPS="2.0"
export CHAOS_DURATION_MINUTES="3"
```

### Large (L) - Production-Like
```bash
export STRESS_DURATION="300"    # 5 minutes (default)
export NUM_THREADS="10"
export TRANSACTION_LOAD_GENERATOR_TPS="2.0"
export CHAOS_DURATION_MINUTES="5"
```

### Extra Large (XL) - Stress Testing
```bash
export STRESS_DURATION="600"    # 10 minutes
export NUM_THREADS="20"
export TRANSACTION_LOAD_GENERATOR_TPS="5.0"
export CHAOS_DURATION_MINUTES="10"
```

## Execution

### Prerequisites

1. **Docker Environment**: All services must be running
2. **Chaos Toolkit**: Installed in the chaos-runner container
3. **Environment Variables**: Set all required variables (see Configuration section)

### Running the Experiment

#### Option 1: Using the Script (Recommended)

```bash
cd chaostooling-demo
./scripts/start-demo-and-run-test.sh
```

#### Option 2: Manual Execution

1. **Start the demo environment**:
   ```bash
   cd chaostooling-demo
   docker-compose up -d
   ```

2. **Wait for services to be ready** (30-60 seconds):
   ```bash
   docker-compose ps
   ```

3. **Run the experiment**:
   ```bash
   docker exec -it chaostooling-demo-chaos-runner-1 bash
   cd /experiments
   chaos run e2e-test/e2e-experiment.json
   ```

#### Option 3: With Custom Environment Variables

```bash
# Set custom variables
export STRESS_DURATION="300"
export NUM_THREADS="10"
export TRANSACTION_LOAD_GENERATOR_TPS="2.0"

# Run experiment
docker exec -it chaostooling-demo-chaos-runner-1 bash -c \
  "cd /experiments && chaos run e2e-test/e2e-experiment.json"
```

## Expected Outcomes

### Successful Run

1. **Baseline Phase**: 50 transactions complete successfully
2. **Chaos Phases**: All 29 scenarios execute while transactions continue
3. **Transaction Integrity**: All transactions maintain data consistency
4. **DR Failover**: System successfully fails over to replica/DR site
5. **Recovery**: All systems recover after rollbacks
6. **Final Validation**: All transaction counts match expected values

### Metrics to Monitor

- **Transaction Success Rate**: Should remain > 95% during chaos
- **Service Availability**: All services should remain accessible
- **Data Consistency**: Primary-replica consistency maintained
- **Replication Lag**: Should remain < 10 seconds
- **Error Rates**: Should spike during chaos but recover
- **Response Times**: Will increase during chaos scenarios

### Expected Duration

- **Total Runtime**: ~30-40 minutes
  - Baseline: 2 minutes
  - Chaos Scenarios: 25-30 minutes (overlapping)
  - Final Validation: 2 minutes
  - Reporting: 1-2 minutes

## Dashboard

The experiment includes a comprehensive Grafana dashboard: `e2e_experiment_dashboard.json`

### Dashboard Sections

1. **Service Graph**: Visual representation of all 17 hops and 29 scenarios
2. **Experiment Status**: Success rate, risk level, risk score, complexity score
3. **Transaction Metrics**: Request rate, latency (P95/P99), success rate
4. **Database Metrics**: 
   - PostgreSQL: CPU, memory, network IO, query rate, connection pool
   - MySQL: Query rate, connection count, order count
   - MongoDB: Document operations, query rate
   - Redis: Command rate, key operations
5. **Messaging Metrics**:
   - Kafka: Message rate, consumer lag, topic depth
   - RabbitMQ: Queue depth, message rate
   - ActiveMQ: Queue depth, message rate
6. **Infrastructure Metrics**: CPU usage, memory usage, network latency
7. **DR Status**: Primary-replica lag, failover status
8. **Chaos Scenario Status**: Active scenarios, scenario success rates

### Accessing the Dashboard

1. **Grafana URL**: http://localhost:3000
2. **Default Credentials**: admin/admin (change on first login)
3. **Import Dashboard**: Upload `chaostooling-demo/dashboards/e2e_experiment_dashboard.json`

## Troubleshooting

### Common Issues

#### 1. Load Generator Not Starting
**Symptom**: No transactions being generated
**Solution**: 
- Check `AUTO_START_LOAD_GENERATOR=true`
- Verify `TRANSACTION_LOAD_GENERATOR_URL` is correct
- Check transaction-load-generator container is running

#### 2. Service Graph Shows "test" or "unknown"
**Symptom**: MongoDB appears as "test" or services appear as "unknown"
**Solution**:
- Verify MongoDB connections set `network.peer.address` attribute
- Ensure all services use `trace_core.py` helpers for Kafka tracing
- Check OpenTelemetry instrumentation is properly configured

#### 3. Experiment Fails During Chaos
**Symptom**: Experiment fails with errors
**Solution**:
- Check service logs: `docker-compose logs <service-name>`
- Verify all services are healthy before starting
- Reduce `STRESS_DURATION` or `NUM_THREADS` for testing
- Check resource limits (CPU, memory)

#### 4. Transactions Not Completing
**Symptom**: Transaction counts don't match expected values
**Solution**:
- Increase `TEST_VALIDATION_DELAY_S` to allow async processing
- Check Kafka consumer lag
- Verify all messaging queues are processing messages
- Check database connection pools aren't exhausted

#### 5. DR Failover Not Working
**Symptom**: Replica doesn't promote after primary failure
**Solution**:
- Verify PostgreSQL replication is configured correctly
- Check container names match configuration
- Ensure replica has proper permissions
- Check replication lag before failover

### Debugging Commands

```bash
# Check service health
docker-compose ps

# View service logs
docker-compose logs app-server-1-site-a
docker-compose logs postgres-primary-site-a
docker-compose logs kafka

# Check transaction load generator
curl http://localhost:6002/stats

# Check database connectivity
docker exec -it chaostooling-demo-postgres-primary-site-a-1 psql -U postgres -d testdb -c "SELECT COUNT(*) FROM mobile_purchases;"

# Check Kafka topics
docker exec -it chaostooling-demo-kafka-1 kafka-topics.sh --list --bootstrap-server localhost:9092

# Check Prometheus metrics
curl http://localhost:9090/api/v1/query?query=chaos_chaos_experiment_success_ratio
```

## Integration with Observability

### OpenTelemetry Tracing

All operations are traced with OpenTelemetry:
- **Service Graph**: Shows all 17 hops in real-time
- **Distributed Traces**: Full trace context across all services
- **Span Attributes**: Database operations, messaging operations, chaos activities

### Prometheus Metrics

The experiment exposes comprehensive metrics:
- `chaos_chaos_experiment_success_ratio`: Overall experiment success
- `chaos_chaos_experiment_risk_level_ratio`: Risk level (1-4)
- `chaos_chaos_experiment_risk_score_ratio`: Risk score (0-100)
- `chaos_chaos_experiment_complexity_score_ratio`: Complexity score (0-100)
- `chaos_db_query_count_total`: Database query counts by system
- `chaos_db_query_latency_ms`: Database query latency
- `chaos_messaging_message_count_total`: Messaging operation counts

### Grafana Dashboards

- **E2E Experiment Dashboard**: Comprehensive view of all metrics
- **Service Graph**: Real-time service dependencies
- **Transaction Flow**: End-to-end transaction visualization

## Best Practices

1. **Start Small**: Begin with S/M sizing, then scale up
2. **Monitor Closely**: Watch dashboard during first runs
3. **Validate Incrementally**: Test individual scenarios before full run
4. **Resource Planning**: Ensure adequate CPU/memory for all services
5. **Backup First**: Backup databases before running DR scenarios
6. **Document Results**: Review experiment reports after each run
7. **Iterate**: Adjust parameters based on results

## Reporting

The experiment generates comprehensive reports:

- **Executive Summary**: High-level overview for management
- **Compliance Report**: Detailed compliance and audit trail
- **Product Owner Report**: Technical details for product teams
- **HTML & JSON Formats**: Multiple formats for different audiences

Reports are saved to: `${CHAOS_REPORTING_OUTPUT_DIR}` (default: `/var/log/chaostoolkit/reports`)

## Related Experiments

- **Enhanced Multi-Hop Transaction Validation**: Focused on transaction validation
- **Production-Scale Distributed Transaction**: Production-scale scenarios
- **Extensive PostgreSQL Experiment**: Deep PostgreSQL chaos testing

## Support

For issues or questions:
1. Check the troubleshooting section
2. Review service logs
3. Check Grafana dashboards for metrics
4. Review experiment reports

## Version History

- **v1.0.0**: Initial comprehensive E2E experiment with 29 scenarios
