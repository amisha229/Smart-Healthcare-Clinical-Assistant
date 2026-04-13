from typing import Optional

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    conversation_id: Optional[int] = Field(
        default=None,
        description="Optional conversation ID. Leave blank to create a new conversation."
    )
    user_id: int = Field(default=1, description="User ID that owns the conversation.")
    user_role: str = Field(default="Doctor", description="Role used to filter medical access.")
    selected_tool: str = Field(default="retrieval", description="Tool to use: retrieval | summarization | medical_knowledge | treatment_comparison | diagnosis_recommendation")
    patient_name: Optional[str] = Field(default=None, description="Required when selected_tool is summarization.")
    knowledge_type: Optional[str] = Field(default="condition", description="Used when selected_tool is medical_knowledge.")
    use_rag: bool = Field(default=True, description="Used when selected_tool is medical_knowledge.")
    disease_name: Optional[str] = Field(default=None, description="Required when selected_tool is treatment_comparison. E.g., 'Type 2 Diabetes Mellitus'")
    message: str = Field(..., description="Clinical question for the assistant.")


class ChatResponse(BaseModel):
    conversation_id: int
    user_id: int
    user_role: str
    selected_tool: str
    patient_name: Optional[str] = None
    knowledge_type: Optional[str] = None
    disease_name: Optional[str] = None
    response: str


class PatientListResponse(BaseModel):
    user_role: str
    patients: list[str]