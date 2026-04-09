import os
import sys

# Add the backend directory to the Python path so we can import modules
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from sqlalchemy import text
from langchain_community.document_loaders import DirectoryLoader, TextLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_huggingface import HuggingFaceEmbeddings
from sqlalchemy.orm import Session
from database import SessionLocal, engine
from models.document_chunk import DocumentChunk, Base

# Ensure path to documents is correct
DOCS_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../documents"))

def ingest_documents():
    print("Setting up database tables if they don't exist...")
    # This creates the table if it's missing, using the models attached to Base
    Base.metadata.create_all(bind=engine)

    print(f"Loading text files from {DOCS_DIR}...")
    loader = DirectoryLoader(DOCS_DIR, glob="**/*.txt", loader_cls=TextLoader, loader_kwargs={'encoding': 'utf-8'})
    documents = loader.load()

    if not documents:
        print("No documents found in the directory.")
        return

    print(f"Loaded {len(documents)} documents.")

    # Split documents into smaller, more granular chunks
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=400,
        chunk_overlap=50
    )
    chunks = text_splitter.split_documents(documents)
    print(f"Split pages into {len(chunks)} text chunks.")

    # Initialize the embedding model
    print("Initializing HuggingFace Embedding model (all-MiniLM-L6-v2)...")
    embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")

    print(f"Generating vectors and inserting into PostgreSQL database...")
    db: Session = SessionLocal()
    
    try:
        # Clear existing data using DELETE to avoid TRUNCATE ownership issues
        db.query(DocumentChunk).delete()
        db.commit()
        
        # Reset the sequence using setval (works with the UPDATE permissions we gave earlier)
        db.execute(text("SELECT setval('document_chunks_chunk_id_seq', 1, false)"))
        db.commit()
        
        inserted_count = 0
        
        # State tracking (persists across chunks but resets per file)
        current_filename = ""
        current_roles = "Nurse,Doctor,Admin"
        current_category = "General"
        current_section = "General"
        current_medical_condition = "General"
        current_content_type = "General"

        for i, chunk in enumerate(chunks):
            text_content = chunk.page_content
            filename = os.path.basename(chunk.metadata.get('source', 'unknown'))
            
            # If we switch to a new PDF, completely reset our tracking state so we don't bleed attributes!
            if filename != current_filename:
                current_filename = filename
                current_roles = "Nurse,Doctor,Admin"
                current_category = "General"
                current_section = "General"
                current_medical_condition = "General"
                current_content_type = "General"

            # --- 1. DETECT DOCUMENT CATEGORY ---
            if "CLINICAL PROTOCOLS" in text_content.upper() or "Clinical" in filename:
                current_category = "Clinical Protocols"
            elif "TREATMENT PROTOCOLS" in text_content.upper() or "Treatment" in filename:
                current_category = "Treatment Protocols"
            elif "Report" in filename:
                current_category = "Patient Report"
                
            # --- 2. DETECT ROLES ---
            if "PUBLIC (Nurse + Doctor + Admin)" in text_content:
                current_roles = "Nurse,Doctor,Admin"
            elif "PRIVATE (Doctor + Admin)" in text_content:
                current_roles = "Doctor,Admin"
            elif "ADMIN ONLY" in text_content:
                current_roles = "Admin"

            # --- 3. DETECT MEDICAL CONDITION ---
            if "Respiratory Infection Guideline" in text_content:
                current_medical_condition = "Respiratory Infection"
            
            # --- 4. DETECT CONTENT TYPE (e.g., the specific type of information) ---
            if "Assessment:" in text_content:
                current_content_type = "Assessment"
            elif "Investigations:" in text_content or "Laboratory tests:" in text_content or "Imaging:" in text_content or "Microbiology:" in text_content:
                current_content_type = "Investigations"
            elif "Management:" in text_content or "Treatment Plan" in text_content:
                current_content_type = "Management and Treatment"
            elif "Medication Safety" in text_content:
                current_content_type = "Medication Safety"
            elif "Initial Stabilization (ABC Protocol)" in text_content:
                current_content_type = "Initial Stabilization"
            elif "Monitoring Protocol" in text_content:
                current_content_type = "Monitoring Protocol"
            elif "Discharge Criteria" in text_content:
                current_content_type = "Discharge Criteria"
            elif "Diagnostic Confirmation" in text_content:
                current_content_type = "Diagnostic Confirmation"
            elif "Severity Stratification" in text_content:
                current_content_type = "Severity Stratification"
            elif "Escalation Protocol" in text_content:
                current_content_type = "Escalation Protocol"

            # Generate the embedding (vector) for this chunk
            chunk_embedding = embeddings.embed_query(text_content)
            
            # Map to your database schema
            new_doc_chunk = DocumentChunk(
                chunk_text=text_content,
                chunk_index=i,
                source_type=filename,
                reference_id=chunk.metadata.get('page', 0),
                allowed_roles=current_roles,
                document_category=current_category,
                section=current_section,            # Keep section for structural hierarchy
                medical_condition=current_medical_condition, # <-- NEW!
                content_type=current_content_type,         # <-- NEW!
                embedding=chunk_embedding
            )
            
            db.add(new_doc_chunk)
            inserted_count += 1
            
            # Commit in batches of 50 to prevent memory overload
            if inserted_count % 50 == 0:
                db.commit()
                print(f"Inserted {inserted_count}/{len(chunks)} chunks...")
        
        # Final commit for the remaining chunks
        db.commit()
        print(f"Successfully processed and stored all {inserted_count} text chunks into PostgreSQL!")

    except Exception as e:
        db.rollback()
        print(f"An error occurred during DB insertion: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    ingest_documents()
