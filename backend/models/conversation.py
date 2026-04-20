from sqlalchemy import Column, Integer, TIMESTAMP, String
from datetime import datetime
from database import Base

class Conversation(Base):
    __tablename__ = "conversations"

    conversation_id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer)
    title = Column(String(200), nullable=True)
    started_at = Column(TIMESTAMP, default=datetime.utcnow)