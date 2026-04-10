import os
import sys
from typing import Optional
from sqlalchemy.orm import Session

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from services.retrieval_service import retrieve_clinical_context
from dotenv import load_dotenv
from models.message import Message
from models.conversation import Conversation
from models.user import User

load_dotenv()

# Groq LLM
llm = ChatOpenAI(
    api_key=os.environ.get("GROQ_API_KEY"),
    base_url="https://api.groq.com/openai/v1",
    model="openai/gpt-oss-20b",
    temperature=0.2,
    max_tokens=1000
)

NOT_FOUND_MSG = (
    "The requested information is not available in the uploaded clinical or treatment documents."
)


def _get_role_guidance(user_role: str) -> str:
    role = (user_role or "Doctor").strip().lower()
    if role == "nurse":
        return (
            "You are responding to a Nurse. Use ONLY public nursing-safe instructions from context. "
            "Do NOT provide doctor-only diagnostics or treatment planning. "
            "If restricted content is requested, clearly state access is restricted."
        )
    if role == "admin":
        return (
            "You are responding to an Admin. Focus only on governance, policy, "
            "compliance, and system-level details."
        )
    return (
        "You are responding to a Doctor. Provide detailed clinical information strictly from the context."
    )


def generate_ai_response(user_message: str, user_role: str = "Doctor") -> str:
    context_result = retrieve_clinical_context(user_message, user_role)

    # Case 1: Data does not exist in the documents at all
    if context_result == "DATA_NOT_FOUND":
        return NOT_FOUND_MSG

    # Case 2: Data exists but this role is not permitted
    if context_result.startswith("ACCESS_DENIED:"):
        denied_role = context_result.split("ACCESS_DENIED:", 1)[1]
        return (
            f"Access Denied: Your role '{denied_role}' does not have permission to access "
            f"this information. Please contact your administrator if you believe this is an error."
        )

    # Case 3: Retrieval error
    if context_result == "RETRIEVAL_ERROR":
        return "An error occurred while retrieving medical knowledge. Please try again."

    # Case 4: Valid context retrieved → pass to LLM
    role_guidance = _get_role_guidance(user_role)

    prompt = ChatPromptTemplate.from_messages([
        (
            "system",
            "You are a Smart Healthcare Clinical Assistant.\n"
            "Answer ONLY using the provided medical context below.\n"
            "Do NOT use any external or prior knowledge.\n"
            "Apply role restrictions strictly: {role_guidance}\n\n"
            "If the specific answer is not found within the context, respond with exactly:\n"
            f"'{NOT_FOUND_MSG}'\n\n"
            "CONTEXT:\n{context}"
        ),
        ("human", "{question}")
    ])

    chain = prompt | llm
    response = chain.invoke({
        "role_guidance": role_guidance,
        "context": context_result,
        "question": user_message
    })
    return response.content.strip()


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
) -> str:
    if conversation_id is None:
        conversation_id = int(str(os.getpid()) + str(len(user_message)))

    _ensure_user_exists(db, user_id=user_id, user_role=user_role)

    conversation = db.query(Conversation).filter(
        Conversation.conversation_id == conversation_id
    ).first()

    if not conversation:
        conversation = Conversation(
            conversation_id=conversation_id,
            user_id=user_id
        )
        db.add(conversation)
        db.commit()
        db.refresh(conversation)

    user_msg = Message(
        conversation_id=conversation_id,
        sender_type="user",
        message_text=user_message
    )
    db.add(user_msg)
    db.commit()

    ai_text = generate_ai_response(user_message, user_role=user_role)

    ai_msg = Message(
        conversation_id=conversation_id,
        sender_type="ai",
        message_text=ai_text
    )
    db.add(ai_msg)
    db.commit()

    return ai_text