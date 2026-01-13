# Production-Scale Demo Scripts

All scripts are located in `chaostooling-demo/scripts/` and are accessible at:
- **Windows/WSL**: `\\wsl.localhost\ubuntu\home\morgan\dev\chaostooling-oss\chaostooling-demo\scripts`
- **Linux**: `/home/morgan/dev/chaostooling-oss/chaostooling-demo/scripts`

## Initialization Scripts

### Database Initialization

#### `init-production-scale-db.sh`
Initializes PostgreSQL database with tables for production-scale experiment:
- `mobile_purchases` table
- `orders` table
- `payments` table
- `notifications` table
- Required indexes

**Usage:**
```bash
/scripts/init-production-scale-db.sh
```

**Environment Variables:**
- `POSTGRES_PRIMARY_HOST` (default: `postgres-primary-site-a`)
- `POSTGRES_PORT` (default: `5432`)
- `POSTGRES_DB` (default: `testdb`)
- `POSTGRES_USER` (default: `postgres`)
- `POSTGRES_PASSWORD` (default: `postgres`)

#### `init-mysql-db.sh`
Initializes MySQL database with tables for multi-database operations:
- `mobile_purchases` table
- `orders` table
- `payments` table
- Required indexes

**Usage:**
```bash
/scripts/init-mysql-db.sh
```

**Environment Variables:**
- `MYSQL_HOST` (default: `mysql`)
- `MYSQL_PORT` (default: `3306`)
- `MYSQL_DB` (default: `testdb`)
- `MYSQL_USER` (default: `root`)
- `MYSQL_PASSWORD` (default: `mysql`)

#### `init-mssql-db.sh`
Initializes MSSQL database with tables for legacy system integration:
- `mobile_purchases` table
- `orders` table
- `payments` table
- Required indexes

**Usage:**
```bash
/scripts/init-mssql-db.sh
```

**Environment Variables:**
- `MSSQL_HOST` (default: `mssql`)
- `MSSQL_PORT` (default: `1433`)
- `MSSQL_DB` (default: `testdb`)
- `MSSQL_USER` (default: `sa`)
- `MSSQL_PASSWORD` (default: `Password123!`)

**Note:** Requires `sqlcmd` tool (available in MSSQL container)

#### `init-mongodb-inventory.sh`
Initializes MongoDB with inventory collections.

**Usage:**
```bash
/scripts/init-mongodb-inventory.sh
```

#### `init-redis-data.sh`
Initializes Redis with test data structures:
- Cache keys for users
- Sets for active users/orders
- Sorted sets for leaderboards
- Lists for notification queues

**Usage:**
```bash
/scripts/init-redis-data.sh
```

**Environment Variables:**
- `REDIS_HOST` (default: `redis`)
- `REDIS_PORT` (default: `6379`)

#### `init-cassandra-keyspace.sh`
Initializes Cassandra keyspace and tables:
- `testdb` keyspace
- `mobile_purchases` table
- `orders` table
- `payments` table
- Required indexes

**Usage:**
```bash
/scripts/init-cassandra-keyspace.sh
```

**Environment Variables:**
- `CASSANDRA_HOST` (default: `cassandra`)
- `CASSANDRA_PORT` (default: `9042`)

**Note:** Requires `cqlsh` tool

### Messaging System Initialization

#### `init-activemq-queues.sh`
Initializes ActiveMQ queues for messaging operations:
- `chaos.test` queue
- `chaos.events` queue

**Usage:**
```bash
/scripts/init-activemq-queues.sh
```

**Environment Variables:**
- `ACTIVEMQ_HOST` (default: `activemq`)
- `ACTIVEMQ_PORT` (default: `61616`)
- `ACTIVEMQ_WEB_PORT` (default: `8161`)
- `ACTIVEMQ_USER` (default: `admin`)
- `ACTIVEMQ_PASSWORD` (default: `admin`)

### Master Initialization Script

#### `init-all-services.sh`
Initializes all services in the correct order:
1. PostgreSQL
2. MySQL
3. MSSQL
4. MongoDB
5. Redis
6. Cassandra
7. ActiveMQ

**Usage:**
```bash
/scripts/init-all-services.sh
```

This is the recommended way to initialize all services at once.

## Verification Scripts

#### `verify-all-services.sh`
Verifies that all services are ready and accessible:
- PostgreSQL connectivity
- MySQL connectivity
- MSSQL connectivity
- MongoDB connectivity
- Redis connectivity
- Cassandra connectivity
- Kafka connectivity
- RabbitMQ connectivity
- ActiveMQ connectivity

**Usage:**
```bash
/scripts/verify-all-services.sh
```

**Exit Codes:**
- `0` - All services ready
- `1` - One or more services not ready

## Experiment Execution Scripts

#### `run-production-scale-experiment.sh`
Runs the production-scale distributed transaction experiment.

**Usage:**
```bash
/scripts/run-production-scale-experiment.sh [experiment-path]
```

**Default experiment path:**
`/experiments/production-scale/production-scale-distributed-transaction-experiment.json`

**Example:**
```bash
/scripts/run-production-scale-experiment.sh
```

## Utility Scripts

#### `setup-extensions.sh`
Sets up chaos toolkit extensions from mounted volumes.

#### `verify-extensions.sh`
Verifies that all required extensions are properly installed.

#### `check-steady-state-probes.sh`
Checks steady-state hypothesis probes.

#### `fix-extension-import.sh`
Fixes extension import issues.

#### `quick-fix-extensions.sh`
Quick fix for common extension issues.

#### `docker-entrypoint.sh`
Docker entrypoint script that:
- Converts Windows line endings to Unix
- Sets up extensions
- Executes the original command

#### `chaos-runner-entrypoint.sh`
Entrypoint script for chaos-runner container.

## PostgreSQL Replication Scripts

#### `init-primary.sh`
Initializes PostgreSQL primary database.

#### `init-replica.sh`
Initializes PostgreSQL replica database.

## Quick Start

1. **Initialize all services:**
   ```bash
   docker compose exec chaos-runner /scripts/init-all-services.sh
   ```

2. **Verify services are ready:**
   ```bash
   docker compose exec chaos-runner /scripts/verify-all-services.sh
   ```

3. **Run the experiment:**
   ```bash
   docker compose exec chaos-runner /scripts/run-production-scale-experiment.sh
   ```

## Script Locations

All scripts are located in:
- **WSL/Windows**: `\\wsl.localhost\ubuntu\home\morgan\dev\chaostooling-oss\chaostooling-demo\scripts`
- **Linux**: `/home/morgan/dev/chaostooling-oss/chaostooling-demo/scripts`
- **Docker**: `/scripts/` (mounted volume)

## Environment Variables

Most scripts use environment variables with sensible defaults. See individual script documentation above for specific variables.

Common variables:
- Database connection settings (host, port, user, password)
- Service endpoints
- Timeout values

## Troubleshooting

### Scripts not executable
```bash
chmod +x /scripts/*.sh
```

### Services not ready
Run `verify-all-services.sh` to identify which services are not ready, then check:
1. Service containers are running: `docker compose ps`
2. Service logs: `docker compose logs <service-name>`
3. Network connectivity: `docker compose exec chaos-runner ping <service-name>`

### Database initialization fails
1. Ensure services are fully started (wait 10-30 seconds after `docker compose up`)
2. Check service logs for errors
3. Verify environment variables are set correctly
4. Try running individual initialization scripts

### Messaging system initialization fails
1. Ensure messaging systems are fully started
2. Check web UI/management ports are accessible
3. Verify credentials are correct
4. Check service logs

## Notes

- All scripts use `set -e` to exit on errors
- Scripts wait for services to be ready before proceeding
- Scripts are idempotent (safe to run multiple times)
- Scripts log progress to stdout/stderr
