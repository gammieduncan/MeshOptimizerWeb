FROM python:3.11-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    wget \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements file
COPY requirements.txt .

# Install Python dependencies
RUN pip install --upgrade pip && \
    pip install -r requirements.txt

# Download gltfpack binary
RUN wget -O /usr/local/bin/gltfpack https://github.com/zeux/meshoptimizer/releases/download/v0.20/gltfpack && \
    chmod +x /usr/local/bin/gltfpack

# Copy application code
COPY . .

# Create directory for SQLite database
RUN mkdir -p /data && chmod 777 /data
ENV DATABASE_URL=sqlite:////data/poly_slimmer.db

# Create non-root user
RUN adduser --disabled-password --gecos "" appuser
RUN chown -R appuser:appuser /app /data
USER appuser

# Start FastAPI app with gunicorn
CMD ["gunicorn", "app.main:app", "--workers", "2", "--worker-class", "uvicorn.workers.UvicornWorker", "--bind", "0.0.0.0:8080"] 