FROM python:3.11-slim

WORKDIR /app

# Install dependencies
RUN pip install --no-cache-dir \
    psycopg2-binary==2.9.9 \
    opentelemetry-api==1.22.0 \
    opentelemetry-sdk==1.22.0 \
    opentelemetry-exporter-otlp-proto-grpc==1.22.0

# Copy span generator script
COPY span_generator.py .

# Make script executable
RUN chmod +x span_generator.py

# Run as non-root user
RUN useradd -m -u 1000 spangen && chown -R spangen:spangen /app
USER spangen

CMD ["python", "-u", "span_generator.py"]
