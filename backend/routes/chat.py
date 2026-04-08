from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from database import SessionLocal
from schemas.chat_schema import ChatRequest
from services.chat_service import process_chat

router = APIRouter()

# DB dependency
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.post("/chat")
def chat(request: ChatRequest, db: Session = Depends(get_db)):

    response = process_chat(
        db,
        request.conversation_id,
        request.message
    )

    return {"response": response}