FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY chaostooling-demo/transaction-load-generator/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy common directory (for otel_setup)
COPY chaostooling-demo/common /app/common

# Copy application
COPY chaostooling-demo/transaction-load-generator/app.py .

# Expose port
EXPOSE 5001

# Run application
CMD ["python", "app.py"]
