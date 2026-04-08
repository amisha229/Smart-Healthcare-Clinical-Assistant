from sqlalchemy import Column, Integer, TIMESTAMP
from datetime import datetime
from models.user import Base

class Conversation(Base):
    __tablename__ = "conversations"

    conversation_id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer)
    started_at = Column(TIMESTAMP, default=datetime.utcnow)