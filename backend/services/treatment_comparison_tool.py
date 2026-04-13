import os
import sys
import re
from datetime import datetime, timedelta
from typing import Optional
from sqlalchemy.orm import Session
from langchain_huggingface import HuggingFaceEmbeddings

# Add backend to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from dotenv import load_dotenv

from models.medical_knowledge_cache import MedicalKnowledgeCache
from models.document_chunk import DocumentChunk
from database import SessionLocal

load_dotenv()

# Initialize Groq LLM
llm = ChatOpenAI(
    api_key=os.environ.get("GROQ_API_KEY"),
    base_url="https://api.groq.com/openai/v1",
    model="openai/gpt-oss-20b",
    temperature=0.3,  # Slightly higher for nuanced comparisons
    max_tokens=1500,
)

treatment_embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")


def _check_treatment_cache(query: str, db: Session) -> Optional[str]:
    """
    Check if this treatment comparison is already cached.
    Return the cached answer if found and NOT expired.
    """
    try:
        cached_entry = db.query(MedicalKnowledgeCache).filter(
            MedicalKnowledgeCache.query == query,
            MedicalKnowledgeCache.knowledge_type == "treatment_comparison",
            MedicalKnowledgeCache.expires_at > datetime.utcnow()
        ).first()
        
        if cached_entry:
            print(f"✅ Treatment Cache HIT! Returning cached comparison for: {query}")
            return cached_entry.response
        
        print(f"⚠️ Treatment Cache MISS! Will generate comparison for: {query}")
        return None
    except Exception as e:
        print(f"⚠️ Cache check error: {e}")
        return None


def _get_role_guidance(user_role: str) -> str:
    """
    Get role-specific guidance for treatment comparison response formatting.
    """
    role = (user_role or "Doctor").strip().lower()
    
    if role == "nurse":
        return (
            "Provide simplified, practical information for nursing staff:\n"
            "- Simple explanation of how each treatment works\n"
            "- Administration instructions and routes\n"
            "- Common side effects to monitor\n"
            "- Patient care guidance and precautions\n"
            "Use clear, non-technical language. Focus on practical nursing care."
        )
    
    if role == "admin":
        return (
            "Provide administrative perspective on treatment comparison:\n"
            "- Cost considerations\n"
            "- Resource requirements\n"
            "- Policy implications\n"
            "Focus on governance and operational aspects."
        )
    
    return (
        "Provide detailed clinical analysis for medical decision-making:\n"
        "- Pharmacological mechanisms and pathophysiology\n"
        "- Clinical efficacy data and evidence-based metrics\n"
        "- Contraindications, drug interactions, and adverse effects\n"
        "- Advanced clinical scenarios and dosing strategies\n"
        "Use technical medical terminology and include clinical evidence."
    )


def _generate_treatment_comparison(query: str, clinical_context: str, user_role: str) -> str:
    """
    Use Groq LLM to generate a detailed treatment comparison based on clinical context.
    """
    role_guidance = _get_role_guidance(user_role)
    normalized_role = (user_role or "Doctor").strip().title()

    focus_instruction = _build_query_focus_instruction(query)

    prompt = ChatPromptTemplate.from_messages([
        (
            "system",
            "You are a clinical treatment comparison assistant.\n"
            "Target Role: {user_role}\n"
            "Role Guidance:\n{role_guidance}\n\n"
            "Requested Focus:\n{focus_instruction}\n\n"
            "Based on the clinical context provided, compare the treatment options at disease level (not per individual patient case):\n\n"
            "Output Format:\n"
            "1. Treatment Summary Table (Markdown table only):\n"
            "   Columns: Regimen | Use Case | Key Pros | Key Cons | Monitoring Needs\n"
            "2. Comparative Analysis Table (Markdown table only):\n"
            "   Columns: Dimension | Option A | Option B | Option C (if available)\n"
            "3. Recommendation (max 3 bullet points)\n\n"
            "Formatting Rules (strict):\n"
            "- Plain text only (Markdown tables and bullets only)\n"
            "- Do NOT output HTML tags like <br>, <table>, <tr>, <td>\n"
            "- Do NOT output symptom tables\n"
            "- Do NOT include patient IDs/case labels (e.g., P-001, Case 002)\n"
            "- Compare treatment strategies, not individual patient narratives\n\n"
            "- Keep answer focused on the user's requested comparison dimension; do not add unrelated sections\n\n"
            "- Keep cells concise: each table cell max 12 words\n"
            "- Total output max 220 words\n"
            "- If data is missing, write 'Not available in context'\n\n"
            "Use ONLY the clinical context provided. If specific information is unavailable, state it clearly.\n\n"
            "===== CLINICAL CONTEXT =====\n"
            "{clinical_context}\n"
            "=============================="
        ),
        ("human", "Compare the following treatment options: {query}")
    ])
    
    chain = prompt | llm
    response = chain.invoke({
        "user_role": normalized_role,
        "role_guidance": role_guidance,
        "focus_instruction": focus_instruction,
        "clinical_context": clinical_context if clinical_context else "No specific clinical context available.",
        "query": query
    })
    
    return response.content


def _sanitize_treatment_output(text: str) -> str:
    """Normalize model output to plain text and remove residual HTML formatting."""
    if not text:
        return text

    cleaned = text
    # Convert common line-break tags first.
    cleaned = re.sub(r"(?i)<\s*br\s*/?\s*>", "\n", cleaned)
    # Remove any other HTML tags if present.
    cleaned = re.sub(r"<[^>]+>", "", cleaned)
    # Collapse excessive blank lines.
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned.strip()


def _build_query_focus_instruction(query: str) -> str:
    """Build a concise instruction that keeps model output relevant to user intent."""
    q = (query or "").lower()
    focus = []

    if any(k in q for k in ["side effect", "adverse", "safety", "burden"]):
        focus.append("Prioritize side-effect burden comparison.")
    if any(k in q for k in ["monitor", "monitoring", "follow-up", "lab"]):
        focus.append("Prioritize monitoring needs comparison (vitals, labs, follow-up cadence).")
    if "mild" in q and "severe" in q:
        focus.append("Compare mild versus severe treatment strategy explicitly.")
    if any(k in q for k in ["cost", "resource", "affordability"]):
        focus.append("Include cost/resource trade-offs only if requested.")
    if any(k in q for k in ["table", "tabular", "format"]):
        focus.append("Respond in compact markdown tables with no narrative paragraphs.")

    if not focus:
        return "Answer the exact comparison asked using compact markdown tables with high-relevance points only."

    return " ".join(focus)


def _retrieve_treatment_context(
    query: str,
    disease_name: str,
    user_role: str,
    db: Session,
    top_k: int = 6,
) -> str:
    """Retrieve treatment chunks with strict disease + role filtering for relevance."""
    normalized_role = (user_role or "Doctor").strip().title()
    vector = treatment_embeddings.embed_query(f"{disease_name} {query}")

    results = (
        db.query(
            DocumentChunk,
            DocumentChunk.embedding.cosine_distance(vector).label("distance"),
        )
        .filter(DocumentChunk.document_type == "treatment")
        .filter(DocumentChunk.disease_name.ilike(f"%{disease_name}%"))
        .filter(DocumentChunk.allowed_roles.ilike(f"%{normalized_role}%"))
        .order_by(DocumentChunk.embedding.cosine_distance(vector))
        .limit(top_k)
        .all()
    )

    if not results:
        unrestricted = (
            db.query(DocumentChunk)
            .filter(DocumentChunk.document_type == "treatment")
            .filter(DocumentChunk.disease_name.ilike(f"%{disease_name}%"))
            .limit(1)
            .all()
        )
        if unrestricted:
            return "ACCESS_RESTRICTED: Relevant content exists but is restricted by your role permissions."
        return "NO_RELEVANT_DATA: No relevant treatment protocols found for this disease."

    context_blocks = []
    for chunk, _distance in results:
        header = (
            f"[Disease: {chunk.disease_name} | Section: {chunk.section} | "
            f"Category: {chunk.document_category} | Allowed: {chunk.allowed_roles}]"
        )
        context_blocks.append(f"{header}\n{chunk.chunk_text}")

    return "\n\n".join(context_blocks)


def _cache_treatment_result(
    query: str,
    response: str,
    source: str,
    db: Session
) -> None:
    """
    Save the treatment comparison to cache for 60 days.
    """
    try:
        cache_entry = MedicalKnowledgeCache(
            query=query,
            knowledge_type="treatment_comparison",
            response=response,
            source=source,
            expires_at=datetime.utcnow() + timedelta(days=60)
        )
        
        db.add(cache_entry)
        db.commit()
        print(f"✅ Treatment comparison cached for: {query}")
    except Exception as e:
        db.rollback()
        print(f"⚠️ Failed to cache treatment comparison: {e}")


def compare_treatments(
    query: str,
    disease_name: str,
    user_role: str = "Doctor",
    db: Optional[Session] = None
) -> str:
    """
    Main function to compare treatment options for a disease based on user query.
    Integrates RAG retrieval, disease filtering, LLM-based comparison, caching, and role-based filtering.
    
    Args:
        query: Treatment comparison query (e.g., "Compare regimens for obese patient vs. CKD patient")
        disease_name: Disease name to filter treatment documents (e.g., "Type 2 Diabetes Mellitus")
        user_role: User's role (Doctor, Nurse, Admin)
        db: Database session for caching and retrieval
        
    Returns:
        Treatment comparison response with structured analysis
    """
    close_db = False
    if db is None:
        db = SessionLocal()
        close_db = True
    
    try:
        # 1. Build disease-filtered search query
        search_query = f"Compare treatments for {disease_name}: {query}"
        
        # 2. Retrieve treatment context filtered by disease + role
        print(f"Retrieving treatment information for: {disease_name}")
        clinical_context = _retrieve_treatment_context(
            query=query,
            disease_name=disease_name,
            user_role=user_role,
            db=db,
            top_k=6,
        )
        
        # Handle access restrictions
        if clinical_context.startswith("ACCESS_RESTRICTED:"):
            return "Treatment comparison information is not accessible for your current role."
        
        # Handle no relevant data
        if clinical_context.startswith("NO_RELEVANT_DATA:") or clinical_context.startswith("No relevant"):
            return f"No treatment comparison data found for {disease_name}. Please verify disease name or try a different query."
        
        # 3. Generate comparison using Groq LLM
        print("Generating treatment comparison with Groq LLM...")
        comparison = _generate_treatment_comparison(query, clinical_context, user_role)
        comparison = _sanitize_treatment_output(comparison)
        
        # 4. Cache the result
        source = "RAG + Groq LLM"
        _cache_treatment_result(search_query, comparison, source, db)
        
        return comparison
        
    except Exception as e:
        print(f"❌ Error in treatment comparison: {str(e)}")
        return f"Error generating treatment comparison: {str(e)}"
    finally:
        if close_db:
            db.close()