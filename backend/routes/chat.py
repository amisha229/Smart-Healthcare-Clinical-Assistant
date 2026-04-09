from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from database import SessionLocal
from schemas.chat_schema import ChatRequest, ChatResponse
from services.chat_service import process_chat
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
    )

    return ChatResponse(
        conversation_id=conversation_id,
        user_id=request.user_id,
        user_role=request.user_role,
        response=response,
    )