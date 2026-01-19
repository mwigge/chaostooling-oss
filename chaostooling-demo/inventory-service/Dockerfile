FROM python:3.11-slim

WORKDIR /app

# Upgrade pip, setuptools, and wheel to ensure proper package building
RUN pip install --upgrade pip setuptools wheel

# Install chaosotel from local path
COPY chaostooling-otel /tmp/chaostooling-otel
WORKDIR /tmp/chaostooling-otel
RUN pip install --no-cache-dir .
WORKDIR /app

COPY chaostooling-demo/inventory-service/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY chaostooling-demo/inventory-service/app.py .

EXPOSE 5000

CMD ["python", "app.py"]

