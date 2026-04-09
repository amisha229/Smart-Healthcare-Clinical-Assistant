from fastapi import FastAPI
from routes.auth import router as auth_router
from routes.chat import router as chat_router

app = FastAPI()

app.include_router(auth_router, prefix="/auth")
app.include_router(chat_router, prefix="/chat")

@app.get("/")
def home():
    return {"message": "Backend running"}