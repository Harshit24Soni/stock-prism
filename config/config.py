import uuid
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field


class PromptObject(BaseModel):
    model_config = ConfigDict(extra="ignore")
    
    content: str
    id: Optional[str] = None
    role: Optional[str] = "user"


class RequestObject(BaseModel):
    model_config = ConfigDict(extra="ignore")

    prompt: PromptObject
    threadId: Optional[str] = Field(default_factory=lambda: str(uuid.uuid4()))
    responseId: Optional[str] = None
