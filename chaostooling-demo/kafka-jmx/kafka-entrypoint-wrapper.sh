#!/bin/bash
# Wrapper script to inject JMX Exporter Java agent into Kafka startup

# Set KAFKA_OPTS to include the JMX exporter Java agent
export KAFKA_OPTS="${KAFKA_OPTS} -javaagent:/opt/jmx_prometheus_javaagent.jar=9999:/opt/kafka-jmx-config.yml"

# Call the original entrypoint/command
exec /etc/confluent/docker/run "$@"

