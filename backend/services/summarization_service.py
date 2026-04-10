from sqlalchemy.orm import Session
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from dotenv import load_dotenv
from models.document_chunk import DocumentChunk
import os

load_dotenv()

llm = ChatOpenAI(
    api_key=os.environ.get("GROQ_API_KEY"),
    base_url="https://api.groq.com/openai/v1",
    model="openai/gpt-oss-20b",
    temperature=0.2,
    max_tokens=1000,
)


def summarize_patient_report(db: Session, patient_name: str, user_role: str) -> str:
    normalized_role = (user_role or "Doctor").strip().title()

    chunks = (
        db.query(DocumentChunk)
        .filter(DocumentChunk.document_type == "patient_report")
        .filter(DocumentChunk.patient_name == patient_name)
        .filter(DocumentChunk.allowed_roles.ilike(f"%{normalized_role}%"))
        .order_by(DocumentChunk.chunk_index.asc())
        .all()
    )

    if not chunks:
        return "I cannot find an accessible report for this patient under your role permissions."

    context = "\n\n".join(
        [
            f"[Section: {chunk.section} | Scope: {chunk.access_scope} | Allowed: {chunk.allowed_roles}]\n{chunk.chunk_text}"
            for chunk in chunks
        ]
    )

    role_policy = {
        "Nurse": (
            "Summarize only public nursing-safe care information. "
            "Do not include doctor-only diagnostics, advanced treatment rationale, or private clinical interpretations."
        ),
        "Doctor": (
            "Provide a clinically complete summary from accessible context, including diagnosis, investigations, treatment, and follow-up."
        ),
        "Admin": (
            "Provide an administrative-level summary only from accessible content; avoid unnecessary bedside clinical detail."
        ),
    }.get(normalized_role, "Use only accessible context and do not hallucinate.")

    prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                "You are a healthcare summarization assistant.\n"
                "Target role: {user_role}.\n"
                "Role policy: {role_policy}\n"
                "Use ONLY the report context below. If unavailable, say so clearly.\n\n"
                "Output format:\n"
                "1) Patient Summary\n"
                "2) Key Clinical Points\n"
                "3) Medications and Follow-up\n"
                "4) Restrictions Note (if any)\n\n"
                "===== REPORT CONTEXT =====\n"
                "{context}\n"
                "=========================="
            ),
            ("human", "Summarize the report for patient {patient_name}."),
        ]
    )

    chain = prompt | llm
    response = chain.invoke(
        {
            "user_role": normalized_role,
            "role_policy": role_policy,
            "patient_name": patient_name,
            "context": context,
        }
    )

    return response.content


def list_accessible_patients(db: Session, user_role: str) -> list[str]:
    normalized_role = (user_role or "Doctor").strip().title()

    rows = (
        db.query(DocumentChunk.patient_name)
        .filter(DocumentChunk.document_type == "patient_report")
        .filter(DocumentChunk.patient_name.isnot(None))
        .filter(DocumentChunk.allowed_roles.ilike(f"%{normalized_role}%"))
        .distinct()
        .all()
    )

    return sorted([row[0] for row in rows if row[0]])
