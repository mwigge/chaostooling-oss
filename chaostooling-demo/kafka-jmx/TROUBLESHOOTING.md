# Troubleshooting Kafka JMX Exporter

## Issue: Connection Refused on kafka:9999

### Possible Causes

1. **Kafka container not restarted** after adding JMX exporter configuration
2. **JMX exporter JAR file not accessible** in container
3. **JMX exporter configuration file issues**
4. **Port 9999 not exposed correctly**

### Diagnostic Steps

#### 1. Check if Kafka container is running

```bash
docker-compose ps kafka
```

#### 2. Check Kafka logs for JMX exporter errors

```bash
docker-compose logs kafka | grep -i jmx
```

Or check the last 100 lines:

```bash
docker-compose logs kafka --tail=100
```

Look for:
- `javaagent` errors
- File not found errors
- Port binding errors
- Configuration errors

#### 3. Verify JAR file exists and is accessible

```bash
# Check if file exists
ls -lh kafka-jmx/jmx_prometheus_javaagent.jar

# Check file size (should be ~100KB+)
# If missing or 0 bytes, download it:
cd kafka-jmx
curl -L -o jmx_prometheus_javaagent.jar \
  https://repo1.maven.org/maven2/io/prometheus/jmx/jmx_prometheus_javaagent/0.20.0/jmx_prometheus_javaagent-0.20.0.jar
```

#### 4. Verify config file is valid YAML

```bash
# Check YAML syntax
cat kafka-jmx/kafka-jmx-config.yml | docker run -i --rm mikefarah/yq eval '.' -
```

#### 5. Check if JMX exporter is listening inside container

```bash
# Execute command inside Kafka container
docker-compose exec kafka ls -la /opt/jmx_prometheus_javaagent.jar
docker-compose exec kafka ls -la /opt/kafka-jmx-config.yml
docker-compose exec kafka cat /opt/kafka-jmx-config.yml

# Check if port 9999 is listening
docker-compose exec kafka netstat -tlnp | grep 9999
# Or
docker-compose exec kafka ss -tlnp | grep 9999
```

#### 6. Test JMX exporter endpoint

```bash
# From host machine
curl http://localhost:9999/metrics

# From inside Prometheus container
docker-compose exec prometheus wget -qO- http://kafka:9999/metrics
```

### Solutions

#### Solution 1: Restart Kafka

If Kafka was started before adding JMX exporter:

```bash
docker-compose restart kafka
```

Or stop and start:

```bash
docker-compose stop kafka
docker-compose up -d kafka
```

#### Solution 2: Download JAR file if missing

```bash
cd wl2/chaostooling-wl-demo/kafka-jmx
curl -L -o jmx_prometheus_javaagent.jar \
  https://repo1.maven.org/maven2/io/prometheus/jmx/jmx_prometheus_javaagent/0.20.0/jmx_prometheus_javaagent-0.20.0.jar
```

#### Solution 3: Verify docker-compose.yml configuration

Ensure these are in the Kafka service:

```yaml
ports:
  - "9999:9999"   # JMX Exporter metrics endpoint
volumes:
  - ./kafka-jmx/jmx_prometheus_javaagent.jar:/opt/jmx_prometheus_javaagent.jar:ro
  - ./kafka-jmx/kafka-jmx-config.yml:/opt/kafka-jmx-config.yml:ro
environment:
  KAFKA_OPTS: "-javaagent:/opt/jmx_prometheus_javaagent.jar=9999:/opt/kafka-jmx-config.yml"
```

#### Solution 4: Check for Java agent errors

If you see errors like "javaagent: invalid path" or "ClassNotFoundException", the JAR path might be wrong.

Verify the path in the container matches what's in KAFKA_OPTS:

```bash
docker-compose exec kafka ls -la /opt/jmx_prometheus_javaagent.jar
```

#### Solution 5: Remove hostPort from config if using KAFKA_OPTS

The `hostPort` in `kafka-jmx-config.yml` is only used when running JMX exporter standalone. When using as Java agent, remove it:

```yaml
# Remove this line:
# hostPort: localhost:9999

rules:
  # ... rest of config
```

Wait, actually `hostPort` is ignored when using as agent, so it shouldn't cause issues. But removing it won't hurt.

### Expected Success Indicators

When working correctly, you should see:

1. **Kafka logs** show JMX exporter started:
   ```
   INFO ... JMX Exporter started on port 9999
   ```

2. **Metrics endpoint responds**:
   ```bash
   curl http://localhost:9999/metrics
   # Should return Prometheus format metrics
   ```

3. **Prometheus target shows UP**:
   - Go to http://localhost:9090/targets
   - `kafka-jmx` target should be UP

4. **Kafka metrics visible**:
   ```bash
   curl http://localhost:9999/metrics | grep kafka_producer
   ```

### Alternative: Use Confluent's built-in JMX

If JMX exporter continues to have issues, Confluent Kafka images have JMX enabled by default. You can scrape JMX directly, but it's more complex. The JMX exporter approach is recommended.

## Issue: host.docker.internal:9323 Connection Refused

This is for Docker daemon metrics, which may not be available in all environments. You can safely:

1. **Remove the scrape job** from `prometheus.yml` if not needed
2. **Or ignore the error** - it won't affect Kafka metrics

To remove:

```yaml
# In prometheus.yml, comment out or remove:
# - job_name: docker
#   scrape_interval: 15s
#   static_configs:
#     - targets: ["host.docker.internal:9323"]
```

