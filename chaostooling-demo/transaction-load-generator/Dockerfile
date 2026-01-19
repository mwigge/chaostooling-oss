FROM python:3.11-slim

WORKDIR /app

# Upgrade pip, setuptools, and wheel to ensure proper package building
RUN pip install --upgrade pip setuptools wheel

# Install chaosotel from local path
COPY chaostooling-otel /tmp/chaostooling-otel
WORKDIR /tmp/chaostooling-otel
RUN pip install --no-cache-dir .
WORKDIR /app

# Install dependencies
COPY chaostooling-demo/transaction-load-generator/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY chaostooling-demo/transaction-load-generator/app.py .

# Expose port
EXPOSE 5001

# Run application
CMD ["python", "app.py"]
