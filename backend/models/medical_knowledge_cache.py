from sqlalchemy import Column, Integer, String, Text, TIMESTAMP
from database import Base
from datetime import datetime

class MedicalKnowledgeCache(Base):
    __tablename__ = "medical_knowledge_cache"

    id = Column(Integer, primary_key=True, index=True)
    query = Column(String(500), unique=True, nullable=False, index=True)
    knowledge_type = Column(String(50), nullable=False)
    response = Column(Text, nullable=False)
    source = Column(String(100), nullable=False)
    cached_at = Column(TIMESTAMP, default=datetime.utcnow)
    expires_at = Column(TIMESTAMP, nullable=False)