# Production-Scale Distributed Transaction Chaos Experiment

## Overview

This comprehensive chaos engineering experiment validates the resilience, observability, and disaster recovery capabilities of a production-scale distributed system. The experiment simulates real-world failure scenarios across 8-10 service hops, including databases, messaging systems, load balancers, and application servers across primary and disaster recovery (DR) sites.

**Experiment Duration:** ~45-60 minutes  
**Service Hops:** 8-10 (HA-Proxy → App Servers → Kafka → RabbitMQ → PostgreSQL Primary/Replica → DR Site → MongoDB → Redis)  
**Background Load:** Continuous transaction generation at 2 TPS throughout the experiment

---

## Background Transaction Load Generator

The experiment includes a **background transaction load generator** that runs continuously throughout the entire experiment lifecycle:

- **Starts:** Before steady-state hypothesis validation (`before_experiment_control`)
- **Runs:** Throughout all chaos scenarios and method execution
- **Stops:** After experiment completion (`after_experiment_control`)
- **Cleanup:** Ensures proper shutdown even if experiment fails (`cleanup_control`)

**Configuration:**
- **URL:** `http://transaction-load-generator:5001` (configurable via `TRANSACTION_LOAD_GENERATOR_URL`)
- **TPS:** 2.0 transactions per second (configurable via `TRANSACTION_LOAD_GENERATOR_TPS`)
- **Auto-start:** Enabled by default (configurable via `AUTO_START_LOAD_GENERATOR`)

**What it does:**
- Generates continuous distributed transactions flowing through:
  - App Server → Payment Service → RabbitMQ → PostgreSQL
  - App Server → Order Service → Kafka → MySQL
  - App Server → Inventory Service → MongoDB → Redis
  - Event-driven updates to MSSQL, Cassandra via messaging

**Why it matters:**
- Simulates realistic production traffic during chaos scenarios
- Tests system behavior under concurrent load and failures
- Validates that observability (traces, metrics, logs) captures real user impact
- Ensures chaos scenarios don't run in isolation but under realistic conditions

**How to Verify It's Running:**
1. **Check Logs:** Look for `"Load generator started successfully"` in `chaostoolkit.log`
2. **Check Stats:** The control verifies load generator status after startup
3. **Monitor Traces:** OpenTelemetry traces should show continuous transaction flows throughout the experiment
4. **Check Metrics:** Prometheus metrics should show continuous transaction rate (~2 TPS)
5. **Manual Verification:** You can call the load generator API directly:
   ```bash
   docker compose exec chaos-runner python3 -c "
   import requests
   stats = requests.get('http://transaction-load-generator:5001/stats').json()
   print('Load Generator Status:', stats)
   "
   ```

---

## Experiment Scenarios

### Baseline: Distributed Transaction Flow

**Purpose:** Establish baseline performance and validate normal operation before chaos injection.

**Actions:**
- Execute 50 baseline distributed transactions through the full stack
- Verify transaction count in PostgreSQL
- Validate all services are healthy and accessible

**Expected Outcome:**
- ✅ All 50 transactions complete successfully
- ✅ Transaction integrity maintained across all databases
- ✅ All services respond within normal latency (< 500ms)
- ✅ OpenTelemetry traces show complete request flows (8-10 spans per transaction)

**Organizational Insights:**
- **Baseline Performance Metrics:** Establishes normal latency, throughput, and error rates
- **Service Dependency Map:** Visualizes actual service dependencies via distributed tracing
- **Transaction Flow Validation:** Confirms end-to-end transaction integrity in normal conditions
- **Observability Coverage:** Validates that all services are properly instrumented and visible

---

### SCENARIO-1: Network Latency Across Sites

**Purpose:** Test system resilience to network degradation between primary and DR sites.

**Actions:**
- Inject 500ms network latency for 30 seconds
- Execute 30 distributed transactions during latency injection
- Monitor transaction completion and error rates

**Expected Outcome:**
- ⚠️ Transaction latency increases by ~500ms (acceptable degradation)
- ✅ All transactions complete successfully (no failures)
- ✅ System gracefully handles network delays
- ⚠️ Some transactions may timeout or retry (expected behavior)
- ✅ OpenTelemetry traces show increased span durations

**Organizational Insights:**
- **Network Resilience:** Validates that the system can handle WAN latency between sites
- **Timeout Configuration:** Reveals if timeout values are appropriate for cross-site communication
- **Retry Logic:** Tests whether retry mechanisms work correctly under latency
- **User Experience Impact:** Measures actual user-facing latency during network issues
- **DR Site Readiness:** Confirms DR site can handle traffic during network degradation
- **Cost Optimization:** Identifies if cross-site communication can be optimized (caching, async processing)

---

### SCENARIO-2: Database Slow Transactions

**Purpose:** Test application behavior when database operations become slow due to resource contention or maintenance.

**Actions:**
- Inject slow transactions in PostgreSQL (5 threads, 3-second delays, 20 seconds duration)
- Execute 30 distributed transactions during slow DB operations
- Monitor application timeouts, connection pool exhaustion, and user experience

**Expected Outcome:**
- ⚠️ Some transactions experience increased latency (3+ seconds)
- ⚠️ Connection pool may approach exhaustion
- ✅ Application continues to serve requests (graceful degradation)
- ⚠️ Some requests may timeout or fail (acceptable under stress)
- ✅ OpenTelemetry shows slow query spans and database lock metrics

**Organizational Insights:**
- **Database Performance:** Identifies slow query patterns and resource bottlenecks
- **Connection Pool Sizing:** Reveals if connection pools are appropriately sized
- **Application Resilience:** Tests if applications handle slow databases gracefully
- **User Experience:** Measures actual impact on end users during database issues
- **Capacity Planning:** Provides data for database capacity and scaling decisions
- **Alerting Thresholds:** Validates that slow query alerts trigger appropriately

---

### SCENARIO-2B: Multi-Database Operations

**Purpose:** Test system behavior when multiple databases experience concurrent stress.

**Actions:**
- **PostgreSQL:** Query saturation (20 threads, 1000 queries/thread, 60s)
- **PostgreSQL:** Lock storm (10 threads, 60s)
- **PostgreSQL:** Connection pool exhaustion (100 connections, 60s)
- **MySQL:** Slow transactions (5 threads, 3s delays, 60s)
- **MySQL:** Query saturation (20 threads, 60s)
- **MSSQL:** Slow transactions (5 threads, 3s delays, 60s)
- **MongoDB:** Document contention (10 threads, 60s)
- **MongoDB:** Query saturation (20 threads, 60s)
- **Redis:** Key contention (10 threads, 60s)
- **Redis:** Command saturation (20 threads, 60s)
- **Cassandra:** Row contention (10 threads, 60s)
- Execute 30 distributed transactions during multi-database stress

**Expected Outcome:**
- ⚠️ Significant performance degradation across all databases
- ⚠️ Increased error rates and timeouts
- ✅ System continues operating (no complete failures)
- ⚠️ Some transactions may fail or timeout (expected under extreme stress)
- ✅ OpenTelemetry traces show database-specific errors and latencies
- ✅ Service graph shows all databases under stress

**Organizational Insights:**
- **Multi-Database Resilience:** Tests if the system can handle concurrent database issues
- **Database Isolation:** Validates that issues in one database don't cascade to others
- **Resource Contention:** Identifies which databases are most vulnerable to contention
- **Scaling Strategy:** Provides data for database scaling and sharding decisions
- **Monitoring Coverage:** Validates that all databases are properly monitored
- **Incident Response:** Tests if teams can identify and respond to multi-database issues
- **Architecture Review:** Reveals if database choices are appropriate for workload patterns

---

### SCENARIO-3: Multi-Messaging Event Flow

**Purpose:** Test system behavior when messaging systems (Kafka, RabbitMQ, ActiveMQ) experience saturation and failures.

**Actions:**
- **Kafka:** Message flood (10 producers, 1000 messages each, 60s)
- **Kafka:** Topic saturation (20 producers, 60s)
- **Kafka:** Slow consumer (5 consumers, 5s delays, 60s)
- **RabbitMQ:** Message flood (10 producers, 1000 messages each, 60s)
- **RabbitMQ:** Queue saturation (20 producers, 60s)
- **ActiveMQ:** Message flood (10 producers, 1000 messages each, 60s)
- Execute 30 distributed transactions during messaging stress

**Expected Outcome:**
- ⚠️ Message queues experience backpressure
- ⚠️ Some messages may be delayed or lost (depending on queue configuration)
- ✅ System continues processing transactions (eventual consistency)
- ⚠️ Consumer lag increases (expected with slow consumers)
- ✅ OpenTelemetry traces show messaging system latencies and errors
- ✅ Service graph shows all messaging systems and their connections

**Organizational Insights:**
- **Messaging Resilience:** Tests if the system handles messaging system failures gracefully
- **Event-Driven Architecture:** Validates event processing under stress
- **Queue Management:** Identifies if queue sizes and retention policies are appropriate
- **Consumer Performance:** Reveals slow consumer patterns and processing bottlenecks
- **Message Loss Prevention:** Tests if critical messages are preserved during failures
- **Scalability:** Provides data for messaging system scaling decisions
- **Observability:** Validates that messaging systems are properly instrumented

---

### SCENARIO-4: Application Server Failure

**Purpose:** Test load balancer failover and application server redundancy.

**Actions:**
- Stop `app-server-1-site-a` container
- Execute 30 distributed transactions
- Verify load balancer routes traffic to `app-server-2-site-a`
- Restart `app-server-1-site-a`

**Expected Outcome:**
- ✅ Load balancer detects server failure within seconds
- ✅ Traffic automatically routes to healthy server (`app-server-2-site-a`)
- ✅ No transaction failures (seamless failover)
- ⚠️ Brief increase in latency during failover (< 1 second)
- ✅ OpenTelemetry traces show requests routed to different servers
- ✅ Service graph shows server health status

**Organizational Insights:**
- **High Availability:** Validates that load balancer failover works correctly
- **Server Redundancy:** Confirms that multiple application servers provide redundancy
- **Failover Time:** Measures actual failover duration (RTO - Recovery Time Objective)
- **User Impact:** Quantifies user-facing impact during server failures
- **Health Check Configuration:** Tests if health checks detect failures quickly enough
- **Capacity Planning:** Validates if remaining servers can handle full load
- **Incident Response:** Tests if monitoring alerts trigger on server failures

---

### SCENARIO-5: Database Primary Failover

**Purpose:** Test database replication and failover to replica during primary database failure.

**Actions:**
- Stop `postgres-primary-site-a` container
- Verify replica connectivity
- Execute transactions (should route to replica or fail gracefully)
- Restart primary database

**Expected Outcome:**
- ⚠️ Primary database becomes unavailable
- ✅ Replica remains accessible (if replication is configured)
- ⚠️ Some transactions may fail (if application doesn't failover to replica)
- ✅ System detects primary failure quickly
- ✅ OpenTelemetry shows database connection errors
- ✅ Service graph shows database health status

**Organizational Insights:**
- **Database High Availability:** Tests if database replication provides true HA
- **Failover Automation:** Reveals if automatic failover is configured or manual intervention is needed
- **Data Consistency:** Validates that replica data is consistent with primary
- **Application Resilience:** Tests if applications can handle primary database failures
- **RTO/RPO:** Measures Recovery Time Objective and Recovery Point Objective
- **Backup Strategy:** Validates that backups are available and tested
- **Disaster Recovery:** Tests if DR procedures are documented and effective

---

### SCENARIO-6: Disaster Recovery Site Failover

**Purpose:** Test complete site failover to DR site when primary site becomes unavailable.

**Actions:**
- Stop `haproxy-site-a` (primary site load balancer)
- Execute 20 transactions through DR site (`haproxy-site-b`)
- Verify DR site can handle production traffic
- Restart primary site load balancer

**Expected Outcome:**
- ✅ DR site becomes active and handles traffic
- ✅ All transactions complete successfully through DR site
- ⚠️ Initial latency may be higher (cold start, different network path)
- ✅ Data consistency maintained across sites
- ✅ OpenTelemetry traces show requests flowing through DR site
- ✅ Service graph shows both primary and DR sites

**Organizational Insights:**
- **Disaster Recovery Readiness:** Validates that DR site can handle production traffic
- **RTO Validation:** Measures actual time to failover to DR site
- **Data Synchronization:** Tests if data is properly replicated to DR site
- **Network Configuration:** Validates DNS and routing to DR site
- **Capacity Validation:** Confirms DR site has sufficient capacity
- **Documentation:** Tests if DR runbooks are accurate and complete
- **Business Continuity:** Validates that business operations can continue during primary site failure
- **Cost Analysis:** Provides data for DR site sizing and cost optimization

---

### SCENARIO-7: Full-Stack Stress Test

**Purpose:** Test system behavior under extreme concurrent stress across compute, database, and messaging systems.

**Actions:**
- **CPU Stress:** 80% load on 2 cores for 60 seconds
- **PostgreSQL:** Query saturation (20 threads, 60s) during CPU stress
- **Memory Stress:** 2GB memory allocation for 60 seconds
- **Kafka:** Topic saturation (20 producers, 60s) during memory stress
- Execute 50 distributed transactions during full-stack stress

**Expected Outcome:**
- ⚠️ Severe performance degradation across all systems
- ⚠️ High error rates and timeouts
- ✅ System continues operating (no complete system failure)
- ⚠️ Many transactions may fail or timeout (expected under extreme stress)
- ✅ OpenTelemetry captures complete failure patterns
- ✅ Service graph shows all systems under stress

**Organizational Insights:**
- **System Limits:** Identifies absolute system capacity and breaking points
- **Resource Contention:** Reveals which resources (CPU, memory, I/O) are bottlenecks
- **Cascading Failures:** Tests if failures in one system cascade to others
- **Graceful Degradation:** Validates if the system degrades gracefully under extreme stress
- **Capacity Planning:** Provides critical data for capacity and scaling decisions
- **Performance Testing:** Validates that performance tests match real-world stress scenarios
- **Monitoring Gaps:** Identifies if all critical metrics are being monitored
- **Alerting Thresholds:** Tests if alerts trigger appropriately under extreme conditions

---

### SCENARIO-8: Final Transaction Integrity Check

**Purpose:** Validate that all transactions maintained data integrity throughout all chaos scenarios.

**Actions:**
- Verify transaction integrity in PostgreSQL
- Check data consistency across primary and replica
- Validate that no transactions were lost or corrupted

**Expected Outcome:**
- ✅ All transactions maintain integrity (`is_integrity_ok: true`)
- ✅ Data consistency verified across primary and replica
- ✅ No orphaned records or corrupted data
- ✅ Transaction counts match expected values

**Organizational Insights:**
- **Data Integrity:** Confirms that chaos scenarios don't corrupt data
- **Transaction Safety:** Validates ACID properties are maintained under stress
- **Audit Trail:** Provides evidence that system maintains data integrity
- **Compliance:** Demonstrates that system meets data integrity requirements
- **Confidence:** Builds confidence that the system can handle failures safely

---

## Post-Experiment Verification

After all scenarios complete, the experiment verifies:

1. **MySQL Connectivity:** Ensures MySQL is accessible after all operations
2. **MSSQL Connectivity:** Ensures MSSQL is accessible after all operations
3. **Cassandra Connectivity:** Ensures Cassandra is accessible after all operations
4. **ActiveMQ Connectivity:** Ensures ActiveMQ is accessible after all operations
5. **Data Consistency:** Validates data consistency across primary and replica databases

**Expected Outcome:**
- ✅ All databases and messaging systems are accessible
- ✅ Data consistency maintained across all systems
- ✅ No permanent damage from chaos scenarios

---

## Expected Overall Outcomes

### ✅ Success Criteria

1. **Resilience:** System continues operating (even with degraded performance) during all chaos scenarios
2. **Observability:** All failures and performance issues are captured in OpenTelemetry traces, metrics, and logs
3. **Data Integrity:** No data corruption or loss throughout the experiment
4. **Failover:** Load balancer and database failover mechanisms work correctly
5. **DR Readiness:** DR site can handle production traffic when primary site fails

### ⚠️ Acceptable Degradations

- Increased latency during stress scenarios
- Some transaction timeouts under extreme stress
- Temporary service unavailability during failover (< 5 seconds)
- Increased error rates during concurrent stress scenarios

### ❌ Failure Indicators

- Complete system failure (all services down)
- Data corruption or loss
- Failover mechanisms not working
- DR site unable to handle traffic
- Observability gaps (missing traces, metrics, or logs)

---

## Organizational Insights & Business Value

### 1. **Risk Assessment & Mitigation**

**What it reveals:**
- Identifies single points of failure (SPOFs) in the architecture
- Validates that redundancy and failover mechanisms work as designed
- Tests disaster recovery procedures and validates RTO/RPO objectives

**Business Value:**
- **Reduced Downtime:** Proactive identification of failure modes prevents production incidents
- **Compliance:** Demonstrates that disaster recovery procedures are tested and validated
- **Insurance:** Provides evidence of system resilience for audits and insurance claims
- **Confidence:** Builds stakeholder confidence in system reliability

---

### 2. **Performance & Capacity Planning**

**What it reveals:**
- Actual system capacity under stress (not just theoretical)
- Resource bottlenecks (CPU, memory, I/O, network, database connections)
- Scaling thresholds and when to scale horizontally or vertically

**Business Value:**
- **Cost Optimization:** Right-size infrastructure based on actual capacity needs
- **Capacity Planning:** Data-driven decisions on when to scale (prevent over/under-provisioning)
- **Performance SLA:** Validates that performance SLAs can be met under stress
- **Budget Planning:** Accurate capacity forecasts for budget planning

---

### 3. **Observability & Monitoring Maturity**

**What it reveals:**
- Coverage of observability (are all services properly instrumented?)
- Alerting effectiveness (do alerts trigger at appropriate thresholds?)
- Trace completeness (can you trace a request through all 8-10 hops?)
- Metric accuracy (do metrics reflect actual system behavior?)

**Business Value:**
- **Faster Incident Response:** Better observability = faster problem identification and resolution
- **Proactive Monitoring:** Identify issues before they impact users
- **Root Cause Analysis:** Complete traces enable faster root cause analysis
- **SRE Maturity:** Demonstrates Site Reliability Engineering best practices

---

### 4. **Architecture & Design Validation**

**What it reveals:**
- Service dependency map (actual dependencies vs. documented)
- Database choice appropriateness (are databases suitable for workload patterns?)
- Messaging system effectiveness (do queues handle backpressure correctly?)
- Load balancer configuration (is failover fast enough?)

**Business Value:**
- **Architecture Optimization:** Identify opportunities to improve architecture
- **Technology Decisions:** Validate that technology choices are appropriate
- **Technical Debt:** Identify areas that need refactoring or optimization
- **Best Practices:** Ensure architecture follows industry best practices

---

### 5. **Team Readiness & Incident Response**

**What it reveals:**
- Team's ability to identify and respond to incidents
- Documentation accuracy (do runbooks match actual procedures?)
- Monitoring effectiveness (can teams see what's happening?)
- Alerting relevance (are alerts actionable?)

**Business Value:**
- **Reduced MTTR:** Faster Mean Time To Recovery through better preparedness
- **Team Training:** Identifies areas where teams need additional training
- **Process Improvement:** Validates incident response procedures
- **Knowledge Sharing:** Creates shared understanding of system behavior

---

### 6. **User Experience Impact**

**What it reveals:**
- Actual user-facing impact during failures (not just technical metrics)
- Graceful degradation (does the system degrade gracefully or fail catastrophically?)
- Timeout and retry effectiveness (do timeouts and retries help or hurt?)

**Business Value:**
- **Customer Satisfaction:** Minimize user impact during incidents
- **SLA Compliance:** Ensure SLAs are met even during failures
- **Product Quality:** Improve product reliability and user experience
- **Competitive Advantage:** More reliable systems = competitive advantage

---

### 7. **Compliance & Audit Trail**

**What it reveals:**
- System behavior under stress (documented evidence)
- Disaster recovery validation (proof that DR procedures work)
- Data integrity validation (proof that data remains consistent)

**Business Value:**
- **Regulatory Compliance:** Demonstrates compliance with regulations (SOC 2, ISO 27001, etc.)
- **Audit Readiness:** Provides evidence for audits and certifications
- **Risk Management:** Documents risk mitigation strategies
- **Stakeholder Confidence:** Builds confidence with executives, board, and customers

---

## Key Metrics to Monitor

### Performance Metrics
- **Transaction Latency:** P50, P95, P99 latencies during each scenario
- **Throughput:** Transactions per second (TPS) during stress
- **Error Rate:** Percentage of failed transactions
- **Timeout Rate:** Percentage of transactions that timeout

### Availability Metrics
- **Uptime:** Service availability during chaos scenarios
- **Failover Time:** Time to failover (RTO)
- **Recovery Time:** Time to recover from failures
- **Data Loss:** Recovery Point Objective (RPO)

### Observability Metrics
- **Trace Coverage:** Percentage of requests with complete traces
- **Metric Coverage:** Number of metrics captured per service
- **Alert Accuracy:** Percentage of alerts that are actionable
- **Log Completeness:** Percentage of events logged

### Business Metrics
- **User Impact:** Number of users affected during failures
- **Revenue Impact:** Estimated revenue loss during downtime
- **SLA Compliance:** Percentage of time SLAs are met
- **Incident Count:** Number of incidents that would have occurred without chaos engineering

---

## Recommendations for Organizations

### 1. **Run Regularly**
- Schedule chaos experiments weekly or monthly
- Include chaos engineering in CI/CD pipelines
- Make chaos experiments part of release validation

### 2. **Start Small, Scale Up**
- Begin with single-service failures
- Gradually increase complexity (multi-service, full-stack)
- Test disaster recovery scenarios quarterly

### 3. **Document Everything**
- Document all findings and insights
- Update runbooks based on chaos experiment results
- Share learnings across teams

### 4. **Integrate with Observability**
- Ensure all services are properly instrumented
- Validate that traces, metrics, and logs are complete
- Test alerting thresholds regularly

### 5. **Involve All Stakeholders**
- Include SRE, DevOps, Development, and Product teams
- Share results with executives and business stakeholders
- Use results to drive architecture and process improvements

---

## Conclusion

This production-scale chaos experiment provides comprehensive validation of system resilience, observability, and disaster recovery capabilities. By running this experiment regularly, organizations can:

- **Prevent Production Incidents:** Identify and fix issues before they impact users
- **Validate Architecture:** Ensure architecture decisions are sound
- **Improve Observability:** Ensure all systems are properly monitored
- **Test Disaster Recovery:** Validate that DR procedures work correctly
- **Build Confidence:** Demonstrate system reliability to stakeholders
- **Drive Improvements:** Use insights to continuously improve the system

The combination of chaos engineering and comprehensive observability (OpenTelemetry) provides unprecedented visibility into system behavior under stress, enabling data-driven decisions about architecture, capacity, and reliability.
