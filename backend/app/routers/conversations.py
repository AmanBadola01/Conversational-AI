import logging
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from sqlalchemy import desc

from backend.app.core.database import get_db
from backend.app.models.db_models import (
    Conversation, Message, Persona, Entity, KGTriple, ConversationSummary
)
from backend.app.models.schemas import (
    ConversationCreate, 
    ConversationUpdate, 
    ConversationResponse, 
    ConversationDetailResponse
)
from backend.app.memory.manager import memory_manager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/conversations", tags=["Conversations"])

# List Conversations: Retrieves all conversations filtered by archive status and search query, ordered with pinned chats first
@router.get("", response_model=List[ConversationResponse])
def list_conversations(
    archived: bool = Query(False, description="Filter for archived conversations"),
    search: Optional[str] = Query(None, description="Search term for conversation titles"),
    db: Session = Depends(get_db)
):
    query = db.query(Conversation).filter(Conversation.is_archived == archived)
    
    if search:
        query = query.filter(Conversation.title.ilike(f"%{search.strip()}%"))

    # Pinned conversations appear first, followed by most recently updated
    conversations = query.order_by(
        desc(Conversation.is_pinned),
        desc(Conversation.updated_at)
    ).all()

    # Populate message count for each conversation
    results = []
    for conv in conversations:
        conv_dict = {
            "id": conv.id,
            "title": conv.title,
            "persona_id": conv.persona_id,
            "memory_type": conv.memory_type,
            "pre_switch_summary": conv.pre_switch_summary,
            "memory_config": conv.memory_config,
            "is_pinned": conv.is_pinned,
            "is_archived": conv.is_archived,
            "created_at": conv.created_at,
            "updated_at": conv.updated_at,
            "message_count": len(conv.messages) if conv.messages else 0
        }
        results.append(ConversationResponse(**conv_dict))

    return results

# Create Conversation: Initializes a new chat session with chosen persona, title, and initial memory strategy
@router.post("", response_model=ConversationResponse, status_code=status.HTTP_201_CREATED)
def create_conversation(
    payload: ConversationCreate,
    db: Session = Depends(get_db)
):
    # Verify persona existence, default to general_assistant if not found
    persona = db.query(Persona).filter(Persona.id == payload.persona_id).first()
    persona_id = persona.id if persona else "general_assistant"

    # Default memory technique follows the persona's recommended memory unless explicitly overridden
    chosen_memory = payload.memory_type
    if not chosen_memory and persona:
        chosen_memory = persona.default_memory

    new_conversation = Conversation(
        title=payload.title or "New Conversation",
        persona_id=persona_id,
        memory_type=chosen_memory or "buffer",
        memory_config=payload.memory_config or {
            "summary_interval": 5,
            "max_buffer_size": 20,
            "max_entity_store_size": 50,
            "auto_switch_enabled": True
        }
    )

    db.add(new_conversation)
    db.commit()
    db.refresh(new_conversation)

    return ConversationResponse(
        id=new_conversation.id,
        title=new_conversation.title,
        persona_id=new_conversation.persona_id,
        memory_type=new_conversation.memory_type,
        pre_switch_summary=new_conversation.pre_switch_summary,
        memory_config=new_conversation.memory_config,
        is_pinned=new_conversation.is_pinned,
        is_archived=new_conversation.is_archived,
        created_at=new_conversation.created_at,
        updated_at=new_conversation.updated_at,
        message_count=0
    )

# Get Conversation Detail: Fetches a single conversation including its chronological message history and persona
@router.get("/{conversation_id}", response_model=ConversationDetailResponse)
def get_conversation(
    conversation_id: str,
    db: Session = Depends(get_db)
):
    conv = db.query(Conversation).filter(Conversation.id == conversation_id).first()
    if not conv:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail=f"Conversation '{conversation_id}' not found."
        )

    # Convert messages and persona
    return ConversationDetailResponse(
        id=conv.id,
        title=conv.title,
        persona_id=conv.persona_id,
        memory_type=conv.memory_type,
        pre_switch_summary=conv.pre_switch_summary,
        memory_config=conv.memory_config,
        is_pinned=conv.is_pinned,
        is_archived=conv.is_archived,
        created_at=conv.created_at,
        updated_at=conv.updated_at,
        message_count=len(conv.messages),
        messages=conv.messages,
        persona=conv.persona
    )

# Update Conversation: Updates conversation settings, handles memory type switching, and updates pin or archive states
@router.patch("/{conversation_id}", response_model=ConversationResponse)
async def update_conversation(
    conversation_id: str,
    payload: ConversationUpdate,
    db: Session = Depends(get_db)
):
    conv = db.query(Conversation).filter(Conversation.id == conversation_id).first()
    if not conv:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail=f"Conversation '{conversation_id}' not found."
        )

    # Check if user is switching memory type mid-conversation
    if payload.memory_type and payload.memory_type.lower() != conv.memory_type.lower():
        # Executes automatic summary catch-up: condenses previous messages before switching
        await memory_manager.switch_memory_type(
            conversation_id=conv.id,
            new_memory_type=payload.memory_type.lower(),
            db=db
        )
        db.refresh(conv)

    if payload.title is not None:
        conv.title = payload.title.strip()
    if payload.persona_id is not None:
        # Validate persona
        persona = db.query(Persona).filter(Persona.id == payload.persona_id).first()
        if persona:
            conv.persona_id = persona.id
    if payload.is_pinned is not None:
        conv.is_pinned = payload.is_pinned
    if payload.is_archived is not None:
        conv.is_archived = payload.is_archived
    if payload.memory_config is not None:
        conv.memory_config = payload.memory_config

    db.commit()
    db.refresh(conv)

    return ConversationResponse(
        id=conv.id,
        title=conv.title,
        persona_id=conv.persona_id,
        memory_type=conv.memory_type,
        pre_switch_summary=conv.pre_switch_summary,
        memory_config=conv.memory_config,
        is_pinned=conv.is_pinned,
        is_archived=conv.is_archived,
        created_at=conv.created_at,
        updated_at=conv.updated_at,
        message_count=len(conv.messages)
    )

# Delete Conversation: Permanently deletes a conversation and cascades deletion to messages, entities, and graph triples
@router.delete("/{conversation_id}", status_code=status.HTTP_200_OK)
def delete_conversation(
    conversation_id: str,
    db: Session = Depends(get_db)
):
    conv = db.query(Conversation).filter(Conversation.id == conversation_id).first()
    if not conv:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail=f"Conversation '{conversation_id}' not found."
        )

    db.delete(conv)
    db.commit()
    return {"status": "deleted", "conversation_id": conversation_id}

# Toggle Pin State: Quickly pins or unpins a conversation to keep critical chats at the top of the sidebar
@router.post("/{conversation_id}/pin", response_model=Dict[str, Any])
def toggle_pin(
    conversation_id: str,
    db: Session = Depends(get_db)
):
    conv = db.query(Conversation).filter(Conversation.id == conversation_id).first()
    if not conv:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail=f"Conversation '{conversation_id}' not found."
        )

    conv.is_pinned = not conv.is_pinned
    db.commit()
    return {"conversation_id": conv.id, "is_pinned": conv.is_pinned}

# Toggle Archive State: Quickly archives or unarchives a conversation without permanently deleting history
@router.post("/{conversation_id}/archive", response_model=Dict[str, Any])
def toggle_archive(
    conversation_id: str,
    db: Session = Depends(get_db)
):
    conv = db.query(Conversation).filter(Conversation.id == conversation_id).first()
    if not conv:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail=f"Conversation '{conversation_id}' not found."
        )

    conv.is_archived = not conv.is_archived
    db.commit()
    return {"conversation_id": conv.id, "is_archived": conv.is_archived}

# Export Conversation: Exports full conversation transcript and all associated memory state as structured JSON
@router.get("/{conversation_id}/export", response_model=Dict[str, Any])
def export_conversation(
    conversation_id: str,
    db: Session = Depends(get_db)
):
    conv = db.query(Conversation).filter(Conversation.id == conversation_id).first()
    if not conv:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail=f"Conversation '{conversation_id}' not found."
        )

    # Gather all memory states for complete audit export
    entities = db.query(Entity).filter(Entity.conversation_id == conversation_id).all()
    triples = db.query(KGTriple).filter(KGTriple.conversation_id == conversation_id).all()
    summary_record = db.query(ConversationSummary).filter(ConversationSummary.conversation_id == conversation_id).first()

    return {
        "export_metadata": {
            "conversation_id": conv.id,
            "title": conv.title,
            "persona": conv.persona.name if conv.persona else "General Assistant",
            "memory_type": conv.memory_type,
            "pre_switch_summary": conv.pre_switch_summary,
            "exported_at": conv.updated_at.isoformat() if conv.updated_at else None
        },
        "transcript": [
            {
                "role": m.role,
                "content": m.content,
                "token_count": m.token_count,
                "timestamp": m.created_at.isoformat() if m.created_at else None
            }
            for m in conv.messages
        ],
        "memory_state": {
            "pre_switch_summary": conv.pre_switch_summary,
            "running_summary": summary_record.summary_text if summary_record else None,
            "entities_count": len(entities),
            "entities": [
                {"name": e.name, "type": e.entity_type, "description": e.description}
                for e in entities
            ],
            "kg_triples_count": len(triples),
            "kg_triples": [
                {"subject": t.subject, "predicate": t.predicate, "object": t.object}
                for t in triples
            ]
        }
    }
