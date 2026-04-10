from sqlalchemy.orm import Session
from langchain_huggingface import HuggingFaceEmbeddings
import sys
import os
import numpy as np

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from database import SessionLocal
from models.document_chunk import DocumentChunk

embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")

# Similarity threshold — scores below this mean the topic is not in the documents.
# Based on actual data analysis: irrelevant chunks score ~0.18–0.45, relevant ones score 0.5+
SIMILARITY_THRESHOLD = 0.5


def _cosine_similarity(vec1, vec2) -> float:
    try:
        a = np.array(vec1, dtype=float)
        b = np.array(vec2, dtype=float)
        norm_a = np.linalg.norm(a)
        norm_b = np.linalg.norm(b)
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return float(np.dot(a, b) / (norm_a * norm_b))
    except Exception as e:
        print(f"[_cosine_similarity error] {e}")
        return 0.0


def _role_has_access(allowed_roles_str: str, user_role: str) -> bool:
    """
    Exact match check. allowed_roles_str is a CSV like 'Nurse,Doctor,Admin'.
    user_role is a single role like 'Nurse'.
    """
    if not allowed_roles_str:
        return False
    allowed = [r.strip().lower() for r in allowed_roles_str.split(",")]
    return user_role.strip().lower() in allowed


def retrieve_clinical_context(query: str, user_role: str, top_k: int = 5) -> str:
    query_vector = embeddings.embed_query(query)
    normalized_role = (user_role or "Doctor").strip().title()

    db: Session = SessionLocal()
    try:
        # STEP 1: If DB is completely empty → not found
        total_count = db.query(DocumentChunk).count()
        if total_count == 0:
            return "DATA_NOT_FOUND"

        # STEP 2: Score every chunk by cosine similarity — NO role filter
        all_chunks = db.query(DocumentChunk).all()

        scored = sorted(
            [
                (chunk, _cosine_similarity(chunk.embedding, query_vector))
                for chunk in all_chunks
            ],
            key=lambda x: x[1],
            reverse=True
        )

        # STEP 3: Keep only chunks above the similarity threshold
        # These are chunks where the topic genuinely exists in the documents
        relevant = [(chunk, score) for chunk, score in scored if score >= SIMILARITY_THRESHOLD]

        if not relevant:
            # The topic does not exist in any document at all
            return "DATA_NOT_FOUND"

        # STEP 4: Topic EXISTS — now split by role access
        allowed_chunks = [
            chunk for chunk, score in relevant
            if _role_has_access(chunk.allowed_roles, normalized_role)
        ]
        denied_chunks = [
            chunk for chunk, score in relevant
            if not _role_has_access(chunk.allowed_roles, normalized_role)
        ]

        if denied_chunks and not allowed_chunks:
            # Topic exists but this role has zero access to any relevant chunk
            return f"ACCESS_DENIED:{normalized_role}"

        if not allowed_chunks:
            # No relevant chunks at all for this role (edge case safety net)
            return f"ACCESS_DENIED:{normalized_role}"

        # STEP 5: Return formatted context for allowed chunks (top_k)
        context_blocks = []
        for res in allowed_chunks[:top_k]:
            header = (
                f"[Source: {res.source_type} | "
                f"Category: {res.document_category} | "
                f"Section: {res.section} | "
                f"Allowed: {res.allowed_roles}]"
            )
            context_blocks.append(f"{header}\n{res.chunk_text}")

        return "\n\n".join(context_blocks)

    except Exception as e:
        print(f"[retrieval error] {type(e).__name__}: {e}")
        return "RETRIEVAL_ERROR"
    finally:
        db.close()