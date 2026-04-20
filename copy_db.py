#!/usr/bin/env python3
"""
Utility script to copy database from local PostgreSQL to Docker PostgreSQL.
This is a helper script for database synchronization during development.
"""

import subprocess
import os
from pathlib import Path

def copy_local_to_docker():
    """Copy local PostgreSQL database to Docker container"""
    
    # Local database credentials
    LOCAL_DB_USER = os.getenv("DB_USER", "postgres")
    LOCAL_DB_PASSWORD = os.getenv("DB_PASSWORD", "postgres")
    LOCAL_DB_NAME = os.getenv("DB_NAME", "healthcare_db")
    LOCAL_DB_HOST = os.getenv("DB_HOST", "localhost")
    LOCAL_DB_PORT = os.getenv("DB_PORT", "5432")
    
    # Docker database credentials (same as local in this setup)
    DOCKER_DB_USER = "postgres"
    DOCKER_DB_PASSWORD = "postgres"
    DOCKER_DB_NAME = "healthcare_db"
    DOCKER_DB_HOST = "postgres"  # Docker service name
    DOCKER_DB_PORT = "5432"
    
    backup_file = Path(__file__).parent / "docker_backup.dump"
    
    print(f"Creating backup from local database at {LOCAL_DB_HOST}:{LOCAL_DB_PORT}")
    
    # Create backup from local database
    dump_cmd = [
        "pg_dump",
        "-U", LOCAL_DB_USER,
        "-h", LOCAL_DB_HOST,
        "-p", LOCAL_DB_PORT,
        "-Fc",  # Custom format
        "-f", str(backup_file),
        LOCAL_DB_NAME
    ]
    
    env = os.environ.copy()
    env["PGPASSWORD"] = LOCAL_DB_PASSWORD
    
    result = subprocess.run(dump_cmd, env=env, capture_output=True, text=True)
    
    if result.returncode != 0:
        print(f"Error creating backup: {result.stderr}")
        return False
    
    print(f"✅ Backup created: {backup_file}")
    print(f"Backup size: {backup_file.stat().st_size / 1024 / 1024:.2f} MB")
    
    return True

if __name__ == "__main__":
    copy_local_to_docker()
