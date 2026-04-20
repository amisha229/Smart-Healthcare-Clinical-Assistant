FROM python:3.11-slim

WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    HF_HOME=/models/huggingface \
    TRANSFORMERS_CACHE=/models/huggingface \
    SENTENCE_TRANSFORMERS_HOME=/models/huggingface

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Pre-download embedding model so first container start does not hang on model fetch.
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2')"

# Copy application code
COPY backend/ ./
COPY documents /documents
COPY docker_backup.dump /docker-bootstrap/docker_backup.dump
RUN chmod +x /app/docker-entrypoint.sh

# Expose port
EXPOSE 8000

# Initialize database and run the application
CMD ["./docker-entrypoint.sh"]
