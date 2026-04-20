import os
import subprocess

from sqlalchemy import inspect, text

from database import Base, engine
from models.user import User
from models.conversation import Conversation
from models.message import Message
from models.document_chunk import DocumentChunk
from models.patient_report import PatientReport
from models.medical_knowledge_cache import MedicalKnowledgeCache
from seed_data import seed_test_users


def _db_has_tables() -> bool:
    return inspect(engine).has_table("users")


def _ensure_vector_extension() -> None:
    with engine.begin() as connection:
        connection.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))


def _restore_from_backup_if_needed() -> None:
    backup_path = os.getenv("BACKUP_SQL_PATH", "/docker-bootstrap/docker_backup.sql")
    # Also check for .dump file
    dump_path = backup_path.replace(".sql", ".dump")
    
    if _db_has_tables():
        print("Database tables already exist. Skipping SQL restore.")
        return

    # Determine which backup file exists
    if os.path.exists(dump_path):
        backup_path = dump_path
    elif not os.path.exists(backup_path):
        print(f"No backup found at {backup_path} or {dump_path}. Skipping restore.")
        return

    if os.path.getsize(backup_path) == 0:
        print(f"Backup file at {backup_path} is empty. Skipping restore.")
        return

    database_url = os.getenv(
        "DATABASE_URL",
        "postgresql://postgres:postgres@localhost:5432/healthcare_db",
    )

    print(f"Restoring database from backup: {backup_path}")
    
    # Determine if it's a dump file or SQL file
    if backup_path.endswith(".dump"):
        # Use pg_restore for custom dump format
        print("Detected custom dump format, using pg_restore...")
        result = subprocess.run(
            [
                "pg_restore",
                "-d", database_url,
                "--no-owner",
                "--no-privileges",
                "--if-exists",
                backup_path
            ],
            capture_output=True,
            text=True,
        )
        # Log warnings but don't fail on non-critical errors
        if result.returncode != 0:
            print(f"⚠️  pg_restore warnings/errors (continuing): {result.stderr}")
        if result.stdout:
            print(result.stdout)
    else:
        # Use psql for SQL format
        print("Detected SQL format, using psql...")
        subprocess.run(
            ["psql", database_url, "-v", "ON_ERROR_STOP=1", "-f", backup_path],
            check=True,
        )
    
    print("Database backup restored successfully.")


def init_db():
    """Initialize database tables"""
    try:
        print("Starting database initialization...")
        _restore_from_backup_if_needed()
        _ensure_vector_extension()
        print(f"Tables to create: {list(Base.metadata.tables.keys())}")
        Base.metadata.create_all(bind=engine)
        print("Database tables created successfully!")
        print(f"Created tables: {list(Base.metadata.tables.keys())}")
        
        # Seed test data
        print("\nSeeding test data...")
        seed_test_users()
        
        # Run document ingestion
        print("\nStarting document ingestion...")
        try:
            from utils.db_ingestion import ingest_documents
            ingest_documents()
            print("✅ Document ingestion completed!")
        except Exception as e:
            print(f"⚠️ Document ingestion error (non-critical): {e}")
        
        # Run treatment ingestion
        print("\nStarting treatment document ingestion...")
        try:
            from utils.db_ingestion_treatments import main as ingest_treatments
            ingest_treatments()
            print("✅ Treatment ingestion completed!")
        except Exception as e:
            print(f"⚠️ Treatment ingestion error (non-critical): {e}")
        
        print("\n" + "="*60)
        print("✅ DATABASE INITIALIZATION COMPLETE")
        print("="*60)
        
    except Exception as e:
        print(f"Error initializing database: {e}")
        import traceback
        traceback.print_exc()
        raise

if __name__ == "__main__":
    init_db()
