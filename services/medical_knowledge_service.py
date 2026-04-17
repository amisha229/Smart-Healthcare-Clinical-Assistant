import os
import sys
import re
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict
from sqlalchemy.orm import Session

# Add backend to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from dotenv import load_dotenv

from models.medical_knowledge_cache import MedicalKnowledgeCache
from services.retrieval_service import retrieve_clinical_context

load_dotenv()

CACHE_KEY_VERSION = "v2"


def _normalize_knowledge_type(knowledge_type: str) -> str:
    value = (knowledge_type or "condition").strip().lower()
    aliases = {
        "symptoms": "symptom",
        "drugs": "drug",
        "conditions": "condition",
        "procedures": "procedure",
        "guidelines": "guideline",
    }
    return aliases.get(value, value)


def _normalize_query(query: str) -> str:
    value = (query or "").strip().lower()
    value = re.sub(r"\s+", " ", value)
    value = re.sub(r"[?.!]+$", "", value)
    return value

# Initialize Groq LLM
llm = ChatOpenAI(
    api_key=os.environ.get("GROQ_API_KEY"),
    base_url="https://api.groq.com/openai/v1",
    model="openai/gpt-oss-20b",
    temperature=0.2,
    max_tokens=400,
)


def _cache_key(query: str, knowledge_type: str) -> str:
    normalized_type = _normalize_knowledge_type(knowledge_type)
    normalized_query = _normalize_query(query)
    return f"{CACHE_KEY_VERSION}::{normalized_type}::{normalized_query}"


def _check_cache(query: str, knowledge_type: str, db: Session) -> Optional[str]:
    """
    Check if this question is already cached in the database.
    Return the cached answer if found and NOT expired.
    """
    normalized_type = _normalize_knowledge_type(knowledge_type)
    key = _cache_key(query, normalized_type)
    cached_entry = db.query(MedicalKnowledgeCache).filter(
        MedicalKnowledgeCache.query == key,
        MedicalKnowledgeCache.knowledge_type == normalized_type,
        MedicalKnowledgeCache.expires_at > datetime.now(timezone.utc)  # Not expired
    ).first()
    
    if cached_entry:
        print(f"✅ Cache HIT! Returning cached answer for: {query}")
        return cached_entry.response
    
    print(f"⚠️ Cache MISS! Will query Groq for: {query}")
    return None


def _query_groq_for_knowledge(query: str, knowledge_type: str, user_role: str) -> str:
    """
    Ask Groq LLM for medical knowledge.
    """
    role = (user_role or "Doctor").strip().title()
    role_policy = {
        "Nurse": "Provide concise nursing-safe explanations only. Avoid doctor-only advanced diagnostics or prescribing decisions.",
        "Doctor": "Provide clinically detailed explanations with differential points when relevant.",
        "Admin": "Provide high-level informational explanation and avoid bedside treatment directives.",
    }.get(role, "Provide safe medical information.")

    prompt = ChatPromptTemplate.from_messages([
        (
            "system",
            "You are a general-purpose medical knowledge assistant. "
            "Keep answers brief and practical by default: 4-6 bullet points, short lines, no tables. "
            "Do not include exhaustive differential lists unless the user explicitly asks for a detailed answer. "
            "End with one brief safety line only when relevant. "
            "Role policy: {role_policy}"
        ),
        ("human", "Knowledge type: {knowledge_type}\nQuestion: {query}")
    ])
    
    chain = prompt | llm
    response = chain.invoke({
        "knowledge_type": knowledge_type,
        "role_policy": role_policy,
        "query": query
    })
    
    return response.content


def _augment_with_rag(query: str, knowledge_type: str, knowledge_response: str, user_role: str) -> str:
    """
    Add clinical context from your documents to the Groq response.
    """
    clinical_context = retrieve_clinical_context(query, user_role)
    
    if (
        clinical_context.startswith("No relevant")
        or clinical_context.startswith("An error")
        or clinical_context.startswith("NO_RELEVANT_DATA:")
        or clinical_context.startswith("ACCESS_RESTRICTED:")
    ):
        return knowledge_response

    # Keep RAG grounded but concise: do not print raw document chunks.
    prompt = ChatPromptTemplate.from_messages([
        (
            "system",
            "Refine the draft answer using the clinical context silently. "
            "Return a concise final answer with 4-6 bullet points, no tables, no source dump, and no section headers. "
            "If the context does not materially improve the draft, keep the draft style and brevity."
        ),
        (
            "human",
            "Knowledge type: {knowledge_type}\n"
            "Question: {query}\n\n"
            "Draft answer:\n{draft}\n\n"
            "Clinical context:\n{context}"
        )
    ])

    chain = prompt | llm
    response = chain.invoke({
        "knowledge_type": knowledge_type,
        "query": query,
        "draft": knowledge_response,
        "context": clinical_context,
    })
    return response.content


def _cache_result(
    query: str,
    knowledge_type: str,
    response: str,
    source: str,
    db: Session
) -> None:
    """
    Save the answer to the database cache for 90 days.
    """
    normalized_type = _normalize_knowledge_type(knowledge_type)
    key = _cache_key(query, normalized_type)
    existing = db.query(MedicalKnowledgeCache).filter(
        MedicalKnowledgeCache.query == key,
        MedicalKnowledgeCache.knowledge_type == normalized_type,
    ).first()

    if existing:
        existing.response = response
        existing.source = source
        existing.cached_at = datetime.now(timezone.utc)
        existing.expires_at = datetime.now(timezone.utc) + timedelta(days=90)
    else:
        cache_entry = MedicalKnowledgeCache(
            query=key,
            knowledge_type=normalized_type,
            response=response,
            source=source,
            expires_at=datetime.now(timezone.utc) + timedelta(days=90)
        )
        db.add(cache_entry)

    db.commit()
    print(f"💾 Cached answer for: {query}")


def get_medical_knowledge(
    query: str,
    knowledge_type: str,
    db: Session,
    user_role: str = "Doctor",
    use_rag: bool = True
) -> Dict[str, str]:
    """
    Main function: Get medical knowledge about a drug/condition/symptom.
    
    Returns: {
        "response": "The medical answer",
        "source": "cache" OR "groq_llm" OR "rag_augmented",
        "knowledge_type": "drug",
        "query": "What is Aspirin?"
    }
    """
    
    normalized_knowledge_type = _normalize_knowledge_type(knowledge_type)

    # STEP 1: Check cache first
    cached_response = _check_cache(query, normalized_knowledge_type, db)
    if cached_response:
        return {
            "response": cached_response,
            "source": "cache",
            "knowledge_type": normalized_knowledge_type,
            "query": query
        }
    
    # STEP 2: Call Groq if not in cache
    print(f"🤖 Querying Groq for: {query}")
    groq_response = _query_groq_for_knowledge(query, normalized_knowledge_type, user_role)
    
    # STEP 3: Optionally augment with RAG
    final_response = groq_response
    source = "groq_llm"
    
    if use_rag:
        print("📚 Adding clinical context from RAG...")
        final_response = _augment_with_rag(
            query=query,
            knowledge_type=normalized_knowledge_type,
            knowledge_response=groq_response,
            user_role=user_role,
        )
        source = "rag_augmented"
    
    # STEP 4: Cache the result for future use
    _cache_result(query, normalized_knowledge_type, final_response, source, db)
    
    # STEP 5: Return the result
    return {
        "response": final_response,
        "source": source,
        "knowledge_type": normalized_knowledge_type,
        "query": query
    }