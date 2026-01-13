FROM python:3.11-slim

WORKDIR /app

# Note: CA certificates are not needed since we use --trusted-host flags
# This allows pip to work when certificates are blocked by firewall but pip access is allowed

# Copy requirements first for better Docker layer caching
COPY requirements.txt .

# Install Python packages
# Using --no-cache-dir to reduce image size
# Using --trusted-host to bypass certificate verification (pip is allowed in firewall, but certificates are not)
RUN pip install --no-cache-dir \
    --trusted-host pypi.org \
    --trusted-host pypi.python.org \
    --trusted-host files.pythonhosted.org \
    -r requirements.txt

COPY app.py .

CMD ["python", "app.py"]

