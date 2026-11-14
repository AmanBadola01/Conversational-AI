from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime


# ----------------- Auth Schemas -----------------
class UserRegister(BaseModel):
    profile_number: Optional[str] = Field(default=None, max_length=80, pattern=r"^-?[0-9]+$")
    username: str = Field(..., min_length=2, max_length=80, example="Aman")
    email: str = Field(..., min_length=3, max_length=255, example="aman@example.com")
    password: str = Field(..., min_length=8, max_length=128)


class UserLogin(BaseModel):
    email: str = Field(..., min_length=3, max_length=255, example="aman@example.com")
    password: str = Field(..., min_length=1, max_length=128)


class UserResponse(BaseModel):
    profile_number: Optional[str] = None
    id: str
    username: str
    email: str
    created_at: datetime

    class Config:
        from_attributes = True


class AuthResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse

# ----------------- Persona Schemas -----------------
class PersonaBase(BaseModel):
    name: str = Field(..., example="General Assistant")
    avatar: str = Field(default="🤖", example="🤖")
    system_prompt: str = Field(..., example="You are a helpful AI assistant.")
    personality: str = Field(default="Helpful, friendly, precise")
    default_memory: str = Field(default="buffer", example="buffer")
    temperature: float = Field(default=0.7, ge=0.0, le=1.0)
    domain: str = Field(default="general", example="general")

class PersonaCreate(PersonaBase):
    id: str = Field(..., example="custom_assistant")

class PersonaResponse(PersonaBase):
    id: str
    is_builtin: bool
    usage_count: int
    created_at: datetime

    class Config:
        from_attributes = True


# ----------------- Message Schemas -----------------
class MessageCreate(BaseModel):
    content: str = Field(..., min_length=1, example="Hello, tell me about our project plans.")

class MessageResponse(BaseModel):
    id: str
    conversation_id: str
    role: str
    content: str
    token_count: int
    created_at: datetime

    class Config:
        from_attributes = True


# ----------------- Conversation Schemas -----------------
class ConversationCreate(BaseModel):
    title: Optional[str] = Field(default="New Conversation")
    persona_id: str = Field(default="general_assistant")
    # None means "use the persona's recommended memory strategy".
    memory_type: Optional[str] = Field(default=None)  # buffer, summary, entity, kg, hybrid
    memory_config: Optional[Dict[str, Any]] = None

class ConversationUpdate(BaseModel):
    title: Optional[str] = None
    persona_id: Optional[str] = None
    memory_type: Optional[str] = None
    is_pinned: Optional[bool] = None
    is_archived: Optional[bool] = None
    memory_config: Optional[Dict[str, Any]] = None

class ConversationResponse(BaseModel):
    id: str
    title: str
    persona_id: str
    memory_type: str
    pre_switch_summary: Optional[str] = None
    memory_config: Optional[Dict[str, Any]] = None
    is_pinned: bool
    is_archived: bool
    created_at: datetime
    updated_at: datetime
    message_count: Optional[int] = 0

    class Config:
        from_attributes = True

class ConversationDetailResponse(ConversationResponse):
    messages: List[MessageResponse] = []
    persona: Optional[PersonaResponse] = None


# ----------------- Memory Schemas -----------------
class EntityCreate(BaseModel):
    name: str = Field(..., example="Gemini 2.0")
    entity_type: str = Field(default="technology", example="technology")
    description: str = Field(..., example="High-performance multimodal generative model from Google")
    is_global: bool = Field(default=False)

class EntityHistoryResponse(BaseModel):
    id: int
    version: int
    description_snapshot: str
    source_message_id: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True

class EntityResponse(BaseModel):
    id: int
    conversation_id: Optional[str] = None
    name: str
    entity_type: str
    description: str
    message_count: int
    is_global: bool
    last_updated: datetime
    history: List[EntityHistoryResponse] = []

    class Config:
        from_attributes = True

class KGTripleCreate(BaseModel):
    subject: str = Field(..., example="Alice")
    predicate: str = Field(..., example="manages")
    object: str = Field(..., example="Project Gemini")

class KGTripleResponse(BaseModel):
    id: int
    conversation_id: str
    subject: str
    predicate: str
    object: str
    source_message_id: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True

class GraphNode(BaseModel):
    id: str
    label: str
    type: str = "concept"

class GraphLink(BaseModel):
    source: str
    target: str
    label: str

class GraphResponse(BaseModel):
    nodes: List[GraphNode]
    links: List[GraphLink]


class SummaryResponse(BaseModel):
    conversation_id: str
    summary_text: str
    last_summarized_message_id: Optional[str] = None
    updated_at: datetime

    class Config:
        from_attributes = True

class TokenUsageResponse(BaseModel):
    conversation_id: str
    total_budget: int = 4000
    system_prompt_tokens: int
    memory_tokens: int
    recent_messages_tokens: int
    generation_reserved_tokens: int
    total_used_tokens: int
    percentage_used: float
    is_warning: bool
