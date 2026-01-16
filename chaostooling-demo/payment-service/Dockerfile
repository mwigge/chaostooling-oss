FROM python:3.11-slim

WORKDIR /app

# Note: CA certificates are not needed since we use --trusted-host flags
# This allows pip to work when certificates are blocked by firewall but pip access is allowed

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

# Copy requirements first for better Docker layer caching
COPY chaostooling-demo/payment-service/requirements.txt .

# Install Python packages
# Using --no-cache-dir to reduce image size
# Using --trusted-host to bypass certificate verification (pip is allowed in firewall, but certificates are not)
RUN pip install --no-cache-dir \
    --trusted-host pypi.org \
    --trusted-host pypi.python.org \
    --trusted-host files.pythonhosted.org \
    -r requirements.txt

COPY chaostooling-demo/payment-service/app.py .

CMD ["python", "app.py"]

