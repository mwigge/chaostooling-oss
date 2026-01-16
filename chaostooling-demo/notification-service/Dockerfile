FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Upgrade pip, setuptools, and wheel to ensure proper package building
RUN pip install --upgrade pip setuptools wheel

# Install psycopg2-binary first to satisfy opentelemetry-instrumentation-psycopg2 dependency
RUN pip install --no-cache-dir \
    --trusted-host pypi.org \
    --trusted-host pypi.python.org \
    --trusted-host files.pythonhosted.org \
    psycopg2-binary==2.9.9

# Install chaosotel from local path
COPY chaostooling-otel /tmp/chaostooling-otel
WORKDIR /tmp/chaostooling-otel
RUN pip install --no-cache-dir \
    --trusted-host pypi.org \
    --trusted-host pypi.python.org \
    --trusted-host files.pythonhosted.org \
    .
WORKDIR /app

# Copy requirements and install
# Using --trusted-host to bypass certificate verification (pip is allowed in firewall, but certificates are not)
COPY chaostooling-demo/notification-service/requirements.txt .
RUN pip install --no-cache-dir \
    --trusted-host pypi.org \
    --trusted-host pypi.python.org \
    --trusted-host files.pythonhosted.org \
    -r requirements.txt

# Copy application
COPY chaostooling-demo/notification-service/app.py .

EXPOSE 5000

CMD ["python", "app.py"]

