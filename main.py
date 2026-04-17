from fastapi import FastAPI
from routes.auth import router as auth_router
from routes.chat import router as chat_router

app = FastAPI(
    title="Healthcare Assistant API",
    description="Clinical assistant with authentication, PostgreSQL-backed conversation history, and RAG-based medical retrieval.",
    version="1.0.0",
)

app.include_router(auth_router, prefix="/auth")
app.include_router(chat_router, prefix="/chat")

@app.get("/")
def home():
    return {"message": "Backend running"}