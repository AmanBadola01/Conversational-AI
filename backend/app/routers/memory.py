import logging
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.app.core.auth import get_current_user, get_owned_conversation
from backend.app.core.database import get_db
from backend.app.models.db_models import (
    Conversation, Message, Entity, EntityHistory, KGTriple, ConversationSummary, Persona, User
)
from backend.app.models.schemas import (
    EntityResponse, EntityCreate, KGTripleResponse, KGTripleCreate,
    GraphResponse, GraphNode, GraphLink, SummaryResponse, TokenUsageResponse
)
from backend.app.core.context_manager import context_manager, count_tokens
from backend.app.chains.router import route_intent, assemble_system_prompt
from backend.app.memory.manager import memory_manager
from backend.app.llm.client import llm_client

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/conversations/{conversation_id}/memory", tags=["Memory Inspection"])

# List Entities: Retrieves all tracked named entities and their full version evolution timelines (v1 -> v2)
@router.get("/entities", response_model=List[EntityResponse])
def get_entities(
    conversation_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    conv = get_owned_conversation(db, conversation_id, current_user)

    # Fetch this conversation's entities and the owner's global entities only.
    entities = db.query(Entity).filter(
        (Entity.conversation_id == conversation_id)
        | ((Entity.is_global == True) & (Entity.user_id == current_user.id))
    ).order_by(Entity.last_updated.desc()).all()

    return entities

# Add Entity: Allows manual creation or injection of an entity fact into the conversation fact store
@router.post("/entities", response_model=EntityResponse, status_code=status.HTTP_201_CREATED)
def create_entity(
    conversation_id: str,
    payload: EntityCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    conv = get_owned_conversation(db, conversation_id, current_user)

    # Check if entity already exists
    existing = db.query(Entity).filter(
        Entity.conversation_id == conversation_id,
        Entity.name.ilike(payload.name.strip())
    ).first()

    if existing:
        # Evolve existing description and record new snapshot version in timeline
        if payload.description.lower() not in existing.description.lower():
            existing.description = f"{existing.description}; {payload.description.strip()}"
        existing.message_count += 1
        existing.last_updated = datetime.now(timezone.utc)

        new_version = len(existing.history) + 1
        history_entry = EntityHistory(
            entity_id=existing.id,
            version=new_version,
            description_snapshot=existing.description
        )
        db.add(history_entry)
        db.commit()
        db.refresh(existing)
        return existing

    # Create new entity fact (globals stay private to their owner)
    new_entity = Entity(
        conversation_id=conversation_id if not payload.is_global else None,
        user_id=current_user.id,
        name=payload.name.strip(),
        entity_type=payload.entity_type.strip(),
        description=payload.description.strip(),
        message_count=1,
        is_global=payload.is_global
    )
    db.add(new_entity)
    db.flush()

    # Record initial version 1 snapshot
    history_entry = EntityHistory(
        entity_id=new_entity.id,
        version=1,
        description_snapshot=new_entity.description
    )
    db.add(history_entry)
    db.commit()
    db.refresh(new_entity)

    return new_entity

# Delete Entity: Removes an entity and its associated version timeline from the fact store.
# Global entities (conversation_id NULL) are listed in every conversation,
# so they must also be deletable through any conversation path.
@router.delete("/entities/{entity_id}", status_code=status.HTTP_200_OK)
def delete_entity(
    conversation_id: str,
    entity_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    conv = get_owned_conversation(db, conversation_id, current_user)
    entity = db.query(Entity).filter(
        Entity.id == entity_id,
        (Entity.conversation_id == conversation_id)
        | ((Entity.is_global == True) & (Entity.user_id == current_user.id))
    ).first()
    if not entity:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail=f"Entity {entity_id} not found."
        )

    db.delete(entity)
    db.commit()
    return {"status": "deleted", "entity_id": entity_id}

# Get Graph Data: Formats relationship triples into nodes and links format for react-force-graph visualization
@router.get("/graph", response_model=GraphResponse)
def get_graph_data(
    conversation_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    conv = get_owned_conversation(db, conversation_id, current_user)

    triples = db.query(KGTriple).filter(
        KGTriple.conversation_id == conversation_id
    ).all()

    nodes_map = {}
    links = []

    for t in triples:
        # Add subject node
        if t.subject not in nodes_map:
            nodes_map[t.subject] = GraphNode(id=t.subject, label=t.subject, type="subject")
        # Add object node
        if t.object not in nodes_map:
            nodes_map[t.object] = GraphNode(id=t.object, label=t.object, type="object")
        # Add directed edge link
        links.append(GraphLink(source=t.subject, target=t.object, label=t.predicate))

    return GraphResponse(
        nodes=list(nodes_map.values()),
        links=links
    )

# Add Triple: Manually creates and injects a (Subject, Predicate, Object) fact into the Knowledge Graph
@router.post("/graph", response_model=KGTripleResponse, status_code=status.HTTP_201_CREATED)
def create_triple(
    conversation_id: str,
    payload: KGTripleCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    conv = get_owned_conversation(db, conversation_id, current_user)

    # Check for duplicate triple
    existing = db.query(KGTriple).filter(
        KGTriple.conversation_id == conversation_id,
        KGTriple.subject.ilike(payload.subject.strip()),
        KGTriple.predicate.ilike(payload.predicate.strip()),
        KGTriple.object.ilike(payload.object.strip())
    ).first()

    if existing:
        return existing

    new_triple = KGTriple(
        conversation_id=conversation_id,
        subject=payload.subject.strip(),
        predicate=payload.predicate.strip(),
        object=payload.object.strip()
    )
    db.add(new_triple)
    db.commit()
    db.refresh(new_triple)

    return new_triple

# Delete Triple: Removes a relationship edge from the Knowledge Graph
@router.delete("/graph/{triple_id}", status_code=status.HTTP_200_OK)
def delete_triple(
    conversation_id: str,
    triple_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    conv = get_owned_conversation(db, conversation_id, current_user)
    triple = db.query(KGTriple).filter(
        KGTriple.id == triple_id,
        KGTriple.conversation_id == conversation_id
    ).first()
    if not triple:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail=f"Graph triple {triple_id} not found."
        )

    db.delete(triple)
    db.commit()
    return {"status": "deleted", "triple_id": triple_id}

# Get Summary: Retrieves the running condensed summary and any pre-switch summary for the conversation
@router.get("/summary", response_model=Dict[str, Any])
def get_summary(
    conversation_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    conv = get_owned_conversation(db, conversation_id, current_user)

    summary_record = db.query(ConversationSummary).filter(
        ConversationSummary.conversation_id == conversation_id
    ).first()

    return {
        "conversation_id": conv.id,
        "pre_switch_summary": conv.pre_switch_summary,
        "running_summary": summary_record.summary_text if summary_record else None,
        "updated_at": summary_record.updated_at if summary_record else None
    }

# Regenerate Summary: Manually triggers Groq utility LLM to synthesize a fresh summary of all past messages
@router.post("/summary/regenerate", response_model=Dict[str, Any])
async def regenerate_summary(
    conversation_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    conv = get_owned_conversation(db, conversation_id, current_user)

    all_messages = db.query(Message).filter(
        Message.conversation_id == conversation_id
    ).order_by(Message.created_at.asc()).all()

    if not all_messages:
        return {"status": "no_messages", "summary": ""}

    # Call Groq to condense all messages to date
    new_summary = await llm_client.summarize_conversation(
        current_summary=conv.pre_switch_summary or "",
        new_messages=all_messages
    )

    summary_record = db.query(ConversationSummary).filter(
        ConversationSummary.conversation_id == conversation_id
    ).first()

    last_msg_id = all_messages[-1].id if all_messages else None
    if not summary_record:
        summary_record = ConversationSummary(
            conversation_id=conversation_id,
            summary_text=new_summary,
            last_summarized_message_id=last_msg_id
        )
        db.add(summary_record)
    else:
        summary_record.summary_text = new_summary
        summary_record.last_summarized_message_id = last_msg_id

    db.commit()
    db.refresh(summary_record)

    return {
        "status": "regenerated",
        "conversation_id": conversation_id,
        "summary": summary_record.summary_text,
        "updated_at": summary_record.updated_at
    }

# Token Usage Audit: Calculates real-time 4,000-token budget allocation breakdown for the frontend telemetry bar
@router.get("/tokens", response_model=TokenUsageResponse)
def get_token_usage(
    conversation_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    conv = get_owned_conversation(db, conversation_id, current_user)

    persona = db.query(Persona).filter(Persona.id == conv.persona_id).first()
    base_prompt = persona.system_prompt if persona else "You are a versatile AI assistant."

    # Fetch active memory context
    memory_context = memory_manager.get_context(
        conversation=conv,
        current_query="",
        db=db
    )

    # Build system prompt with small_talk default directive
    full_prompt = assemble_system_prompt(base_prompt, "small_talk", memory_context)

    # Fetch recent messages and middle truncate
    all_messages = db.query(Message).filter(
        Message.conversation_id == conversation_id
    ).order_by(Message.created_at.asc()).all()

    truncated, _, _ = context_manager.smart_middle_truncate(
        messages=all_messages,
        max_tokens=context_manager.recent_budget
    )

    audit = context_manager.calculate_token_breakdown(
        system_prompt=full_prompt,
        memory_context=memory_context,
        messages=truncated,
        conversation_id=conversation_id
    )

    return TokenUsageResponse(
        conversation_id=conversation_id,
        total_budget=audit["total_budget"],
        system_prompt_tokens=audit["system_prompt_tokens"],
        memory_tokens=audit["memory_tokens"],
        recent_messages_tokens=audit["recent_messages_tokens"],
        generation_reserved_tokens=audit["generation_reserved_tokens"],
        total_used_tokens=audit["total_used_tokens"],
        percentage_used=audit["percentage_used"],
        is_warning=audit["is_warning"]
    )
