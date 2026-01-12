# Fix for Confluent Kafka JMX Exporter

## Issue

The JMX exporter isn't starting even though `KAFKA_OPTS` is set. This is because Confluent's Kafka image might append to `KAFKA_OPTS` instead of replacing it, or there might be syntax issues.

## Solution Options

### Option 1: Use KAFKA_JMX_OPTS (Recommended for Confluent)

Confluent Kafka images have a separate variable `KAFKA_JMX_OPTS` that's specifically for JMX configuration. However, for JMX Exporter as a Java agent, we still use `KAFKA_OPTS`.

### Option 2: Verify KAFKA_OPTS is being used

The Confluent image should respect `KAFKA_OPTS`. Verify the syntax is correct:

```yaml
environment:
  KAFKA_OPTS: "-javaagent:/opt/jmx_prometheus_javaagent.jar=9999:/opt/kafka-jmx-config.yml"
```

### Option 3: Use entrypoint script (if KAFKA_OPTS doesn't work)

If `KAFKA_OPTS` isn't working, you might need to create a custom entrypoint script that sets the Java agent.

## Current Configuration

```yaml
kafka:
  image: confluentinc/cp-kafka:7.5.0
  ports:
    - "9092:9092"
    - "9999:9999"   # JMX Exporter metrics endpoint
  volumes:
    - ./kafka-jmx/jmx_prometheus_javaagent.jar:/opt/jmx_prometheus_javaagent.jar:ro
    - ./kafka-jmx/kafka-jmx-config.yml:/opt/kafka-jmx-config.yml:ro
  environment:
    KAFKA_BROKER_ID: 1
    KAFKA_ZOOKEEPER_CONNECT: zookeeper:2181
    KAFKA_LISTENERS: PLAINTEXT://0.0.0.0:9092
    KAFKA_ADVERTISED_LISTENERS: PLAINTEXT://kafka:9092
    KAFKA_LISTENER_SECURITY_PROTOCOL_MAP: PLAINTEXT:PLAINTEXT
    KAFKA_INTER_BROKER_LISTENER_NAME: PLAINTEXT
    KAFKA_OFFSETS_TOPIC_REPLICATION_FACTOR: 1
    # Enable JMX Exporter
    KAFKA_OPTS: "-javaagent:/opt/jmx_prometheus_javaagent.jar=9999:/opt/kafka-jmx-config.yml"
```

## Debugging Steps

1. **Check if files are mounted:**
   ```bash
   docker-compose exec kafka ls -la /opt/jmx_prometheus_javaagent.jar
   docker-compose exec kafka ls -la /opt/kafka-jmx-config.yml
   ```

2. **Check environment variable:**
   ```bash
   docker-compose exec kafka env | grep KAFKA_OPTS
   ```

3. **Check Java process:**
   ```bash
   docker-compose exec kafka ps aux | grep java
   ```
   Look for `javaagent` in the command line.

4. **Check if port is listening:**
   ```bash
   docker-compose exec kafka netstat -tlnp | grep 9999
   ```

5. **Check Kafka logs for errors:**
   ```bash
   docker-compose logs kafka | grep -i -E "(jmx|javaagent|error|9999)"
   ```

## Alternative: Use JMX_PORT for native JMX (not Prometheus exporter)

If you want to use native JMX (not JMX Exporter), you can use:

```yaml
environment:
  JMX_PORT: 9999
  KAFKA_JMX_OPTS: "-Dcom.sun.management.jmxremote -Dcom.sun.management.jmxremote.authenticate=false -Dcom.sun.management.jmxremote.ssl=false -Djava.rmi.server.hostname=kafka -Dcom.sun.management.jmxremote.port=9999 -Dcom.sun.management.jmxremote.rmi.port=9999"
```

But this won't give you Prometheus format metrics - you'd need a separate JMX exporter service.

## Recommended Fix

The `KAFKA_OPTS` approach should work. If it doesn't, the issue is likely:

1. Files not mounted correctly
2. Kafka container not restarted after adding configuration
3. Syntax error in KAFKA_OPTS (extra spaces, quotes, etc.)

Try this exact configuration (no extra spaces):

```yaml
KAFKA_OPTS: "-javaagent:/opt/jmx_prometheus_javaagent.jar=9999:/opt/kafka-jmx-config.yml"
```

