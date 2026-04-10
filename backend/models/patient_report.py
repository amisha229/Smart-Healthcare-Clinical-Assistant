from sqlalchemy import Column, Integer, String, TIMESTAMP
from datetime import datetime
from database import Base


class PatientReport(Base):
    __tablename__ = "patient_reports"

    id = Column(Integer, primary_key=True, autoincrement=True)
    report_id = Column(String(50), unique=True, nullable=False, index=True)
    patient_name = Column(String(150), nullable=False, index=True)
    report_date = Column(String(30), nullable=True)
    department = Column(String(100), nullable=True)
    hospital = Column(String(150), nullable=True)
    attending_doctor = Column(String(150), nullable=True)
    source_file = Column(String(255), nullable=True)
    created_at = Column(TIMESTAMP, default=datetime.utcnow)
