from sqlalchemy import Column, Integer, String, Text
from pgvector.sqlalchemy import Vector
from database import Base

class DocumentChunk(Base):
    __tablename__ = 'document_chunks'

    chunk_id = Column(Integer, primary_key=True, autoincrement=True)
    chunk_text = Column(Text, nullable=False)
    chunk_index = Column(Integer)
    source_type = Column(String(50))
    reference_id = Column(Integer, nullable=True)
    allowed_roles = Column(String(255), default="Admin")
    document_category = Column(String(100), nullable=True)  # e.g., Clinical Guidelines, Treatment Protocols
    section = Column(String(255), nullable=True)            # e.g., Initial Stabilization, Diagnostic Confirmation
    medical_condition = Column(String(255), nullable=True)  # e.g., Respiratory Infection, Community-Acquired Pneumonia
    content_type = Column(String(255), nullable=True)       # e.g., Assessment, Management, Medication Safety
    embedding = Column(Vector(384))  # 384 dimensions for our HuggingFace model
