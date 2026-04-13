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
    document_type = Column(String(50), nullable=True)       # guideline | protocol | patient_report | treatment
    report_id = Column(String(50), nullable=True)
    patient_name = Column(String(150), nullable=True)
    hospital = Column(String(150), nullable=True)
    attending_doctor = Column(String(150), nullable=True)
    access_scope = Column(String(50), nullable=True)        # public | private | admin
    allowed_roles = Column(String(255), default="Admin")
    document_category = Column(String(100), nullable=True)  # e.g., Clinical Guidelines, Treatment Protocols, Treatment Comparison
    section = Column(String(255), nullable=True)            # e.g., Initial Stabilization, Diagnostic Confirmation, Patient Case
    medical_condition = Column(String(255), nullable=True)  # e.g., Respiratory Infection, Community-Acquired Pneumonia
    content_type = Column(String(255), nullable=True)       # e.g., Assessment, Management, Medication Safety, Treatment Regimen
    
    # Treatment document specific fields
    disease_name = Column(String(150), nullable=True)       # e.g., Type 2 Diabetes Mellitus, Rheumatoid Arthritis
    disease_code = Column(String(50), nullable=True)        # e.g., T2DM, RA
    icd_code = Column(String(50), nullable=True)            # e.g., E11, M05
    patient_case_id = Column(String(50), nullable=True)     # e.g., P-001-T2DM, P-013-RA
    treatment_regimen = Column(Text, nullable=True)         # Structured treatment details
    key_advantages = Column(Text, nullable=True)            # Comma-separated or bullet-pointed
    key_risks = Column(Text, nullable=True)                 # Comma-separated or bullet-pointed
    clinical_outcomes = Column(Text, nullable=True)         # Summary of outcomes
    severity_stage = Column(String(100), nullable=True)     # mild | moderate | severe
    treatment_tags = Column(String(500), nullable=True)     # Comma-separated tags for filtering
    
    embedding = Column(Vector(384))  # 384 dimensions for our HuggingFace model
