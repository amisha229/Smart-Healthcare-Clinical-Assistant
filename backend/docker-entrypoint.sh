#!/bin/sh
set -e

echo "Waiting for PostgreSQL to accept connections..."
until pg_isready -d "$DATABASE_URL" >/dev/null 2>&1; do
  sleep 2
done

echo "PostgreSQL is ready. Initializing application database..."
python init_db.py

echo "Starting API server..."
exec uvicorn main:app --host 0.0.0.0 --port 8000
