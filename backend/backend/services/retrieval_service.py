from sqlalchemy.orm import Session
from langchain_huggingface import HuggingFaceEmbeddings
import sys
import os
import re

# Add backend to path if needed
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from database import SessionLocal
from models.document_chunk import DocumentChunk

_embeddings = None


def _get_embeddings() -> HuggingFaceEmbeddings:
    global _embeddings
    if _embeddings is None:
        _embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
    return _embeddings

def retrieve_clinical_context(query: str, user_role: str, top_k: int = 3) -> str:
    """
    Performs a vector search in PostgreSQL to find the most relevant medical documents.
    Strictly filters based on the user's role (Admin, Doctor, Nurse).
    """
    # 1. Convert the user's text question into a vector
    query_vector = _get_embeddings().embed_query(query)
    normalized_role = (user_role or "Doctor").strip().title()
    query_lower = (query or "").lower()
    query_tokens = {t for t in re.findall(r"[a-z0-9]+", query_lower) if len(t) >= 3}
    admin_intent_keywords = {
        "audit", "audit logs", "compliance", "governance", "data security",
        "access control", "modification", "modifications", "record access", "policy"
    }
    
    db: Session = SessionLocal()
    try:
        # 2. Pull unrestricted and role-filtered candidates with similarity scores.
        unrestricted_candidates = (
            db.query(
                DocumentChunk,
                DocumentChunk.embedding.cosine_distance(query_vector).label("distance")
            )
            .order_by(DocumentChunk.embedding.cosine_distance(query_vector))
            .limit(max(top_k * 3, 8))
            .all()
        )

        role_candidates = (
            db.query(
                DocumentChunk,
                DocumentChunk.embedding.cosine_distance(query_vector).label("distance")
            )
            .filter(
                DocumentChunk.allowed_roles.ilike(f"%{normalized_role}%")
            )
            .order_by(DocumentChunk.embedding.cosine_distance(query_vector))
            .limit(max(top_k * 3, 8))
            .all()
        )

        # 3. Restricted-access detection.
        # If best overall match is strong but is outside current role, and role-visible matches are much weaker,
        # treat this as access restricted (not "not found").
        if unrestricted_candidates:
            best_any_chunk, best_any_distance = unrestricted_candidates[0]
            best_role_distance = role_candidates[0][1] if role_candidates else None
            role_has_best = normalized_role.lower() in (best_any_chunk.allowed_roles or "").lower()

            strong_overall_match = best_any_distance is not None and best_any_distance <= 0.47
            role_is_much_weaker = (
                best_role_distance is None or
                (best_role_distance is not None and (best_role_distance - best_any_distance) >= 0.05)
            )

            admin_intent = any(keyword in query_lower for keyword in admin_intent_keywords)
            best_any_is_admin_only = (best_any_chunk.allowed_roles or "").strip().lower() == "admin"
            has_admin_only_candidate = any(
                ((cand_chunk.allowed_roles or "").strip().lower() == "admin") and (cand_dist is not None and cand_dist <= 0.62)
                for cand_chunk, cand_dist in unrestricted_candidates[:8]
            )

            # If role-visible candidates have meaningful lexical overlap, prefer serving those
            # instead of classifying as restricted.
            role_has_viable_match = False
            for role_chunk, role_dist in role_candidates[:5]:
                role_tokens = {t for t in re.findall(r"[a-z0-9]+", (role_chunk.chunk_text or "").lower()) if len(t) >= 3}
                overlap_count = len(query_tokens & role_tokens)
                if overlap_count >= 1 and role_dist is not None and role_dist <= 0.60:
                    role_has_viable_match = True
                    break

            # Strongly bias to ACCESS_RESTRICTED for governance/admin intent asked by non-admin roles.
            if admin_intent and normalized_role != "Admin" and (best_any_is_admin_only or has_admin_only_candidate):
                return "ACCESS_RESTRICTED: Relevant content exists but is restricted by your role permissions."

            if strong_overall_match and (not role_has_best) and role_is_much_weaker and not role_has_viable_match:
                return "ACCESS_RESTRICTED: Relevant content exists but is restricted by your role permissions."

        # 4. Build final role-filtered result set.
        results = [row[0] for row in role_candidates[:top_k]]

        if not results:
            # If there is no role-visible result at all, decide between restricted vs not found.
            if unrestricted_candidates:
                return "ACCESS_RESTRICTED: Relevant content exists but is restricted by your role permissions."

            return "NO_RELEVANT_DATA: No relevant medical protocols found in the knowledge base."

        # 5. Additional guard: if role results are all weak, classify as not found.
        best_role_distance = role_candidates[0][1] if role_candidates else None
        if best_role_distance is not None and best_role_distance > 0.42:
            # Lexical fallback for short/specific terms (e.g., ICU, nephritis, audit logs).
            top_role_chunks = [row[0] for row in role_candidates[:5]]
            has_overlap = False
            for chunk in top_role_chunks:
                text_tokens = {t for t in re.findall(r"[a-z0-9]+", (chunk.chunk_text or "").lower()) if len(t) >= 3}
                if query_tokens & text_tokens:
                    has_overlap = True
                    break

            if not has_overlap:
                return "NO_RELEVANT_DATA: No relevant medical protocols found in the knowledge base."

        # 6. Format role-filtered context blocks.
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
