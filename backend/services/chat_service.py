import os
import sys
import re
from typing import Optional
from sqlalchemy.orm import Session

# Add backend to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from services.retrieval_service import retrieve_clinical_context
from services.summarization_service import summarize_patient_report
from services.medical_knowledge_service import get_medical_knowledge
from services.treatment_comparison_tool import compare_treatments
from services.diagnosis_recommendation import recommend_diagnosis
from dotenv import load_dotenv

from models.message import Message
from models.conversation import Conversation
from models.user import User
from models.medical_knowledge_cache import MedicalKnowledgeCache
from database import engine

# Load the .env file containing the Groq API key
load_dotenv()
MedicalKnowledgeCache.__table__.create(bind=engine, checkfirst=True)

# Initialize Groq using OpenAI-compatible client endpoint (This prevents decommissioning errors)
llm = ChatOpenAI(
    api_key=os.environ.get("GROQ_API_KEY"),
    base_url="https://api.groq.com/openai/v1",
    model="openai/gpt-oss-20b", 
    temperature=0.2, # Low temperature for high factual consistency
    max_tokens=1000
)


def _is_treatment_comparison_query(user_message: str) -> bool:
    """Heuristic guard to ensure treatment tool is used only for treatment-focused prompts."""
    text = (user_message or "").strip().lower()
    if not text:
        return False

    # Queries that are clearly meta/general and should not hit treatment comparison.
    blocked_patterns = [
        r"\bwho\s+are\s+you\b",
        r"\bwhat\s+agent\b",
        r"\bprime\s+minister\b",
        r"\bwhat\s+time\b",
        r"\bweather\b",
    ]
    for pattern in blocked_patterns:
        if re.search(pattern, text):
            return False

    # Explicit comparison phrasing.
    comparison_patterns = [
        r"\bcompare\b",
        r"\bcomparison\b",
        r"\bdifference between\b",
        r"\bwhich is better\b",
        r"\bbetter than\b",
    ]
    if any(re.search(pattern, text) for pattern in comparison_patterns):
        return True

    # Allow shorthand comparison lists such as "metformin vs gliclazide vs sitagliptin".
    if re.search(r"\bvs\b|\bversus\b", text):
        parts = [part.strip() for part in re.split(r"\bvs\b|\bversus\b", text) if part.strip()]
        if len(parts) >= 2:
            return True

    treatment_keywords = [
        "treatment", "regimen", "therapy", "compare", "comparison", "medication",
        "drug", "dose", "dosing", "side effect", "adverse", "contraindication",
        "pros", "cons", "efficacy", "outcome", "management", "guideline"
    ]
    return any(keyword in text for keyword in treatment_keywords)


def _get_role_guidance(user_role: str) -> str:
    role = (user_role or "Doctor").strip().lower()

    if role == "nurse":
        return (
            "You are responding to a Nurse. Use ONLY public nursing-safe instructions from context. "
            "Do NOT provide doctor-only diagnostics, advanced treatment planning, or decision rationale. "
            "If the question asks for doctor/admin-only content, explicitly state that this is restricted for Nurse role. "
            "Prefer concise operational guidance: monitoring, supportive care, escalation triggers, and documentation steps."
        )

    if role == "admin":
        return (
            "You are responding to an Admin. Focus on governance, policy, compliance, audit, and system-level controls "
            "available in context. Do NOT provide clinical bedside treatment details unless explicitly present in admin-allowed context."
        )

    return (
        "You are responding to a Doctor. Provide clinically detailed, context-grounded guidance from allowed protocol content, "
        "including diagnostic and treatment reasoning only when present in context."
    )

def generate_ai_response(user_message: str, user_role: str = "Doctor"):
    """
    Complete RAG Pipeline: Retrieves DB chunks based on role, then passes them to Groq LLM.
    """
    print(f"Retrieving DB chunks for role: {user_role}...")
    
    # 1. Retrieve the exact database chunks (Our Retrieval Engine)
    context_chunks = retrieve_clinical_context(user_message, user_role)
    
    if context_chunks.startswith("ACCESS_RESTRICTED:"):
        return "I cannot provide access to this information for your current role."

    if context_chunks.startswith("NO_RELEVANT_DATA:"):
        return "This question is outside the medical knowledge base available to this assistant. Please ask a medical guideline, treatment protocol, or patient-report question."

    print("Feeding chunks to Groq LLM for answer generation...")
    role_guidance = _get_role_guidance(user_role)

    # 2. Build the System Prompt
    prompt = ChatPromptTemplate.from_messages([
        (
            "system",
            "You are a highly capable AI Healthcare Assistant supporting a {user_role}.\n"
            "You must answer the user's question USING ONLY the provided Medical Context blocks below.\n"
            "Apply this role policy strictly: {role_guidance}\n"
            "If the answer is not in the context, you MUST say 'I cannot find this information in the allowed medical protocols.'\n"
            "Never invent or hallucinate medical advice.\n\n"
            "Response format:\n"
            "1) Access Scope: one line describing what this role can use.\n"
            "2) Answer: bullet points from allowed context only.\n"
            "3) Restricted Note: include only if user asked for restricted content.\n\n"
            "===== MEDICAL CONTEXT =====\n"
            "{context}\n"
            "==========================="
        ),
        ("human", "{question}")
    ])

    # 3. Create the Chain and generate the final answer
    chain = prompt | llm
    
    response = chain.invoke({
        "user_role": user_role,
        "role_guidance": role_guidance,
        "context": context_chunks,
        "question": user_message
    })

    return response.content


def _ensure_user_exists(db: Session, user_id: int, user_role: str) -> None:
    existing_user = db.query(User).filter(User.user_id == user_id).first()
    if existing_user:
        return

    test_user = User(
        user_id=user_id,
        username=f"swagger_user_{user_id}",
        password="testpass123",
        role=user_role,
    )
    db.add(test_user)
    db.commit()


def process_chat(
    db: Session,
    conversation_id: Optional[int],
    user_message: str,
    user_id: int = 1,
    user_role: str = "Doctor",
    selected_tool: str = "retrieval",
    patient_name: Optional[str] = None,
    knowledge_type: str = "condition",
    use_rag: bool = True,
    disease_name: Optional[str] = None,
):

    if conversation_id is None:
        conversation_id = int(str(os.getpid()) + str(len(user_message)))

    _ensure_user_exists(db, user_id=user_id, user_role=user_role)

    # 0. Check if conversation exists, create if not
    conversation = db.query(Conversation).filter(Conversation.conversation_id == conversation_id).first()
    if not conversation:
        conversation = Conversation(conversation_id=conversation_id, user_id=user_id)
        db.add(conversation)
        try:
            db.commit()
            db.refresh(conversation) # Make absolutely sure the conversation is created before inserting messages
        except Exception as e:
            db.rollback()
            print(f"Error creating conversation: {e}")
            raise e

    # 1. Store user message
    user_msg = Message(
        conversation_id=conversation_id,
        sender_type="user",
        message_text=user_message
    )
    db.add(user_msg)
    db.commit()

    # 2. Generate AI response based on selected tool
    tool = (selected_tool or "retrieval").strip().lower()
    if tool == "summarization":
        if (user_role or "").strip().title() == "Admin":
            ai_text = "Summarization tool is not available for Admin role."
        elif not patient_name:
            ai_text = "Please provide patient_name when using summarization tool."
        else:
            ai_text = summarize_patient_report(db, patient_name=patient_name, user_role=user_role)
    elif tool == "medical_knowledge":
        mk = get_medical_knowledge(
            query=user_message,
            knowledge_type=knowledge_type or "condition",
            db=db,
            user_role=user_role,
            use_rag=use_rag,
        )
        ai_text = mk.get("response", "Unable to fetch medical knowledge right now.")
    elif tool == "treatment_comparison":
        if not disease_name:
            ai_text = "Please provide disease_name when using treatment_comparison tool. E.g., 'Type 2 Diabetes Mellitus', 'Rheumatoid Arthritis'."
        elif not _is_treatment_comparison_query(user_message):
            ai_text = "This is not related to a treatment-comparison question."
        else:
            ai_text = compare_treatments(
                query=user_message,
                disease_name=disease_name,
                user_role=user_role,
                db=db
            )
    elif tool == "diagnosis_recommendation":
        ai_text = recommend_diagnosis(
            query=user_message,
            user_role=user_role,
            db=db,
        )
    else:
        ai_text = generate_ai_response(user_message, user_role=user_role)

    # 3. Store AI response
    ai_msg = Message(
        conversation_id=conversation_id,
        sender_type="ai",
        message_text=ai_text
    )
    db.add(ai_msg)
    db.commit()

    return ai_text