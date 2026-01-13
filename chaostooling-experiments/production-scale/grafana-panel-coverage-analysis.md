# Grafana Panel Coverage Analysis

## Overview

This document maps each scenario's expected outcomes to existing Grafana dashboard panels and identifies missing panels that should be added to provide complete visibility into chaos experiment results.

---

## Existing Panels in E2E Dashboard

### Experiment Overview & Status
- ✅ **Experiment Status** (Gauge) - Overall experiment success/failure
- ✅ **Risk Level** (Gauge) - Risk assessment
- ✅ **Risk Score** (Gauge) - Risk score calculation
- ✅ **Complexity Score** (Gauge) - Experiment complexity
- ✅ **Experiment Duration** (Time Series) - How long experiment has been running
- ✅ **Success vs Failed** (Time Series) - Success/failure over time
- ✅ **Overall Success Rate (%)** (Gauge) - Percentage of successful operations
- ✅ **Scenarios Tested** (Stat) - Number of scenarios
- ✅ **Total Activities** (Stat) - Total activities executed
- ✅ **Validation Probes** (Stat) - Number of validation probes
- ✅ **Current Running Activity** (Logs) - Current activity being executed
- ✅ **Test State** (Gauge) - Overall test health status

### Service Graph & Tracing
- ✅ **Service Graph** (Node Graph) - Visual service dependency map
- ✅ **Total Services in Graph** (Gauge) - Count of services in graph

### Transaction Metrics
- ✅ **Transactions Ran (Total/Successful/Failed)** (Time Series) - Transaction counts
- ✅ **Reconnection Attempts** (Time Series) - Database reconnection attempts

### System Health Metrics
- ✅ **Database Query Rate** (Time Series) - Queries per second by database
- ✅ **Database Query Latency (P95/P99)** (Time Series) - Database latency percentiles
- ✅ **Messaging System Message Rate** (Time Series) - Messages per second by messaging system
- ✅ **Database Errors** (Bar Gauge) - Errors by database system and type
- ✅ **Messaging System Errors** (Bar Gauge) - Errors by messaging system and type
- ✅ **Service Request Rate** (Time Series) - HTTP requests per second by service
- ✅ **Service Request Latency (P95/P99)** (Time Series) - Service latency percentiles

### Kafka Metrics
- ✅ **Kafka Bytes In/Out Rate** (Time Series)
- ✅ **Kafka Error Rate & Requests** (Time Series)
- ✅ **Kafka Message Rate** (Time Series)
- ✅ **Kafka Partition & Leader Metrics** (Time Series)
- ✅ **Kafka Producer Latency** (Time Series)
- ✅ **Kafka Request Success Rate** (Time Series)

### Service Graph Strength
- ✅ **Service Strength (Requests/Second)** (Time Series)
- ✅ **Connection Strength (Service-to-Service Request Rate)** (Time Series)
- ✅ **Database & Messaging System Strength (Requests/Second)** (Time Series)

### Logs
- ✅ **Experiment Execution Logs (with Progress)** (Logs) - Loki logs from experiment

---

## Scenario-by-Scenario Coverage Analysis

### Baseline: Distributed Transaction Flow

**Expected Outcomes:**
1. ✅ All 50 transactions complete successfully
2. ✅ Transaction integrity maintained across all databases
3. ✅ All services respond within normal latency (< 500ms)
4. ✅ OpenTelemetry traces show complete request flows (8-10 spans per transaction)

**Existing Panels:**
- ✅ **Transactions Ran (Total/Successful/Failed)** - Shows transaction completion
- ✅ **Service Request Latency (P95/P99)** - Shows latency (< 500ms)
- ✅ **Service Graph** - Shows complete request flows
- ✅ **Overall Success Rate (%)** - Shows transaction success rate

**Missing Panels:**
- ❌ **Transaction Integrity Check** - Panel showing transaction integrity validation results
- ❌ **Span Count per Transaction** - Panel showing number of spans per transaction (to verify 8-10 spans)
- ❌ **Baseline Latency Comparison** - Panel comparing current latency to baseline

---

### SCENARIO-1: Network Latency Across Sites

**Expected Outcomes:**
1. ⚠️ Transaction latency increases by ~500ms (acceptable degradation)
2. ✅ All transactions complete successfully (no failures)
3. ✅ System gracefully handles network delays
4. ⚠️ Some transactions may timeout or retry (expected behavior)
5. ✅ OpenTelemetry traces show increased span durations

**Existing Panels:**
- ✅ **Service Request Latency (P95/P99)** - Shows latency increase
- ✅ **Transactions Ran (Total/Successful/Failed)** - Shows transaction completion
- ✅ **Service Graph** - Shows span durations in traces

**Missing Panels:**
- ❌ **Network Latency Injection Status** - Panel showing when network latency is injected
- ❌ **Latency Delta (Current vs Baseline)** - Panel showing latency increase (should show ~500ms increase)
- ❌ **Timeout Rate** - Panel showing percentage of transactions that timeout
- ❌ **Retry Count** - Panel showing number of retries during latency
- ❌ **Cross-Site Latency** - Panel specifically for latency between primary and DR sites
- ❌ **Network Latency by Service** - Panel showing latency impact per service

---

### SCENARIO-2: Database Slow Transactions

**Expected Outcomes:**
1. ⚠️ Some transactions experience increased latency (3+ seconds)
2. ⚠️ Connection pool may approach exhaustion
3. ✅ Application continues to serve requests (graceful degradation)
4. ⚠️ Some requests may timeout or fail (acceptable under stress)
5. ✅ OpenTelemetry shows slow query spans and database lock metrics

**Existing Panels:**
- ✅ **Database Query Latency (P95/P99)** - Shows slow query latency
- ✅ **Database Errors** - Shows database errors
- ✅ **Service Request Latency (P95/P99)** - Shows application latency impact
- ✅ **Transactions Ran (Total/Successful/Failed)** - Shows transaction failures

**Missing Panels:**
- ❌ **Slow Transaction Count** - Panel showing number of transactions exceeding 3 seconds
- ❌ **Connection Pool Utilization** - Panel showing connection pool usage (to detect exhaustion)
- ❌ **Database Lock Metrics** - Panel showing lock counts, deadlocks, lock wait time
- ❌ **Slow Query Rate** - Panel showing rate of slow queries (> 1s, > 3s thresholds)
- ❌ **Database Lock Storm Visualization** - Panel showing lock contention over time
- ❌ **Connection Pool Exhaustion Events** - Panel showing when connection pools are exhausted

---

### SCENARIO-2B: Multi-Database Operations

**Expected Outcomes:**
1. ⚠️ Significant performance degradation across all databases
2. ⚠️ Increased error rates and timeouts
3. ✅ System continues operating (no complete failures)
4. ⚠️ Some transactions may fail or timeout (expected under extreme stress)
5. ✅ OpenTelemetry traces show database-specific errors and latencies
6. ✅ Service graph shows all databases under stress

**Existing Panels:**
- ✅ **Database Query Latency (P95/P99)** - Shows latency across databases
- ✅ **Database Errors** - Shows errors by database system
- ✅ **Database Query Rate** - Shows query rates per database
- ✅ **Service Graph** - Shows all databases in graph

**Missing Panels:**
- ❌ **Multi-Database Stress Status** - Panel showing which databases are under stress
- ❌ **Database Performance Degradation** - Panel comparing current vs baseline performance per database
- ❌ **Database-Specific Error Rates** - Panel showing error rates per database (PostgreSQL, MySQL, MSSQL, MongoDB, Redis, Cassandra)
- ❌ **Database Contention Metrics** - Panel showing lock contention, row contention, document contention per database
- ❌ **Database Connection Pool Status** - Panel showing connection pool status per database
- ❌ **Database Query Saturation** - Panel showing query saturation levels per database
- ❌ **Database Resource Utilization** - Panel showing CPU, memory, I/O per database

---

### SCENARIO-3: Multi-Messaging Event Flow

**Expected Outcomes:**
1. ⚠️ Message queues experience backpressure
2. ⚠️ Some messages may be delayed or lost (depending on queue configuration)
3. ✅ System continues processing transactions (eventual consistency)
4. ⚠️ Consumer lag increases (expected with slow consumers)
5. ✅ OpenTelemetry traces show messaging system latencies and errors
6. ✅ Service graph shows all messaging systems and their connections

**Existing Panels:**
- ✅ **Messaging System Message Rate** - Shows message rates
- ✅ **Messaging System Errors** - Shows messaging errors
- ✅ **Kafka Message Rate** - Shows Kafka-specific metrics
- ✅ **Kafka Producer Latency** - Shows Kafka latency
- ✅ **Service Graph** - Shows messaging systems

**Missing Panels:**
- ❌ **Queue Backpressure Status** - Panel showing queue depth and backpressure per messaging system
- ❌ **Message Delay/Loss Rate** - Panel showing delayed or lost messages
- ❌ **Consumer Lag** - Panel showing consumer lag for Kafka, RabbitMQ, ActiveMQ
- ❌ **Slow Consumer Detection** - Panel identifying slow consumers
- ❌ **Messaging System Saturation** - Panel showing saturation levels (topic/queue depth)
- ❌ **RabbitMQ Metrics** - Panel for RabbitMQ-specific metrics (queue depth, message rate, consumer count)
- ❌ **ActiveMQ Metrics** - Panel for ActiveMQ-specific metrics (queue depth, message rate, consumer count)
- ❌ **Message Processing Latency** - Panel showing end-to-end message processing time
- ❌ **Event-Driven Transaction Flow** - Panel showing transactions flowing through messaging systems

---

### SCENARIO-4: Application Server Failure

**Expected Outcomes:**
1. ✅ Load balancer detects server failure within seconds
2. ✅ Traffic automatically routes to healthy server (`app-server-2-site-a`)
3. ✅ No transaction failures (seamless failover)
4. ⚠️ Brief increase in latency during failover (< 1 second)
5. ✅ OpenTelemetry traces show requests routed to different servers
6. ✅ Service graph shows server health status

**Existing Panels:**
- ✅ **Service Request Rate** - Shows traffic routing to different servers
- ✅ **Service Request Latency (P95/P99)** - Shows failover latency spike
- ✅ **Service Graph** - Shows server health status
- ✅ **Transactions Ran (Total/Successful/Failed)** - Shows no transaction failures

**Missing Panels:**
- ❌ **Load Balancer Failover Events** - Panel showing when failover occurs
- ❌ **Server Health Status** - Panel showing health status of each application server
- ❌ **Failover Duration** - Panel showing time from failure detection to traffic rerouting
- ❌ **Server-Specific Request Distribution** - Panel showing request distribution across servers
- ❌ **HAProxy Backend Status** - Panel showing HAProxy backend server status
- ❌ **Failover Latency Spike** - Panel showing latency increase during failover (< 1s)
- ❌ **Server Availability** - Panel showing uptime/availability per server

---

### SCENARIO-5: Database Primary Failover

**Expected Outcomes:**
1. ⚠️ Primary database becomes unavailable
2. ✅ Replica remains accessible (if replication is configured)
3. ⚠️ Some transactions may fail (if application doesn't failover to replica)
4. ✅ System detects primary failure quickly
5. ✅ OpenTelemetry shows database connection errors
6. ✅ Service graph shows database health status

**Existing Panels:**
- ✅ **Database Errors** - Shows connection errors
- ✅ **Reconnection Attempts** - Shows reconnection attempts
- ✅ **Service Graph** - Shows database health status
- ✅ **Database Query Rate** - Shows query routing

**Missing Panels:**
- ❌ **Database Primary/Replica Status** - Panel showing which database is primary/replica
- ❌ **Database Failover Events** - Panel showing when primary fails and replica takes over
- ❌ **Replication Lag** - Panel showing replication lag between primary and replica
- ❌ **Database Connection Failures** - Panel showing connection failure rate
- ❌ **Database Failover Duration** - Panel showing time to failover (RTO)
- ❌ **Transaction Routing** - Panel showing which transactions route to primary vs replica
- ❌ **Database Availability** - Panel showing primary/replica availability

---

### SCENARIO-6: Disaster Recovery Site Failover

**Expected Outcomes:**
1. ✅ DR site becomes active and handles traffic
2. ✅ All transactions complete successfully through DR site
3. ⚠️ Initial latency may be higher (cold start, different network path)
4. ✅ Data consistency maintained across sites
5. ✅ OpenTelemetry traces show requests flowing through DR site
6. ✅ Service graph shows both primary and DR sites

**Existing Panels:**
- ✅ **Service Request Rate** - Shows traffic to DR site
- ✅ **Service Request Latency (P95/P99)** - Shows DR site latency
- ✅ **Service Graph** - Shows both sites
- ✅ **Transactions Ran (Total/Successful/Failed)** - Shows transaction success

**Missing Panels:**
- ❌ **Site Failover Status** - Panel showing which site is active (Primary vs DR)
- ❌ **DR Site Activation Time** - Panel showing time to activate DR site (RTO)
- ❌ **Cross-Site Data Consistency** - Panel showing data consistency between sites
- ❌ **Site-Specific Metrics** - Panel comparing metrics between primary and DR sites
- ❌ **DR Site Capacity** - Panel showing DR site capacity utilization
- ❌ **Network Path Latency** - Panel showing latency difference between primary and DR network paths
- ❌ **Site Health Status** - Panel showing health status of both sites
- ❌ **Traffic Distribution** - Panel showing traffic split between primary and DR sites

---

### SCENARIO-7: Full-Stack Stress Test

**Expected Outcomes:**
1. ⚠️ Severe performance degradation across all systems
2. ⚠️ High error rates and timeouts
3. ✅ System continues operating (no complete system failure)
4. ⚠️ Many transactions may fail or timeout (expected under extreme stress)
5. ✅ OpenTelemetry captures complete failure patterns
6. ✅ Service graph shows all systems under stress

**Existing Panels:**
- ✅ **Service Request Latency (P95/P99)** - Shows performance degradation
- ✅ **Database Errors** - Shows high error rates
- ✅ **Messaging System Errors** - Shows messaging errors
- ✅ **Transactions Ran (Total/Successful/Failed)** - Shows transaction failures
- ✅ **Service Graph** - Shows all systems under stress

**Missing Panels:**
- ❌ **System-Wide Stress Status** - Panel showing which systems are under stress
- ❌ **Resource Contention** - Panel showing CPU, memory, I/O contention across systems
- ❌ **Cascading Failure Detection** - Panel showing if failures cascade between systems
- ❌ **System Capacity Utilization** - Panel showing capacity usage across all systems
- ❌ **Stress Test Timeline** - Panel showing when different stress scenarios are active
- ❌ **Performance Degradation Heatmap** - Panel showing performance degradation across all services
- ❌ **Error Rate by System** - Panel showing error rates per system (database, messaging, compute)
- ❌ **Graceful Degradation Status** - Panel showing if systems degrade gracefully vs fail catastrophically

---

### SCENARIO-8: Final Transaction Integrity Check

**Expected Outcomes:**
1. ✅ All transactions maintain integrity (`is_integrity_ok: true`)
2. ✅ Data consistency verified across primary and replica
3. ✅ No orphaned records or corrupted data
4. ✅ Transaction counts match expected values

**Existing Panels:**
- ✅ **Transactions Ran (Total/Successful/Failed)** - Shows transaction counts

**Missing Panels:**
- ❌ **Transaction Integrity Status** - Panel showing transaction integrity check results
- ❌ **Data Consistency Status** - Panel showing data consistency between primary and replica
- ❌ **Orphaned Records Count** - Panel showing orphaned or corrupted records
- ❌ **Transaction Count Validation** - Panel comparing actual vs expected transaction counts
- ❌ **Data Integrity Metrics** - Panel showing integrity metrics (checksums, validation results)

---

## Summary of Missing Panels

### Critical Missing Panels (High Priority)

1. **Transaction Integrity & Data Consistency**
   - Transaction Integrity Status
   - Data Consistency Status (Primary vs Replica)
   - Transaction Count Validation

2. **Network & Latency**
   - Network Latency Injection Status
   - Latency Delta (Current vs Baseline)
   - Cross-Site Latency
   - Timeout Rate
   - Retry Count

3. **Database-Specific Metrics**
   - Connection Pool Utilization
   - Database Lock Metrics (locks, deadlocks, lock wait time)
   - Slow Query Rate (> 1s, > 3s thresholds)
   - Database-Specific Error Rates (per database system)
   - Database Contention Metrics
   - Replication Lag

4. **Messaging System Metrics**
   - Queue Backpressure Status
   - Consumer Lag (Kafka, RabbitMQ, ActiveMQ)
   - Message Delay/Loss Rate
   - RabbitMQ-Specific Metrics
   - ActiveMQ-Specific Metrics

5. **Failover & High Availability**
   - Load Balancer Failover Events
   - Server Health Status
   - Database Primary/Replica Status
   - Site Failover Status (Primary vs DR)
   - Failover Duration (RTO)

6. **Stress & Resource Monitoring**
   - System-Wide Stress Status
   - Resource Contention (CPU, Memory, I/O)
   - Connection Pool Exhaustion Events
   - System Capacity Utilization

### Medium Priority Missing Panels

7. **Baseline Comparison**
   - Baseline Latency Comparison
   - Performance Degradation (Current vs Baseline)
   - Span Count per Transaction

8. **Service-Specific Health**
   - HAProxy Backend Status
   - Server Availability
   - Database Availability

9. **Advanced Metrics**
   - Cascading Failure Detection
   - Graceful Degradation Status
   - Stress Test Timeline

---

## Recommended Panel Additions

### Priority 1: Critical for Experiment Validation

1. **Transaction Integrity Panel**
   - Query: Custom metric or probe result showing `is_integrity_ok`
   - Type: Stat/Gauge
   - Purpose: Validate SCENARIO-8 outcome

2. **Connection Pool Utilization Panel**
   - Query: `chaos_db_connection_pool_utilization` or similar
   - Type: Time Series
   - Purpose: Validate SCENARIO-2 connection pool exhaustion

3. **Database Lock Metrics Panel**
   - Query: `chaos_db_lock_count_total`, `chaos_db_deadlock_count_total`
   - Type: Time Series
   - Purpose: Validate SCENARIO-2 lock storm outcomes

4. **Consumer Lag Panel**
   - Query: Consumer lag metrics from Kafka, RabbitMQ, ActiveMQ
   - Type: Time Series
   - Purpose: Validate SCENARIO-3 slow consumer outcomes

5. **Failover Events Panel**
   - Query: Custom events or annotations for failover events
   - Type: Annotations or Stat
   - Purpose: Validate SCENARIO-4 and SCENARIO-5 failover outcomes

### Priority 2: Enhanced Visibility

6. **Network Latency Injection Status**
   - Query: Custom metric or annotation when latency is injected
   - Type: Annotation or Stat
   - Purpose: Correlate latency increases with injection events

7. **Queue Backpressure Status**
   - Query: Queue depth metrics from messaging systems
   - Type: Time Series
   - Purpose: Validate SCENARIO-3 backpressure outcomes

8. **Site Failover Status**
   - Query: Custom metric indicating active site (Primary vs DR)
   - Type: Stat
   - Purpose: Validate SCENARIO-6 DR failover

9. **Replication Lag Panel**
   - Query: PostgreSQL replication lag metrics
   - Type: Time Series
   - Purpose: Validate SCENARIO-5 database replication

10. **Slow Query Rate Panel**
    - Query: `rate(chaos_db_slow_query_count_total[5m])`
    - Type: Time Series
    - Purpose: Validate SCENARIO-2 slow transaction outcomes

---

## Implementation Notes

### Metrics That Need to Be Recorded

To support the missing panels, the following metrics should be recorded:

1. **Connection Pool Metrics:**
   - `chaos_db_connection_pool_active`
   - `chaos_db_connection_pool_max`
   - `chaos_db_connection_pool_utilization`

2. **Lock Metrics:**
   - `chaos_db_lock_count_total`
   - `chaos_db_deadlock_count_total`
   - `chaos_db_lock_wait_time_seconds`

3. **Consumer Lag:**
   - `chaos_messaging_consumer_lag` (for Kafka, RabbitMQ, ActiveMQ)

4. **Queue Metrics:**
   - `chaos_messaging_queue_depth`
   - `chaos_messaging_queue_backpressure`

5. **Failover Events:**
   - `chaos_failover_event_total` (with labels for type: server, database, site)

6. **Transaction Integrity:**
   - `chaos_transaction_integrity_check` (gauge: 0=failed, 1=passed)

7. **Replication Lag:**
   - `chaos_db_replication_lag_seconds`

8. **Network Latency:**
   - `chaos_network_latency_injected_ms` (annotation or metric)

---

## Next Steps

1. **Add Missing Metrics:** Update `chaosotel/core/metrics_core.py` to record the missing metrics
2. **Create Missing Panels:** Add panels to `e2e_dashboard.json` for each missing metric
3. **Test Panel Queries:** Verify that Prometheus queries return data during experiments
4. **Document Panel Usage:** Update this document with actual panel queries once implemented
