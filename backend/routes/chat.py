from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from database import SessionLocal
from schemas.chat_schema import (
    ChatRequest,
    ChatResponse,
    PatientListResponse,
    ConversationSummaryResponse,
    ChatHistoryResponse,
    ChatHistoryItem,
    ConversationDeleteResponse,
    ConversationRenameRequest,
    ConversationRenameResponse,
)
from services.chat_service import process_chat
from services.summarization_service import list_accessible_patients
from uuid import uuid4
from models.conversation import Conversation
from models.message import Message

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

    result = process_chat(
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

    if isinstance(result, dict):
        response_text = result.get("response", "")
        source = result.get("source")
    else:
        response_text = str(result)
        source = None

    return ChatResponse(
        conversation_id=conversation_id,
        user_id=request.user_id,
        user_role=request.user_role,
        selected_tool=request.selected_tool,
        patient_name=request.patient_name,
        knowledge_type=request.knowledge_type,
        disease_name=request.disease_name,
        response=response_text,
        source=source,
    )


@router.patch(
    "/conversations/{conversation_id}",
    response_model=ConversationRenameResponse,
    summary="Rename conversation",
    description="Updates the title for a saved conversation owned by the user.",
)
def rename_conversation(
    conversation_id: int,
    payload: ConversationRenameRequest,
    user_id: int = Query(..., description="User ID that owns the conversation."),
    db: Session = Depends(get_db),
):
    convo = (
        db.query(Conversation)
        .filter(Conversation.conversation_id == conversation_id, Conversation.user_id == user_id)
        .first()
    )
    if not convo:
        raise HTTPException(status_code=404, detail="Conversation not found for this user.")

    convo.title = payload.title.strip()
    db.commit()
    db.refresh(convo)

    return ConversationRenameResponse(conversation_id=conversation_id, title=convo.title)


@router.get(
    "/patients",
    response_model=PatientListResponse,
    summary="List accessible patient names",
    description="Returns patient names available to a role for summarization dropdown."
)
def patients(user_role: str = "Doctor", db: Session = Depends(get_db)):
    return PatientListResponse(user_role=user_role, patients=list_accessible_patients(db, user_role))


@router.get(
    "/conversations",
    response_model=list[ConversationSummaryResponse],
    summary="List user conversations",
    description="Returns saved conversation threads from PostgreSQL for a specific user.",
)
def conversations(user_id: int = Query(..., description="User ID whose conversations should be listed."), db: Session = Depends(get_db)):
    rows = (
        db.query(Conversation)
        .filter(Conversation.user_id == user_id)
        .order_by(Conversation.started_at.desc())
        .all()
    )

    summaries: list[ConversationSummaryResponse] = []
    for convo in rows:
        message_count = (
            db.query(Message)
            .filter(Message.conversation_id == convo.conversation_id)
            .count()
        )
        summaries.append(
            ConversationSummaryResponse(
                conversation_id=convo.conversation_id,
                title=convo.title,
                started_at=convo.started_at.isoformat() if convo.started_at else None,
                message_count=message_count,
            )
        )

    return summaries


@router.get(
    "/conversations/{conversation_id}",
    response_model=ChatHistoryResponse,
    summary="Get conversation history",
    description="Returns the full message history for a single saved conversation.",
)
def conversation_history(conversation_id: int, user_id: int = Query(..., description="User ID that owns the conversation."), db: Session = Depends(get_db)):
    convo = (
        db.query(Conversation)
        .filter(Conversation.conversation_id == conversation_id, Conversation.user_id == user_id)
        .first()
    )
    if not convo:
        raise HTTPException(status_code=404, detail="Conversation not found for this user.")

    messages = (
        db.query(Message)
        .filter(Message.conversation_id == conversation_id)
        .order_by(Message.timestamp.asc())
        .all()
    )

    return ChatHistoryResponse(
        conversation_id=conversation_id,
        user_id=user_id,
        messages=[
            ChatHistoryItem(
                sender="user" if msg.sender_type == "user" else "ai",
                message=msg.message_text,
                timestamp=msg.timestamp.isoformat() if msg.timestamp else None,
            )
            for msg in messages
        ],
    )


@router.delete(
    "/conversations/{conversation_id}",
    response_model=ConversationDeleteResponse,
    summary="Delete conversation",
    description="Deletes a saved conversation and all of its messages for the owning user.",
)
def delete_conversation(conversation_id: int, user_id: int = Query(..., description="User ID that owns the conversation."), db: Session = Depends(get_db)):
    convo = (
        db.query(Conversation)
        .filter(Conversation.conversation_id == conversation_id, Conversation.user_id == user_id)
        .first()
    )
    if not convo:
        raise HTTPException(status_code=404, detail="Conversation not found for this user.")

    deleted_messages = (
        db.query(Message)
        .filter(Message.conversation_id == conversation_id)
        .delete(synchronize_session=False)
    )
    db.delete(convo)
    db.commit()

    return ConversationDeleteResponse(
        conversation_id=conversation_id,
        deleted_messages=deleted_messages or 0,
        deleted_conversation=True,
    )