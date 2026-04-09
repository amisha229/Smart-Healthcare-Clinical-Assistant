from sqlalchemy.orm import Session
from langchain_huggingface import HuggingFaceEmbeddings
import sys
import os

# Add backend to path if needed
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from database import SessionLocal
from models.document_chunk import DocumentChunk

# Initialize embedding model once to speed up queries
embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")

def retrieve_clinical_context(query: str, user_role: str, top_k: int = 3) -> str:
    """
    Performs a vector search in PostgreSQL to find the most relevant medical documents.
    Strictly filters based on the user's role (Admin, Doctor, Nurse).
    """
    # 1. Convert the user's text question into a vector
    query_vector = embeddings.embed_query(query)
    normalized_role = (user_role or "Doctor").strip().title()
    
    db: Session = SessionLocal()
    try:
        # 2. Database Query: Filter by Role, then Sort by Vector Similarity (Cosine Distance)
        results = db.query(DocumentChunk).filter(
            DocumentChunk.allowed_roles.ilike(f"%{normalized_role}%")
        ).order_by(
            DocumentChunk.embedding.cosine_distance(query_vector)
        ).limit(top_k).all()
        
        if not results:
            return "No relevant medical protocols found for your query and access level."
            
        # 3. Format the retrieved chunks into a clean context block
        context_blocks = []
        for res in results:
            header = f"[Source: {res.source_type} | Category: {res.document_category} | Section: {res.section} | Allowed: {res.allowed_roles}]"
            context_blocks.append(f"{header}\n{res.chunk_text}")
            
        return "\n\n".join(context_blocks)
        
    except Exception as e:
        print(f"Error during retrieval: {e}")
        return "An error occurred while retrieving medical knowledge."
    finally:
        db.close()

# Quick test if you run this file directly!
if __name__ == "__main__":
    test_query = "What is the management for severe respiratory infection?"
    test_role = "Nurse" # Change this to "Admin" or "Doctor" to test security!
    
    print(f"--- Testing Retrieval for Role: {test_role} ---")
    print(f"Query: {test_query}\n")
    
    retrieved_text = retrieve_clinical_context(test_query, test_role)
    print(retrieved_text)
