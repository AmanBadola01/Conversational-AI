import uuid
from datetime import datetime, timezone
from sqlalchemy import (
    Column, String, Text, Integer, Float, Boolean, 
    DateTime, ForeignKey, JSON
)
from sqlalchemy.orm import relationship
from backend.app.core.database import Base

# Global Helper: Generates unique UUID keys across all memory tables and messages
def generate_uuid() -> str:
    return str(uuid.uuid4())

# Global Helper: Provides timezone-aware UTC timestamps for memory versioning and ordering
def get_utc_now() -> datetime:
    return datetime.now(timezone.utc)


class User(Base):
    """An account. Every conversation and its memory belong to one account."""

    __tablename__ = "users"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    username = Column(String(80), nullable=False)
    email = Column(String(255), nullable=False, unique=True, index=True)
    profile_number = Column(String(80), nullable=True)
    password_hash = Column(String(255), nullable=False)
    created_at = Column(DateTime(timezone=True), default=get_utc_now, nullable=False)

    conversations = relationship("Conversation", back_populates="owner", cascade="all, delete-orphan")


# Memory Technique: Central Orchestrator — stores active memory_type (buffer, summary, entity, kg, hybrid) and auto-switching state
class Conversation(Base):
    """
    Tracks a chat session.
    Stores the active persona, memory strategy (buffer, summary, entity, kg, hybrid),
    and user customization options.
    """
    __tablename__ = "conversations"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True)
    title = Column(String(255), nullable=False, default="New Conversation")
    persona_id = Column(String(50), ForeignKey("personas.id"), nullable=False, default="general_assistant")
    memory_type = Column(String(50), nullable=False, default="buffer")  # buffer, summary, entity, kg, hybrid
    pre_switch_summary = Column(Text, nullable=True, default=None)  # Stores summary of past messages when user switches memory type mid-conversation
    memory_config = Column(JSON, nullable=True, default=lambda: {
        "summary_interval": 5,
        "max_buffer_size": 20,
        "max_entity_store_size": 50,
        "auto_switch_enabled": True
    })
    is_pinned = Column(Boolean, default=False, nullable=False)
    is_archived = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime(timezone=True), default=get_utc_now, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=get_utc_now, onupdate=get_utc_now, nullable=False)

    # Relationships (Cascades ensure clean deletion)
    messages = relationship("Message", back_populates="conversation", cascade="all, delete-orphan", order_by="Message.created_at")
    entities = relationship("Entity", back_populates="conversation", cascade="all, delete-orphan")
    kg_triples = relationship("KGTriple", back_populates="conversation", cascade="all, delete-orphan")
    summary = relationship("ConversationSummary", back_populates="conversation", uselist=False, cascade="all, delete-orphan")
    persona = relationship("Persona", back_populates="conversations")
    owner = relationship("User", back_populates="conversations")


# Memory Technique: Buffer Memory (stores verbatim dialogue turns) & Smart Middle-Truncation (via has_entity_definition)
class Message(Base):
    """
    Stores each message turn in a conversation verbatim.
    Includes token count and an entity protection flag for Smart Middle-Truncation.
    """
    __tablename__ = "messages"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    conversation_id = Column(String(36), ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False, index=True)
    role = Column(String(20), nullable=False)  # 'user', 'assistant', 'system'
    content = Column(Text, nullable=False)
    token_count = Column(Integer, nullable=False, default=0)
    has_entity_definition = Column(Boolean, default=False, nullable=False)  # Never middle-truncated if True
    created_at = Column(DateTime(timezone=True), default=get_utc_now, nullable=False)

    # Relationship
    conversation = relationship("Conversation", back_populates="messages")


# Memory Technique: Entity Memory (dynamic fact store for people, projects, dates) & Cross-Session Memory (via is_global)
class Entity(Base):
    """
    Entity Memory Store:
    Tracks facts learned about people, organizations, projects, technologies, and dates.
    """
    __tablename__ = "entities"

    id = Column(Integer, primary_key=True, autoincrement=True)
    conversation_id = Column(String(36), ForeignKey("conversations.id", ondelete="CASCADE"), nullable=True, index=True)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True)
    name = Column(String(150), nullable=False, index=True)
    entity_type = Column(String(50), nullable=False, default="other")  # person, organization, project, technology, date, concept
    description = Column(Text, nullable=False)
    message_count = Column(Integer, default=1, nullable=False)
    is_global = Column(Boolean, default=False, nullable=False)  # For cross-session memory
    last_updated = Column(DateTime(timezone=True), default=get_utc_now, onupdate=get_utc_now, nullable=False)

    # Relationships
    conversation = relationship("Conversation", back_populates="entities")
    history = relationship("EntityHistory", back_populates="entity", cascade="all, delete-orphan", order_by="EntityHistory.version")


# Memory Technique: Entity Memory Evolution Timeline (records fact snapshots v1 -> v2 as dialogue progresses)
class EntityHistory(Base):
    """
    Entity Evolution Timeline:
    Records version snapshots (v1 -> v2 -> v3) of how an entity's description
    evolved as new facts were revealed across the conversation.
    """
    __tablename__ = "entity_history"

    id = Column(Integer, primary_key=True, autoincrement=True)
    entity_id = Column(Integer, ForeignKey("entities.id", ondelete="CASCADE"), nullable=False, index=True)
    version = Column(Integer, nullable=False, default=1)
    description_snapshot = Column(Text, nullable=False)
    source_message_id = Column(String(36), ForeignKey("messages.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime(timezone=True), default=get_utc_now, nullable=False)

    # Relationship
    entity = relationship("Entity", back_populates="history")


# Memory Technique: Knowledge Graph Memory (extracts and stores Subject-Predicate-Object relationship triples)
class KGTriple(Base):
    """
    Knowledge Graph Triples:
    Stores (Subject, Predicate, Object) relational facts extracted from conversations.
    Powers the interactive force-directed graph visualization in the UI.
    """
    __tablename__ = "kg_triples"

    id = Column(Integer, primary_key=True, autoincrement=True)
    conversation_id = Column(String(36), ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False, index=True)
    subject = Column(String(150), nullable=False, index=True)
    predicate = Column(String(100), nullable=False, index=True)
    object = Column(String(200), nullable=False, index=True)
    source_message_id = Column(String(36), ForeignKey("messages.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime(timezone=True), default=get_utc_now, nullable=False)

    # Relationship
    conversation = relationship("Conversation", back_populates="kg_triples")


# Memory Technique: Summary Memory (stores LLM-condensed macro-summary updated periodically every N turns)
class ConversationSummary(Base):
    """
    Summary Memory:
    Stores the running condensed summary paragraph updated periodically by the Utility LLM.
    """
    __tablename__ = "conversation_summaries"

    id = Column(Integer, primary_key=True, autoincrement=True)
    conversation_id = Column(String(36), ForeignKey("conversations.id", ondelete="CASCADE"), unique=True, nullable=False, index=True)
    summary_text = Column(Text, nullable=False)
    last_summarized_message_id = Column(String(36), nullable=True)
    updated_at = Column(DateTime(timezone=True), default=get_utc_now, onupdate=get_utc_now, nullable=False)

    # Relationship
    conversation = relationship("Conversation", back_populates="summary")


# Memory Technique: Persona-Memory Pairing (maps each persona to its recommended memory strategy)
class Persona(Base):
    """
    Chatbot Personas:
    Pre-configured or user-created AI personalities with custom system prompts,
    recommended memory strategies, and temperature settings.
    """
    __tablename__ = "personas"

    id = Column(String(50), primary_key=True)  # e.g., "general_assistant", "code_helper"
    name = Column(String(100), nullable=False)
    avatar = Column(String(50), nullable=False, default="🤖")
    system_prompt = Column(Text, nullable=False)
    personality = Column(String(255), nullable=False)
    default_memory = Column(String(50), nullable=False, default="buffer")  # recommended memory strategy
    temperature = Column(Float, nullable=False, default=0.7)
    domain = Column(String(50), nullable=False, default="general")  # general, technical, creative, business, educational
    is_builtin = Column(Boolean, default=False, nullable=False)
    owner_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True)
    usage_count = Column(Integer, default=0, nullable=False)
    created_at = Column(DateTime(timezone=True), default=get_utc_now, nullable=False)

    # Relationship
    conversations = relationship("Conversation", back_populates="persona")
