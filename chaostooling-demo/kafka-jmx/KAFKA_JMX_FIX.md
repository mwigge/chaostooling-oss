# Fix: Kafka JMX Exporter Not Starting

## Problem

The `KAFKA_OPTS` environment variable is not being applied by the Confluent Kafka Docker image. The Java process doesn't include the `-javaagent` argument.

## Solution: Use Entrypoint Wrapper Script

Instead of relying on `KAFKA_OPTS` being picked up automatically, we use a wrapper script that sets it and then calls the original Confluent entrypoint.

### Files Created

1. **`kafka-entrypoint-wrapper.sh`** - Wrapper script that:
   - Sets `KAFKA_OPTS` with the Java agent
   - Calls the original Confluent entrypoint

2. **Updated `docker-compose.yml`** to:
   - Mount the wrapper script
   - Use it as the entrypoint

### How It Works

The wrapper script:
```bash
export KAFKA_OPTS="${KAFKA_OPTS} -javaagent:/opt/jmx_prometheus_javaagent.jar=9999:/opt/kafka-jmx-config.yml"
exec /etc/confluent/docker/run "$@"
```

This ensures the Java agent is added to `KAFKA_OPTS` before Kafka starts.

## Apply the Fix

1. **Make the wrapper script executable** (if not already):
   ```bash
   chmod +x kafka-jmx/kafka-entrypoint-wrapper.sh
   ```

2. **Recreate the Kafka container** (not just restart):
   ```bash
   docker-compose stop kafka
   docker-compose rm -f kafka
   docker-compose up -d kafka
   ```

3. **Verify the Java agent is loaded**:
   ```bash
   docker-compose exec kafka ps aux | grep java | grep javaagent
   ```
   
   You should see `-javaagent:/opt/jmx_prometheus_javaagent.jar=9999` in the output.

4. **Test the metrics endpoint**:
   ```bash
   curl http://localhost:9999/metrics | head -20
   ```

5. **Check Prometheus targets**:
   - Go to http://localhost:9090/targets
   - `kafka-jmx` should show as UP

## Verification

After applying the fix, you should see in the Java process:

```bash
docker-compose exec kafka ps aux | grep java
```

Should include:
```
-javaagent:/opt/jmx_prometheus_javaagent.jar=9999:/opt/kafka-jmx-config.yml
```

## Why This Works

The Confluent Kafka image uses `/etc/confluent/docker/run` as its entrypoint, which reads environment variables and builds the Java command. By using a wrapper script, we can:

1. Set `KAFKA_OPTS` before calling the entrypoint
2. Ensure it's included in the final Java command
3. Work around any limitations in how the image handles `KAFKA_OPTS`

## Alternative: Check Confluent Image Version

If the wrapper script doesn't work, you might need to check if your Confluent image version supports `KAFKA_OPTS`. Some older versions might not handle it correctly.

You can also try setting it in the environment with proper escaping:

```yaml
environment:
  KAFKA_OPTS: "-javaagent:/opt/jmx_prometheus_javaagent.jar=9999:/opt/kafka-jmx-config.yml"
```

But the wrapper script approach is more reliable.

