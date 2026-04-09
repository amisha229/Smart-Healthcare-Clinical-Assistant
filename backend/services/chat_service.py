from models.message import Message
from models.conversation import Conversation
from sqlalchemy.orm import Session

# Dummy AI function (replace later with RAG)
def generate_ai_response(user_message: str):
    return f"AI response for: {user_message}"


def process_chat(db: Session, conversation_id: int, user_message: str):

    # 0. Check if conversation exists, create if not
    conversation = db.query(Conversation).filter(Conversation.conversation_id == conversation_id).first()
    if not conversation:
        conversation = Conversation(conversation_id=conversation_id, user_id=1) # Defaulting user_id to 1 for now
        db.add(conversation)
        try:
            db.commit()
        except:
            db.rollback()

    # 1. Store user message
    user_msg = Message(
        conversation_id=conversation_id,
        sender_type="user",
        message_text=user_message
    )
    db.add(user_msg)
    db.commit()

    # 2. Generate AI response
    ai_text = generate_ai_response(user_message)

    # 3. Store AI response
    ai_msg = Message(
        conversation_id=conversation_id,
        sender_type="ai",
        message_text=ai_text
    )
    db.add(ai_msg)
    db.commit()

    return ai_text