# Stage 1: Build the custom collector
FROM golang:1.24 AS builder

# Install opentelemetry-collector-builder
RUN go install go.opentelemetry.io/collector/cmd/builder@v0.117.0

WORKDIR /app
COPY builder-config.yaml .

# Build the collector
RUN builder --config builder-config.yaml

# Stage 2: Final image
FROM debian:bookworm-slim

# Install CA certificates for HTTPS exporters and curl for JMX metrics JAR download
RUN apt-get update && apt-get install -y ca-certificates curl && rm -rf /var/lib/apt/lists/*

# Download JMX metrics JAR for JMX receiver
RUN curl -L -o /opt/opentelemetry-java-contrib-jmx-metrics.jar \
    https://github.com/open-telemetry/opentelemetry-java-contrib/releases/download/v1.32.0/opentelemetry-jmx-metrics-1.32.0.jar

COPY --from=builder /app/otelcol-custom/otelcol-custom /usr/local/bin/otelcol-custom
COPY config.yaml /etc/otelcol-custom/config.yaml

ENTRYPOINT ["/usr/local/bin/otelcol-custom"]
CMD ["--config=/etc/otelcol-custom/config.yaml"]
