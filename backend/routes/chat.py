from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from database import SessionLocal
from schemas.chat_schema import ChatRequest, ChatResponse, PatientListResponse
from services.chat_service import process_chat
from services.summarization_service import list_accessible_patients
from uuid import uuid4

router = APIRouter(tags=["Chat"])

# DB dependency
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.post(
    "",
    response_model=ChatResponse,
    summary="Clinical Retrieval Chat",
    description="Retrieves medical context from PostgreSQL and generates an answer with Groq."
)
def chat(request: ChatRequest, db: Session = Depends(get_db)):
    conversation_id = request.conversation_id or int(str(uuid4().int)[:8])

    response = process_chat(
        db=db,
        conversation_id=conversation_id,
        user_message=request.message,
        user_id=request.user_id,
        user_role=request.user_role,
        selected_tool=request.selected_tool,
        patient_name=request.patient_name,
        knowledge_type=request.knowledge_type or "condition",
        use_rag=request.use_rag,
        disease_name=request.disease_name,
    )

    return ChatResponse(
        conversation_id=conversation_id,
        user_id=request.user_id,
        user_role=request.user_role,
        selected_tool=request.selected_tool,
        patient_name=request.patient_name,
        knowledge_type=request.knowledge_type,
        disease_name=request.disease_name,
        response=response,
    )


@router.get(
    "/patients",
    response_model=PatientListResponse,
    summary="List accessible patient names",
    description="Returns patient names available to a role for summarization dropdown."
)
def patients(user_role: str = "Doctor", db: Session = Depends(get_db)):
    return PatientListResponse(user_role=user_role, patients=list_accessible_patients(db, user_role))