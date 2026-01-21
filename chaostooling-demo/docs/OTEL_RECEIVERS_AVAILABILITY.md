# OpenTelemetry Collector Receivers - Availability Matrix

## Overview

This document provides a comprehensive overview of available OpenTelemetry Collector Contrib receivers for database and messaging systems used in the chaostooling-oss project.

**Key Finding**: All systems have metric receivers available, but **none generate server-side spans**. Span generation requires custom implementation.

---

## Database Systems

### PostgreSQL ✅

| Property | Value |
|----------|-------|
| **Receiver Name** | `postgresqlreceiver` |
| **Module** | `github.com/open-telemetry/opentelemetry-collector-contrib/receiver/postgresqlreceiver` |
| **Signals** | Metrics only |
| **Server-Side Spans** | ❌ No |
| **Status** | ✅ **Already configured in your OTEL Collector** |

**What It Collects**:
- Database-level metrics: `postgresql.db.size`, `postgresql.database.count`
- Connection metrics: `postgresql.backends`, `postgresql.connections`
- Transaction metrics: `postgresql.commits`, `postgresql.rollbacks`, `postgresql.deadlocks`
- I/O metrics: `postgresql.blocks_read`, `postgresql.bgwriter.*`
- Row operations: `postgresql.rows`, `postgresql.operations`
- Temporary files: `postgresql.temp_files`

**Configuration** (already in place):
```yaml
receivers:
  postgresql:
    endpoint: postgres-primary-site-a:5432
    username: postgres
    password: postgres
    databases: [testdb]
    collection_interval: 10s
```

**PostgreSQL Requirements**:
- ✅ No special configuration needed
- ✅ Uses standard `pg_stat_*` views (enabled by default)
- ✅ Works with `postgres` superuser (already configured)

**For Span Generation**: See [POSTGRESQL_SPAN_GENERATION_GUIDE.md](POSTGRESQL_SPAN_GENERATION_GUIDE.md)

---

### MySQL ✅

| Property | Value |
|----------|-------|
| **Receiver Name** | `mysqlreceiver` |
| **Module** | `github.com/open-telemetry/opentelemetry-collector-contrib/receiver/mysqlreceiver` |
| **Signals** | Metrics only |
| **Server-Side Spans** | ❌ No |
| **Status** | Available (not yet configured) |

**What It Collects**:
- Server metrics: `mysql.buffer_pool.pages`, `mysql.connections`, `mysql.threads`
- Query metrics: `mysql.queries`, `mysql.slow_queries`
- Lock metrics: `mysql.locks`, `mysql.lock_waits`
- Replication metrics: `mysql.replica_lag`, `mysql.replica_sql_delay`
- Table metrics: `mysql.table.rows`, `mysql.table.size`
- InnoDB metrics: `mysql.innodb.*`

**Configuration Example**:
```yaml
receivers:
  mysql:
    endpoint: mysql:3306
    username: root
    password: mysql
    database: testdb
    collection_interval: 10s
    metrics:
      mysql.buffer_pool.pages:
        enabled: true
      mysql.connections:
        enabled: true
      mysql.queries:
        enabled: true
```

**MySQL Requirements**:
- ✅ No special configuration needed
- ✅ Uses `SHOW GLOBAL STATUS`, `SHOW GLOBAL VARIABLES`
- ✅ Works with `root` user (already configured in docker-compose)
- Optional: Enable `performance_schema` for detailed metrics

**To Add to Your Collector**:
1. Add to `builder-config.yaml`: `- gomod: github.com/open-telemetry/opentelemetry-collector-contrib/receiver/mysqlreceiver v0.117.0`
2. Add receiver config to `config.yaml`
3. Add to metrics pipeline: `receivers: [mysql, ...]`
4. Rebuild: `docker-compose build otel-collector`

---

### MongoDB ✅

| Property | Value |
|----------|-------|
| **Receiver Name** | `mongodbreceiver` |
| **Module** | `github.com/open-telemetry/opentelemetry-collector-contrib/receiver/mongodbreceiver` |
| **Signals** | Metrics only |
| **Server-Side Spans** | ❌ No |
| **Status** | Available (not yet configured) |

**What It Collects**:
- Database metrics: `mongodb.database.count`, `mongodb.collection.count`
- Connection metrics: `mongodb.connection.count`, `mongodb.network.io.receive`, `mongodb.network.io.transmit`
- Operation metrics: `mongodb.operation.count` (insert, query, update, delete)
- Memory metrics: `mongodb.memory.usage`
- Lock metrics: `mongodb.lock.acquire.count`, `mongodb.lock.acquire.wait_count`
- Index metrics: `mongodb.index.count`, `mongodb.index.size`
- Replication metrics: `mongodb.replica_set.member_count`, `mongodb.replica_set.lag`

**Configuration Example**:
```yaml
receivers:
  mongodb:
    hosts:
      - endpoint: mongodb:27017
    username: ""
    password: ""
    collection_interval: 10s
    initial_delay: 10s
    metrics:
      mongodb.database.count:
        enabled: true
      mongodb.connection.count:
        enabled: true
      mongodb.operation.count:
        enabled: true
```

**MongoDB Requirements**:
- ✅ No authentication configured (default)
- ✅ Uses MongoDB driver's `serverStatus` and `dbStats` commands
- Optional: Enable `clusterMonitor` role for replica set metrics

**To Add to Your Collector**:
1. Add to `builder-config.yaml`: `- gomod: github.com/open-telemetry/opentelemetry-collector-contrib/receiver/mongodbreceiver v0.117.0`
2. Add receiver config to `config.yaml`
3. Rebuild collector

---

### Redis ✅

| Property | Value |
|----------|-------|
| **Receiver Name** | `redisreceiver` |
| **Module** | `github.com/open-telemetry/opentelemetry-collector-contrib/receiver/redisreceiver` |
| **Signals** | Metrics only |
| **Server-Side Spans** | ❌ No |
| **Status** | Available (not yet configured) |

**What It Collects**:
- Server metrics: `redis.uptime`, `redis.connected_clients`, `redis.blocked_clients`
- Memory metrics: `redis.memory.used`, `redis.memory.peak`, `redis.memory.rss`
- Persistence metrics: `redis.rdb.changes_since_last_save`, `redis.aof.size`
- Stats metrics: `redis.commands.processed`, `redis.connections.received`, `redis.connections.rejected`
- Key metrics: `redis.keys.evicted`, `redis.keys.expired`
- Network metrics: `redis.net.input`, `redis.net.output`
- Replication metrics: `redis.replication.offset`, `redis.replication.lag`

**Configuration Example**:
```yaml
receivers:
  redis:
    endpoint: redis:6379
    collection_interval: 10s
    password: ""
    transport: tcp
    metrics:
      redis.uptime:
        enabled: true
      redis.memory.used:
        enabled: true
      redis.commands.processed:
        enabled: true
```

**Redis Requirements**:
- ✅ No authentication configured (default)
- ✅ Uses Redis `INFO` command
- ✅ Works with default Redis configuration

**To Add to Your Collector**:
1. Add to `builder-config.yaml`: `- gomod: github.com/open-telemetry/opentelemetry-collector-contrib/receiver/redisreceiver v0.117.0`
2. Add receiver config to `config.yaml`
3. Rebuild collector

---

### Cassandra ✅ (via JMX)

| Property | Value |
|----------|-------|
| **Receiver Name** | `jmxreceiver` |
| **Module** | `github.com/open-telemetry/opentelemetry-collector-contrib/receiver/jmxreceiver` |
| **Signals** | Metrics only |
| **Server-Side Spans** | ❌ No |
| **Status** | Available (not yet configured) |

**What It Collects**:
- Client request metrics: `cassandra.client.request.count`, `cassandra.client.request.latency`
- Storage metrics: `cassandra.storage.load`, `cassandra.storage.total_hints`
- Compaction metrics: `cassandra.compaction.tasks.pending`, `cassandra.compaction.tasks.completed`
- Cache metrics: `cassandra.cache.hit_rate` (key cache, row cache)
- JVM metrics: heap usage, GC count, GC time, thread count

**Configuration Example**:
```yaml
receivers:
  jmx:
    endpoint: cassandra:7199
    target_system: cassandra,jvm
    collection_interval: 10s
    jar_path: /opt/opentelemetry-jmx-metrics.jar
```

**Cassandra Requirements**:
- ✅ JMX must be enabled (default on port 7199)
- ✅ No authentication by default
- Requires `opentelemetry-jmx-metrics.jar` file in OTEL Collector container

**To Add to Your Collector**:
1. Add to `builder-config.yaml`: `- gomod: github.com/open-telemetry/opentelemetry-collector-contrib/receiver/jmxreceiver v0.117.0`
2. Download `opentelemetry-jmx-metrics.jar` to otel-collector directory
3. Add receiver config with `target_system: cassandra`
4. Rebuild collector

**JAR Download**:
```bash
cd chaostooling-demo/otel-collector
wget https://github.com/open-telemetry/opentelemetry-java-instrumentation/releases/latest/download/opentelemetry-jmx-metrics.jar
```

---

### MSSQL/SQL Server ✅

| Property | Value |
|----------|-------|
| **Receiver Name** | `sqlserverreceiver` |
| **Module** | `github.com/open-telemetry/opentelemetry-collector-contrib/receiver/sqlserverreceiver` |
| **Signals** | Metrics only |
| **Server-Side Spans** | ❌ No |
| **Status** | Available (not yet configured) |

**What It Collects**:
- Database metrics: `sqlserver.database.count`, `sqlserver.database.io.*`
- Connection metrics: `sqlserver.user.connection.count`
- Lock metrics: `sqlserver.lock.wait_time`, `sqlserver.lock.wait.rate`
- Transaction metrics: `sqlserver.transaction.rate`, `sqlserver.transaction.write.rate`
- Buffer metrics: `sqlserver.page.buffer_cache.hit_ratio`, `sqlserver.page.life_expectancy`
- Batch requests: `sqlserver.batch.request.rate`, `sqlserver.batch.sql_compilation.rate`

**Configuration Example**:
```yaml
receivers:
  sqlserver:
    collection_interval: 10s
    username: sa
    password: Password123!
    server: mssql
    port: 1433
```

**SQL Server Requirements**:
- ✅ Works with `sa` user (already configured: `Password123!`)
- ✅ Uses Windows Performance Counters or direct connection
- ✅ Linux compatible (uses direct SQL queries)

**To Add to Your Collector**:
1. Add to `builder-config.yaml`: `- gomod: github.com/open-telemetry/opentelemetry-collector-contrib/receiver/sqlserverreceiver v0.117.0`
2. Add receiver config to `config.yaml`
3. Rebuild collector

---

## Messaging Systems

### Kafka ⚠️ (Special Case)

| Property | Value |
|----------|-------|
| **Receiver Name** | `kafkareceiver` |
| **Module** | `github.com/open-telemetry/opentelemetry-collector-contrib/receiver/kafkareceiver` |
| **Signals** | Traces, Metrics, Logs (all three!) |
| **Server-Side Spans** | ❌ No (consumes telemetry from topics) |
| **Status** | Available (not yet configured) |

**Important**: Kafka receiver **consumes telemetry data** from Kafka topics. It does NOT monitor Kafka itself or generate spans.

**What It Does**:
- Reads traces from `otlp_spans` topic
- Reads metrics from `otlp_metrics` topic
- Reads logs from `otlp_logs` topic
- Acts as a telemetry pipeline, not a Kafka monitor

**To Monitor Kafka Itself**, use `jmxreceiver`:

```yaml
receivers:
  jmx/kafka:
    endpoint: kafka:9999
    target_system: kafka,jvm
    jar_path: /opt/opentelemetry-jmx-metrics.jar
```

**Kafka JMX Metrics**:
- Broker metrics: `kafka.broker.messages_in`, `kafka.broker.bytes_in`
- Topic metrics: `kafka.topic.partitions`, `kafka.topic.offset`
- Consumer metrics: `kafka.consumer_group.lag`, `kafka.consumer_group.offset`
- Producer metrics: `kafka.producer.request_rate`, `kafka.producer.byte_rate`

**Kafka Requirements**:
- ✅ JMX exporter already configured in docker-compose (port 9999)
- ✅ JMX config file at `kafka-jmx/kafka-jmx-config.yml`

---

### RabbitMQ ✅

| Property | Value |
|----------|-------|
| **Receiver Name** | `rabbitmqreceiver` |
| **Module** | `github.com/open-telemetry/opentelemetry-collector-contrib/receiver/rabbitmqreceiver` |
| **Signals** | Metrics only |
| **Server-Side Spans** | ❌ No |
| **Status** | Beta (available, not yet configured) |

**What It Collects**:
- Node metrics: `rabbitmq.node.memory.used`, `rabbitmq.node.disk.free`
- Queue metrics: `rabbitmq.queue.messages`, `rabbitmq.queue.consumers`
- Connection metrics: `rabbitmq.connection.count`
- Channel metrics: `rabbitmq.channel.count`
- Message rates: `rabbitmq.message.published`, `rabbitmq.message.delivered`, `rabbitmq.message.acked`

**Configuration Example**:
```yaml
receivers:
  rabbitmq:
    endpoint: http://rabbitmq:15672
    username: chaos
    password: password
    collection_interval: 10s
    metrics:
      rabbitmq.node.memory.used:
        enabled: true
      rabbitmq.queue.messages:
        enabled: true
```

**RabbitMQ Requirements**:
- ✅ Management plugin must be enabled (default in `rabbitmq:3-management` image)
- ✅ User must have monitoring permissions (default `chaos` user works)
- ✅ Management UI on port 15672 (already exposed)

**To Add to Your Collector**:
1. Add to `builder-config.yaml`: `- gomod: github.com/open-telemetry/opentelemetry-collector-contrib/receiver/rabbitmqreceiver v0.117.0`
2. Add receiver config to `config.yaml`
3. Rebuild collector

---

### ActiveMQ ❌ (No Dedicated Receiver)

| Property | Value |
|----------|-------|
| **Receiver Name** | Use `jmxreceiver` |
| **Module** | `github.com/open-telemetry/opentelemetry-collector-contrib/receiver/jmxreceiver` |
| **Signals** | Metrics only (via JMX) |
| **Server-Side Spans** | ❌ No |
| **Status** | Available via JMX (not yet configured) |

**What It Collects** (via JMX):
- Broker metrics: `activemq.broker.memory_usage`, `activemq.broker.store_usage`
- Queue metrics: `activemq.queue.size`, `activemq.queue.consumer_count`
- Producer metrics: `activemq.producer.count`, `activemq.producer.message_rate`
- Consumer metrics: `activemq.consumer.count`, `activemq.consumer.message_rate`
- JVM metrics: heap usage, GC metrics

**Configuration Example**:
```yaml
receivers:
  jmx/activemq:
    endpoint: activemq:1099
    target_system: activemq,jvm
    jar_path: /opt/opentelemetry-jmx-metrics.jar
```

**ActiveMQ Requirements**:
- ⚠️ JMX must be enabled on ActiveMQ
- Need to add JMX port to docker-compose.yml
- Requires JMX configuration in ActiveMQ

**To Enable JMX in ActiveMQ**:

Add to docker-compose.yml:
```yaml
activemq:
  environment:
    - ACTIVEMQ_OPTS=-Dcom.sun.management.jmxremote -Dcom.sun.management.jmxremote.port=1099 -Dcom.sun.management.jmxremote.authenticate=false -Dcom.sun.management.jmxremote.ssl=false
  ports:
    - "1099:1099"  # JMX port
```

---

## Summary Matrix

| System | Receiver | Signals | Server Spans | Status | Action Required |
|--------|----------|---------|--------------|--------|-----------------|
| **PostgreSQL** | `postgresqlreceiver` | Metrics | ❌ No | ✅ Configured | None |
| **MySQL** | `mysqlreceiver` | Metrics | ❌ No | Available | Add to builder + config |
| **MongoDB** | `mongodbreceiver` | Metrics | ❌ No | Available | Add to builder + config |
| **Redis** | `redisreceiver` | Metrics | ❌ No | Available | Add to builder + config |
| **Cassandra** | `jmxreceiver` | Metrics | ❌ No | Available | Add to builder + download JAR |
| **MSSQL** | `sqlserverreceiver` | Metrics | ❌ No | Available | Add to builder + config |
| **Kafka** | `jmxreceiver` | Metrics | ❌ No | Available | Add to builder + download JAR |
| **RabbitMQ** | `rabbitmqreceiver` | Metrics | ❌ No | Available | Add to builder + config |
| **ActiveMQ** | `jmxreceiver` | Metrics | ❌ No | Available | Enable JMX + add to builder |

---

## Key Insights

### 1. All Receivers Collect Metrics Only

**None of these receivers generate server-side spans.** They collect operational metrics from the systems (CPU, memory, connections, etc.).

### 2. Span Generation Requires Custom Implementation

To get service graph visibility and query-level traces, you need to implement span generation separately. See:
- [POSTGRESQL_SPAN_GENERATION_GUIDE.md](POSTGRESQL_SPAN_GENERATION_GUIDE.md) for PostgreSQL
- Same approaches apply to other databases

### 3. JMX-Based Systems

Java-based systems (Cassandra, Kafka, ActiveMQ) use the `jmxreceiver` with `target_system` parameter:
- Requires `opentelemetry-jmx-metrics.jar`
- Connects to JMX port (7199 for Cassandra, 9999 for Kafka, 1099 for ActiveMQ)

### 4. Easy to Add

All receivers can be added to your existing OTEL Collector by:
1. Adding one line to `builder-config.yaml`
2. Adding receiver config to `config.yaml`
3. Updating metrics pipeline
4. Rebuilding: `docker-compose build otel-collector`

---

## Quick Setup: Add All Receivers

Want to add all available receivers at once?

### Step 1: Update builder-config.yaml

```yaml
receivers:
  - gomod: go.opentelemetry.io/collector/receiver/otlpreceiver v0.117.0
  - gomod: github.com/open-telemetry/opentelemetry-collector-contrib/receiver/prometheusreceiver v0.117.0
  - gomod: github.com/open-telemetry/opentelemetry-collector-contrib/receiver/dockerstatsreceiver v0.117.0
  - gomod: github.com/open-telemetry/opentelemetry-collector-contrib/receiver/postgresqlreceiver v0.117.0
  - gomod: github.com/open-telemetry/opentelemetry-collector-contrib/receiver/mysqlreceiver v0.117.0
  - gomod: github.com/open-telemetry/opentelemetry-collector-contrib/receiver/mongodbreceiver v0.117.0
  - gomod: github.com/open-telemetry/opentelemetry-collector-contrib/receiver/redisreceiver v0.117.0
  - gomod: github.com/open-telemetry/opentelemetry-collector-contrib/receiver/sqlserverreceiver v0.117.0
  - gomod: github.com/open-telemetry/opentelemetry-collector-contrib/receiver/rabbitmqreceiver v0.117.0
  - gomod: github.com/open-telemetry/opentelemetry-collector-contrib/receiver/jmxreceiver v0.117.0
```

### Step 2: Download JMX JAR

```bash
cd chaostooling-demo/otel-collector
wget https://github.com/open-telemetry/opentelemetry-java-instrumentation/releases/latest/download/opentelemetry-jmx-metrics.jar
```

### Step 3: Add Receivers to config.yaml

See individual sections above for configuration examples.

### Step 4: Update Metrics Pipeline

```yaml
metrics:
  receivers: [
    otlp,
    prometheus,
    docker_stats,
    postgresql,
    postgresql/replica,
    mysql,
    mongodb,
    redis,
    sqlserver,
    rabbitmq,
    jmx/cassandra,
    jmx/kafka,
    jmx/activemq,
    servicegraph
  ]
  processors: [batch]
  exporters: [prometheus]
```

### Step 5: Rebuild and Restart

```bash
docker-compose build otel-collector
docker-compose restart otel-collector
docker-compose logs -f otel-collector
```

---

## Next Steps

1. **Choose which receivers to add** based on your monitoring needs
2. **For span generation**: Follow [POSTGRESQL_SPAN_GENERATION_GUIDE.md](POSTGRESQL_SPAN_GENERATION_GUIDE.md)
3. **Create dashboards** for the new metrics in Grafana
4. **Set up alerts** in Prometheus for critical metrics

---

**Created**: 2026-01-21
**Last Updated**: 2026-01-21

**References**:
- [OpenTelemetry Collector Contrib Receivers](https://github.com/open-telemetry/opentelemetry-collector-contrib/tree/main/receiver)
- [PostgreSQL Receiver](https://github.com/open-telemetry/opentelemetry-collector-contrib/tree/main/receiver/postgresqlreceiver)
- [MySQL Receiver](https://github.com/open-telemetry/opentelemetry-collector-contrib/tree/main/receiver/mysqlreceiver)
- [MongoDB Receiver](https://github.com/open-telemetry/opentelemetry-collector-contrib/tree/main/receiver/mongodbreceiver)
- [Redis Receiver](https://github.com/open-telemetry/opentelemetry-collector-contrib/tree/main/receiver/redisreceiver)
- [SQL Server Receiver](https://github.com/open-telemetry/opentelemetry-collector-contrib/tree/main/receiver/sqlserverreceiver)
- [RabbitMQ Receiver](https://github.com/open-telemetry/opentelemetry-collector-contrib/tree/main/receiver/rabbitmqreceiver)
- [JMX Receiver](https://github.com/open-telemetry/opentelemetry-collector-contrib/tree/main/receiver/jmxreceiver)
- [Kafka Receiver](https://github.com/open-telemetry/opentelemetry-collector-contrib/tree/main/receiver/kafkareceiver)
