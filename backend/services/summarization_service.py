from sqlalchemy.orm import Session
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from dotenv import load_dotenv
from models.document_chunk import DocumentChunk
import os
import re

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

    if normalized_role == "Admin":
        return "Summarization tool is not available for Admin role."

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

    # Age control: do not allow hallucinated age if age is not present in accessible context.
    age_present = bool(
        re.search(r"\b\d{1,3}\s*-?\s*year\s*-?\s*old\b", context, re.IGNORECASE)
        or re.search(r"\bage\b\s*[:=]?\s*\d{1,3}\b", context, re.IGNORECASE)
    )

    role_policy = {
        "Nurse": (
            "Summarize only public nursing-safe care information. "
            "Do not include doctor-only diagnostics, advanced treatment rationale, private clinical interpretations, or confidential notes. "
            "Focus on bedside care actions: monitoring, escalation triggers, medication administration, and follow-up tasks."
        ),
        "Doctor": (
            "Provide a clinically complete summary from accessible context, including diagnosis, investigations, treatment, and follow-up. "
            "Include concise clinical reasoning where explicitly present in context."
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
                "Age rule: {age_rule}\n"
                "Use ONLY the report context below. If unavailable, say so clearly.\n\n"
                "Output format:\n"
                "1) Access Scope\n"
                "2) Patient Summary\n"
                "3) Key Clinical Points\n"
                "4) Medications and Follow-up\n"
                "5) Restrictions Note (if any)\n\n"
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
            "age_rule": (
                "If patient age is not explicitly stated in context, write: 'Age: Not available in accessible report.' "
                "Never infer, estimate, or invent age."
                if not age_present
                else "If age exists in context, report it exactly as written; do not estimate."
            ),
            "patient_name": patient_name,
            "context": context,
        }
    )

    return response.content


def list_accessible_patients(db: Session, user_role: str) -> list[str]:
    normalized_role = (user_role or "Doctor").strip().title()

    if normalized_role == "Admin":
        return []

    rows = (
        db.query(DocumentChunk.patient_name)
        .filter(DocumentChunk.document_type == "patient_report")
        .filter(DocumentChunk.patient_name.isnot(None))
        .filter(DocumentChunk.allowed_roles.ilike(f"%{normalized_role}%"))
        .distinct()
        .all()
    )

    return sorted([row[0] for row in rows if row[0]])
