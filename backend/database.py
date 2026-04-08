from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

DATABASE_URL = "postgresql://teamuser:strongpassword@172.25.80.237:5432/healthcare"

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)