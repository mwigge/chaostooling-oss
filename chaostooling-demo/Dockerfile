FROM python:3.11-slim

WORKDIR /app

# Install system dependencies for database drivers and network tools
RUN apt-get update && apt-get install -y \
    gcc \
    unixodbc-dev \
    libpq-dev \
    postgresql-client \
    curl \
    docker.io \
    iproute2 \
    iptables \
    stress-ng \
    dos2unix \
    tdsodbc \
    freetds-bin \
    freetds-dev \
    && rm -rf /var/lib/apt/lists/*

# Install Chaos Toolkit
RUN pip install chaostoolkit "chaostoolkit-lib[jsonpath]"
RUN pip install opentelemetry-exporter-otlp-proto-grpc

# Install dependencies for extensions
RUN pip install \
    psycopg2-binary \
    mysql-connector-python \
    pyodbc \
    pymongo \
    redis \
    cassandra-driver \
    kafka-python \
    pika \
    stomp.py \
    requests \
    psutil \
    mcp \
    opentelemetry-api \
    opentelemetry-sdk \
    opentelemetry-exporter-otlp \
    opentelemetry-instrumentation-requests \
    python-json-logger


# Disable Python bytecode generation
ENV PYTHONDONTWRITEBYTECODE=1

# Copy setup and entrypoint scripts
COPY scripts/docker-entrypoint.sh /docker-entrypoint.sh
COPY scripts/chaos-runner-entrypoint.sh /chaos-runner-entrypoint.sh
COPY scripts/setup-extensions.sh /setup-extensions.sh
COPY scripts/run-chaos.sh /usr/local/bin/run-chaos
RUN dos2unix /docker-entrypoint.sh /chaos-runner-entrypoint.sh /setup-extensions.sh /usr/local/bin/run-chaos && \
    chmod +x /docker-entrypoint.sh /chaos-runner-entrypoint.sh /setup-extensions.sh /usr/local/bin/run-chaos

# Run setup-extensions.sh during build to pre-install extensions
RUN /setup-extensions.sh || true

WORKDIR /experiments

ENTRYPOINT ["/docker-entrypoint.sh"]
CMD ["bash"]
