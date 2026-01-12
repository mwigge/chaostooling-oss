# Prometheus Metric Naming for Kafka JMX Exporter

## Format Rules

Prometheus metrics follow these conventions:

1. **Metric Names:**
   - Lowercase letters only
   - Underscores (`_`) as separators (no hyphens or dots)
   - Descriptive but concise
   - Units appended when relevant (e.g., `_seconds`, `_bytes`, `_total`)

2. **Metric Types:**
   - **COUNTER**: Always monotonically increasing, gets `_total` suffix
   - **GAUGE**: Can go up or down, no suffix
   - **HISTOGRAM**: Creates multiple metrics:
     - `_bucket` - histogram buckets with `le` label
     - `_count` - total count
     - `_sum` - sum of all values

3. **Labels:**
   - Extracted from JMX MBean attributes
   - Use lowercase with underscores
   - Examples: `client_id`, `topic`, `partition`, `request`

## Dashboard Expected Metrics

Based on the Kafka dashboard queries, these are the expected metric names:

### Producer Metrics

| Dashboard Query | Expected Prometheus Metric | Type | Notes |
|----------------|---------------------------|------|-------|
| `rate(kafka_producer_record_send_rate_counter_total[1m])` | `kafka_producer_record_send_rate_counter_total` | COUNTER | Producer throughput |
| `rate(kafka_producer_record_error_rate_counter_total[1m])` | `kafka_producer_record_error_rate_counter_total` | COUNTER | Producer errors |
| `rate(kafka_producer_request_latency_bucket[1m])` | `kafka_producer_request_latency_bucket` | HISTOGRAM | Producer latency |

### Consumer Metrics

| Dashboard Query | Expected Prometheus Metric | Type | Notes |
|----------------|---------------------------|------|-------|
| `rate(kafka_consumer_records_consumed_rate_counter_total[1m])` | `kafka_consumer_records_consumed_rate_counter_total` | COUNTER | Consumer throughput |
| `kafka_consumer_lag_messages` | `kafka_consumer_lag_messages` | GAUGE | Consumer lag |

## JMX → Prometheus Mapping

### JMX MBean Pattern

```
kafka.producer<type=producer-metrics, client-id=my-client><>record-send-rate
```

Becomes Prometheus metric:

```
kafka_producer_record_send_rate_counter{client_id="my-client"} 1234.5
```

### Configuration Example

```yaml
rules:
  - pattern: kafka.producer<type=(.*-producer-metrics|producer-metrics), client-id=(.+)><>record-send-rate
    name: kafka_producer_record_send_rate_counter
    type: COUNTER
    labels:
      client_id: "$2"
```

Where:
- `pattern`: JMX MBean pattern with regex groups `(.*)`
- `name`: Prometheus metric name (JMX Exporter automatically adds `_total` for COUNTER)
- `type`: `COUNTER`, `GAUGE`, or `HISTOGRAM`
- `labels`: Extracted from regex groups (`$1`, `$2`, etc.)

## Common JMX Exporter Patterns

### Counter (Rate Metrics)

```yaml
- pattern: kafka.producer<type=producer-metrics, client-id=(.+)><>record-send-rate
  name: kafka_producer_record_send_rate_counter
  type: COUNTER
  labels:
    client_id: "$1"
```

**Result:** `kafka_producer_record_send_rate_counter_total{client_id="my-client"}`

### Gauge (Current Value)

```yaml
- pattern: kafka.consumer<type=consumer-fetch-manager-metrics, client-id=(.+), topic=(.+), partition=(.+)><>records-lag
  name: kafka_consumer_lag_messages
  type: GAUGE
  labels:
    client_id: "$1"
    topic: "$2"
    partition: "$3"
```

**Result:** `kafka_consumer_lag_messages{client_id="my-client", topic="my-topic", partition="0"}`

### Histogram (Latency Distribution)

For histograms, JMX Exporter needs multiple patterns or you use percentiles:

```yaml
- pattern: kafka.network<type=RequestMetrics, name=RequestLatencyMs, request=(.+), clientId=(.+)><>Mean
  name: kafka_producer_request_latency_ms
  type: GAUGE
  labels:
    request: "$1"
    client_id: "$2"
    quantile: "0.5"
```

## Important Notes

### Histogram Metrics

⚠️ **Kafka JMX doesn't expose histogram buckets directly**. The dashboard query for `kafka_producer_request_latency_bucket` expects a Prometheus histogram, but Kafka JMX only provides:
- Percentiles (P50, P95, P99, P999)
- Average/Mean values
- Max values

**Options:**
1. **Use percentile metrics** (recommended): Query `kafka_producer_request_latency_milliseconds{quantile="0.95"}` instead of histogram buckets
2. **Update dashboard query**: Change to use the percentile metrics that are actually available
3. **Use summary metrics**: JMX Exporter can create summary metrics from percentiles, but not true histograms

### Automatic Suffixes

- **COUNTER metrics**: JMX Exporter automatically adds `_total` suffix
  - Config: `name: kafka_producer_record_send_rate_counter`
  - Result: `kafka_producer_record_send_rate_counter_total`

- **HISTOGRAM metrics**: Creates `_bucket`, `_count`, `_sum` (if using HISTOGRAM type)
- **GAUGE metrics**: No suffix added

## Verification

After setup, verify metrics are exposed:

```bash
curl http://localhost:9999/metrics | grep kafka_producer
```

Expected output:
```
# HELP kafka_producer_record_send_rate_counter_total ...
# TYPE kafka_producer_record_send_rate_counter_total counter
kafka_producer_record_send_rate_counter_total{client_id="my-client"} 1234.5

# HELP kafka_producer_request_latency_milliseconds ...
# TYPE kafka_producer_request_latency_milliseconds gauge
kafka_producer_request_latency_milliseconds{client_id="my-client", quantile="0.95"} 150.0
```

## Dashboard Query Updates

If metrics don't match exactly, you may need to adjust dashboard queries:

- **Latency histogram**: Use `kafka_producer_request_latency_milliseconds{quantile="0.95"}` instead of `rate(kafka_producer_request_latency_bucket[1m])`
- **Consumer lag**: May need to aggregate: `sum(kafka_consumer_lag_messages)` if multiple partitions

## References

- [Prometheus Naming Best Practices](https://prometheus.io/docs/practices/naming/)
- [JMX Exporter Configuration](https://github.com/prometheus/jmx_exporter#configuration)
- [Kafka JMX Metrics](https://kafka.apache.org/documentation/#monitoring)
- [Prometheus Metric Types](https://prometheus.io/docs/concepts/metric_types/)

