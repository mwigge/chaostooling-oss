# Plan: Add Test + Probe to Every Scenario with Proper Chaosotel Integration

## Overview
This plan ensures every scenario has:
1. **A chaos test** (action that tests the system under chaos conditions)
2. **A probe** (validation/status check)
3. **Proper chaosotel integration** (all activities use chaosotel for tracing, metrics, and logs)

**Note:** All existing probes and actions already use chaosotel via `from chaosotel import ...`, so we just need to ensure proper structure.

## Pattern for Each Scenario

Each scenario should follow this structure:
1. `SCENARIO-X-Name` (action - injects chaos)
2. `test-*-during-X` (action - chaos test, tests system under chaos)
3. `probe-X-status` (probe - validates/checks status)

## Scenarios Requiring Activities

### Scenarios Missing Both Test and Probe (0 activities)

These scenarios need both a chaos test AND a probe added.

### Scenarios Missing Either Test or Probe (1 activity)

These scenarios already have 1 activity but need the missing one added.

#### SCENARIO-1-PostgreSQL-Cache-Miss-Storm
**Current Status:** Has test, missing probe  
**Location:** After line 634 (after test-transactions-during-cache-miss)

**Probe to Add:**
```json
{
  "name": "probe-postgres-cache-miss-status",
  "type": "probe",
  "provider": {
    "type": "python",
    "module": "chaosdb.probes.postgres.postgres_system_metrics",
    "func": "collect_postgres_system_metrics",
    "arguments": {
      "host": "${postgres_primary_host}",
      "port": "${postgres_port}",
      "database": "${postgres_db}",
      "user": "${postgres_user}",
      "password": "${postgres_password}"
    }
  },
  "tolerance": true
}
```

#### SCENARIO-4-PostgreSQL-Lock-Storm
**Current Status:** Has test, missing probe  
**Location:** After line 701 (after test-transactions-during-lock-storm)

**Probe to Add:**
```json
{
  "name": "probe-postgres-lock-storm-status",
  "type": "probe",
  "provider": {
    "type": "python",
    "module": "chaosdb.probes.postgres.postgres_lock_storm_status",
    "func": "probe_lock_storm_status",
    "arguments": {
      "host": "${postgres_primary_host}",
      "port": "${postgres_port}",
      "database": "${postgres_db}",
      "user": "${postgres_user}",
      "password": "${postgres_password}"
    }
  },
  "tolerance": true
}
```

#### SCENARIO-6-PostgreSQL-Query-Saturation
**Current Status:** Has probe, missing test  
**Location:** After line 740 (after SCENARIO-6 action, before probe)

**Chaos Test to Add:**
```json
{
  "name": "test-transactions-during-postgres-query-saturation",
  "type": "action",
  "provider": {
    "type": "python",
    "module": "chaosdb.probes.postgres.postgres_transaction_validation",
    "func": "probe_api_transaction_flow",
    "arguments": {
      "api_url": "${site_a_haproxy_url}",
      "num_transactions": "${distributed_transaction_test_count}"
    }
  }
}
```

#### SCENARIO-7-PostgreSQL-Slow-Transactions
**Current Status:** Has test, missing probe  
**Location:** After line 789 (after test-transactions-during-slow-postgres)

**Probe to Add:**
```json
{
  "name": "probe-postgres-slow-transactions-status",
  "type": "probe",
  "provider": {
    "type": "python",
    "module": "chaosdb.probes.postgres.postgres_slow_transactions_status",
    "func": "probe_slow_transactions_status",
    "arguments": {
      "host": "${postgres_primary_host}",
      "port": "${postgres_port}",
      "database": "${postgres_db}",
      "user": "${postgres_user}",
      "password": "${postgres_password}"
    }
  },
  "tolerance": true
}
```

#### SCENARIO-8-Network-Latency-Across-Sites
**Current Status:** Has test, missing probe  
**Location:** After line 816 (after test-distributed-transactions-under-latency)

**Probe to Add:**
```json
{
  "name": "probe-network-latency-status",
  "type": "probe",
  "provider": {
    "type": "python",
    "module": "chaosnetwork.probes.network_latency",
    "func": "probe_network_latency",
    "arguments": {
      "target_host": "${postgres_primary_host}",
      "duration_seconds": 10
    }
  },
  "tolerance": true
}
```

### Scenarios Missing Both Test and Probe (0 activities)

These scenarios need both a chaos test AND a probe added.

### PostgreSQL Scenarios

#### SCENARIO-2-PostgreSQL-Vacuum-Starvation
**Current Status:** 0 activities  
**Location:** After line 652

**1. Chaos Test to Add:**
```json
{
  "name": "test-transactions-during-vacuum-starvation",
  "type": "action",
  "provider": {
    "type": "python",
    "module": "chaosdb.probes.postgres.postgres_transaction_validation",
    "func": "probe_api_transaction_flow",
    "arguments": {
      "api_url": "${site_a_haproxy_url}",
      "num_transactions": "${distributed_transaction_test_count}"
    }
  }
}
```

**2. Probe to Add:**
```json
{
  "name": "probe-postgres-vacuum-status",
  "type": "probe",
  "provider": {
    "type": "python",
    "module": "chaosdb.probes.postgres.postgres_system_metrics",
    "func": "collect_postgres_system_metrics",
    "arguments": {
      "host": "${postgres_primary_host}",
      "port": "${postgres_port}",
      "database": "${postgres_db}",
      "user": "${postgres_user}",
      "password": "${postgres_password}"
    }
  },
  "tolerance": true
}
```

#### SCENARIO-3-PostgreSQL-Temp-File-Spill
**Current Status:** 0 activities  
**Location:** After line 670

**1. Chaos Test to Add:**
```json
{
  "name": "test-transactions-during-temp-spill",
  "type": "action",
  "provider": {
    "type": "python",
    "module": "chaosdb.probes.postgres.postgres_transaction_validation",
    "func": "probe_api_transaction_flow",
    "arguments": {
      "api_url": "${site_a_haproxy_url}",
      "num_transactions": "${distributed_transaction_test_count}"
    }
  }
}
```

**2. Probe to Add:**
```json
{
  "name": "probe-postgres-temp-file-usage",
  "type": "probe",
  "provider": {
    "type": "python",
    "module": "chaosdb.probes.postgres.postgres_system_metrics",
    "func": "collect_postgres_system_metrics",
    "arguments": {
      "host": "${postgres_primary_host}",
      "port": "${postgres_port}",
      "database": "${postgres_db}",
      "user": "${postgres_user}",
      "password": "${postgres_password}"
    }
  },
  "tolerance": true
}
```

#### SCENARIO-5-PostgreSQL-Pool-Exhaustion
**Current Status:** 0 activities  
**Location:** After line 720

**1. Chaos Test to Add:**
```json
{
  "name": "test-transactions-during-pool-exhaustion",
  "type": "action",
  "provider": {
    "type": "python",
    "module": "chaosdb.probes.postgres.postgres_transaction_validation",
    "func": "probe_api_transaction_flow",
    "arguments": {
      "api_url": "${site_a_haproxy_url}",
      "num_transactions": "${distributed_transaction_test_count}"
    }
  }
}
```

**2. Probe to Add:**
```json
{
  "name": "probe-postgres-pool-exhaustion-status",
  "type": "probe",
  "provider": {
    "type": "python",
    "module": "chaosdb.probes.postgres.postgres_pool_exhaustion_status",
    "func": "probe_pool_exhaustion_status",
    "arguments": {
      "host": "${postgres_primary_host}",
      "port": "${postgres_port}",
      "database": "${postgres_db}",
      "user": "${postgres_user}",
      "password": "${postgres_password}"
    }
  },
  "tolerance": true
}
```

### MySQL Scenarios

#### SCENARIO-9-MySQL-Slow-Transactions
**Current Status:** 0 activities  
**Location:** After line 836

**1. Chaos Test to Add:**
```json
{
  "name": "test-transactions-during-slow-mysql",
  "type": "action",
  "provider": {
    "type": "python",
    "module": "chaosdb.probes.postgres.postgres_transaction_validation",
    "func": "probe_api_transaction_flow",
    "arguments": {
      "api_url": "${site_a_haproxy_url}",
      "num_transactions": "${distributed_transaction_test_count}"
    }
  }
}
```

**2. Probe to Add:**
```json
{
  "name": "probe-mysql-slow-transactions-status",
  "type": "probe",
  "provider": {
    "type": "python",
    "module": "chaosdb.probes.mysql.mysql_slow_transactions_status",
    "func": "probe_slow_transactions_status",
    "arguments": {
      "host": "${mysql_host}",
      "port": "${mysql_port}",
      "database": "${mysql_db}",
      "user": "${mysql_user}",
      "password": "${mysql_password}"
    }
  },
  "tolerance": true
}
```

#### SCENARIO-10-MySQL-Query-Saturation
**Current Status:** 0 activities  
**Location:** After line 854

**1. Chaos Test to Add:**
```json
{
  "name": "test-transactions-during-mysql-query-saturation",
  "type": "action",
  "provider": {
    "type": "python",
    "module": "chaosdb.probes.postgres.postgres_transaction_validation",
    "func": "probe_api_transaction_flow",
    "arguments": {
      "api_url": "${site_a_haproxy_url}",
      "num_transactions": "${distributed_transaction_test_count}"
    }
  }
}
```

**2. Probe to Add:**
```json
{
  "name": "probe-mysql-query-saturation-status",
  "type": "probe",
  "provider": {
    "type": "python",
    "module": "chaosdb.probes.mysql.mysql_query_saturation_status",
    "func": "probe_query_saturation_status",
    "arguments": {
      "host": "${mysql_host}",
      "port": "${mysql_port}",
      "database": "${mysql_db}",
      "user": "${mysql_user}",
      "password": "${mysql_password}"
    }
  },
  "tolerance": true
}
```

### MSSQL Scenarios

#### SCENARIO-11-MSSQL-Slow-Transactions
**Current Status:** 0 activities  
**Location:** After line 873

**1. Chaos Test to Add:**
```json
{
  "name": "test-transactions-during-slow-mssql",
  "type": "action",
  "provider": {
    "type": "python",
    "module": "chaosdb.probes.postgres.postgres_transaction_validation",
    "func": "probe_api_transaction_flow",
    "arguments": {
      "api_url": "${site_a_haproxy_url}",
      "num_transactions": "${distributed_transaction_test_count}"
    }
  }
}
```

**2. Probe to Add:**
```json
{
  "name": "probe-mssql-slow-transactions-status",
  "type": "probe",
  "provider": {
    "type": "python",
    "module": "chaosdb.probes.mssql.mssql_slow_transactions_status",
    "func": "probe_slow_transactions_status",
    "arguments": {
      "host": "${mssql_host}",
      "port": "${mssql_port}",
      "database": "${mssql_db}",
      "user": "${mssql_user}",
      "password": "${mssql_password}"
    }
  },
  "tolerance": true
}
```

### MongoDB Scenarios

#### SCENARIO-12-MongoDB-Document-Contention
**Current Status:** 0 activities  
**Location:** After line 889

**1. Chaos Test to Add:**
```json
{
  "name": "test-transactions-during-mongodb-contention",
  "type": "action",
  "provider": {
    "type": "python",
    "module": "chaosdb.probes.postgres.postgres_transaction_validation",
    "func": "probe_api_transaction_flow",
    "arguments": {
      "api_url": "${site_a_haproxy_url}",
      "num_transactions": "${distributed_transaction_test_count}"
    }
  }
}
```

**2. Probe to Add:**
```json
{
  "name": "probe-mongodb-document-contention-status",
  "type": "probe",
  "provider": {
    "type": "python",
    "module": "chaosdb.probes.mongodb.mongodb_document_contention_status",
    "func": "probe_document_contention_status",
    "arguments": {
      "host": "mongodb",
      "port": 27017,
      "database": "${mongodb_db}"
    }
  },
  "tolerance": true
}
```

#### SCENARIO-13-MongoDB-Query-Saturation
**Current Status:** 0 activities  
**Location:** After line 905

**1. Chaos Test to Add:**
```json
{
  "name": "test-transactions-during-mongodb-query-saturation",
  "type": "action",
  "provider": {
    "type": "python",
    "module": "chaosdb.probes.postgres.postgres_transaction_validation",
    "func": "probe_api_transaction_flow",
    "arguments": {
      "api_url": "${site_a_haproxy_url}",
      "num_transactions": "${distributed_transaction_test_count}"
    }
  }
}
```

**2. Probe to Add:**
```json
{
  "name": "probe-mongodb-query-saturation-status",
  "type": "probe",
  "provider": {
    "type": "python",
    "module": "chaosdb.probes.mongodb.mongodb_query_saturation_status",
    "func": "probe_query_saturation_status",
    "arguments": {
      "host": "mongodb",
      "port": 27017,
      "database": "${mongodb_db}"
    }
  },
  "tolerance": true
}
```

### Redis Scenarios

#### SCENARIO-14-Redis-Key-Contention
**Current Status:** 0 activities  
**Location:** After line 920

**1. Chaos Test to Add:**
```json
{
  "name": "test-transactions-during-redis-contention",
  "type": "action",
  "provider": {
    "type": "python",
    "module": "chaosdb.probes.postgres.postgres_transaction_validation",
    "func": "probe_api_transaction_flow",
    "arguments": {
      "api_url": "${site_a_haproxy_url}",
      "num_transactions": "${distributed_transaction_test_count}"
    }
  }
}
```

**2. Probe to Add:**
```json
{
  "name": "probe-redis-key-contention-status",
  "type": "probe",
  "provider": {
    "type": "python",
    "module": "chaosdb.probes.redis.redis_key_contention_status",
    "func": "probe_key_contention_status",
    "arguments": {
      "host": "${redis_host}",
      "port": "${redis_port}"
    }
  },
  "tolerance": true
}
```

#### SCENARIO-15-Redis-Command-Saturation
**Current Status:** 0 activities  
**Location:** After line 935

**1. Chaos Test to Add:**
```json
{
  "name": "test-transactions-during-redis-command-saturation",
  "type": "action",
  "provider": {
    "type": "python",
    "module": "chaosdb.probes.postgres.postgres_transaction_validation",
    "func": "probe_api_transaction_flow",
    "arguments": {
      "api_url": "${site_a_haproxy_url}",
      "num_transactions": "${distributed_transaction_test_count}"
    }
  }
}
```

**2. Probe to Add:**
```json
{
  "name": "probe-redis-command-saturation-status",
  "type": "probe",
  "provider": {
    "type": "python",
    "module": "chaosdb.probes.redis.redis_command_saturation_status",
    "func": "probe_command_saturation_status",
    "arguments": {
      "host": "${redis_host}",
      "port": "${redis_port}"
    }
  },
  "tolerance": true
}
```

### Kafka Scenarios

#### SCENARIO-17-Kafka-Message-Flood
**Current Status:** 0 activities  
**Location:** After line 980

**1. Chaos Test to Add:**
```json
{
  "name": "test-transactions-during-kafka-message-flood",
  "type": "action",
  "provider": {
    "type": "python",
    "module": "chaosdb.probes.postgres.postgres_transaction_validation",
    "func": "probe_api_transaction_flow",
    "arguments": {
      "api_url": "${site_a_haproxy_url}",
      "num_transactions": "${distributed_transaction_test_count}"
    }
  }
}
```

**2. Probe to Add:**
```json
{
  "name": "probe-kafka-message-flood-status",
  "type": "probe",
  "provider": {
    "type": "python",
    "module": "chaosdb.probes.kafka.kafka_message_flood_status",
    "func": "probe_message_flood_status",
    "arguments": {
      "bootstrap_servers": "${kafka_bootstrap_servers}",
      "topic": "${kafka_topic}"
    }
  },
  "tolerance": true
}
```

#### SCENARIO-18-Kafka-Topic-Saturation
**Current Status:** 0 activities  
**Location:** After line 995

**1. Chaos Test to Add:**
```json
{
  "name": "test-transactions-during-kafka-topic-saturation",
  "type": "action",
  "provider": {
    "type": "python",
    "module": "chaosdb.probes.postgres.postgres_transaction_validation",
    "func": "probe_api_transaction_flow",
    "arguments": {
      "api_url": "${site_a_haproxy_url}",
      "num_transactions": "${distributed_transaction_test_count}"
    }
  }
}
```

**2. Probe to Add:**
```json
{
  "name": "probe-kafka-topic-saturation-status",
  "type": "probe",
  "provider": {
    "type": "python",
    "module": "chaosdb.probes.kafka.kafka_topic_saturation_status",
    "func": "probe_topic_saturation_status",
    "arguments": {
      "bootstrap_servers": "${kafka_bootstrap_servers}",
      "topic": "${kafka_topic}"
    }
  },
  "tolerance": true
}
```

#### SCENARIO-19-Kafka-Slow-Consumer
**Current Status:** 0 activities  
**Location:** After line 1011

**1. Chaos Test to Add:**
```json
{
  "name": "test-transactions-during-kafka-slow-consumer",
  "type": "action",
  "provider": {
    "type": "python",
    "module": "chaosdb.probes.postgres.postgres_transaction_validation",
    "func": "probe_api_transaction_flow",
    "arguments": {
      "api_url": "${site_a_haproxy_url}",
      "num_transactions": "${distributed_transaction_test_count}"
    }
  }
}
```

**2. Probe to Add:**
```json
{
  "name": "probe-kafka-slow-consumer-status",
  "type": "probe",
  "provider": {
    "type": "python",
    "module": "chaosdb.probes.kafka.kafka_slow_consumer_status",
    "func": "probe_slow_consumer_status",
    "arguments": {
      "bootstrap_servers": "${kafka_bootstrap_servers}",
      "topic": "${kafka_topic}"
    }
  },
  "tolerance": true
}
```

### RabbitMQ Scenarios

#### SCENARIO-20-RabbitMQ-Message-Flood
**Current Status:** 0 activities  
**Location:** After line 1030

**1. Chaos Test to Add:**
```json
{
  "name": "test-transactions-during-rabbitmq-message-flood",
  "type": "action",
  "provider": {
    "type": "python",
    "module": "chaosdb.probes.postgres.postgres_transaction_validation",
    "func": "probe_api_transaction_flow",
    "arguments": {
      "api_url": "${site_a_haproxy_url}",
      "num_transactions": "${distributed_transaction_test_count}"
    }
  }
}
```

**2. Probe to Add:**
```json
{
  "name": "probe-rabbitmq-message-flood-status",
  "type": "probe",
  "provider": {
    "type": "python",
    "module": "chaosdb.probes.rabbitmq.rabbitmq_message_flood_status",
    "func": "probe_message_flood_status",
    "arguments": {
      "host": "${rabbitmq_host}",
      "port": "${rabbitmq_port}",
      "user": "${rabbitmq_user}",
      "password": "${rabbitmq_password}",
      "queue": "chaos_test_queue"
    }
  },
  "tolerance": true
}
```

#### SCENARIO-21-RabbitMQ-Queue-Saturation
**Current Status:** 0 activities  
**Location:** After line 1048

**1. Chaos Test to Add:**
```json
{
  "name": "test-transactions-during-rabbitmq-queue-saturation",
  "type": "action",
  "provider": {
    "type": "python",
    "module": "chaosdb.probes.postgres.postgres_transaction_validation",
    "func": "probe_api_transaction_flow",
    "arguments": {
      "api_url": "${site_a_haproxy_url}",
      "num_transactions": "${distributed_transaction_test_count}"
    }
  }
}
```

**2. Probe to Add:**
```json
{
  "name": "probe-rabbitmq-queue-saturation-status",
  "type": "probe",
  "provider": {
    "type": "python",
    "module": "chaosdb.probes.rabbitmq.rabbitmq_queue_saturation_status",
    "func": "probe_queue_saturation_status",
    "arguments": {
      "host": "${rabbitmq_host}",
      "port": "${rabbitmq_port}",
      "user": "${rabbitmq_user}",
      "password": "${rabbitmq_password}",
      "queue": "chaos_test_queue"
    }
  },
  "tolerance": true
}
```

## Chaosotel Integration Verification

All activities use chaosotel for tracing, metrics, and logs:

### Actions (Chaos Tests)
- `probe_api_transaction_flow` from `chaosdb.probes.postgres.postgres_transaction_validation`
  - Uses: `from chaosotel import flush, get_metric_tags, get_metrics_core, get_tracer`
  - Provides: Full tracing, metrics, and logs

### Probes (Status Checks)
All probes use chaosotel:
- `from chaosotel import flush, get_metric_tags, get_metrics_core, get_tracer`
- `from opentelemetry._logs import get_logger_provider`
- `from opentelemetry.sdk._logs import LoggingHandler`
- Proper span creation with `tracer.start_as_current_span()`
- Metrics recording via `metrics.record_*()` methods
- Logging via OpenTelemetry LoggingHandler

## Implementation Summary

**Total Scenarios Needing Activities:** 20

**Breakdown:**
- **Scenarios with 0 activities:** 15 (need both test + probe = 30 activities)
- **Scenarios with 1 activity:** 5 (need 1 missing activity = 5 activities)
  - SCENARIO-1: Has test, needs probe
  - SCENARIO-4: Has test, needs probe
  - SCENARIO-6: Has probe, needs test
  - SCENARIO-7: Has test, needs probe
  - SCENARIO-8: Has test, needs probe

**Activities to Add:**
- **Chaos Tests (Actions):** 16 (15 for 0-activity scenarios + 1 for SCENARIO-6)
- **Probes (Validations):** 19 (15 for 0-activity scenarios + 4 for scenarios missing probes)
- **Total Activities:** 35

**Activity Types:**
- **Chaos Tests:** Test distributed transactions under chaos conditions
- **Probes:** Validate/check system status during chaos

**Priority Order:**
1. PostgreSQL scenarios (3)
2. MySQL scenarios (2)
3. MSSQL scenarios (1)
4. MongoDB scenarios (2)
5. Redis scenarios (2)
6. Kafka scenarios (3)
7. RabbitMQ scenarios (2)

## Verification Checklist

For each scenario, verify:
- [ ] SCENARIO-X action exists (chaos injection)
- [ ] test-transactions-during-X action exists (chaos test)
- [ ] probe-X-status probe exists (validation)
- [ ] All activities use chaosotel (verified - all existing code uses chaosotel)
- [ ] Test is a proper chaos test (tests system under chaos conditions)

## Next Steps

1. Review this updated plan
2. Implement all 30 activities (15 tests + 15 probes) in e2e-experiment.json
3. Verify chaosotel integration (already confirmed in codebase)
4. Test each scenario after adding activities
5. Verify that all scenarios now have at least 2 activities (1 test + 1 probe)
6. Update reporting to confirm activity counts
