from typing import Optional

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    conversation_id: Optional[int] = Field(
        default=None,
        description="Optional conversation ID. Leave blank to create a new conversation."
    )
    user_id: int = Field(default=1, description="User ID that owns the conversation.")
    user_role: str = Field(default="Doctor", description="Role used to filter medical access.")
    message: str = Field(..., description="Clinical question for the assistant.")


class ChatResponse(BaseModel):
    conversation_id: int
    user_id: int
    user_role: str
    response: str