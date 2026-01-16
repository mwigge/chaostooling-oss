FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y libpq-dev gcc && rm -rf /var/lib/apt/lists/*

# Upgrade pip, setuptools, and wheel to ensure proper package building
RUN pip install --upgrade pip setuptools wheel

# Install psycopg2-binary first to satisfy opentelemetry-instrumentation-psycopg2 dependency
RUN pip install --no-cache-dir psycopg2-binary==2.9.9

# Install chaosotel from local path
COPY chaostooling-otel /tmp/chaostooling-otel
WORKDIR /tmp/chaostooling-otel
RUN pip install --no-cache-dir .
WORKDIR /app

COPY chaostooling-demo/app-server/requirements.txt .
RUN pip install -r requirements.txt

# Copy common directory (for otel_setup)
COPY chaostooling-demo/common /app/common

COPY chaostooling-demo/app-server/app.py .

CMD ["python", "app.py"]

