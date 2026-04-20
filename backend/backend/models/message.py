from sqlalchemy import Column, Integer, String, Text, TIMESTAMP
from datetime import datetime
from models.user import Base

class Message(Base):
    __tablename__ = "messages"

    message_id = Column(Integer, primary_key=True, index=True)
    conversation_id = Column(Integer)
    sender_type = Column(String(10))  # "user" or "ai"
    message_text = Column(Text)
    timestamp = Column(TIMESTAMP, default=datetime.utcnow)