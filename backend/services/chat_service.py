from models.message import Message
from sqlalchemy.orm import Session

# Dummy AI function (replace later with RAG)
def generate_ai_response(user_message: str):
    return f"AI response for: {user_message}"


def process_chat(db: Session, conversation_id: int, user_message: str):

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